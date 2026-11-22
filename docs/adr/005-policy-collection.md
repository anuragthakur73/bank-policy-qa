# ADR-005: Demo Bank policy in its own collection, searched alongside RBI, with an RBI trace

Date: 23 Nov 2026 · Status: accepted

## Context
Option C (ADR-004) adds a fictional Demo Bank policy layer. Interviewees answer most questions from
their bank's policy, not RBI text, so answers must show the bank rule AND the RBI paragraph behind it.
The policy lives in `policy/demo_bank/home_loan_v1.yaml` (31 rules, format in `policy/schema.md`).

## Decision
1. **Separate collection** `policy_v1`, one point per rule, same embedding model as `clauses_v1`.
   Point ID = `uuid5(doc_id|rule_id|policy_version)`.
2. **Same field names** as RBI clauses (`doc_id`, `clause_no` = rule ID, `version_label`, `effective_from`, ...)
   plus policy-only fields (`rule_id`, `bank_discretion`, `vs_rbi`, `rbi_ref`, `params`, `review`, `synthetic`).
3. **Per-layer quotas**: `retrieve(q, layers=("policy","rbi"))` returns the top 3 rules, then the top 5 RBI clauses.
   Rows carry `layer`.
4. **Deterministic trace**: for each retrieved rule, its `rbi_ref` paragraphs are fetched from `clauses_v1` by
   number (keyword payload indexes on `metadata.doc_id` / `metadata.clause_no`), not by similarity.
   Status per paragraph: `found`, `not_found`, `not_indexed` (direction not in the corpus yet).
5. Contract v0 → **v0.1**: fields added only; default `layers=("rbi",)` keeps old callers unchanged.

## Why
- One collection per layer keeps RBI text and synthetic bank text physically apart: synthetic content can never
  be mistaken for regulation, and either layer can be rebuilt alone.
- Quotas instead of one merged ranking: a policy question should always surface the rule *and* the regulation;
  a single ranking lets one layer crowd out the other.
- Trace by number, not by search: "DB-HL-009 implements para 111" is a fact in the policy file. Fetching
  para 111 exactly is reliable and auditable; similarity could return para 112.

## Alternatives considered
1. One collection with a `layer` payload filter: fewer moving parts, but mixes synthetic and regulatory text and
   still needs two queries to guarantee both layers.
2. Let the LLM find the RBI paragraph: cheaper to build, but untestable and can cite the wrong paragraph.

## Consequences
- 13 rules cite RBI; only those citing the Credit Facilities Directions (`CF`) trace today. Rules citing the
  Responsible Business Conduct Directions (`RBC`: KFS, reset, penal, prepayment, document return, grievance)
  return `not_indexed` until RBC is parsed and indexed.
- Two vector searches per question (~2x embedding + search latency; embedding cost is negligible).
- Re-running `ingest.index_policy` recreates `policy_v1`: pass all policy files in one run.
