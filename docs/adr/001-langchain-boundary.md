# ADR-001: Where LangChain is used, and where it isn't

Date: 22 Nov 2026 · Status: accepted

## Decision
Use LangChain for documents, embeddings and the vector store (`langchain-qdrant`, `langchain-openai`).
Call the Anthropic SDK directly for answer generation.

## Why
- Native citations need the raw `search_result` content blocks in the Messages API; a wrapper would hide or lag them.
- LangChain's vector-store interface lets us swap Qdrant or the embedding model in one place, and is the same interface the LangGraph agent in Project 1B will use.
- The `/retrieve` contract (`app/retrieve.py`) is ours, not LangChain's, so callers never depend on LangChain types.

## Alternatives considered
1. All-LangChain (ChatAnthropic for generation): less code, but citation support is harder to control and debug.
2. No LangChain (raw qdrant-client + SDKs): fewer dependencies, but loses the hands-on LangChain/LangGraph learning goal and the swap-ability.

## Consequences
- Two clients to keep updated. Pinned in `requirements.txt`.
- Revisit if LangChain's Anthropic integration supports search-result citations end to end.
