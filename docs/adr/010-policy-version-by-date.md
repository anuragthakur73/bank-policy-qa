# ADR-010: Answer from the Demo Bank policy version in force on an "as on" date

Date: 25 Nov 2026 · Status: accepted (Week 4 S2)

## Context
Only the latest policy files were indexed (home loan v1.1, effective 1 Jan 2027; LAP v1.0, effective 1 Jan 2027),
so a question asked in November or December 2026 was answered from rules not yet in force. Home loan v1.0 (approved,
effective 1 Dec 2026) was not searchable at all. Discovery round 1 (ADR-004): staff pain is "what changed and did
everyone hear", and a costly incident was an LTV change that was not followed.

## Decision
1. Every version of every product is indexed side by side (85 rules: home loan v1.0 31 + v1.1 34, LAP v1.0 20).
   `app/policy_versions.py` reads all policy files; a version runs from its effective_from to the day before the
   next version of the same product starts; the latest is open-ended. Two versions may not share a start date.
2. Payload gets policy_version, policy_status, effective_to, and integer effective_from_n / effective_to_n
   (yyyymmdd) with integer payload indexes. Policy search filters product AND effective_from_n <= as_on <=
   effective_to_n before ranking.
3. `answer(..., as_on=None)` defaults to today. Products with no version in force on that date are dropped from the
   policy search; if none remain, the policy layer is skipped.
4. **Before a product's first version starts (Anurag, 25 Nov 2026, option a):** the answer opens with
   "Demo Bank's <product> policy is not in force on <date> (... takes effect on <date>), so its rules are not used
   below" and comes from RBI only. Rejected (b): answering from the upcoming version with a warning - a branch cannot
   apply a policy before its start date.
5. If a cited rule changes or is withdrawn in the next version, a line is appended: "Note: DB-HL-004 is due to change
   on 1 Jan 2027 (policy v1.1.0, draft); see the staff circular." Draft versions are worded "is due to".
6. Notices are written by code from the policy files, not by the model: deterministic, testable, auditable.
   Refusal is judged on the model's text before notices are added.
7. Contract v0.3 -> v0.4: `retrieve(..., as_on=None)`; rows gain policy_version, policy_status. as_on=None searches
   all versions (diagnostics only). Audit adds as_on, policy_status, cited_rule_versions, notices.
8. Eval/spot checks default AS_ON=2027-01-01 (golden_v2 was written against home loan v1.1 + LAP v1.0);
   `eval/date_check.py` asks the same questions on different dates.

## Alternatives considered
- Index only the version in force and re-index on each effective date: simpler search, but "as on" questions about
  another date become impossible and a missed re-index silently serves the wrong rules.
- Let the model read effective dates from the result titles and decide: not deterministic; the conflict check
  (ADR-006) already showed judgment calls vary run to run.
- Qdrant datetime range on ISO strings: works, but integer yyyymmdd keeps the filter simple and portable.

## Consequences
- Draft versions are searchable from their planned date. For a real bank, only approved versions should be indexed;
  here v1.1 and LAP v1.0 stay draft until Anurag's sign-off, and the notices say "draft".
- The Streamlit screen uses today's date until the S5 date picker, so today it answers from RBI only (correct).
- RBI clauses are not yet date-filtered (one version of each direction is indexed).
