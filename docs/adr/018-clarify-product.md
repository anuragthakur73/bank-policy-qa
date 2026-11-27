# ADR-018: Ask which product when the question and the caller do not say

Date: 27 Nov 2026 · Status: proposed (Week 5 S4) - accepted after golden_v2_3 runs (product given + text)

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
