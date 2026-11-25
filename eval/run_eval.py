# run: python -m eval.run_eval [golden file]   (default eval/golden_v2.jsonl)
# Scores, per question:
#   hit_at_5    expected RBI clause in the top 5 RBI SEARCH hits, matched by doc_id. Scored on rec["rbi_search"]
#               (before de-duplication). Before 24 Nov it was scored after de-duplication, so a paragraph that
#               search found AND a rule trace added was not counted: the 23 Nov "7/14" was understated.
#   in_context  expected RBI clause anywhere the model saw (incl. paras traced from a Demo Bank rule)
#   cited_ok    expected RBI clause cited
#   rule_hit    expected Demo Bank rule among the policy rules sent to the model (top 3 + keyword hit, ADR-011)      rule_cited  expected rule cited
#   answer_ok   every must_contain item appears in the answer (crude check on key figures); an item may list
#               accepted spellings separated by "|", e.g. "3 working days|three working days"
#   refusal_ok  refused exactly when expected
#   product_ok  every cited Demo Bank rule belongs to the expected product (DB-HL vs DB-LAP); questions with rules only
#   headline_ok the FIRST figure in the answer (rule IDs and para numbers ignored) equals the row's "headline"
#               (Week 4: l01 said "75%" first and "65%" later, so must_contain passed on a wrong answer)
#   product     PRODUCT_CONTEXT=given (default) passes the row's "product", as the screen selector would;
#               PRODUCT_CONTEXT=text passes nothing, so the product is detected from the question (ADR-009)
#   as_on       AS_ON env (default 2027-01-01: golden_v2 was written against home loan v1.1 + LAP v1.0); a row's own
#               "as_on" wins (ADR-010)
#   manual      manual_review questions (policy gaps): answer recorded, NOT auto-scored except rule_hit
#   timings     per-stage ms from the audit record (Week 3); retrieval mode from env RETRIEVAL_MODE (default hybrid)
import json, datetime, os, pathlib, re, sys
from app.generate import answer, PROMPT_VERSION
MODE = os.environ.get("RETRIEVAL_MODE", "vector")
PRODUCT_CONTEXT = os.environ.get("PRODUCT_CONTEXT", "given")
AS_ON = os.environ.get("AS_ON", "2027-01-01")
assert PRODUCT_CONTEXT in ("given", "text"), "PRODUCT_CONTEXT must be given or text"
_IGNORE = re.compile(r"DB-[A-Z]+-\d{3}|\bparas?(?:graphs?)?\s*[\d(),\s-]+(?:and\s*\d+)?|\b(?:CF|RBC)\s*\d+", re.I)
def first_figure(text: str):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", _IGNORE.sub(" ", text))
    return m[0].replace(",", "") if m else None

GOLDEN = sys.argv[1] if len(sys.argv) > 1 else "eval/golden_v2.jsonl"
prefix = lambda rid: rid.rsplit("-", 1)[0]          # DB-HL-004 -> DB-HL
rows = [json.loads(l) for l in open(GOLDEN, encoding="utf-8")]
out = []
for r in rows:
    ctx = r.get("product") if PRODUCT_CONTEXT == "given" else None
    text, cites, rec = answer(r["question"], caller="eval", product=ctx, as_on=r.get("as_on") or AS_ON)
    doc = r.get("expected_doc", "RBI-CB-CREDIT-FAC-2025")
    exp, rules, ref = r.get("expected_clauses", []), r.get("expected_rules", []), r["expect_refusal"]
    got = [c.split(":", 1)[1] for c in rec["rbi_search"][:5] if c.startswith(doc + ":")]
    in_context = {x["clause_no"] for x in rec["retrieved"] if x["doc_id"] == doc}
    cited = {c.split(":", 1)[1] for c in rec.get("cited_rbi", []) if c.startswith(doc + ":")}
    pol = [x["clause_no"] for x in rec["retrieved"] if x.get("layer") == "policy"]
    must = r.get("must_contain", [])
    manual = bool(r.get("manual_review"))
    row = {"id": r["id"], "source": r.get("source"),
           "hit_at_5": any(c in got for c in exp) if exp and not ref else None,
           "in_context": any(c in in_context for c in exp) if exp and not ref else None,
           "cited_ok": any(c in cited for c in exp) if exp and not ref else None,
           "manual": manual, "note": r.get("note"),
           "rule_hit": any(x in pol for x in rules) if rules and not ref else None,
           "rule_cited": any(x in rec.get("cited_rules", []) for x in rules) if rules and not ref and not manual else None,
           "product_ok": all(prefix(c) in {prefix(x) for x in rules} for c in rec.get("cited_rules", []))
                         if rules and not ref else None,
           "answer_ok": all(any(a.lower() in text.lower() for a in m.split("|")) for m in must)
                        if must and not ref and not manual else None,
           "refusal_ok": None if manual else rec["refused"] == ref,
           "headline_ok": first_figure(text) == r["headline"].replace(",", "") if r.get("headline") and not ref else None,
           "first_figure": first_figure(text),
           "keyword_rules": [x["clause_no"] for x in rec["retrieved"] if x.get("how") == "keyword"], "products": rec["products"], "product_source": rec["product_source"],
           "retrieved_rbi": got, "retrieved_rules": pol, "cited": sorted(cited),
           "cited_rules": rec.get("cited_rules", []),
           "answer": text[:400], "expected_answer": r.get("expected_answer"),
           "cost_usd": rec["cost_usd"], "latency_ms": rec["latency_ms"],
           "timings_ms": rec["timings_ms"], "retries": rec["retries"]}
    out.append(row)
    bad = [k for k in ("cited_ok", "rule_cited", "product_ok", "answer_ok", "headline_ok", "refusal_ok") if row[k] is False]
    print("MAN" if manual else ("OK " if not bad else "BAD"), r["id"], "| rules", pol, "cited", row["cited_rules"], "| rbi", got,
          "cited", row["cited"], ("| FAILED " + ",".join(bad)) if bad else "")

