# run: python -m eval.compare_pipelines REPORT_PLAIN.json REPORT_GRAPH.json     (Week 5 S3, ADR-016; no API calls)
# Done-when for the LangGraph port: retrieval identical per question, model-scored metrics within +-2 (one-run
# moves of +-2 are noise: Week 4 lesson 4), validator outcomes listed where they differ.
import json, sys

RETRIEVAL = ("retrieved_rbi", "retrieved_rules", "keyword_rules", "products", "product_source")
MODEL = ("cited_ok", "rule_cited", "product_ok", "answer_ok", "headline_ok", "version_ok", "notice_ok", "pii_ok",
         "refusal_ok")

def load(p):
    d = json.load(open(p, encoding="utf-8"))
    return d["summary"], {r["id"]: r for r in d["rows"]}

(sa, a), (sb, b) = load(sys.argv[1]), load(sys.argv[2])
assert a.keys() == b.keys(), "the two reports cover different questions"
diff_ret = [(i, k) for i in a for k in RETRIEVAL if a[i][k] != b[i][k]]
print(f"{sa.get('pipeline', 'plain')} vs {sb.get('pipeline', '?')} | {len(a)} questions")
print("retrieval identical:", "YES" if not diff_ret else f"NO ({len(diff_ret)} differences)")
for i, k in diff_ret[:20]:
    print(f"   {i} {k}: {a[i][k]} -> {b[i][k]}")
ok = True
print(f"{'metric':12} {'A':>7} {'B':>7}  delta")
for m in MODEL:
    pa, pb = sum(r[m] is True for r in a.values()), sum(r[m] is True for r in b.values())
    na, nb = sum(r[m] is not None for r in a.values()), sum(r[m] is not None for r in b.values())
    d = pb - pa
    ok &= abs(d) <= 2
    print(f"{m:12} {pa:>3}/{na:<3} {pb:>3}/{nb:<3}  {d:+d}{'  <-- beyond +-2' if abs(d) > 2 else ''}")
flips = [(i, m, a[i][m], b[i][m]) for i in a for m in MODEL if a[i][m] is not None and a[i][m] != b[i][m]]
print("per-question flips:", len(flips))
for f in flips:
    print("  ", *f)
val = [(i, a[i]["validation"], b[i]["validation"]) for i in a if a[i]["validation"] != b[i]["validation"]]
print("validator outcome differs:", len(val), val[:10])
print(f"cost ${sa['total_cost_usd']} -> ${sb['total_cost_usd']} | median latency {sa['median_latency_s']} s -> "
      f"{sb['median_latency_s']} s")
print("DONE-WHEN:", "MET" if ok and not diff_ret else "NOT MET")
sys.exit(0 if ok and not diff_ret else 1)
