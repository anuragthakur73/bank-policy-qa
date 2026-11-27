# run: python -m app.generate   (smoke test: RBI question, policy question, out-of-scope question)
# Retrieves Demo Bank rules (with their traced RBI paragraphs) and RBI clauses, asks Claude to answer ONLY
# from them with native citations, refuses when they don't answer, and appends one audit record per query
# to logs/audit.jsonl.
import json, logging, os, time, uuid, datetime
from urllib.parse import quote
from dotenv import load_dotenv; load_dotenv()
import anthropic
from app.retrieve import CONTRACT_VERSION, RETRIES, count_sdk_retries
from app.search import search
from app.validate import validate, blocking, named_refs
from app.pii import mask
from app import product as prod
from app import policy_versions as pv

from functools import lru_cache
@lru_cache
def _client():          # created on first use: importing this module (API, tests) needs no API key
    return anthropic.Anthropic()
count_sdk_retries("anthropic._base_client", "anthropic")   # hidden API retries show up in the audit log
PROMPT_VERSION = "answer-v6"   # v6 (Week 6 S1, v09): an eligibility list in a Demo Bank rule is complete; v5 (ADR-017): retry note says not to name sources outside the results; v4 (Week 5 S2): Car Loan added to the product list; v3 (ADR-009): rules labelled by product; per-product answers
REFUSAL = "Not covered by the indexed documents."
SYSTEM = ("You answer questions from Indian bank lending staff using ONLY the search results provided. "
          "There are two kinds of result. 'DEMO BANK RULE' results are the policy of Demo Bank, a fictional bank: "
          "they say what this bank does. 'RBI' results are clauses of RBI Master Directions: they say what every "
          "bank must do. Each result's title gives its chapter and section; a clause applies to the subject of the "
          "chapter it sits in. Definitions are part of the same directions: use them to classify the case. "
          "If a Demo Bank rule answers the question, start with that rule's answer in one sentence (the figure or "
          "yes/no) and name the rule ID, then cite the RBI clause it implements, or say it is a bank-discretion "
          "rule with no RBI requirement. If only RBI results answer it, answer from RBI. If a Demo Bank rule and an "
          "RBI clause disagree, give both and say so. At most one caveat that the results actually require. "
          "A Demo Bank rule that lists who may apply is a complete list: a borrower type it does not list is not "
          "eligible under that rule, so answer 'No' and name the rule. "
          "Each DEMO BANK RULE title names its product (Home Loan, LAP, Car Loan). Apply a rule only to its own product. "
          "If the question does not say which product and rules of more than one product are given, answer "
          "for each product separately, starting each part with the product name. "
          "Cite a result for every statement. Quote figures (percentages, amounts, days) exactly. "
          f"If the search results do not answer the question, reply exactly: '{REFUSAL}' "
          "Do not use outside knowledge, and do not guess.")
PRICE_IN, PRICE_OUT = 0.10, 0.50   # USD per 1M tokens, Claude Haiku 5.5 (financial-viability doc, 18 Nov 2026)

def is_refusal(text: str) -> bool:
    """The answer IS the refusal, possibly followed by extra remarks (g010, 26 Nov). A labelled per-product answer
    with one product 'Not covered' starts with the product name, so it is not a refusal (ADR-009)."""
    return text.replace("*", "").strip().startswith(REFUSAL.rstrip("."))

LINK_FRAGMENTS = os.environ.get("LINK_FRAGMENTS", "data/parsed/link_fragments.json")   # ingest/link_fragments.py

