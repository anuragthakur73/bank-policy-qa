# run: python -m app.retrieve   (smoke test)
# The return shape of retrieve() is the /retrieve contract that 1B and Project 2 will call.
# Rule: add fields, never rename or remove them.
# v0.1 (ADR-005): adds the Demo Bank policy layer. Old calls (layers=("rbi",)) return the same rows
# as v0, plus new fields that are None for RBI clauses.
import os, re
from functools import lru_cache
from dotenv import load_dotenv; load_dotenv()
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client.http import models as qm
from qdrant_client.http.exceptions import ResponseHandlingException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

CONTRACT_VERSION = "v0.1"
FIELDS = ("doc_id", "clause_no", "title", "chapter", "section", "section_anchor",
          "version_label", "version_as_on", "effective_from", "effective_to",
          "source_url", "content_hash", "parent_clause")
POLICY_FIELDS = ("rule_id", "bank_discretion", "vs_rbi", "rbi_ref", "params", "review", "synthetic")
COLLECTIONS = {"rbi": "clauses_v1", "policy": "policy_v1"}
# Short names used in policy rbi_ref.direction -> doc_id in clauses_v1. Only indexed directions trace.
INDEXED_RBI = {"CF": "RBI-CB-CREDIT-FAC-2025"}

_network = retry(retry=retry_if_exception_type(ResponseHandlingException), stop=stop_after_attempt(4),
                 wait=wait_exponential(multiplier=1, max=8), reraise=True)

@lru_cache
def _store(layer: str = "rbi"):
    return QdrantVectorStore.from_existing_collection(
        embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        collection_name=COLLECTIONS[layer],
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])

# Transient network/DNS failures reaching Qdrant (e.g. "getaddrinfo failed" on a flaky hotspot)
# are retried; any other error fails immediately.
@_network
def _search(question: str, k: int, layer: str = "rbi"):
    return _store(layer).similarity_search_with_score(question, k=k)

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

def _row(meta: dict, score, layer: str, text: str) -> dict:
    return {**{f: meta.get(f) for f in FIELDS}, **{f: meta.get(f) for f in POLICY_FIELDS},
            "layer": layer, "score": None if score is None else round(float(score), 4),
            "text": meta.get("clause_text", text), "trace": []}

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
        m = _clause(INDEXED_RBI[key], p)
        out.append({"direction": key, "para": p, "status": "found" if m else "not_found",
                    "clause": _row(m, None, "rbi", "") if m else None})
    return out

def retrieve(question: str, k: int = 5, layers=("rbi",), k_policy: int = 3) -> list[dict]:
    """Policy rules first (each with its RBI trace), then RBI clauses. Each layer has its own quota."""
    rows = []
    if "policy" in layers:
        for d, s in _search(question, k_policy, "policy"):
            r = _row(d.metadata, s, "policy", d.page_content)
            r["trace"] = trace(d.metadata)
            rows.append(r)
    if "rbi" in layers:
        rows += [_row(d.metadata, s, "rbi", d.page_content) for d, s in _search(question, k, "rbi")]
    return rows

if __name__ == "__main__":
    # 1) RBI layer alone: unchanged v0 behaviour. Expected clause in brackets, top 5.
    smoke = [("What is the maximum LTV for gold loans up to 2.5 lakh?", "44"),
             ("Does the LTV have to be maintained for the whole loan tenure?", "45"),
             ("When do these directions come into effect?", "2")]
    found = 0
    for q, exp in smoke:
        hits = retrieve(q)
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