METRICS = ("hit_at_5", "in_context", "cited_ok", "rule_hit", "rule_cited", "product_ok", "answer_ok", "headline_ok",
           "refusal_ok")
def score(k, sub=None):
    vals = [o[k] for o in (sub or out) if o[k] is not None]
    return f"{sum(vals)}/{len(vals)}" if vals else "-"

summary = {k: score(k) for k in METRICS}
real = [o for o in out if str(o["source"]).startswith("interview")]
summary["interview_questions"] = {k: score(k, real) for k in METRICS} if real else "-"
GROUPS = {"rbi_only": lambda o: "rbi-only" in str(o["source"]), "lap": lambda o: o["id"].startswith("l"),
          "cross_product": lambda o: o["id"].startswith("x"), "home_loan_policy": lambda o: o["id"].startswith("p")}
summary["by_group"] = {g: {k: score(k, [o for o in out if f(o)]) for k in METRICS} for g, f in GROUPS.items()}
summary["n_questions"] = len(out)
summary["manual_review"] = [{"id": o["id"], "refused": o["answer"].startswith("Not covered"), "answer": o["answer"][:200]}
                            for o in out if o["manual"]]
summary["total_cost_usd"] = round(sum(o["cost_usd"] for o in out), 5)
summary["avg_latency_s"] = round(sum(o["latency_ms"] for o in out) / len(out) / 1000, 1)
lat = sorted(o["latency_ms"] for o in out)
summary["median_latency_s"] = round(lat[len(lat) // 2] / 1000, 1)
stages = sorted({k for o in out for k in o["timings_ms"]})
summary["avg_stage_ms"] = {k: int(sum(o["timings_ms"].get(k, 0) for o in out) / len(out)) for k in stages}
summary["slowest"] = [{"id": o["id"], "latency_ms": o["latency_ms"], **o["timings_ms"], "retries": o["retries"]}
                      for o in sorted(out, key=lambda o: -o["latency_ms"])[:4]]
summary["retries"] = {k: sum(o["retries"].get(k, 0) for o in out) for k in ("openai", "qdrant", "anthropic")}
summary["retrieval_mode"] = MODE
summary["product_context"] = PRODUCT_CONTEXT
summary["as_on"] = AS_ON
summary["policy_keyword"] = os.environ.get("POLICY_KEYWORD", "1")
summary["keyword_added"] = {o["id"]: o["keyword_rules"] for o in out if o["keyword_rules"]}
summary["product_source"] = {s: sum(o["product_source"] == s for o in out) for s in ("given", "detected", "unclear")}
summary["golden_set"] = pathlib.Path(GOLDEN).stem
summary["prompt_version"] = PROMPT_VERSION
pathlib.Path("eval/reports").mkdir(parents=True, exist_ok=True)
path = f'eval/reports/{datetime.datetime.now():%Y-%m-%d_%H%M}_{PROMPT_VERSION}_{MODE}_product-{PRODUCT_CONTEXT}_{summary["golden_set"]}.json'
with open(path, "w", encoding="utf-8") as f:
    json.dump({"summary": summary, "rows": out}, f, indent=2, ensure_ascii=False)
print("\n", json.dumps(summary, indent=1), "\nreport:", path)
