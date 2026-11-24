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

## Week 2 · Session 3: Demo Bank policy layer indexed (23 Nov 2026)
- Policy: policy/demo_bank/home_loan_v1.yaml, 31 rules (13 RBI-bound, 18 bank discretion), format policy/schema.md; designed from public SBI + ICICI studies; reviewed 30/31 (DB-HL-019 deposit amount pending).
- ingest/index_policy.py -> Qdrant policy_v1 (31 points) + keyword payload indexes on clauses_v1 (doc_id, clause_no).
- app/retrieve.py contract v0.1: layers=("policy","rbi"), top 3 rules + top 5 RBI clauses; each rule traced to its RBI para by number (found / not_found / not_indexed). Default call unchanged. ADR-005.
- Results: pytest 9 passed; RBI smoke 3/3 (same top 5 as before); policy smoke 5/5 incl. Rs 50 lakh LTV -> DB-HL-009 + para 111 found.
- Gap: rules citing RBC Directions (KFS, reset, penal, prepayment, document return, grievance) trace as not_indexed until RBC is parsed and indexed.

## Week 2 · Session 4: cited two-layer answers + bank-vs-RBI conflict check (23 Nov 2026)
- Corpus: added RBI (Commercial Banks – Responsible Business Conduct) Directions, 2025, updated as on 1 Oct 2026 (458 clauses). clauses_v1 now 975 clauses from 2 directions; ingest/index.py rebuilds the payload indexes after recreate.
- Trace: RBC paragraphs now resolve (prepayment 352/353, KFS 348, reset 349, penal 351, documents 354–359, grievance 346). PMAY rule uses scheme_ref (government scheme, not RBI) and is out of conflict scope.
- Answers: prompt answer-v2 — Demo Bank rule first (rule ID), then the RBI para it implements, or "bank discretion"; traced paras always in context; audit log records cited_rules and cited_rbi. Streamlit shows Demo Bank vs RBI sources separately.
- Eval golden_v0 (answer-v2, stricter scoring: hit@5 = top 5 RBI search hits only, matched by doc_id): hit@5 7/8 · in_context 8/8 · cited 8/8 · refusal 10/10 · $0.0088 · 6.3 s avg. Miss g005: para 111 pushed out of RBI top 5 after RBC was added; answer still correct via DB-HL-009 trace. Logged in failures.md (Week 3: hybrid search).
- Conflict check (app/conflict.py, ADR-006), iterated on evidence:
  - v1 run 1: flagged 3 real gaps in the draft (DB-HL-014, 025, 028 missing RBI borrower notices) → rules fixed; run 2 12/12 pass, but equal-vs-stricter verdicts flipped between runs.
  - v2: binary complies/looser, 3 runs, majority vote. Flagged further unstated details, a different one each run (and twice misread the rule).
  - v3: blocking verdict = contradiction only (silence complies) + non-blocking coverage list merged over runs. Result: fixtures 5/5, unstable 0, 11/12 pass; DB-HL-014 looser 3/3 — genuine: its wording allowed prepayment only at a reset vs RBC 349(3)(ii) "at any point". Wording fixed; re-run: 12/12 pass, fixtures 5/5, one split vote (DB-HL-009 complies 2 : looser 1, passes on majority). Coverage list: 116 unstated RBI items across 11 rules, not acted on (policy frozen for Week 2).
- Policy: 31/31 reviewed (DB-HL-019 deposit Rs 2,500 confirmed). Labels DB-HL-001/002/020 corrected to stricter. Frozen for Week 2 after the DB-HL-014 wording fix.
- Tests: 15 offline (policy file, para parser, verdict parser, RBC parse). Reports kept per run in eval/reports (v1 before/after, v2, v3, answer-v2 old/new scoring).
- Interview takeaway: the checker caught real compliance gaps in a policy I drafted, and its own instability showed why "contradiction" and "coverage" must be separate checks.

## Week 2 · Session 5: golden_v1 with real interview questions (23 Nov 2026)
- golden_v1: 33 questions = 10 RBI (v0) + 16 Demo Bank policy (drafted) + 7 verbatim interview questions (I01–I07). Questions also logged in notes/interviews/questions.csv (private).
- Eval adds rule_hit, rule_cited, answer_ok (key figures), manual review for policy-gap questions, and a separate interview score line.
- Results (answer-v2): hit@5 7/14 · in_context 14/14 · cited 14/14 · rule_hit 20/20 · rule_cited 16/16 · answer_ok 12/12 · refusal 29/29 · $0.032 · 12.1 s avg.
- Interview questions: I01 stamp duty + I03 education loan refused correctly; I07 (firm as applicant) right but hedged, wrong rule cited; I02, I04, I05 honest refusals on policy gaps; I06 careful partial answer. Manual verdicts (Anurag): all 4 acceptable. Nothing invented.
- Policy v1.1 backlog started: policy/demo_bank/backlog_v1_1.md (composite-loan LTV, NPS pension, floor purchase, second house on charged land, firms as applicants, coverage list).
- Demo video v2 script: docs/demo/demo_v2_script.md. LinkedIn post drafted.
- Week 3 carry-over: hybrid search; per-stage latency; policy v1.1; LAP / vehicle / education policies; head-office interviews (I08–I10) for Option A.

## Week 3 · Session 1: hybrid search + stage timing (24 Nov 2026)
- Built: BM25 keyword search (app/keyword.py, rank_bm25) fused with vector search by reciprocal rank fusion (default
  RETRIEVAL_MODE=hybrid); same thing with LangChain BM25Retriever + EnsembleRetriever (app/retrieve_lc.py) - identical
  top 5 on 14/14. /retrieve contract v0.2 (new "retrieval" field, mode + timings args). ADR-007.
- Audit log: per-stage ms (embed, policy search, trace, RBI vector, RBI keyword, model), retries (OpenAI, Qdrant,
  Anthropic), RBI search order before de-duplication. Question embedded once (was twice). Rule traces read clauses locally.
- Found and fixed an eval bug: Week 2 "hit@5 7/14" was a scoring error; vector search was already 14/14.
  So hybrid has no measured benefit on golden_v1 - kept provisionally (cheap), to be tested on harder RBI-only questions.
- Results (fixed scoring, good connection): hybrid and vector both hit@5 14/14, rules 20/20 found, 16/16 cited,
  answers 12/12, refusals 29/29, RBI cited 13-14/14, ~$0.031, median ~6 s.
- 30-40 s answers explained: Qdrant Cloud over a poor connection (~12 s steps). Not code.
- Interview verdicts (24 Nov): i02, i05 refused; i04, i06 give nearest rules after "not covered" - all accepted.
- Tests: 19 (4 new). pytest.ini added, so plain `pytest -q` works.
- Lesson: check the measuring tool before acting on a number - a second script scoring the same thing exposed the bug.
