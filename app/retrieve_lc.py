# run: python -m app.retrieve_lc "your question"
# The same hybrid search as app/retrieve.py, built from LangChain parts (for hands-on familiarity):
#   BM25Retriever (langchain-community, wraps rank_bm25)  +  the Qdrant vector store as a retriever
#   -> EnsembleRetriever (langchain-classic): weighted reciprocal rank fusion, c=60.
# With equal weights and the same tokenizer it should rank like the hand-built version; eval/compare_retrieval.py
# checks that. Differences to know (ADR-007): no per-row scores or ranks come back, and the vector call skips
# our Qdrant retry wrapper.
import sys
from functools import lru_cache
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from app import keyword
from app.retrieve import N_CANDIDATES, _store

@lru_cache
def ensemble(n: int = N_CANDIDATES) -> EnsembleRetriever:
    rows, _, _ = keyword.corpus()
    docs = [Document(page_content=keyword.page_content(r), metadata=r) for r in rows]
    bm25 = BM25Retriever.from_documents(docs, preprocess_func=keyword.tokenize, k=n)
    vector = _store("rbi").as_retriever(search_kwargs={"k": n})
    # Duplicates are merged by page_content: both retrievers use keyword.page_content's exact string.
    return EnsembleRetriever(retrievers=[vector, bm25], weights=[0.5, 0.5], c=60)

def search(question: str, k: int = 5) -> list[Document]:
    return ensemble().invoke(question)[:k]

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "For how long is the Key Facts Statement valid?"
    for d in search(q):
        print(d.metadata["doc_id"], "para", d.metadata["clause_no"], "|", d.page_content.split("\n")[-1][:90])
