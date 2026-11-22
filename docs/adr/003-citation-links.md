# ADR-003: How citations link to RBI clauses

Date: 22 Nov 2026 · Status: accepted (revisit before public launch, Week 8)

## Decision
Each citation links to the RBI page with a text fragment (`#:~:text=<first words of the clause>`) that scrolls to
and highlights the clause. RBI's own section anchor (e.g. `#C4D`) is kept as a fallback link.

## Evidence (tested 22 Nov 2026)
- RBI pages have no per-paragraph anchors; they do have section anchors (`C<chapter><section>`).
- Text-fragment link to para 44 highlighted it; `#C4D` landed on section D's heading.
- First visit without RBI's language cookie redirects to the home-page language picker; the target is lost.
  After choosing English, links work. The UI shows a one-line note about this.

## Risk
RBI's website terms (checked 19 Nov 2026) say deep links need prior permission. Owner's decision: keep clause-level
links. Before the public URL goes live, decide whether to write to RBI for permission.

## Alternatives considered
1. Link to page top only: always works, but users must search the page.
2. Host our own copy of the text: best UX, but conflicts with RBI's "all rights reserved".
