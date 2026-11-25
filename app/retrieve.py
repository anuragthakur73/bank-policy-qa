# run: python -m app.retrieve   (smoke test)
# The return shape of retrieve() is the /retrieve contract that 1B and Project 2 will call.
# Rule: add fields, never rename or remove them.
# v0.1 (ADR-005): adds the Demo Bank policy layer. Old calls (layers=("rbi",)) return the same rows
# as v0, plus new fields that are None for RBI clauses.
# v0.2 (ADR-007): RBI search is hybrid by default (vector + BM25 keyword, fused by reciprocal rank fusion).
# New field "retrieval" says how each row was found. mode="vector" gives the v0.1 behaviour.
# Pass timings={} to get per-stage milliseconds back.
# v0.3 (ADR-009): products=("lap",) etc. filters the policy layer by product; each product gets its own
# k_policy quota. New field "product" on policy rows. products=None keeps the v0.2 behaviour (no filter).
# v0.4 (ADR-010): as_on=date keeps only policy rules in force on that date (every version is indexed).
# New fields policy_version, policy_status. as_on=None searches all versions (old behaviour, not for answers).
# v0.5 (ADR-011): with a product and as_on, the policy layer returns the vector top k_policy PLUS the best keyword
# (BM25) match if it is not already there (retrieval.mode = "keyword"), so up to k_policy + 1 rules per product.
# Env POLICY_KEYWORD=0 turns it off.
# v0.6 (ADR-012): with products given, RBI clauses limited to another product (app/rbi_scope.py, e.g. housing
# finance -> home_loan) are dropped; the RBI search fetches 2k candidates so k remain. New row field "rbi_scope".
import logging, os, re, time
from contextlib import contextmanager
from functools import lru_cache
from dotenv import load_dotenv; load_dotenv()
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from openai import APIConnectionError as OpenAIConnectionError
from qdrant_client.http import models as qm
from qdrant_client.http.exceptions import ResponseHandlingException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from app import keyword

CONTRACT_VERSION = "v0.6"
MODES = ("vector", "hybrid", "hybrid_lc")   # hybrid_lc = same idea built with LangChain (app/retrieve_lc.py)
N_CANDIDATES = 20                           # each search's shortlist before fusion
FIELDS = ("doc_id", "clause_no", "title", "chapter", "section", "section_anchor",
          "version_label", "version_as_on", "effective_from", "effective_to",
          "source_url", "content_hash", "parent_clause")
POLICY_FIELDS = ("product", "policy_version", "policy_status", "rule_id", "bank_discretion", "vs_rbi", "rbi_ref", "params", "review", "synthetic")
COLLECTIONS = {"rbi": "clauses_v1", "policy": "policy_v1"}
# Short names used in policy rbi_ref.direction -> doc_id in clauses_v1. Only indexed directions trace.
INDEXED_RBI = {"CF": "RBI-CB-CREDIT-FAC-2025", "RBC": "RBI-CB-RBC-2025"}

RETRIES = {"qdrant": 0, "openai": 0}   # retries since start; generate.py logs the change per query

class _SdkRetryCounter(logging.Handler):
    """Counts an SDK's own 'Retrying request ...' log lines (openai and anthropic both log them at INFO)."""
    def __init__(self, name):
        super().__init__(); self.name_ = name
    def emit(self, record):
        if record.getMessage().startswith("Retrying request"):
            RETRIES[self.name_] = RETRIES.get(self.name_, 0) + 1
def count_sdk_retries(logger_name: str, key: str):
    lg = logging.getLogger(logger_name)
    lg.setLevel(logging.INFO); lg.addHandler(_SdkRetryCounter(key)); lg.propagate = False
count_sdk_retries("openai._base_client", "openai")
def _count_retry(_state):
    RETRIES["qdrant"] += 1
