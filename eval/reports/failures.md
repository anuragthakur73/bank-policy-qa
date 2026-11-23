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
