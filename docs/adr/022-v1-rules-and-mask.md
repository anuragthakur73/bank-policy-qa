# ADR-022: `/v1` additions for Project 1B: rules by ID and date, params on chunks, masking

Date: 29 Nov 2026 · Status: accepted (Week 7 S2) · Contract v0.6 -> v0.7 (additive only, ADR-013)

## Context
Project 1B (loan-file pre-check) checks a file with code, not with the model, for every rule that has `params`
(design v0.3, section 4). For that it needs, from 1A:
1. The exact rule in force on the file's date, by rule ID: e.g. DB-HL-030 (deviations). Loan file F11 (tenure 31
   years) is "Not Eligible" on 15 Dec 2026, when v1.0.0 allows no tenure deviation, and "Eligible – Deviation
   Approval Required" on 15 Jan 2027, when v1.1.0 allows up to 2 years. A search can rank the wrong version or miss
   the rule; a code check must never depend on ranking.
2. The rule's machine-readable values (`params`), section and bank-discretion flag.
3. Masking for the officer's free-text notes before any model call (1B never sees a model without masking).

Found while building: `bank_discretion` and `section` were already on `/v1` chunks, but for policy chunks `section`
holds the rule title and `chapter` the policy section (same field names as RBI clauses, ADR-013). The search index
also still holds DB-HL-030 as it was before Anurag's 28 Nov change, until it is re-indexed (Week 7 S3).

## Options for "rule by ID and date"
| Option | Gives the version in force? | Current with the file? | Chosen |
|---|---|---|---|
| `/v1/retrieve` with the rule ID as the query | Only if it ranks first | No: index lags the file | No |
| Qdrant lookup by rule ID + date filter | Yes | No: index lags the file | No |
| **Read the policy YAML files (the registry ADR-010 already uses)** | **Yes, by the same date logic** | **Yes** | **Yes** |

## Decision
1. `GET /v1/rules?product=&as_on=&section=` - every rule of the version in force on the date, in file order.
   No version in force: 200, empty list, a notice ("not in force on 15 Dec 2026 (v1.0.0, draft, starts 1 Jan
   2027)") - 1B then checks on RBI only, as the answer path does (ADR-010).
2. `GET /v1/rules/{rule_id}?as_on=` - one rule; the product comes from the ID prefix, the version from the date.
   404 with a plain reason: no version in force, or the rule is not in that version ("... (it is in v1.1.0)").
   IDs must match `DB-(HL|LAP|VL)-nnn` (422 otherwise). `as_on` defaults to today.
3. Rules come from `app/rules.py`, which reads `policy/demo_bank/*.yaml` through `app/policy_versions` - never search,
   no network, no model. Each rule has the same `id` as its `/v1/retrieve` chunk (`doc_id:rule_id@version`),
   `params` (dates as ISO strings), `section`, `title`, `bank_discretion`, `vs_rbi`, `rbi_ref`, status, effective
   dates, link and `content_hash` (sha256 of the text, computed as `ingest/index_policy.py` does).
4. `/v1/retrieve` chunks gain `rule_section` (policy section), `params` (as indexed) and `content_hash`. Old fields
   keep their meaning: nothing renamed, nothing removed. For code checks, 1B uses `/v1/rules`, not chunk params.
5. `POST /v1/mask {text}` -> `{masked, entities}` with ADR-015 + ADR-021 masking. Fails closed: if masking cannot
   run (e.g. spaCy model missing), 503 and no text. The audit log keeps entity types and length, never the text.
6. Every call is audited (endpoint, rule or product, as_on, version returned). `CONTRACT_VERSION` = v0.7.
7. `eval/api_smoke.py` (live, Windows): 3 new checks and an index-freshness report listing rules whose indexed text
   or params differ from the files - the signal to re-index.

## Consequences
- 1B's code checks get the rule in force by date with one call per product; F11's two dates return DB-HL-030
  v1.0.0 and v1.1.0 with different `allowed` (test `test_f11_two_dates_two_versions_of_db_hl_030`).
- Two sources for a rule now exist: the file (`/v1/rules`) and the index (`/v1/retrieve`). They agree after a
  re-index; `content_hash` and the smoke report show when they don't. Judgement checks via `/v1/answer` still use
  the index, so a stale index can still affect an answer until S3 re-indexes.
- `content_hash` covers the text only; a params-only change shows in the smoke report (it compares params) but not
  in the hash.
- Draft versions (home loan v1.1, LAP, car) are returned with `policy_status: draft`, as the answer path does.
- Not yet: authentication and rate limits (no deployment yet); RBI clause lookup by number (`rbi_ref` is returned
  as written; 1B links to it).

Tests: `tests/test_api_rules.py` (19, offline; search is made to fail if called).
