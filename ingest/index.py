# run: python -m ingest.index credit_facilities
# Embeds every live clause (omitted "*****" paragraphs skipped) and loads it into Qdrant via LangChain.
import json, os, sys, uuid
from dotenv import load_dotenv; load_dotenv()
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore

COLLECTION = "clauses_v1"
docs, ids = [], []
for key in sys.argv[1:]:
    for line in open(f"data/parsed/{key}.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["omitted"]:
            continue
        text = r.pop("text")
        docs.append(Document(page_content=text, metadata=r))
        # same clause + same version -> same id, so re-running replaces instead of duplicating
        ids.append(str(uuid.uuid5(uuid.NAMESPACE_URL, f'{r["doc_id"]}|{r["clause_no"]}|{r["version_as_on"]}')))

QdrantVectorStore.from_documents(
    docs, OpenAIEmbeddings(model="text-embedding-3-small"), ids=ids,
    url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"],
    collection_name=COLLECTION, force_recreate=True)
print("indexed", len(docs), "clauses into", COLLECTION)
