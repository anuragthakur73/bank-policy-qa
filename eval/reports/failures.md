# Failure log

One line per failed question. Stage: parsing (clause text wrong), retrieval (right clause not in top 5),
generation (right clause retrieved but answer/citation wrong), refusal (refused when it shouldn't, or vice versa).

| Date | Question id | Stage | What happened | Fix idea |
| --- | --- | --- | --- | --- |
| 2026-11-22 | g002 | generation | Retrieved and cited para 39, but answered "the indexed documents do not state a maximum tenure for a bullet repayment gold loan" — para 39 sits in Chapter IV (gold/silver collateral), so the 12-month cap does apply. Scored as a pass by cited_ok; wrong on substance. | Put chapter/section in each search result's title; prompt: apply a clause to the chapter it sits in; add an answer-correctness check to the eval |
| 2026-11-22 | g005 | generation (minor) | Correct 80%, but also cited para 44 (gold-loan LTV) for a home-loan question. | Penalise irrelevant citations in the eval (citation precision); reranker in Week 3 |
| 2026-11-22 | all | eval design | Golden set v0 is 10/10 "draft-claude", written while looking at the clause text, so wording overlaps the source. Scores are optimistic. | Replace ≥5 with interview/own questions in Week 2 |
