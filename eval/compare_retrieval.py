# run: python -m eval.compare_retrieval            (search only: no Claude calls, embedding cost < $0.001)
# For every golden question with an expected RBI clause: is it in the RBI top 5 for each retrieval mode?
# Also checks that the hand-built hybrid and the LangChain hybrid return the same top 5 (ADR-007).
import json, os, sys, time
from app.retrieve import retrieve, MODES

GOLDEN = sys.argv[1] if len(sys.argv) > 1 else "eval/golden_v1.jsonl"
modes = os.environ.get("MODES", ",".join(MODES)).split(",")
qs = [json.loads(l) for l in open(GOLDEN, encoding="utf-8")]
qs = [q for q in qs if q.get("expected_clauses") and not q["expect_refusal"]]
hits = {m: 0 for m in modes}; ms = {m: [] for m in modes}; same = 0; tops = {}
for q in qs:
    doc = q.get("expected_doc", "RBI-CB-CREDIT-FAC-2025")
    line = [q["id"]]
    for m in modes:
        t0 = time.perf_counter()
        rows = retrieve(q["question"], 5, layers=("rbi",), mode=m)
        ms[m].append((time.perf_counter() - t0) * 1000)
        top = [r["clause_no"] for r in rows if r["doc_id"] == doc]
        tops[m] = [(r["doc_id"], r["clause_no"]) for r in rows]
        ok = any(c in top for c in q["expected_clauses"]); hits[m] += ok
        line.append(f'{m}:{"OK " if ok else "MISS"}')
    if "hybrid" in tops and "hybrid_lc" in tops:
        agree = tops["hybrid"] == tops["hybrid_lc"]; same += agree
        line.append("" if agree else f'DIFF {[c for _, c in tops["hybrid"]]} vs {[c for _, c in tops["hybrid_lc"]]}')
    print("  ".join(line), "| expected", q["expected_clauses"])
print()
for m in modes:
    v = sorted(ms[m])
    print(f"{m:10s} hit@5 {hits[m]}/{len(qs)}   median {v[len(v)//2]:.0f} ms   max {v[-1]:.0f} ms")
if "hybrid" in modes and "hybrid_lc" in modes:
    print(f"hybrid vs hybrid_lc: identical top 5 on {same}/{len(qs)} questions")
