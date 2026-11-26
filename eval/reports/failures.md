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

## 24 Nov 2026 · Week 3 Session 3 · change circular diff-v1 (Haiku 5.5, $0.0012, passed the automatic check first try)
- Automatic check passed (11/11 rule IDs, no invented figures), but a human read found 2 meaning errors:
  DB-HL-002 written as a tightening ("now financed only if regularised") when it is a relaxation (v1.0 banned
  unauthorised colonies outright); DB-HL-004 said "pension-earning is now defined" and left out the real change
  (every NPS subscriber can now repay to age 70). Minor: DB-HL-034 dropped "self-occupation".
- Lesson: number and ID checks can't catch the direction of a change. diff-v2 adds a required `direction` field
  (new / relaxed / tightened / clarified / withdrawn), a "who qualifies first" instruction, and a direction check
  for new and withdrawn rules. A human still reads every circular before issue.

## 24 Nov 2026 · Week 3 Session 4 · LAP v1.0 conflict check + spot checks
- DB-LAP-011 flagged looser (2/3): tenure extension capped by max tenure/age, which RBC 349(3) does not set (only
  349(5) no negative amortisation). DB-HL-014 has the same cap and passed 3/3 -> the check is inconsistent on this
  wording. Fix (Anurag): keep the cap, state the higher-EMI fallback, state no fixed-rate switch, label equal; same
  fallback added to DB-HL-014 (v1.1 now changes 12 rules). Fixed-rate switch is optional (349(2) "may, at its
  option"), not a gap.
- Shared policy index: i04 (home-loan NPS age) also cited DB-LAP-003. Need a product filter on policy retrieval
  (UI selector or product detected from the question) -> Week 4.
- Spot checks: LAP 3/3, home loan still 5/5 after adding 20 LAP rules.

## 25 Nov 2026 · Week 3 Session 5 · golden_v2 (51 Qs), answer-v2, hybrid vs vector
- WRONG ANSWER (both modes): l01 "max LTV on a loan against a self-occupied flat, Rs 80 lakh" answered 75% from the
  HOME-LOAN rule DB-HL-009; correct is 65% (DB-LAP-007). Scored answer_ok only because "65" appears later in the
  text -> must_contain is too weak for headline figures. Root cause: one shared policy index, no product filter.
- product_ok 23/30 in both modes: 7 answers also cite a rule of the other product (p07, p10, p12, p13, i04, l01, l08).
  The 2 cross-product questions that name the product passed.
- l07 (LAP as overdraft) refused: DB-LAP-009 not in the policy top 3 (54 rules now compete for 3 slots).
- Hybrid vs vector: hit@5 23/23 both (RBI-only 8/8 both); cited 22/23 vs 21/23; same cost ($0.050) and latency
  (~6 s). No measurable retrieval benefit from hybrid, even on exact-term RBI-only questions (which I wrote after
  reading the paragraphs - biased towards keyword search, yet vector found them all too).
- r04 cited para 108 instead of 109 (both relevant); r01 (vector run) cited the LAP rule, not RBI para 36.

## 25 Nov 2026 - Week 4 S1 product filter (answer-v3)
- Fixed: product_ok 23/30 -> 30/30 with product given; l01 now 65% (headline_ok 9/9).
- l07 (overdraft on LAP): still refused. Not crowding any more: LAP-only top 3 is DB-LAP-001/017/016. Vocabulary gap -
  DB-LAP-009 never says "overdraft". Options: state "not available as an overdraft or cash credit" in the rule
  (policy edit, needs Anurag), or raise k_policy when one product is searched.
- p09: answer says "implements RBI paragraphs 352 and 353" but cites only DB-HL-017 (2/2 runs under answer-v3;
  v2 cited both paras). A mentioned-but-uncited paragraph should fail the S3 citation validator.
- Scoring bug found: refused = "REFUSAL in text" counted labelled per-product answers with one "Not covered" part as
  refusals (p08, p11, p14 in text mode). Fixed: refused = whole answer; partly_refused logged.

## 25 Nov 2026 - Week 4 S2b keyword slot (ADR-011)
- l07 fixed: DB-LAP-009 was 8th of 20 by vector search; BM25 ranks it 1st; added as a 4th rule.
- Open: d4 (LAP question on 15 Dec 2026, LAP not in force) cites RBI para 111 (housing-loan LTV) in 2/2 runs.
  Para 111 does not apply to LAP; answer text was not logged, so unknown whether the answer misapplied it.
  Audit now logs the answer.
- Noise: keyword slot adds weak matches (DB-HL-001, DB-LAP-001) on RBI-only questions.
- d4 confirmed WRONG (logged answer): "Rs 80 lakh is capped at 75% LTV" for a LAP, from CF para 111. Fix: ADR-012.
- d4 fixed by ADR-012 (25 Nov 23:01). New pattern: answer names an RBI para in text but does not cite it (p09, g005) -> S3 check.

## 26 Nov 2026 - Week 4 S3 validator, first run (enforce)
- 47 pass, 3 passed after retry (p01, i06, r06: rule/para named but not cited -> cited on retry), 1 refused (r04).
- r04 root cause (old, since Week 3): CF 108 and 109 start with the same 8 words, so their text-fragment links are
  identical; citations were mapped back by link, so the model's citation of 109 was recorded as 108. The validator
  caught it (quote not in 108). Fix: map citations by search_result_index. 12 link groups are shared across the
  1,039 RBI clauses (incl. the deleted "*****" paras).
- STILL OPEN: the shared LINK itself - clicking a 109 citation highlights para 108 on the RBI page. Needs a longer or
  start,end text fragment and a link check against rbi.org.in (ingest/check_links.py) - not done offline.
- headline_ok false alarm on p06: answer restated "Rs 80,000" from the question before "55%". Scorer now skips
  figures that appear in the question.
- figure warnings: 3 answers, all worked-out figures (p01 44 / 72.7, p04 20): correct answers. Keeps the check warn-only.
- Run 2 (00:23): r04 now cites 109 (mapping fix works). p02 refused after retry: correct answer named para 113 (the
  para DB-HL-010 implements) without citing it, twice -> check relaxed to warn for paras implemented by a cited rule.
  g010: refusal followed by extra remarks was not counted as a refusal -> is_refusal = starts with the refusal.
- Run 3 (00:38): clean on refusals (51/51). g001 answered "80%" with ZERO citations - wrote <span index="10-1"> markup
  into the text. New blocking checks no_citations / citation_markup_in_text; first live check in the next eval.

## 26 Nov 2026 - Week 4 S5, golden_v2_1 (60 Qs)
- v01 headline_ok false alarm: first figure came from the "not in force" notice -> scorer skips notices.
- v09 refusal: not a defect. v1.0 DB-HL-003 does not settle whether an HUF is an "individual"; RBI CF 219E treats HUFs
  as individuals in its own context. Moved to manual review. Shows why v1.1 states the exclusion.
