# run: python -m eval.date_check   (6 live questions, ~$0.006) — Week 4 S2, ADR-010
# Same questions asked on different "as on" dates must use the policy version in force on that date.
from app.generate import answer

P01 = ("Customer wants a composite loan of Rs 40 lakh to buy a plot and build a house on it; total cost Rs 55 lakh. "
       "What LTV applies?")
I04 = "what will be the max age is case of a pensioner under NPS ?"
CASES = [  # (id, question, product, as_on, check, what it shows)
    ("d1", P01, "home_loan", "2026-12-15",
     lambda t, r: "DB-HL-032" not in r["cited_rules"] and set(r["cited_rule_versions"].values()) <= {"1.0.0"},
     "v1.0 in force: no composite-loan rule yet (DB-HL-032 is new in v1.1)"),
    ("d2", P01, "home_loan", "2027-01-02",
     lambda t, r: "DB-HL-032" in r["cited_rules"] and r["cited_rule_versions"]["DB-HL-032"] == "1.1.0",
     "v1.1 in force: DB-HL-032 answers it"),
    ("d3", "What is the maximum LTV for a home loan of Rs 50 lakh?", "home_loan", "2026-11-25",
     lambda t, r: not r["cited_rules"] and t.startswith("Demo Bank's Home Loan policy is not in force"),
     "before 1 Dec 2026: no home-loan policy in force -> notice + RBI only"),
    ("d4", "What is the maximum LTV on a loan against a self-occupied flat for a loan of Rs 80 lakh?", "lap",
     "2026-12-15",
     lambda t, r: (not r["cited_rules"] and t.startswith("Demo Bank's Loan Against Property (LAP) policy is not in force")
                   and "RBI-CB-CREDIT-FAC-2025:111" not in r["cited_rbi"] and "75%" not in t),
     "LAP starts 1 Jan 2027 -> notice + RBI only, and NOT the housing-loan LTV (para 111, 75%) - ADR-012"),
    ("d5", I04, "home_loan", "2026-12-15",
     lambda t, r: r["cited_rule_versions"].get("DB-HL-004") == "1.0.0" and "Note: DB-HL-004 is due to change on 1 Jan 2027" in t,
     "v1.0 rule, plus a note that it is due to change on 1 Jan 2027"),
    ("d6", I04, "home_loan", "2027-01-02",
     lambda t, r: r["cited_rule_versions"].get("DB-HL-004") == "1.1.0" and "Note:" not in t,
     "v1.1 rule, no change note (no later version)"),
]
ok = 0
for cid, q, product, as_on, check, why in CASES:
    text, cites, rec = answer(q, caller="date_check", product=product, as_on=as_on)
    hit = check(text, rec); ok += hit
    print(f'{"PASS" if hit else "FAIL"} {cid} as on {as_on}: {why}')
    print(f'   cited {rec["cited_rule_versions"]} | rbi {rec["cited_rbi"]} | notices {rec["notices"]}')
    print("   A:", " ".join(text.split())[:300], "\n")
print(f"{ok}/{len(CASES)} date checks passed")
