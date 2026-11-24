# ADR-007: Hybrid (vector + keyword) search for RBI clauses

Date: 24 Nov 2026 · Status: SUPERSEDED 25 Nov 2026 - default back to vector (see Decision 25 Nov)

## Context
On golden_v1 (23 Nov) the eval reported that vector search put the expected RBI paragraph in its top 5 for only
7 of 14 questions, so keyword search was added for exact terms (LTV, KFS, penal charges, foreclosure).

## Correction (24 Nov, after the first run)
The 7/14 was an eval scoring bug, not weak search: hit@5 was scored after de-duplication, so a paragraph that
search found AND a rule trace had already added was not counted. `eval/compare_retrieval.py` (no de-duplication)
gave vector 14/14, hybrid 14/14, LangChain hybrid 14/14. Fixed in run_eval.py (scores `rbi_search`).
So on golden_v1, hybrid search has no measured retrieval benefit; the set is too easy to tell them apart.
Kept as default because it costs ~6 ms and no extra API calls, and exact-term matching matters for future
documents (KYC, PSL) and RBI-only questions. To prove or drop it: a harder RBI-only test set (Week 3 Session 5).

## Results with fixed scoring (24 Nov, 3 runs, golden_v1)
| | hybrid run 1 (bad connection) | hybrid run 2 | vector |
|---|---|---|---|
| hit@5 / in context | 14/14 / 14/14 | 14/14 / 14/14 | 14/14 / 14/14 |
| RBI cited | 13/14 (g005) | 13/14 (g008) | 14/14 |
| rule found / cited | 20/20 / 16/16 | 20/20 / 16/16 | 20/20 / 16/16 |
| answer ok / refusal ok | 12/12 / 29/29 | 12/12* / 29/29 | 12/12 / 29/29 |
| median latency | 13.4 s | 6.1 s | 6.3 s |
*p15 answered "three working days"; the scorer wanted "3 working days" (scorer fixed). On a good connection the two
modes perform the same; one citation miss per hybrid run on a different question each time is within what one
run can show (not tested for significance).

## Decision
- RBI search = vector shortlist (Qdrant, top 20) + BM25 keyword shortlist (rank_bm25, top 20), merged by
  reciprocal rank fusion (score = sum of 1/(60 + rank)), top 5 returned. Default mode `hybrid`.
- Keyword search runs in memory over the same text the vector index embeds (chapter > section header + clause).
  It loads `data/parsed/*.jsonl`, or scrolls Qdrant when that folder is absent (fresh clone, server).
- A small synonym list maps bank shorthand to RBI wording (LTV, KFS, EMI, foreclosure, title deeds).
- Policy-rule traces now look clauses up locally instead of one Qdrant call per paragraph.
- `/retrieve` contract v0.2: new `retrieval` field (mode, vector_rank, keyword_rank, fused); `mode` and
  `timings` arguments. Nothing renamed or removed; `mode="vector"` reproduces v0.1.
- The audit log records per-stage times (policy search, trace, RBI vector, RBI keyword, model) and retries
  (Qdrant via tenacity, Anthropic via the SDK's retry log line).

## Built twice (learning goal)
`app/retrieve_lc.py` builds the same thing from LangChain parts: `BM25Retriever` (langchain-community) +
Qdrant retriever → `EnsembleRetriever` (langchain-classic). Selected with `RETRIEVAL_MODE=hybrid_lc`.
`eval/compare_retrieval.py` checks the two give the same top 5. The hand-built version stays the default because:
1. `langchain-community` prints a notice that it is being sunset with limited maintenance (checked 24 Nov 2026);
   no replacement package for BM25Retriever is named.
2. The LangChain version returns no ranks or scores, which the audit log and eval need.
3. Its vector call bypasses our Qdrant retry wrapper.

## Alternatives considered
- Qdrant's built-in sparse vectors (BM25/SPLADE) with server-side fusion: one system, scales better, but
  needs re-indexing and a new collection. Revisit when the corpus grows past a few thousand clauses or for
  Project 2.
- A reranker (e.g. a cross-encoder) on the fused list: adds cost and latency; revisit if hit@5 stays below target.

## Consequences / risks
- The keyword index lives in each process's memory (~1,000 clauses: built in well under a second, my estimate;
  measured times are in the audit log). Re-indexing Qdrant without refreshing `data/parsed` would make the
  two indexes disagree.
- The KFS and title-deed synonyms were added after seeing the p15 and p13 misses, so those two questions
  no longer test keyword search blind. New synonyms come only from real staff questions.

## Decision 25 Nov 2026 (Anurag): default back to vector search
golden_v2 (51 Qs, incl. 8 RBI-only exact-term questions): hit@5 23/23 vector and hybrid (RBI-only 8/8 both); cited
21/23 vs 22/23 (one question, within run-to-run variation); same cost and latency. Hybrid adds a second index to keep
in sync and gives no measured benefit, so `RETRIEVAL_MODE` defaults to `vector`. Kept: app/keyword.py (also used for
local clause lookup in policy traces), `hybrid` and `hybrid_lc` modes, eval/compare_retrieval.py.
Revisit when the corpus grows (KYC, priority-sector directions) or real staff questions miss on exact terms.
