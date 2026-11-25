# run: python -m eval.spot_check   (asks the interview questions that policy v1.1 was written to answer; ~$0.005)
# Pass = the expected rule is cited and the answer is not a refusal. Prints answers for a human read.
import json
import os
from app.generate import answer, REFUSAL
AS_ON = os.environ.get("AS_ON", "2027-01-01")   # policies these checks were written for (ADR-010)

EXPECT = {"i02": "DB-HL-032", "i04": "DB-HL-004", "i05": "DB-HL-033", "i06": "DB-HL-034", "i07": "DB-HL-003"}
rows = {json.loads(l)["id"]: json.loads(l) for l in open("eval/golden_v1.jsonl", encoding="utf-8")}
ok = 0
for qid, rule in EXPECT.items():
    text, cites, rec = answer(rows[qid]["question"], caller="spot", as_on=AS_ON)
    hit = rule in rec["cited_rules"] and REFUSAL not in text
    ok += hit
    print(f'{"PASS" if hit else "FAIL"} {qid} expects {rule} | cited {rec["cited_rules"]} {rec["cited_rbi"]} | {rec["latency_ms"]} ms')
    print("   Q:", rows[qid]["question"])
    print("   A:", " ".join(text.split())[:600], "\n")
print(f"{ok}/{len(EXPECT)} interview questions answered from the expected v1.1 rule")
