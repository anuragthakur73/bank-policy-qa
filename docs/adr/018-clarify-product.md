# ADR-018: Ask which product when the question and the caller do not say

Date: 27 Nov 2026 · Status: accepted 27 Nov 2026 (Week 5 S4) - done-when met on golden_v2_3, both contexts

## Context
With three products, a question that names none ("What penal charge applies if an EMI is paid late?") was searched
across all three and answered three times (ADR-009). golden_v2_2, product from text: product_ok 37/47, every miss a
correctly labelled but long multi-product answer (p04-p15, i04). i01 (stamp duty) flips between a refusal and a
three-part "no amount given" answer run to run. Staff almost always mean one product.

## Decision
1. `app/clarify.py` (deterministic, no model call): ask when the caller gave no product, the question names none,
   it is not about a topic the bank policy does not cover (gold, FDs, digital lending, education/personal loans,
   project finance, builders, securities, cash credit, NBFC, export, MSME, NPA, KYC) and does not ask what RBI
   says, the policy layer is in use, and at least two products are in force on the as-on date.
2. Graph (ADR-016): conditional edge route -> clarify -> END. Nothing is searched and the model is not called; the
   reply is a code-written question with options (each product in force + "RBI rule only"). Audited with
   mode=clarify. CLARIFY=0 turns it off. The plain flow is unchanged (rollback only).
3. The reply is the same question asked again with product set: a product key, or `rbi_only` (RBI clauses only).
   API: `mode="clarify"` with a `clarify` field; `rbi_only` accepted by /v1/answer and /v1/retrieve. Screen: one
   button per option.
4. Not asked: the as-on date. It defaults to today, which is what frontline staff mean; a policy not yet in force
   already gets a code-written notice (ADR-010). Asking for a date would add a step to almost every question.

## Done when
golden_v2_3 (77 = v2_2 + k01-k05) in both contexts: clarify_ok on every tagged row (asks on k01, k02, i01 always;
on the 13 text_only rows only when the product is not passed; never on the 22 "never" rows); text-context product_ok
47/47 after the simulated reply; no regression in product-given scores.

## Trade-off
One extra step for staff who leave the product on "Work out from my question" and do not name it; free and instant.
A question on an RBI-only topic missing from the list is asked about unnecessarily; "RBI rule only" answers it.

## Result (27 Nov 2026, golden_v2_3, graph, answer-v5; 21:49 product given, 21:57 product from text)
| Metric | Given | Text | Text before S4 (v2_2, 01:19) |
|---|---|---|---|
| Asked / clarify_ok | 3 (i01, k01, k02) / 25/25 | 16 / 38/38 | - |
| Right-product rules | 52/52 | 52/52 | 37/47 |
| RBI cited / rules cited | 29/29 / 51/51 | 29/29 / 51/51 | 28/28 / 46/46 |
| Answers / refusals | 40/40 / 76/76 | 40/40 / 76/76 | 35/35 / 69/71 |
| Validator | 77 pass, 0 retries | 77 pass, 0 retries | 4 retries |
| Cost / median latency | $0.085 / 6.4 s | $0.084 / 6.1 s | $0.091 / 7.1 s |
Every text-context home-loan question that used to get a three-product answer now asks, and after the reply cites
only home-loan rules. i01 (stamp duty) asks, and after "RBI rule only" refuses cleanly: stable for the first time.
Headline 22/24 in the report; after the scorer change in the same commit (number words before a unit; x04 headline
dropped) c07 reads 3 and x04 is unscored, so 22/22.