@lru_cache
def _fragments() -> dict:
    try:
        with open(LINK_FRAGMENTS, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def _enc(s: str) -> str:
    return quote(s, safe="").replace("-", "%2D")     # '-' and ',' are syntax inside a text directive

def clause_link(h: dict) -> str:
    """RBI: opens the page and highlights the clause (text fragment).
    ADR-019 (Week 5 S5): the phrase comes from ingest/link_fragments.py - unique on RBI's page and inside one page
    block, with the para number as prefix where needed ("38.-,A bank shall not:"). Without that file: the clause's
    first 8 words (ADR-003), which can be shared (CF 108/109) or cross a block break. Deleted paras: section anchor.
    Demo Bank: the rule's place in the policy file (a fictional bank has no web page)."""
    if h.get("layer") == "policy":
        return f'{h["source_url"]}#{h["rule_id"]}'
    f = _fragments().get(f'{h.get("doc_id")}|{h.get("clause_no")}')
    if f and f.get("status") == "ok":
        return h["source_url"] + "#:~:text=" + (_enc(f["prefix"]) + "-," if f.get("prefix") else "") + _enc(f["start"])
    if f and f.get("status") == "deleted":
        return h["source_url"] + ("#" + h["section_anchor"] if h.get("section_anchor") else "")
    words = " ".join(h["text"].split()[1:9])
    return h["source_url"] + "#:~:text=" + _enc(words)

def section_link(h: dict) -> str:
    """Fallback: RBI's own section anchor, e.g. #C4D."""
    if h.get("layer") == "policy":
        return clause_link(h)
    return h["source_url"] + ("#" + h["section_anchor"] if h.get("section_anchor") else "")

def _title(h: dict) -> str:
    if h.get("layer") == "policy":
        ref = h.get("rbi_ref") or {}
        basis = (f'implements {ref.get("direction")} para {ref.get("para")}' if not h.get("bank_discretion")
                 else "bank discretion (no RBI requirement)")
        return (f'DEMO BANK RULE {h["rule_id"]} | {prod.NAMES.get(h.get("product"), "")} | '
                f'{h["chapter"]} > {h["section"]} | '
                f'{h["version_label"]} | {basis}')
    return (f'RBI | {h["title"]} | {h.get("chapter") or ""} > {h.get("section") or ""} | '
            f'para {h["clause_no"]} ({h["version_label"]})')

def _sources(hits: list[dict]) -> list[dict]:
    """Policy rules, then the RBI paragraphs they trace to, then searched RBI clauses; no duplicates."""
    out, seen = [], set()
    def add(h):
        key = (h["doc_id"], h["clause_no"])
        if key not in seen:
            seen.add(key); out.append(h)
    for h in hits:
        if h.get("layer") == "policy":
            add(h)
            for t in h.get("trace") or []:
                if t["status"] == "found":
                    add({**t["clause"], "layer": "rbi", "score": None, "traced_from": h["rule_id"]})
    for h in hits:
        if h.get("layer") != "policy":
            add(h)
    return out

AUDIT_LOG = os.environ.get("AUDIT_LOG", "logs/audit.jsonl")   # tests point this at a temp file
VALIDATOR = os.environ.get("VALIDATOR", "enforce")   # enforce: retry once, then refuse | log: record issues only

def _ask(model: str, results: list, q: str, hits: list, retry_note: list | None = None):
    """One model call -> (message, answer text, citations mapped back to the retrieved rows)."""
    content = results + [{"type": "text", "text": q}]
    if retry_note:
        content.append({"type": "text", "text": "A check of your previous answer to this question found: "
                        + "; ".join(i["detail"] for i in retry_note) + ". Answer again from the same results. Cite a "
                        "result for every rule ID and RBI paragraph you name, and use only rules and clauses that "
                        "apply to the product and date asked about. Do not name any rule ID or RBI paragraph that is "
                        "not among the results; if a source is not in the results, leave it out."})
    # Haiku 5.5 thinks by default (effort "medium") and thinking tokens count against max_tokens,
    # so a tight cap can end the reply before any answer text. Low effort is enough for grounded Q&A.
    msg = _client().messages.create(model=model, max_tokens=2000, system=SYSTEM, output_config={"effort": "low"},
                                    messages=[{"role": "user", "content": content}])
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if msg.stop_reason == "max_tokens" and not text:
        text = "[no answer: hit max_tokens before any text]"
    by_source = {clause_link(h): h for h in hits}
    cites = []
    for b in msg.content:
        if b.type != "text":
            continue
        for c in (getattr(b, "citations", None) or []):
            src = getattr(c, "source", "")
            # Map back by position, not by link: different clauses can share a link (CF 108 and 109 start with the
            # same 8 words, so their text-fragment links are identical - r04 was mapped to the wrong para).
            idx = getattr(c, "search_result_index", None)
            h = hits[idx] if isinstance(idx, int) and 0 <= idx < len(hits) else by_source.get(src, {})
            cites.append({"title": getattr(c, "title", ""), "source": src, "hit_index": idx if h else None,
                          "fallback": section_link(h) if h else "", "layer": h.get("layer"),
                          "doc_id": h.get("doc_id"), "clause_no": h.get("clause_no"),
                          "rule_id": h.get("rule_id"), "policy_version": h.get("policy_version"),
                          "cited_text": getattr(c, "cited_text", "")})
    return msg, text, cites

def _prepare(q: str, k: int, layers, product, as_on) -> dict:
    """Mask -> search -> search_result blocks. Shared by the plain flow and the LangGraph flow (Week 5 S3)."""
    t0, rid = time.perf_counter(), str(uuid.uuid4())
    # ADR-015: mask personal data FIRST - the search, the model and the audit log only ever see the masked question
    q, pii_found = mask(q)
    timings, before = {}, dict(RETRIES)
    found = search(q, k, layers=layers, product=product, as_on=as_on, timings=timings)
    hits = _sources(found["rows"])
    return {"t0": t0, "rid": rid, "q": q, "pii_found": pii_found, "timings": timings, "before": before,
            "found": found, "as_on": found["as_on"], "products": found["products"],
            # RBI search results in rank order BEFORE de-duplication with traced paragraphs (the eval scores this)
            "rbi_search": [f'{h["doc_id"]}:{h["clause_no"]}' for h in found["rows"] if h.get("layer") == "rbi"],
            "hits": hits, "model": os.environ.get("DEFAULT_MODEL", "claude-haiku-5-5"),
            "results": [{"type": "search_result", "source": clause_link(h), "title": _title(h),
                         "content": [{"type": "text", "text": h["text"]}],
                         "citations": {"enabled": True}} for h in hits]}

def _finish(ctx: dict, caller: str, msg, text: str, cites: list, usage: list, check: dict, model_ms: int,
            extra: dict | None = None):
    """Audit record + code-written notices + audit log line. Identical for both flows."""
    found, hits, as_on, products = ctx["found"], ctx["hits"], ctx["as_on"], ctx["products"]
    timings = ctx["timings"]; timings["model_ms"] = model_ms
    u_in, u_out = sum(x.input_tokens for x in usage), sum(x.output_tokens for x in usage)
    rec = {"request_id": ctx["rid"], "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
           "caller": caller, "question": ctx["q"], "contract": CONTRACT_VERSION, "layers": list(found["layers"]),
           "products": list(products), "product_source": found["product_source"], "pii_masked": ctx["pii_found"],
           "retrieved": [{"layer": h.get("layer"), "doc_id": h["doc_id"], "clause_no": h["clause_no"],
                          "version_as_on": h["version_as_on"], "score": h["score"],
                          "traced_from": h.get("traced_from"),
                          "how": (h.get("retrieval") or {}).get("mode")} for h in hits],
           "model": ctx["model"], "prompt_version": PROMPT_VERSION, "stop_reason": msg.stop_reason,
           "tokens_in": u_in, "tokens_out": u_out,
           "cost_usd": round((u_in * PRICE_IN + u_out * PRICE_OUT) / 1e6, 6),
           "latency_ms": int((time.perf_counter() - ctx["t0"]) * 1000),
           "retrieval_mode": found["mode"], "timings_ms": timings, "rbi_search": ctx["rbi_search"],
           "retries": {k: RETRIES.get(k, 0) - ctx["before"].get(k, 0) for k in ("openai", "qdrant", "anthropic")},
           # refused = the whole answer is the refusal. A labelled per-product answer where one product is
           # "Not covered" is a partial answer (ADR-009), logged separately; before 25 Nov any occurrence counted.
           "refused": is_refusal(text), "partly_refused": REFUSAL in text and not is_refusal(text),
           "as_on": as_on.isoformat(), "policy_status": pv.status(products, as_on),
           "cited_rule_versions": {c["rule_id"]: c["policy_version"] for c in cites if c["layer"] == "policy"},
           "cited_clauses": sorted({c["clause_no"] for c in cites if c["clause_no"] and c["layer"] != "policy"}),
           "cited_rbi": sorted({f'{c["doc_id"]}:{c["clause_no"]}' for c in cites if c["layer"] == "rbi"}),
           "cited_rules": sorted({c["rule_id"] for c in cites if c["layer"] == "policy"}),
           "human_action": None, "validation": check, "model_calls": len(usage),
           "pipeline": "plain", **(extra or {})}
    # ADR-017: sources the answer names that were retrieved but not cited -> one code-written line of links
    last = check.get("second", check.get("first", [])) if check.get("action") != "refused_after_retry" else []
    refs = [] if rec["refused"] else named_refs(last)
    rec["named_refs"] = refs
    # Kept apart from cited_rules / cited_rbi, which stay "what the model cited" (ADR-017 option b, 27 Nov).
    rec["linked_rules"] = sorted({r["rule_id"] for r in refs if r.get("rule_id")})
    rec["linked_rbi"] = sorted({r["rbi"] for r in refs if r.get("rbi")})
    if refs:
        text += "\n\nAlso named in this answer (linked by the system, not quoted): " + " · ".join(
            f'{r["label"]} ({r["link"]})' for r in refs)
    # Deterministic notices (not written by the model): product not yet in force / a rule in the answer changes soon.
    # A rule the system linked is as much in front of the reader as one the model cited, so it gets its notice too
    # (c07, 27 Nov: DB-VL-019 named but not cited, so a change to it would not have been flagged).
    pre, post = pv.notices(products, as_on, sorted(set(rec["cited_rules"]) | set(rec["linked_rules"])))
    if pre or post:
        text = "\n\n".join(["\n".join(pre)] * bool(pre) + [text] + ["\n".join(post)] * bool(post))
    rec["notices"] = pre + post
    rec["answer"] = text   # what the user was shown, notices included (an audit trail needs the output, not only the inputs)
    os.makedirs(os.path.dirname(AUDIT_LOG) or ".", exist_ok=True)
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return text, cites, rec

def _answer_plain(q, k, caller, layers, product, as_on):
    """The flow as it was through Week 5 S2, kept for comparison with the graph (ADR-016)."""
    ctx = _prepare(q, k, layers, product, as_on)
    model, results, hits = ctx["model"], ctx["results"], ctx["hits"]
    products, as_on, q = ctx["products"], ctx["as_on"], ctx["q"]
    t_model = time.perf_counter()
    msg, text, cites = _ask(model, results, q, hits)
    # S3 (ADR-014): check the answer against what was retrieved; one retry with the problems listed, then refuse.
    issues = validate(text, cites, hits, products, as_on, q)
    check = {"mode": VALIDATOR, "first": issues, "action": "pass" if not blocking(issues) else "flagged"}
    usage = [msg.usage]
    if blocking(issues) and VALIDATOR == "enforce":
        check["draft_1"] = text
        msg, text, cites = _ask(model, results, q, hits, retry_note=blocking(issues))
        usage.append(msg.usage)
        issues = validate(text, cites, hits, products, as_on, q)
        check["second"] = issues
        if blocking(issues):
            check["action"], check["draft_2"], text, cites = "refused_after_retry", text, REFUSAL, []
        else:
            check["action"] = "passed_after_retry"
    return _finish(ctx, caller, msg, text, cites, usage, check, int((time.perf_counter() - t_model) * 1000))

def answer(q: str, k: int = 5, caller: str = "cli", layers=("policy", "rbi"), product: str | None = None,
           as_on=None):
    """product: home_loan | lap | vehicle_loan from the screen selector / API / loan file; None = detect from the question.
    as_on: date (or 'YYYY-MM-DD') the answer must hold on; None = today. Only policy rules in force then are used;
    a product whose policy is not yet in force is left out and the answer says so (ADR-010).
    Default: the LangGraph flow (app/graph.py, ADR-016, accepted 27 Nov 2026). PIPELINE=plain runs the original
    flow - kept one release for rollback."""
    if product == "rbi_only":      # the "RBI rule only" reply to a clarifying question (ADR-018)
        product, layers = None, tuple(l for l in layers if l != "policy")
    if os.environ.get("PIPELINE", "graph") == "graph":
        from app.graph import run
        return run(q, k=k, caller=caller, layers=layers, product=product, as_on=as_on)
    return _answer_plain(q, k, caller, layers, product, as_on)

if __name__ == "__main__":
    for q in ["What is the maximum loan-to-value ratio for a gold loan of 3 lakh rupees?",
              "What is the maximum LTV for a home loan of Rs 50 lakh?",
              "Can my customer's grandfather be a co-applicant on her home loan?",
              "What documents are needed for video KYC?"]:   # last one should refuse: KYC not indexed
        text, cites, rec = answer(q)
        print("Q:", q); print("A:", text)
        for c in cites:
            label = f'rule {c["rule_id"]}' if c["layer"] == "policy" else f'{c["doc_id"]} para {c["clause_no"]}'
            print(f'  -> {label}: "{c["cited_text"][:70]}..."')
        print(f'  [{rec["latency_ms"]} ms {rec["timings_ms"]} retries {rec["retries"]} | {rec["tokens_in"]} in / {rec["tokens_out"]} out | '
              f'${rec["cost_usd"]:.5f} | refused={rec["refused"]} | rules {rec["cited_rules"]} | rbi {rec["cited_rbi"]}]\n')
