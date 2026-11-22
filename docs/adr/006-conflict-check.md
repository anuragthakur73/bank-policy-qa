# ADR-006: Bank-vs-RBI conflict check = traced RBI text + LLM verdict, proven on planted fixtures

Date: 23 Nov 2026 · Status: accepted

## Context
Option C's headline feature is flagging any bank rule looser than RBI (ADR-004). Published bank documents do lag
RBI: the SBI study found MITC wording where only the bank chooses EMI vs tenure after a rate change, while RBI
para 349(3) requires the borrower to be offered the choice. Demo Bank's 13 RBI-bound rules declare `vs_rbi`.

## Decision
1. For each rule with `rbi_ref`, fetch the cited paragraph(s) **by number** (policy trace, ADR-005); no search.
2. Ask Claude (Haiku, effort low, prompt `conflict-v1`) for JSON: `equal | stricter | looser | unclear`, the
   paragraph relied on, and a one-sentence reason quoting RBI. Malformed output → `unclear`.
3. Outcomes: equal/stricter → pass; looser → FLAG; unclear → human review; cited text not indexed → cannot_check.
4. **Proof by fixtures**: `conflict_fixtures.yaml` holds 5 rules that are deliberately looser (incl. one echoing
   real SBI wording). The check must catch 5/5 while flagging 0 of Demo Bank's own rules.
5. Every run writes `eval/reports/<date>_conflict-v1.json` (rows + summary + cost).

## Why
- Most limits are prose ("shall not exceed", "within 30 days", "no pre-payment charges"): numeric rules alone
  would miss reset options, disclosure and penal-charge form. An LLM reads prose; the fixtures measure whether it
  reads it correctly.
- Fetching the paragraph by number means the model judges against the right text, and a reviewer can see exactly
  which RBI words decided the verdict.

## Alternatives considered
1. Deterministic checks on `params` only (e.g. LTV bands vs para 111): exact, already in tests/test_policy.py,
   but covers about a third of rules. Kept as a second line of defence, not the main check.
2. Letting the answer prompt spot conflicts at question time: untestable and only fires when someone asks.

## Consequences
- The checker is itself a model: false negatives are possible. Fixtures are the regression test; add one for
  every real-world conflict found. Unclear verdicts go to a human, never auto-pass.
- Rules citing non-RBI sources (PMAY-U 2.0 guidelines) return cannot_check until those are indexed.
- Cost: ~18 Haiku calls per full run, well under $0.01.

## Update (23 Nov 2026): conflict-v2
- conflict-v1 run 1 flagged 3 real gaps in Demo Bank's draft (DB-HL-014, 025, 028: missing borrower notices
  RBI requires). Rules fixed; run 2 passed 12/12, fixtures 5/5.
- But equal-vs-stricter verdicts flipped between runs (DB-HL-001, 025, 026). That distinction is a judgment
  call, not a compliance fact.
- v2: the model answers only `complies | looser | unclear`; each rule is checked 3 times and the majority
  wins (no majority -> unclear -> human review); disagreement between runs is reported as `unstable`.
  Equal-vs-stricter stays a human label (`vs_rbi`), and tests forbid `looser` there.

## Update (23 Nov 2026): conflict-v3 - contradiction vs coverage
- conflict-v2 counted a rule's silence on any RBI requirement as "looser". On long RBI paragraphs (348, 349, 92)
  each run found a different unstated detail (and twice misread the rule), so fixing one flag produced the next.
- v3 separates two questions in one call:
  1. **Blocking verdict = contradiction only**: looser if the rule permits what RBI forbids, sets a weaker limit
     or deadline, or removes a borrower choice. Silence complies (RBI binds the bank regardless).
  2. **Non-blocking coverage list**: every relevant RBI requirement the rule does not restate, merged across the
     3 runs, for a one-pass human decision on what the policy text should add.
- Fixtures FX-001..005 are all contradictions, so the regression bar is unchanged (5/5).
