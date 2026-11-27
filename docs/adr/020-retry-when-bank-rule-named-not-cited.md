# ADR-020: Retry when a bank-rule answer names a retrieved Demo Bank rule but cites none

Date: 27 Nov 2026 · Status: deferred 27 Nov 2026 (Week 6 S1) - revisit if `named_not_cited` is ever non-empty

## Context
ADR-017 turned "a retrieved source is named but not cited" into a warning plus a code-written "Also named" link.
Side effect: a question that needs a Demo Bank rule could pass with only RBI cited and the bank rule present as a
system link, not as the model's own sourced statement. Idea (Week 5): retry (never refuse) in that case.

## Evidence (golden_v2_3, 77 Qs, answer-v5, 27 Nov 21:49 / 21:57)
- Checker retries: 0 in both runs.
- Answers with no Demo Bank rule cited but one named + linked: 0 with product given; 2 with product from text
  (r04, r07). Both are RBI-only questions (no rule expected), answered correctly from RBI; naming a bank rule in
  passing is harmless there. Bank-rule questions affected: 0 of 52 in both runs.

## Decision
Do not build the retry now: it adds a model call and a new failure path for a case not yet observed. Instead
`eval/run_eval.py` reports `named_not_cited`: bank-rule questions (rule expected) answered with no Demo Bank rule
cited although one was named and linked. The eval report shows it every run.

## Revisit when
`named_not_cited` is non-empty in any golden-set run, or in production feedback.

## Consequences
+ No extra cost or latency; the risk is measured, not assumed. - A real occurrence passes once before it is seen.
