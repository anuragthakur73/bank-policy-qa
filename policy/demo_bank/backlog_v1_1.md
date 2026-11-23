# Demo Bank Home Loan Policy — v1.1 backlog

Source: real loan-officer questions in eval/golden_v1.jsonl (I0X = interview ID) and the conflict-v3 coverage list.
Policy v1.0.0 is frozen for Week 2; these are drafted in Week 3 as v1.1 (new `policy_version`, new `effective_from`).

| # | From | Gap | Proposed rule (to draft) | Likely RBI link |
|---|---|---|---|---|
| 1 | I02 | Composite loan: is LTV on combined plot + construction cost, or each part separately? | State how LTV applies to plot + construction loans (combined cost, plot share capped) | CF 111 (LTV), 90 (plot) |
| 2 | I04 | Does an NPS pension count as "pension" for the age-70 limit in DB-HL-004? | Define which pensions qualify (defined-benefit, NPS annuity) and the proof needed | none: bank discretion |
| 3 | I05 | Loan to buy one floor of a multi-storey house | Allow / refuse purchase of an independent floor; conditions (separate title, approved plan, undivided share) | CF 92 (sanctioned plan) |
| 4 | I06 | Second house on land already carrying a bank-funded house | Conditions when the land already has a charge (existing mortgage, sanctioned plan for 2nd unit, combined LTV) | CF 94-type second-house clause (verify para) |
| 5 | I07 | Answer cited DB-HL-006, not DB-HL-003, for "company as applicant" | Make DB-HL-003 state explicitly that firms, companies and trusts cannot be applicants or co-applicants | none: bank discretion |
| 6 | conflict-v3 | 116 RBI requirements not restated across 11 rules | One pass: add the frontline-relevant ones; leave bank-internal duties to RBI | per rule |

Process for each: draft rule → `review: needs_review` → Anurag's review → `python -m app.conflict` → add the
interview question's expected answer to golden_v1 (manual_review: false).
