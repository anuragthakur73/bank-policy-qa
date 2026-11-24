# ADR-008: "What changed" circular between policy versions

Date: 24 Nov 2026 · Status: accepted

## Context
Interviews (Nov 2026): the real pain is not "the rule as on date X" but "what changed, and did everyone hear".
Policy v1.1 changed 11 rules. Branches need a one-page circular, and it must list exactly the changes - a missed
or invented change in a circular is a compliance error.

## Decision
`app/policy_diff.py`, in three steps:
1. **Diff in plain code** (the source of truth): rule by rule, added / changed / removed, comparing only
   substantive fields (rule text, params, RBI ref, scheme ref, bank_discretion, vs_rbi, section, title).
   Review status and notes are not policy changes and are ignored.
2. **Claude explains** each change in two lines (what changed; what staff do differently), from the old and new
   rule text only. Built with LangChain `ChatAnthropic.with_structured_output(..., method="json_schema")` -
   a Pydantic schema, native structured output, low effort.
3. **Verify, then ship**: the output must cover exactly the diff's rule IDs, and every number it writes must appear
   in that rule's old or new text. One retry; if it still fails, plain-text fallback ("read the annex").
Output: `docs/circulars/<old>_to_<new>.md` (table + annex with full new text) and a JSON report in eval/reports.

## Why LangChain here, when ADR-001 uses the SDK for answers
Answers need native citations (raw `search_result` blocks), which LangChain hides. The circular needs a typed object,
which is exactly what `with_structured_output` gives; it is also the pattern Project 1B's agent tools will use.

## Alternatives considered
- LLM writes the whole circular from both files: shorter code, but it can miss or invent a change - the failure
  that matters most here. Rejected.
- No LLM (diff + rule text only): always correct, but a 300-word rule tells staff nothing about what to do
  differently. Kept as the fallback.

## Limits
- The number check catches invented figures, not wrong meaning in words. A human reads the circular before issue.
- Cross-rule effects (e.g. DB-HL-030 deviations covering new rule DB-HL-032) are not detected.

## Update (24 Nov 2026): results and a human review step
- diff-v1: passed the automatic check but a reader found 2 meaning errors (DB-HL-002 relaxation written as a
  tightening; DB-HL-004's real effect, NPS -> age 70, left out).
- diff-v2 (required `direction` field, "who qualifies first"): fixed both of those, but labelled DB-HL-001
  "relaxed" when it adds conditions, and still left out age 70 on DB-HL-004.
- Decision: stop tuning the prompt; add a reviewer step. `docs/circulars/<name>.review.yaml` holds corrections
  (with reasons) and the reviewer's name. They pass the same checks as model output, are marked † in the circular,
  and the circular says "NOT YET REVIEWED - do not issue" until `reviewed_by` is set. `--from-report` re-renders a
  saved run with corrections, without a new API call. This matches how a bank issues circulars (maker-checker).
- Measured: 11 lines, 3 needed correction after v2 (27%); $0.0015 per run.
