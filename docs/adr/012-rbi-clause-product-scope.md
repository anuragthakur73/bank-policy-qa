# ADR-012: RBI clauses limited to one product are not used for another product

Date: 25 Nov 2026 · Status: accepted 25 Nov 2026

## Context
date_check d4 (LAP question as on 15 Dec 2026, before the LAP policy starts, so RBI only under ADR-010) answered
"capped at 75% LTV" from CF para 111 - the housing-loan LTV cap. Para 111 sits in CF Chapter VIII B (Housing
Finance) and does not apply to LAP (LAP study, Week 3). With no bank rule in context, the closest RBI text won, and
the model applied it while noting it was "best read as applying to individual housing loans". A wrong figure.
In S1 RBI clauses were left untagged ("separate collection, applies to all products"): that was wrong for sections
written for one kind of loan.

## Decision
1. `app/rbi_scope.py` maps RBI ranges to the one product they are limited to. First entry: CF paras 89-124
   (Chapter VIII B, Housing Finance, sections B to B.8) -> home_loan. Everything else: not limited.
2. When the question's product is known (given or detected), RBI search fetches 2k candidates, drops clauses limited
   to another product, keeps k. Unclear product (both searched) keeps everything.
3. The filter uses the product ASKED about, not the products whose policy is in force: in d4 no LAP policy is in
   force, but the question is still about LAP.
4. Rules' traced RBI paragraphs are unaffected (a rule names its own paragraph). Contract v0.6, row field rbi_scope.
5. Local mapping, no re-index: 1 range today; move into the index payload when the mapping grows.

## Alternatives considered
- Tell the model the product and let it judge applicability: it already doubted para 111 and answered anyway.
- Refuse every product question when the product's policy is not in force: too blunt; KFS, penal-charge and
  pre-payment rules (RBC 348-359) do apply to LAP.

## To verify (domain - Anurag)
Whether other CF sections should be limited too (e.g. B.5 housing intermediaries, CRE sections C-E), and whether any
housing-finance paragraph applies to LAP. Mapping is one line per range.

## Result (25 Nov 2026)
d4 now: notice + "Not covered by the indexed documents" (no para 111, no 75%). date_check 6/6.
golden_v2: retrieval changed only for 7 LAP-context questions (housing-finance paras removed, as intended). rules
30/30, refusals 51/51, product_ok 30/30, headline_ok 9/9. RBI cited 22/23 -> 20/23, but g005 and g008 had IDENTICAL
RBI results to the previous run: the model named para 111 in the text without citing it (g005, same pattern as p09)
or cited a different para (g008). Model variance, not this change. RBI cited has read 21, 22, 20 across runs with
the same retrieval: single-run moves of +/-2 in model-scored metrics are noise.
