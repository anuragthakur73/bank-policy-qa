# ADR-009: Product filter on the Demo Bank policy layer

Date: 25 Nov 2026 · Status: accepted (Week 4 S1)

## Context
With home loan (34 rules) and LAP (20 rules) in one collection `policy_v1`, the policy top 3 mixed products.
golden_v2 (25 Nov): 7/30 answers cited a rule of the other product (product_ok 23/30). Worst case l01: a LAP LTV
question answered "75%" from home-loan rule DB-HL-009 instead of 65% from DB-LAP-007, and must_contain("65")
still passed because 65% appeared later in the answer. l07 refused: the LAP rule was crowded out of the top 3.

## Decision
1. Every policy point carries `metadata.product` (from the policy file header), with a keyword payload index.
2. Product is resolved in this order (`app/product.py`): given by the caller (screen selector, API, loan file)
   > named in the question (keywords: LAP, loan against property/flat/shop, mortgage loan; home/housing/composite
   loan) > unclear. Both products named counts as unclear.
3. Qdrant filters policy search by product before ranking. Each product searched gets its own k_policy (3) quota,
   so with an unclear question both products' best rules reach the model and neither crowds out the other.
4. Prompt answer-v3: rule titles name the product; apply a rule only to its own product; if the product is
   unclear, answer each product separately, labelled.
5. RBI clauses are NOT tagged or filtered: they sit in their own collection and apply to all products.
6. Contract v0.2 -> v0.3: `retrieve(..., products=None)` keeps old behaviour; rows gain `product`. Audit records
   `products` and `product_source` (given | detected | unclear).
7. Eval: rows carry `product` (what the selector would send). PRODUCT_CONTEXT=given (default) uses it;
   PRODUCT_CONTEXT=text measures detection alone. New metric headline_ok: the first figure in the answer must equal
   the expected figure (9 rows).

## Alternatives considered
- One collection per product: duplicates nothing today, but every new product (vehicle, education) means a new
  collection, new indexes and a retrieval change; a payload filter is one field. Cross-product questions would need
  two searches either way.
- Asking the officer "Home loan or LAP?" when unclear: safer, but one more step on every unlabelled question.
  Rejected for now; revisit if labelled two-product answers confuse pilot users.
- Detecting the product with an LLM call: adds cost and latency to every query; keywords cover the questions seen.

## Consequences
- In a real deployment the product almost always comes from the loan file or screen, so "given" is the realistic
  mode; "text" mode is the fallback for free-text questions.
- Keyword detection misses unnamed products (e.g. "who approves a FOIR deviation?"); those get two labelled answers.

## Result (25 Nov 2026, golden_v2, vector, answer-v3)
Product given: product_ok 30/30 (was 23/30), headline_ok 9/9, no other score dropped, $0.056 / 51 questions.
Text only: product_ok 22/30; 31 of 51 questions name no product. Every miss is a correctly labelled two-product
answer, so the cost of "unclear" is longer answers, not wrong ones. This supports passing the product from the
screen or loan file as the normal path.
