# run: python -m ingest.index_policy          (indexes EVERY version in policy/demo_bank; ADR-010)
#      python -m ingest.index_policy FILE...  (only these files; end dates still come from all versions on disk)
# Embeds every Demo Bank policy rule into Qdrant collection "policy_v1" (ADR-005).
# Pass ALL policy files in one run: the collection is recreated each time.
# Also adds keyword payload indexes on clauses_v1 so a rule's RBI paragraph can be fetched by number,
# and on policy_v1 metadata.product (ADR-009) and the integer effective dates (ADR-010).
# Every version of a product is indexed side by side; search picks the one in force on the as-on date.
import hashlib, json, os, sys, uuid
import yaml
from dotenv import load_dotenv; load_dotenv()
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from app import policy_versions as pv

COLLECTION = "policy_v1"
RBI_COLLECTION = "clauses_v1"

def jsonable(x):
    """YAML dates -> strings, so the payload is plain JSON."""
    return json.loads(json.dumps(x, default=str))

docs, ids, pending = [], [], []
paths = sys.argv[1:] or [v["path"] for vs in pv.registry().values() for v in vs]
for path in paths:
    pol = yaml.safe_load(open(path, encoding="utf-8"))
    assert pol.get("synthetic") is True, f"{path}: only synthetic Demo Bank policies may be indexed"
    product = pol["product"]
    doc_id = f"DEMO-BANK-{product.upper().replace('_', '-')}-POLICY"
    names = {"home_loan": "Home Loan", "lap": "Loan Against Property (LAP)",
             "vehicle_loan": "Car Loan", "education_loan": "Education Loan"}
    ver = pv.version(product, pol["policy_version"])          # effective_to = day before the next version
    title = f"Demo Bank (fictional) {names.get(product, product.replace('_', ' ').title())} Policy"
    for r in pol["rules"]:
        text = " ".join(r["rule"].split())
        meta = jsonable({
            # same field names as RBI clauses (retrieve contract)
            "doc_id": doc_id, "clause_no": r["rule_id"], "title": title,
            "chapter": r["section"], "section": r["title"], "section_anchor": None,
            "version_label": f'policy v{pol["policy_version"]} ({pol["status"]}, synthetic)',
            "version_as_on": pol["effective_from"], "effective_from": pol["effective_from"],
            "effective_to": ver["effective_to"], "policy_version": ver["version"], "policy_status": pol["status"],
            "effective_from_n": pv.date_n(ver["effective_from"]), "effective_to_n": pv.date_n(ver["effective_to"]),
            "source_url": path.replace("\\", "/"),   # repo path: a fictional bank has no URL
            "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(), "parent_clause": None,
            "clause_text": text,
            # policy-only fields
            "layer": "policy", "product": product, "rule_id": r["rule_id"], "bank_discretion": r["bank_discretion"],
            "vs_rbi": r["vs_rbi"], "rbi_ref": r.get("rbi_ref"), "params": r.get("params"),
            "review": r["review"], "synthetic": True, "design_basis": r.get("design_basis")})
        header = f"Demo Bank {product.replace('_', ' ')} policy > {r['section']} > {r['title']}"
        docs.append(Document(page_content=f"{header}\n{text}", metadata=meta))
        ids.append(str(uuid.uuid5(uuid.NAMESPACE_URL, f'{doc_id}|{r["rule_id"]}|{pol["policy_version"]}')))
        if r["review"] != "ok":
            pending.append(r["rule_id"])

QdrantVectorStore.from_documents(
    docs, OpenAIEmbeddings(model="text-embedding-3-small"), ids=ids,
    url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"],
    collection_name=COLLECTION, force_recreate=True)

client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
for field in ("metadata.doc_id", "metadata.clause_no"):
    client.create_payload_index(RBI_COLLECTION, field_name=field,
                                field_schema=qm.PayloadSchemaType.KEYWORD)

client.create_payload_index(COLLECTION, field_name="metadata.product",
                            field_schema=qm.PayloadSchemaType.KEYWORD)
for field in ("metadata.effective_from_n", "metadata.effective_to_n"):
    client.create_payload_index(COLLECTION, field_name=field, field_schema=qm.PayloadSchemaType.INTEGER)
from collections import Counter
print("indexed", len(docs), "rules into", COLLECTION,
      dict(Counter(f'{d.metadata["product"]} v{d.metadata["policy_version"]} '
                   f'{d.metadata["effective_from"]}..{d.metadata["effective_to"] or "open"}' for d in docs)),
      "| payload indexes ok on", RBI_COLLECTION, "and", COLLECTION)
if pending:
    print("note: still needs_review:", ", ".join(pending))
