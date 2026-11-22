# ADR-002: Clause schema carries version fields from day one

Date: 22 Nov 2026 · Status: accepted

## Decision
Every indexed clause stores: `doc_id`, `clause_no`, `chapter`, `section`, `section_anchor`, `version_label`,
`version_as_on`, `effective_from`, `effective_to` (null = in force), `applies_to`, `source_url`, `content_hash`, `omitted`.
Point IDs are `uuid5(doc_id|clause_no|version_as_on)`.

## Why
- Our primary edge is "the rule as on a given date" for frontline lending staff. That needs version metadata on
  every clause; adding it later means re-parsing and re-indexing everything.
- RBI consolidated ~9,000 circulars into Master Directions on 28 Nov 2025 and keeps amending them
  ("updated as on" dates, "Previous Versions" pages), so more versions will arrive.
- `content_hash` lets us detect which clauses changed between two versions.
- Deterministic IDs make re-indexing idempotent and let two versions of one clause live side by side.

## Alternatives considered
1. Text + URL only: simplest, but blocks date-aware answers and version diffing.
2. One collection per version: easy to filter, but cross-version questions ("what changed?") get harder.

## Consequences
- Slightly larger payloads (cheap). Filters on `effective_from`/`effective_to` come in Week 3–4.
- Amendment markers in the text (e.g. "17 [") are a future signal for clause-level effective dates.