# 6 attempts, waits 1, 2, 4, 8, 16 s (about 30 s in all): enough to ride out a flaky hotspot's DNS dropouts.
_network = retry(retry=retry_if_exception_type((ResponseHandlingException, OpenAIConnectionError)),
                 stop=stop_after_attempt(6), wait=wait_exponential(multiplier=1, max=30),
                 reraise=True, before_sleep=_count_retry)

@contextmanager
def _timed(timings, stage: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        if timings is not None:
            timings[stage] = timings.get(stage, 0) + int((time.perf_counter() - t0) * 1000)

@lru_cache
def _embedder():
    return OpenAIEmbeddings(model="text-embedding-3-small")

@lru_cache           # a failed open raises, so it is not cached and the next call tries again
@_network            # opening the collection is itself a Qdrant call
def _store(layer: str = "rbi"):
    return QdrantVectorStore.from_existing_collection(
        embedding=_embedder(),
        collection_name=COLLECTIONS[layer],
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])

@_network
def _embed(question: str) -> list[float]:
    """OpenAI embedding, retried on connection errors after the SDK's own 2 retries give up."""
    return _embedder().embed_query(question)

# Transient network/DNS failures reaching Qdrant (e.g. "getaddrinfo failed" on a flaky hotspot)
# are retried; any other error fails immediately.
@_network
def _search(question: str, k: int, layer: str = "rbi"):
    return _store(layer).similarity_search_with_score(question, k=k)

@_network
def _search_vec(vector: list[float], k: int, layer: str = "rbi", product: str | None = None, as_on=None):
    """Qdrant only: the question is embedded once per query and reused for both layers.
    product / as_on: policy layer only; Qdrant filters BEFORE ranking, so the quota is spent on eligible rules."""
    return _store(layer).similarity_search_with_score_by_vector(vector, k=k, filter=policy_filter(product, as_on))

def policy_filter(product: str | None = None, as_on=None):
    """product = X and effective_from <= as_on <= effective_to (dates as yyyymmdd integers)."""
    from app.policy_versions import date_n
    must = []
    if product:
        must.append(qm.FieldCondition(key="metadata.product", match=qm.MatchValue(value=product)))
    if as_on:
        n = date_n(as_on)
        must += [qm.FieldCondition(key="metadata.effective_from_n", range=qm.Range(lte=n)),
                 qm.FieldCondition(key="metadata.effective_to_n", range=qm.Range(gte=n))]
    return qm.Filter(must=must) if must else None

@_network
def _clause(doc_id: str, clause_no: str):
    """Fetch one RBI clause by number (needs the payload indexes made by ingest.index_policy)."""
    pts, _ = _store("rbi").client.scroll(
        COLLECTIONS["rbi"], limit=1, with_payload=True,
        scroll_filter=qm.Filter(must=[
            qm.FieldCondition(key="metadata.doc_id", match=qm.MatchValue(value=doc_id)),
            qm.FieldCondition(key="metadata.clause_no", match=qm.MatchValue(value=clause_no))]))
    return pts[0].payload.get("metadata") if pts else None

def paras(spec) -> list[str]:
    """'90, 93, 95' -> ['90','93','95'];  '114-118' -> ['114',...,'118'];  '349(3)' -> ['349']."""
    out = []
    for part in re.split(r"[,;]", str(spec or "")):
        part = part.strip()
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if m:
            out += [str(i) for i in range(int(m[1]), int(m[2]) + 1)]
            continue
        m = re.match(r"(\d+)", part)
        if m:
            out.append(m[1])
    return list(dict.fromkeys(out))

def _row(meta: dict, score, layer: str, text: str, retrieval: dict | None = None) -> dict:
    """score = vector similarity (None if the row was not found by vector search)."""
    return {**{f: meta.get(f) for f in FIELDS}, **{f: meta.get(f) for f in POLICY_FIELDS},
            "layer": layer, "score": None if score is None else round(float(score), 4),
            "text": meta.get("clause_text", text), "trace": [], "retrieval": retrieval}

