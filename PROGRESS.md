# Progress

## Week 1 (23–29 Nov 2026)
Goals:
1. Thin slice works: Credit Facilities Directions 2025 parsed into versioned clauses, indexed in Qdrant via LangChain, answered by Claude with clause citations and a refusal path.
2. Evaluation and audit from day one: golden set v0 (10 questions) runs in one command; every query is logged with tokens, cost and latency.
3. Discovery started: at least 3 interviews booked, real questions logged in questions.csv.

Hours: ~6.5/10 (Step 0 + Sessions 1–3; estimate, correct if needed)

## Session 2 log (22 Nov 2026)
- Saved Credit Facilities Directions 2025 (updated as on 1 Oct 2026). First save was the Master Directions list page by mistake; re-saved.
- Parser: 536 paragraphs (472 live, 64 omitted "*****"), no gaps 1–454, no duplicate numbers. Chapter, section and RBI section anchor captured per paragraph.
- Fixes found by checking: para 4 starts with a bare "4."; "F.3 Heading 303. text" merged on one line; section headings were leaking into the previous paragraph.
- Anchors: no per-paragraph anchors. RBI has section anchors (e.g. #C4D = Chapter IV, section D, which holds para 44).
- Link test (22 Nov, built-in browser): text-fragment link scrolls to and highlights para 44 — WORKS. Section anchor #C4D lands on section D heading — WORKS (fallback).
- Caveat: on a first visit with no RBI language cookie, rbi.org.in redirects to its home page language picker and the link target is lost; after choosing English the same link works. Handle in UI (note under the link) in Session 4/5.
- Week 2 to-do: para 4 (definitions) is 15,360 chars — split by sub-clause; amendment footnote markers like "17 [" / "1 [" in text — strip, and use them for version history.

## Session 3 log (22 Nov 2026)
- Session 3: indexed 472 clauses; retrieval smoke test 3/3
