# Progress

## Week 1 (23–29 Nov 2026)
Goals:
1. Thin slice works: Credit Facilities Directions 2025 parsed into versioned clauses, indexed in Qdrant via LangChain, answered by Claude with clause citations and a refusal path.
2. Evaluation and audit from day one: golden set v0 (10 questions) runs in one command; every query is logged with tokens, cost and latency.
3. Discovery started: at least 3 interviews booked, real questions logged in questions.csv.

Hours: ~10/10 (Step 0 + Sessions 1–5; estimate — replace with your logged time)

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

## Session 4 log (22 Nov 2026)
- app/generate.py: cited answers (search_result citations), exact refusal sentence, audit log per query (logs/audit.jsonl).
- Fix: Haiku 5.5 thinking used all 600 max_tokens on the first run (empty answer); raised to 2000.
- Smoke test: Rs 3 lakh gold loan -> 80%, cited paras 33 + 44; video KYC -> refused. ADR-002 (clause schema), ADR-003 (citation links).

## Session 5 log (22 Nov 2026)
- Streamlit UI (answer, cited paras with highlight + section links, RBI language-page note, time/cost/request id).
- Eval golden_v0 (10 questions: 8 answerable, 2 refusal) — report eval/reports/2026-11-22.json:
  - hit@5 8/8 · cited 8/8 · refusal 10/10 (automated)
  - Manual review: 7/8 substantively correct. g002 cited para 39 but said no tenure cap is stated (wrong); g005 correct but also cited gold-loan para 44. Logged in eval/reports/failures.md.
- Cost per question: avg $0.00059 (min $0.00029, max $0.00085); 10 questions = $0.0059.
- Time per question: avg 11.4 s, median 5.1 s, max 29.6 s; answered avg 13.7 s vs refused 1.9 s (thinking time).
- Qdrant DNS failures on phone hotspot (~1 in 5 lookups): added retry (4 attempts, 1–8 s backoff) in app/retrieve.py.
- Caveat: golden set is 10/10 draft-claude; scores optimistic. Do not quote 100% publicly.

## Week 2 carry-over
- Replace >=5 golden questions with real interview/own questions; add answer-correctness + citation-precision checks.
- Cut latency: compare accuracy vs time with lower/no thinking.
- Fix g002 pattern: add chapter/section to search-result titles; prompt to apply a clause within its chapter.
- Split para 4 definitions; strip amendment markers ("17 [").
- Interviews: >=3 booked (Week 1 done-list item still open).
- Demo video v1 (22 Nov 2026, 67 s, local only): answer + para 44/33 highlights + KYC refusal work. Answer hedged ("do not expressly confirm gold loan is a consumption loan") because para 4(viii) definition wasn't retrieved and chapter context isn't in the prompt. Re-record after Week 2 fixes.
## Fix round after demo v1 (22 Nov 2026) — prompt answer-v1
- Para 4 split into 45 definitions (e.g. 4(viii) Consumption Loan); chapter > section header embedded with each clause; search-result titles carry chapter/section; prompt answer-v1 (answer first, max one caveat); thinking effort low.
- Eval golden_v0 with answer-v1: hit@5 8/8 · cited 8/8 · refusal 10/10 · manual review 8/8 (v0 was 7/8). Avg 7.8 s (v0 11.4 s); $0.00645 for 10 questions.
- Reports: eval/reports/2026-11-22_answer-v0.json vs 2026-11-22_answer-v1.json.
- Still slow outliers: g001 17.7 s, g006 16.1 s, g009 13.3 s.

## Discovery round 1 + decision (22 Nov 2026)
- 7 interviews: H1 failed on frequency (3/7 costly incidents), H2 failed (0/7 mainly public docs), H3 failed as worded. 7/7 learn RBI changes via internal circulars; 7/7 can't use outside AI tools; 7/7 English.
- Decision: Option C (ADR-004) — fictional Demo Bank policy layer now; head-office user tested with 2–3 interviews.
