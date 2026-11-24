# Failure log

One line per failed question. Stage: parsing (clause text wrong), retrieval (right clause not in top 5),
generation (right clause retrieved but answer/citation wrong), refusal (refused when it shouldn't, or vice versa).

| Date | Question id | Stage | What happened | Fix idea |
| --- | --- | --- | --- | --- |
| 2026-11-22 | g002 | generation | Retrieved and cited para 39, but answered "the indexed documents do not state a maximum tenure for a bullet repayment gold loan" — para 39 sits in Chapter IV (gold/silver collateral), so the 12-month cap does apply. Scored as a pass by cited_ok; wrong on substance. | Put chapter/section in each search result's title; prompt: apply a clause to the chapter it sits in; add an answer-correctness check to the eval |
| 2026-11-22 | g005 | generation (minor) | Correct 80%, but also cited para 44 (gold-loan LTV) for a home-loan question. | Penalise irrelevant citations in the eval (citation precision); reranker in Week 3 |
| 2026-11-22 | all | eval design | Golden set v0 is 10/10 "draft-claude", written while looking at the clause text, so wording overlaps the source. Scores are optimistic. | Replace ≥5 with interview/own questions in Week 2 |
| 2026-11-22 | g002, g005 | FIXED (answer-v1) | After splitting para 4 definitions, adding chapter/section context and the answer-first prompt: g002 now says 12 months (para 39, Chapter IV); g005 cites only para 111. Manual review 8/8. | — |

## 23 Nov 2026 · answer-v2 · g005 (hit@5 miss, answer correct)
- Q: Rs 50 lakh individual home loan, max LTV. RBI top 5 = paras 44, 219G, 45, 112 (Credit Facilities) + 1 RBC clause; para 111 missing.
- Answer correct (80%) and cites para 111, which arrived through DB-HL-009's trace, not search.
- Regression vs answer-v1 for RBI-only callers: adding the RBC directions (458 clauses) took a top-5 slot, and gold-loan LTV paras outrank housing para 111.
- Week 3 fix candidates: hybrid keyword + vector search; "housing finance" terms in the contextual header; per-document quota.

## 23 Nov 2026 · answer-v2 · golden_v1 (33 Qs)
- RBI search alone weak on housing/conduct paras: hit@5 7/14 (misses g005, p01, p02, p09, p10, p13, p15); traces cover it (in_context 14/14, cited 14/14). Week 3: hybrid keyword + vector search.
- i07 (partnership firm as applicant): right conclusion but hedged; DB-HL-003 (individuals only) not retrieved, cited DB-HL-006. Fix in policy v1.1 (backlog #5) + retrieval.
- Latency 12.1 s avg (median 8.1 s); four ~31-32 s outliers (p13, p15, i07, p14). Cause not measured (suspect retry/stall). Week 3: per-stage timing in the audit log.

## 24 Nov 2026 · Week 3 Session 1 · hybrid search, answer-v2, golden_v1
- EVAL BUG (fixed): hit@5 was scored after de-duplicating searched paras against traced paras, so 23 Nov "7/14"
  was understated. Raw search (eval/compare_retrieval.py): vector 14/14, hybrid 14/14, hybrid_lc 14/14 (identical top 5).
- Citation misses, context was correct: g005 and p01 did not cite para 111 (traced, in context); p13 mentioned
  DB-HL-028 in plain text instead of a native citation. Run-to-run variation or a context-order effect: rerun to tell.
- Latency 8.6 s avg (median 7.0 s), was 12.1 s. Four ~12.3 s stalls (i01, i02, p15, p17) inside vector-search
  stages, no Qdrant/Anthropic retries logged. Embedding and Qdrant were timed together; now split (embed_ms) and
  OpenAI retries counted. Question now embedded once per query (was twice, ~2 s).
- Answer shape: i04 and i06 now give closest rules after saying not covered (i06 starts with the refusal line).

## 24 Nov 2026 · reruns with fixed scoring (2x hybrid, 1x vector)
- Stalls explained: Qdrant Cloud calls on a poor connection (run 1: 16/33 questions had a Qdrant stage >10 s, in ~12 s
  steps, max 24 s; 5 Qdrant retries). OpenAI embedding max 2.4 s, model max 8 s. Good-connection runs: no stage >3.1 s.
  Not a code problem. Options (not done): lower Qdrant timeout + retry to fail fast; local Qdrant for dev/demo.
- Model is now the main cost of time: ~4.3 s of ~6 s median.
- Citation misses vary by run: g005 (run 1, para 111 named in text, not cited), g008 (run 2, cited 36 and 4(xxxvi), not 35).
  Vector run: none. One miss per run on a different question -> treat as model variation; watch in Session 5.
- p15 false failure: "three working days" vs must_contain "3 working days". Scorer now accepts "a|b" alternatives.
- 2026-11-24_answer-v2_hybrid_golden_v1.json (no time in name) = first run with the OLD hit@5 scoring; kept for the record.

## 24 Nov 2026 · Week 3 Session 2 · policy v1.1 conflict check (conflict-v3, 3 runs)
- 15/15 RBI-bound rules pass, fixtures 5/5, $0.029. Unstable votes: DB-HL-034 (1 of 3 "looser": the model read
  "takeover required instead of a second charge" as departing from para 94; declining an RBI permission is stricter,
  so the 2 "complies" votes are right); DB-HL-032 (1 of 3 "unclear"). Watch on the next run.
- Coverage list noise: for DB-HL-033/034 it lists CF 92 sanctioned-plan duties that the rules cover by referring to
  DB-HL-020. Cross-references are invisible to a one-rule-at-a-time check -> possible check improvement: include the
  referenced rules' text. Not blocking.
