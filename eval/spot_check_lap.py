# run: python -m eval.spot_check_lap   (3 LAP questions after indexing lap_v1; ~$0.003)
from app.generate import answer, REFUSAL

QS = [("What is the maximum LTV for a loan against a commercial shop?", "DB-LAP-007", "55%"),
      ("Can a customer take a loan against property to buy shares?", "DB-LAP-001", None),
      ("Is there a foreclosure charge on a floating-rate LAP taken for business?", "DB-LAP-013", None)]
ok = 0
for q, rule, must in QS:
    text, cites, rec = answer(q, caller="spot")
    hit = rule in rec["cited_rules"] and REFUSAL not in text and (must is None or must in text)
    ok += hit
    print(f'{"PASS" if hit else "FAIL"} expects {rule} | cited {rec["cited_rules"]} {rec["cited_rbi"]} | {rec["latency_ms"]} ms')
    print("   Q:", q); print("   A:", " ".join(text.split())[:400], "\n")
print(f"{ok}/{len(QS)} LAP questions answered from the expected rule")