def trace(rule_meta: dict) -> list[dict]:
    """The RBI paragraph(s) a policy rule implements. status: found | not_found | not_indexed."""
    ref = rule_meta.get("rbi_ref") or {}
    key = str(ref.get("direction", "")).split(";")[0].strip()
    if not ref:
        return []
    if key not in INDEXED_RBI:
        # same shape as indexed refs: one entry per paragraph, so these resolve unchanged once indexed
        return [{"direction": key, "para": p, "status": "not_indexed", "clause": None}
                for p in (paras(ref.get("para")) or [ref.get("para")])]
    out = []
    for p in paras(ref.get("para")):
        # local lookup first (same data as the index, no network); Qdrant only if the clause isn't local
        m = keyword.clause(INDEXED_RBI[key], p) or _clause(INDEXED_RBI[key], p)
        out.append({"direction": key, "para": p, "status": "found" if m else "not_found",
                    "clause": _row(m, None, "rbi", "") if m else None})
    return out

def _key(meta: dict) -> str:
    return f'{meta["doc_id"]}|{meta["clause_no"]}'

def _rbi_hybrid(question: str, qvec: list[float], k: int, timings=None) -> list[dict]:
    """Vector shortlist + BM25 shortlist -> reciprocal rank fusion -> top k."""
    with _timed(timings, "rbi_vector_ms"):
        vec = _search_vec(qvec, N_CANDIDATES, "rbi")
    with _timed(timings, "rbi_keyword_ms"):
        kw = keyword.search(question, N_CANDIDATES)
    vrank = {_key(d.metadata): (i, d, s) for i, (d, s) in enumerate(vec, start=1)}
    krank = {_key(m): (i, m, s) for i, (m, s) in enumerate(kw, start=1)}
    fused = keyword.rrf([list(vrank), list(krank)])
    rows = []
    for key in sorted(fused, key=lambda x: -fused[x])[:k]:
        v, kk = vrank.get(key), krank.get(key)
        meta = v[1].metadata if v else kk[1]
        info = {"mode": "hybrid", "vector_rank": v[0] if v else None, "keyword_rank": kk[0] if kk else None,
                "keyword_score": round(kk[2], 3) if kk else None, "fused": round(fused[key], 5)}
        rows.append(_row(meta, v[2] if v else None, "rbi", v[1].page_content if v else "", info))
    return rows

