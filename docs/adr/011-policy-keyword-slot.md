# ADR-011: One keyword (BM25) slot in the policy search

Date: 25 Nov 2026 · Status: accepted 25 Nov 2026 (Week 4 S2b)

## Context
l07 "Can a loan against property be given as an overdraft?" was refused in every run. DB-LAP-009 answers it
("Demo Bank does not offer LAP as an overdraft"), but the rule is mostly about tenure, so vector search ranks it
8th of 20 LAP rules even with the product and date filters; only the top 3 reach the model. Keyword search (BM25)
ranks it 1st: it is the only rule in any policy file containing "overdraft".
ADR-007 dropped hybrid search for RBI because it showed no measured gain. Here there is a measured failure.

## Decision
Per product searched (with an as-on date): rank all eligible rules by vector similarity, keep the top 3, and add the
best BM25 match among the rules in force if it is not already there. At most 4 rules per product. BM25 is built
locally from the policy files (no network). Rows found this way carry retrieval.mode = "keyword". Contract v0.5.
POLICY_KEYWORD=0 turns it off for comparison.

## Why not reciprocal rank fusion (as in ADR-007)
Estimate (inference: only DB-LAP-009's vector rank is known): 8th by vector + 1st by keyword = 1/68 + 1/61 = 0.0311;
a rule 3rd by vector and 2nd by keyword = 0.0320; 1st and 3rd = 0.0323. Fusion would likely still leave DB-LAP-009
4th. A reserved slot guarantees an exact-term match reaches the model; the model still decides whether it answers.

## Alternatives considered
- Raise k_policy to 8: more context on every question to fix one; does not generalise to rank 12.
- Split DB-LAP-009 (tenure vs facility form): good policy hygiene, but fixes one rule and needs a policy change.

## Risks
One more rule in context can distract the model (e.g. l08 tenure, where BM25's top hit is DB-LAP-011).
Accept only if golden_v2 shows no drop in any score.

## Result (25 Nov 2026, golden_v2 as on 1 Jan 2027, product given)
Off (S2) -> on: rules found 29/30 -> 30/30, rules cited 29/30 -> 30/30, refusals 50/51 -> 51/51 (l07 now "No" from
DB-LAP-009). No score dropped; l08 still correct. Cost $0.054 -> $0.058 per 51 questions, median 6.4 -> 6.7 s.
Follow-up: the slot fires on 16/51 questions, including RBI-only gold-loan questions (DB-HL-001 / DB-LAP-001 added
on weak matches like "loan"). Harmless in this run, but noise; consider a minimum keyword score.
