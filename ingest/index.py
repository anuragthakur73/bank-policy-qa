# run: python -m ingest.index credit_facilities responsible_business_conduct   (ALL documents: the collection is recreated)
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
        r["clause_text"] = text
        # Contextual header: the chapter/section tells search (and Claude) what a clause is about,
        # e.g. para 44 sits in "Chapter IV - Lending against Gold and Silver Collateral".
        header = " > ".join(x for x in (r.get("chapter"), r.get("section")) if x)
        docs.append(Document(page_content=f"{header}\n{text}" if header else text, metadata=r))
        # same clause + same version -> same id, so re-running replaces instead of duplicating
        ids.append(str(uuid.uuid5(uuid.NAMESPACE_URL, f'{r["doc_id"]}|{r["clause_no"]}|{r["version_as_on"]}')))

QdrantVectorStore.from_documents(
    docs, OpenAIEmbeddings(model="text-embedding-3-small"), ids=ids,
    url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"],
    collection_name=COLLECTION, force_recreate=True)
# force_recreate drops payload indexes: rebuild the ones the policy trace uses (ADR-005)
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
for field in ("metadata.doc_id", "metadata.clause_no"):
    client.create_payload_index(COLLECTION, field_name=field, field_schema=qm.PayloadSchemaType.KEYWORD)
print("indexed", len(docs), "clauses into", COLLECTION, "from", ", ".join(sys.argv[1:]), "| payload indexes ok")
