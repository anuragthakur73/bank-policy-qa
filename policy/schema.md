# Demo Bank policy format (v1)

Demo Bank is a **fictional** bank. Its policies are synthetic. They were designed from
two public comparative studies (SBI and ICICI Bank home-loan pages, Nov 2026) and the RBI
Master Directions. Nothing comes from any bank's internal circulars, including Union Bank
of India's.

One YAML file per product, e.g. `policy/demo_bank/home_loan_v1.yaml`.

## File header

| Field | Type | Meaning |
|---|---|---|
| `bank` | string | Always `Demo Bank (fictional)` |
| `product` | string | `home_loan`, `lap`, `vehicle_loan`, `education_loan` |
| `policy_version` | string | Semantic version, e.g. `1.0.0` |
| `effective_from` | date | Date the version applies from (used for as-on-date answers) |
| `status` | enum | `draft` \| `approved` \| `superseded` |
| `synthetic` | bool | Must be `true` |
| `rbi_corpus_version` | map | Version ("updated as on") of each RBI direction cited |
| `design_basis` | list | Studies used to design the rules (study IDs, not copied text) |
| `rules` | list | The rules (below) |

## Rule fields

| Field | Required | Meaning |
|---|---|---|
| `rule_id` | yes | Stable ID, `DB-HL-001`. Never reused after deletion. |
| `section` | yes | Grouping: `eligibility`, `amount_ltv`, `pricing`, `charges`, `property`, `process`, `governance` |
| `title` | yes | Short name |
| `rule` | yes | Plain-English rule text. This is what gets embedded and cited. |
| `params` | no | Machine-readable values (numbers, bands, lists) for checks and agents (1B / Project 2) |
| `rbi_ref` | conditional | `{direction, para, note}`. Required when `bank_discretion: false` |
| `bank_discretion` | yes | `true` when no RBI rule fixes this parameter |
| `vs_rbi` | conditional | `equal` \| `stricter` \| `not_applicable`. The conflict check flags anything else, e.g. a rule `looser` than RBI |
| `design_basis` | yes | Study source IDs that informed the value, plus `synthetic` where the value is invented |
| `review` | yes | `needs_review` (synthetic value an experienced banker should sanity-check) or `ok` |
| `review_note` | no | One line on what the reviewer decided and why (kept / changed what) |

## Rules for writing rules

1. Where RBI fixes a limit, Demo Bank must be **equal or stricter**, never looser.
2. Every `bank_discretion: true` rule that has no published basis in either study is
   tagged `design_basis: [synthetic]` and `review: needs_review`.
3. Rule text must be self-contained: one rule answers one question without needing
   another rule's text.
4. Changing a rule = a new `policy_version` with a new `effective_from`. The old file stays
   (for "what changed" and as-on-date answers).
