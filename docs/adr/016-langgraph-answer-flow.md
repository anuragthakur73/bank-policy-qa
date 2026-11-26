# ADR-016: Run the answer flow as a LangGraph graph

Date: 27 Nov 2026 · Status: accepted 27 Nov 2026 (Week 5 S3) - default PIPELINE=graph; plain kept one release for rollback

## Context
The answer flow already had branches and a loop written as if/else in `app/generate.py`: kill switch -> search only
(ADR-013); validate -> retry once -> refuse (ADR-014); product not in force -> notice (ADR-010). Week 5 S4 adds
another branch (ask a clarifying question when the product or date is missing). Anurag wants hands-on LangGraph.
Project 1B (agentic loan classification) will be multi-step and will call /v1, so 1A should not become that agent.

## Decision
1. `app/graph.py`: a StateGraph with nodes mask -> route -> retrieve -> generate -> validate -> finish, a
   conditional edge validate -> generate (one retry with the problems listed) or -> refuse, and a conditional edge
   after mask -> search_only when the kill switch is on (`app/killswitch.py`, shared with the API and the screen).
2. Nodes call the SAME functions as the plain flow (`_prepare`, `_ask`, `validate`, `_finish` in app/generate.py).
   The graph adds no model calls and no prompts. `route` only records products and in-force versions for the
   trace; the search applies them exactly as before, so retrieval cannot drift.
3. The audit record gains `pipeline` (plain | graph), `graph_trace` (the steps that ran, e.g. generate twice on a
   retry) and `graph_route`. Fields are only added (contract rule).
4. `PIPELINE=graph` selects the graph; the plain flow stays behind `PIPELINE=plain` until the comparison passes,
   then the default flips and plain stays one release for rollback.
5. No checkpointer / memory: each question is independent (one-question service). LangGraph state holds one request.

## Done when
golden_v2_2 run on both flows: retrieval identical per question; model-scored metrics within +-2; api_smoke 4/4;
offline tests pass (tests/test_graph.py runs both flows on the same faked search, model and validator and requires
identical answers, citations, validation records and model calls for pass / warn / retry / refuse / log / kill switch).

## Trade-off
A dependency (langgraph 1.2.24 + 4 packages) for a flow that was ~40 lines of if/else. Worth it because S4 and
1B add branches; a graph keeps them visible (`python -m app.graph` prints the Mermaid diagram) and traceable per
answer. If the comparison fails, the plain flow stays default and the gap is logged.

## First comparison (27 Nov 2026, 01:50 plain vs 02:08 graph, golden_v2_2, no embedding cache)
Model metrics within +-1 (cited 27->28, headline 21->22, refusals 71->70: i01 flips between runs, as in S2).
Retrieval differed on ONE question: p07's 5th RBI clause (170E, score 0.2757, near-tied with 105 at 0.281).
Cause: text-embedding-3-small returned a slightly different vector for the same question on the second call; both
flows run the same search code. Fix: optional on-disk embedding cache (EMBED_CACHE, app/retrieve.py), on by default
in eval/run_eval.py, so repeated runs embed each question once. Done-when NOT yet met: re-run both flows with the
cache. Default stays PIPELINE=plain until then.

## Second comparison - done-when MET (27 Nov 2026, 02:45 plain vs 02:53 graph, embedding cache 72/72 reused)
Retrieval identical on all 72 questions. Model metrics: RBI cited 27->28, rules cited 46->47, answers 35->36,
refusals 69->71, rest equal; $0.086 / 6.4 s -> $0.084 / 6.3 s. All 5 flips come from two validator refusals in the
plain run (g002, p03), not from the flow: both first drafts were correct but named a retrieved source without citing
it; the retries named a source that was NOT retrieved and were refused. The graph run passed both first time.
Accepted; default flipped to graph. The validator retry behaviour is a separate change (ADR-017).
