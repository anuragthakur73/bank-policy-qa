# ADR-013: /v1 retrieval API for Project 1B and Project 2

Date: 25 Nov 2026 · Status: accepted (Week 4 S4)

## Context
1A is the retrieval layer of the Loan Origination System (Project 2) and of the agentic loan-file pre-check (1B).
Until now the contract was a Python function (`app.retrieve.retrieve`); other projects need a network service with a
stable, documented schema. The RBI draft model-risk guidance (status: draft, see regulatory-status-log) proposes a
way to stop a model quickly - a kill switch.

## Decision
1. FastAPI app `app/api.py`, versioned path /v1: GET /v1/health, POST /v1/retrieve, POST /v1/answer.
   OpenAPI page at /docs is the contract document for 1B.
2. /v1/retrieve takes query, product?, as_on?, top_k, k_policy, sources; returns chunks with a stable id
   (RBI `doc_id:clause_no`; policy `doc_id:rule_id@policy_version`), source_type, product, policy_version/status,
   effective dates, rbi_scope, link, retrieval info, and each rule's RBI trace as chunk ids. Plus product_source,
   policy_status per product and the "not in force" notices. No Claude call.
3. One planning function `app/search.py` serves both the API and the answer path, so product (ADR-009), date
   (ADR-010), keyword slot (ADR-011) and RBI scope (ADR-012) rules cannot drift apart.
4. Kill switch: env KILL_SWITCH=1 or a file named KILL_SWITCH in the working folder (no restart needed; file is
   git-ignored). /v1/answer then returns mode "search_only": chunks, no model call, cost 0, and the switch use is
   audited. Retrieval keeps working - staff can still read the rules.
5. Contract rule unchanged: add fields, never rename or remove; a breaking change means /v2.
6. Pydantic validation: unknown product, top_k > 10, bad dates, empty or unknown sources -> 422.
7. Every API call is audited (endpoint, question, as_on, product, chunk ids returned). Tests replace the audit writer
   so test runs never write to logs/audit.jsonl.

## Alternatives considered
- Let 1B import the Python package: couples the projects' environments and release cycles; no audit at the boundary.
- One /answer endpoint only: 1B's agent needs raw rules and clauses to reason over, not prose.

## Not yet
Authentication, rate limits and deployment (Week 7 in the build plan); PII masking (S5).