def retrieve(question: str, k: int = 5, layers=("rbi",), k_policy: int = 3,
             mode: str | None = None, timings: dict | None = None, products=None, as_on=None,
             asked_products=None) -> list[dict]:
    """Policy rules first (each with its RBI trace), then RBI clauses. Each layer has its own quota.
    products: tuple of Demo Bank products to search (app.product.PRODUCTS); each gets k_policy rules.
    as_on: datetime.date; only policy rules in force on that date.
    asked_products: the products the question is about, for the RBI scope filter (default: products). Differs
    from products when a product's policy is not in force: its rules are skipped, but its scope still applies.
    mode: "vector" (default since 25 Nov, ADR-007; env RETRIEVAL_MODE), "hybrid" or "hybrid_lc"."""
    mode = mode or os.environ.get("RETRIEVAL_MODE", "vector")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    rows, qvec = [], None
    if "policy" in layers or ("rbi" in layers and mode != "hybrid_lc"):
        with _timed(timings, "embed_ms"):          # OpenAI call, timed apart from the Qdrant calls
            qvec = _embed(question)
    if "policy" in layers:
        with _timed(timings, "policy_search_ms"):
            found = []
            for p in (products or (None,)):
                if p and as_on and os.environ.get("POLICY_KEYWORD", "1") == "1":
                    from app import policy_keyword, policy_versions as pv
                    n_rules = len(pv.in_force(p, as_on)["rules"])      # rank every eligible rule (<= ~40)
                    found += policy_keyword.merge(_search_vec(qvec, n_rules, "policy", p, as_on),
                                                  policy_keyword.search(question, p, as_on), k_policy)
                else:
                    found += [(d, s, {"mode": "vector"}) for d, s in _search_vec(qvec, k_policy, "policy", p, as_on)]
        with _timed(timings, "trace_ms"):
            for d, s, info in found:
                r = _row(d.metadata, s, "policy", d.page_content, info)
                r["trace"] = trace(d.metadata)
                rows.append(r)
    if "rbi" in layers:
        from app import rbi_scope
        scope_to = asked_products if asked_products is not None else products
        k_rbi, k = k, (2 * k if scope_to else k)        # over-fetch, then drop clauses for another product
        n_before = len(rows)
        if mode == "vector":
            with _timed(timings, "rbi_vector_ms"):
                rows += [_row(d.metadata, s, "rbi", d.page_content, {"mode": "vector", "vector_rank": i})
                         for i, (d, s) in enumerate(_search_vec(qvec, k, "rbi"), start=1)]
        elif mode == "hybrid":
            rows += _rbi_hybrid(question, qvec, k, timings)
        else:
            from app.retrieve_lc import search as lc_search
            with _timed(timings, "rbi_hybrid_lc_ms"):
                rows += [_row(d.metadata, None, "rbi", d.page_content, {"mode": "hybrid_lc", "fused_rank": i})
                         for i, d in enumerate(lc_search(question, k), start=1)]
        rbi_rows = [r for r in rows[n_before:] if rbi_scope.applies(r["doc_id"], r["clause_no"], scope_to)]
        for r in rbi_rows:
            r["rbi_scope"] = rbi_scope.scope(r["doc_id"], r["clause_no"])
        rows = rows[:n_before] + rbi_rows[:k_rbi]
    return rows

if __name__ == "__main__":
    # 1) RBI layer alone: unchanged v0 behaviour. Expected clause in brackets, top 5.
    smoke = [("What is the maximum LTV for gold loans up to 2.5 lakh?", "44"),
             ("Does the LTV have to be maintained for the whole loan tenure?", "45"),
             ("When do these directions come into effect?", "2")]
    found = 0
    for q, exp in smoke:
        hits = retrieve(q, mode=os.environ.get("RETRIEVAL_MODE"))
        ok = exp in [h["clause_no"] for h in hits]; found += ok
        print(("OK  " if ok else "MISS"), q, "->", [(h["clause_no"], h["score"]) for h in hits])
    print(f"RBI layer: {found}/{len(smoke)} expected clauses in top 5\n")

    # 2) Both layers: expected Demo Bank rule in the policy top 3; expected traced RBI para (if any).
    psmoke = [("What is the maximum LTV for a home loan of Rs 50 lakh?", "DB-HL-009", "111"),
              ("Can a grandparent be a co-applicant for a home loan?", "DB-HL-006", None),
              ("What FOIR applies if net monthly income is Rs 1 lakh?", "DB-HL-011", None),
              ("Is stamp duty included in property cost for LTV?", "DB-HL-010", "113"),
              ("Is there a prepayment charge on a floating rate home loan?", "DB-HL-017", None)]
    pf = 0
    for q, rule, para in psmoke:
        hits = retrieve(q, layers=("policy", "rbi"))
        pol = [h for h in hits if h["layer"] == "policy"]
        rbi = [h["clause_no"] for h in hits if h["layer"] == "rbi"]
        traced = [(t["para"], t["status"]) for h in pol if h["rule_id"] == rule for t in h["trace"]]
        ok = rule in [h["rule_id"] for h in pol] and (para is None or (para, "found") in traced)
        pf += ok
        print(("OK  " if ok else "MISS"), q, "\n     policy", [(h["rule_id"], h["score"]) for h in pol],
              "| trace", traced, "| rbi", rbi)
    print(f"\nPolicy layer: {pf}/{len(psmoke)} expected rules (and traced paras) found")
