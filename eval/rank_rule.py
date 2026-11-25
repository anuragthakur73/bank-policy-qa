# run: python -m eval.rank_rule "question" RULE_ID [product] [as_on]   (no Claude call; ~$0.00001)
# Where does a rule rank in the filtered policy search? Used for l07 (DB-LAP-009 never reached the top 3).
import sys
from app.retrieve import _embed, _search_vec
from app.policy_versions import to_date
q, rule = sys.argv[1], sys.argv[2]
product = sys.argv[3] if len(sys.argv) > 3 else None
as_on = to_date(sys.argv[4]) if len(sys.argv) > 4 else None
for i, (d, s) in enumerate(_search_vec(_embed(q), 25, "policy", product, as_on), start=1):
    m = d.metadata
    print(f'{"->" if m["rule_id"] == rule else "  "} {i:2} {m["rule_id"]:11} v{m.get("policy_version")} {s:.3f}  {m["section"]} > {m["title"]}')
