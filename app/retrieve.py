# run: python -m app.retrieve   (smoke test)
# The return shape of retrieve() is the /retrieve contract v0 that 1B and Project 2 will call.
# Rule: add fields, never rename or remove them.
import os
from functools import lru_cache
from dotenv import load_dotenv; load_dotenv()
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore

CONTRACT_VERSION = "v0"
FIELDS = ("doc_id", "clause_no", "title", "chapter", "section", "section_anchor",
          "version_label", "version_as_on", "effective_from", "effective_to",
          "source_url", "content_hash")

@lru_cache
def _store():
    return QdrantVectorStore.from_existing_collection(
        embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        collection_name="clauses_v1",
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])

def retrieve(question: str, k: int = 5) -> list[dict]:
    hits = _store().similarity_search_with_score(question, k=k)
    return [{**{f: d.metadata.get(f) for f in FIELDS},
             "score": round(float(s), 4), "text": d.page_content} for d, s in hits]

if __name__ == "__main__":
    # expected clause in brackets; check by eye that it appears in the top 5
    smoke = [("What is the maximum LTV for gold loans up to 2.5 lakh?", "44"),
             ("Does the LTV have to be maintained for the whole loan tenure?", "45"),
             ("When do these directions come into effect?", "2")]
    found = 0
    for q, exp in smoke:
        hits = retrieve(q)
        ok = exp in [h["clause_no"] for h in hits]; found += ok
        print(("OK  " if ok else "MISS"), q, "->", [(h["clause_no"], h["score"]) for h in hits])
    print(f"\nretrieval smoke test: {found}/{len(smoke)} expected clauses in top 5")
