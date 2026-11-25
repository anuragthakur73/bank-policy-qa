# ADR-014: Check every answer against what was retrieved; retry once, then refuse

Date: 25 Nov 2026 · Status: accepted 26 Nov 2026 (Week 4 S3)

## Context
The model sometimes names a source it does not cite (p09, g005: "implements RBI paragraphs 352 and 353" with no
citation), and before ADR-012 applied a housing-loan paragraph to LAP (d4). Week 3: automatic checks catch invented
figures but not a wrong direction of change, so checks are a floor, not proof. A reviewer or auditor needs every
named rule and paragraph to be a clickable, checked citation.

## Decision
1. Keep native citations (search_result blocks), not the JSON-schema output in the original Week 4 plan: native
   citations copy the cited text from the source and keep the clause links (Anurag: links must go straight to the
   RBI clause). The schema's coverage / missing_inputs fields are deferred; they can be added without changing this.
2. `app/validate.py` (pure, deterministic). Blocking checks ("fail"):
   - cited_not_retrieved: a citation that maps to no retrieved row
   - quote_not_in_source: cited text not found in the cited row
   - version_not_in_force: a policy rule version not in force on the as-on date (ADR-010)
   - wrong_product: a rule of another product, or an RBI clause limited to another product (ADR-009, ADR-012)
   - named_not_cited: a rule ID or RBI paragraph named in the answer but not cited (a reference that appears inside
     a cited source's text is allowed, e.g. DB-LAP-009 mentions DB-LAP-003)
   Logged only ("warn"): figure_not_in_sources - a %, Rs, lakh/crore, years/months/days figure not found in the
   cited sources or the question. Not blocking yet: answers legitimately work figures out (p04: 65 - 45 = 20 years).
3. On a blocking issue: one retry with the problems listed; if it still fails, the answer becomes the refusal.
   Both drafts and all issues are kept in the audit record (validation.first / second / draft_1 / draft_2).
4. VALIDATOR=log records issues without retrying (for comparison runs). Default: enforce.
5. Refusals are not checked. Notices (ADR-010) are added after the check; they are written by code.

## Trade-off
A correct answer that names a paragraph without citing it can now be retried (extra ~$0.001, ~5 s) or, rarely,
refused. For staff acting on a rule, an uncited claim is worse than a slower or missing answer.

## Revisions after live runs (26 Nov 2026)
1. Citations are mapped back by search_result_index, not by link: CF 108 and 109 share a text-fragment link, so
   r04's citation of 109 had been recorded as 108 since Week 3. Run 2: r04 cites 109.
2. Run 2 refused p02 (a correct answer): it said "DB-HL-010 implements RBI para 113" and cited the rule, not para
   113, in both drafts. The rule -> para link is a fact in the policy file, so a para that a CITED rule implements is
   now a warning (implemented_para_not_cited). Paras with no such link still block (l01 named CF 219G/44, x02 327).
3. is_refusal: an answer that starts with the refusal counts as a refusal even with remarks after it (g010); the
   remarks are still checked.
Lesson: a blocking check needs its false-refusal rate measured on real answers before it ships; run 2 refused 1
correct answer of 51.
4. Run 3 (26 Nov 00:38): 47 pass, 4 passed after retry, 0 refused; refusals 51/51, rules 30/30, product_ok 30/30,
   headline_ok 9/9, RBI cited 22/23; $0.060 per 51 questions (+~5% for retries), 6.4 s median.
   The miss, g001, answered correctly but wrote <span index="10-1"> markup instead of citing -> two new blocking
   checks: no_citations, citation_markup_in_text (not yet run live; next eval).
   Warnings in run 3: figure_not_in_sources 4 (all worked-out or uncited figures), implemented_para_not_cited 5.
