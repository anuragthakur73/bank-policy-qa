# run: python -m eval.run_eval
# Scores retrieval (hit@5), citation (cited the expected clause) and refusal on the golden set.
import json, datetime, pathlib
from app.generate import answer, REFUSAL, PROMPT_VERSION

rows = [json.loads(l) for l in open("eval/golden_v0.jsonl", encoding="utf-8")]
out = []
for r in rows:
    text, cites, rec = answer(r["question"], caller="eval")
    doc = r.get("expected_doc", "RBI-CB-CREDIT-FAC-2025")      # golden_v0 questions are all Credit Facilities
    # hit@5 = the top 5 RBI clauses from SEARCH only (not policy rules, not paragraphs pulled in by a rule's trace)
    searched = [x for x in rec["retrieved"] if x.get("layer", "rbi") == "rbi" and not x.get("traced_from")][:5]
    got = [x["clause_no"] for x in searched if x["doc_id"] == doc]
    in_context = {x["clause_no"] for x in rec["retrieved"] if x["doc_id"] == doc}   # everything shown to the model
    cited = {c.split(":", 1)[1] for c in rec.get("cited_rbi", []) if c.startswith(doc + ":")}
    exp, ref = r["expected_clauses"], r["expect_refusal"]
    row = {"id": r["id"],
           "hit_at_5": None if ref else any(c in got for c in exp),
           "in_context": None if ref else any(c in in_context for c in exp),
           "cited_ok": None if ref else any(c in cited for c in exp),
           "refusal_ok": rec["refused"] == ref,
           "retrieved": got, "cited": sorted(cited), "cited_rules": rec.get("cited_rules", []),
           "answer": text[:300], "expected_answer": r.get("expected_answer"),
           "cost_usd": rec["cost_usd"], "latency_ms": rec["latency_ms"]}
    out.append(row)
    flag = "OK " if row["refusal_ok"] and row["cited_ok"] is not False else "BAD"
    print(flag, r["id"], "| retrieved", got, "| cited", rec["cited_clauses"])

def score(k):
    vals = [o[k] for o in out if o[k] is not None]
    return f"{sum(vals)}/{len(vals)}"

summary = {k: score(k) for k in ("hit_at_5", "in_context", "cited_ok", "refusal_ok")}
summary["total_cost_usd"] = round(sum(o["cost_usd"] for o in out), 5)
summary["avg_latency_s"] = round(sum(o["latency_ms"] for o in out) / len(out) / 1000, 1)
summary["golden_set"] = "golden_v0"
summary["prompt_version"] = PROMPT_VERSION
pathlib.Path("eval/reports").mkdir(parents=True, exist_ok=True)
path = f"eval/reports/{datetime.date.today()}_{PROMPT_VERSION}.json"   # one file per prompt version, never overwritten by another
with open(path, "w", encoding="utf-8") as f:
    json.dump({"summary": summary, "rows": out}, f, indent=2, ensure_ascii=False)
print("\n", summary, "\nreport:", path)
