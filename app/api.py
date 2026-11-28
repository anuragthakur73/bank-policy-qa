# run: uvicorn app.api:app --port 8000      then open http://127.0.0.1:8000/docs  (Week 4 S4, ADR-013)
# The service Project 1B and Project 2 call. Endpoints:
#   GET  /v1/health    contract version, kill switch state, policy versions on disk
#   POST /v1/retrieve  rules + RBI clauses for a question, product and as-on date (no Claude call; ~$0.00001)
#   POST /v1/answer    cited answer; with the kill switch on, returns the retrieval only (search-only mode)
#   GET  /v1/rules, GET /v1/rules/{rule_id}   rules in force on a date, with params, from the policy files - never
#                      search (Week 7 S2, ADR-022). For 1B's code checks.
#   POST /v1/mask      ADR-015 + ADR-021 masking for a caller's free text (1B masks loan-file notes before any model)
# Kill switch (RBI draft model-risk guidance: ability to stop the model): env KILL_SWITCH=1, or a file named
# KILL_SWITCH in the working folder - the file works without a restart.
# Contract rule (as in app/retrieve.py): add fields, never rename or remove them. Breaking change -> /v2.
import datetime, json, os, pathlib, time, uuid
from typing import Literal
from fastapi import FastAPI, HTTPException, Path, Query as Q
from pydantic import BaseModel, Field
from app import policy_versions as pv, rules as rules_mod
from app.retrieve import CONTRACT_VERSION
from app.search import search
from app.pii import mask

API_VERSION = "v1"
Product = Literal["home_loan", "lap", "vehicle_loan", "rbi_only"]   # rbi_only: the reply to a clarifying question
Source = Literal["policy", "rbi"]

app = FastAPI(title="Bank Policy Q&A - retrieval service", version=f"{API_VERSION} (contract {CONTRACT_VERSION})",
              description="Demo Bank (fictional, synthetic) policy rules and RBI Master Direction clauses, filtered by "
                          "product and by the policy version in force on an as-on date. Not legal advice.")

from app.killswitch import kill_switch_on   # moved to its own module in Week 5 S3; still importable from here

def _audit(rec: dict):
    os.makedirs("logs", exist_ok=True)
    with open("logs/audit.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

# ---------- models
class Query(BaseModel):
    query: str = Field(min_length=3, max_length=1000, examples=["What is the maximum LTV for a home loan of Rs 50 lakh?"])
    product: Product | None = Field(None, description="From the loan file or screen. Omit to detect from the question; "
                                                      "if unclear, every product is searched.")
    as_on: datetime.date | None = Field(None, description="Date the answer must hold on. Default: today.")

class RetrieveRequest(Query):
    top_k: int = Field(5, ge=1, le=10, description="RBI clauses to return")
    k_policy: int = Field(3, ge=1, le=5, description="Policy rules per product by meaning (+1 keyword match, ADR-011)")
    sources: list[Source] = Field(["policy", "rbi"], min_length=1)

class TraceRef(BaseModel):
    direction: str
    para: str
    status: Literal["found", "not_found", "not_indexed"]
    chunk_id: str | None = Field(None, description="id of the traced RBI clause, if found")

class Chunk(BaseModel):
    id: str = Field(description="RBI: doc_id:clause_no. Policy: doc_id:rule_id@policy_version")
    source_type: Source
    doc_id: str
    clause_no: str
    title: str | None
    chapter: str | None
    section: str | None
    text: str
    link: str
    score: float | None
    retrieval: dict | None
    version_label: str | None
    effective_from: str | None
    effective_to: str | None
    product: str | None = None
    policy_version: str | None = None
    policy_status: str | None = None
    rule_id: str | None = None
    bank_discretion: bool | None = None
    vs_rbi: str | None = None
    rbi_scope: str | None = None
    synthetic: bool
    trace: list[TraceRef] = []
    # ADR-022 (contract v0.7). For policy chunks the older fields keep their meaning: chapter = policy section,
    # section = rule title (same field names as RBI clauses, ADR-013). rule_section repeats the policy section under
    # a clear name. params come from the search index: use /v1/rules for the values in the policy file.
    rule_section: str | None = Field(None, description="Policy chunks: policy section, e.g. eligibility, governance")
    params: dict | None = Field(None, description="Policy chunks: the rule's machine-readable values, as indexed")
    content_hash: str | None = Field(None, description="sha256 of the text when indexed. Policy chunks: differs from "
                                                       "/v1/rules content_hash if the index is behind the file")

class ProductStatus(BaseModel):
    product: str
    in_force: str | None
    next: str | None
    next_status: str | None
    next_from: str | None

class Rule(BaseModel):
    id: str = Field(description="doc_id:rule_id@policy_version - same id as the rule's /v1/retrieve chunk")
    rule_id: str
    product: str
    policy_version: str
    policy_status: str = Field(description="approved | draft")
    effective_from: str
    effective_to: str | None = Field(description="Day before the next version starts; null = open")
    section: str = Field(description="Policy section, e.g. eligibility, limits, governance")
    title: str
    text: str
    params: dict | None = Field(description="Machine-readable values for code checks; null for text-only rules")
    bank_discretion: bool | None
    vs_rbi: str | None
    rbi_ref: dict | None
    review: str | None
    synthetic: bool
    link: str
    content_hash: str = Field(description="sha256 of the rule text, computed as the index does: compare with a "
                                          "retrieved chunk to see whether the index is behind the file")

class RulesResponse(BaseModel):
    api: str
    contract: str
    product: str
    as_on: datetime.date
    in_force: ProductStatus
    notices: list[str]
    rules: list[Rule]

class RuleResponse(BaseModel):
    api: str
    contract: str
    as_on: datetime.date
    rule: Rule

class MaskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000, examples=["Customer Ramesh Sharma, PAN ABCDE1234F, wants Rs 40 lakh"])

class MaskResponse(BaseModel):
    api: str
    contract: str
    request_id: str
    masked: str
    entities: list[str] = Field(description="Types masked, in text order. Raw values are never returned or logged")

class RetrieveResponse(BaseModel):
    api: str
    contract: str
    request_id: str
    as_on: datetime.date
    products: list[str]
    product_source: Literal["given", "detected", "unclear"]
    policy_status: list[ProductStatus]
    notices: list[str]
    chunks: list[Chunk]
    timings_ms: dict
    pii_masked: list[str] = Field([], description="Types of personal data masked in the query before search (ADR-015)")

class Citation(BaseModel):
    chunk_id: str | None
    rule_id: str | None
    policy_version: str | None
    doc_id: str | None
    clause_no: str | None
    cited_text: str
    link: str

class AnswerResponse(BaseModel):
    api: str
    contract: str
    request_id: str
    mode: Literal["answer", "search_only", "clarify"]
    answer: str | None
    refused: bool | None
    citations: list[Citation]
    notices: list[str]
    as_on: datetime.date
    products: list[str]
    product_source: str
    chunks: list[Chunk] = Field([], description="Filled in search_only mode")
    pii_masked: list[str] = []
    cost_usd: float | None
    latency_ms: int
    clarify: dict | None = Field(None, description="mode=clarify (ADR-018): {missing, question, options}. Ask again "
                                                  "with product set to one option's value")

# ---------- helpers
def _id(h: dict) -> str:
    if h.get("layer") == "policy":
        return f'{h["doc_id"]}:{h["rule_id"]}@{h.get("policy_version")}'
    return f'{h["doc_id"]}:{h["clause_no"]}'

def _chunk(h: dict) -> Chunk:
    from app.generate import clause_link
    trace = [TraceRef(direction=t["direction"], para=str(t["para"]), status=t["status"],
                      chunk_id=_id({**t["clause"], "layer": "rbi"}) if t.get("clause") else None)
             for t in (h.get("trace") or [])]
    return Chunk(id=_id(h), source_type=h["layer"], doc_id=h["doc_id"], clause_no=str(h["clause_no"]),
                 title=h.get("title"), chapter=h.get("chapter"), section=h.get("section"), text=h["text"],
                 link=clause_link(h), score=h.get("score"), retrieval=h.get("retrieval"),
                 version_label=h.get("version_label"),
                 effective_from=str(h["effective_from"]) if h.get("effective_from") else None,
                 effective_to=str(h["effective_to"]) if h.get("effective_to") else None,
                 product=h.get("product"), policy_version=h.get("policy_version"),
                 policy_status=h.get("policy_status"), rule_id=h.get("rule_id"),
                 bank_discretion=h.get("bank_discretion"), vs_rbi=h.get("vs_rbi"), rbi_scope=h.get("rbi_scope"),
                 synthetic=bool(h.get("synthetic")), trace=trace,
                 rule_section=h.get("chapter") if h["layer"] == "policy" else None,
                 params=h.get("params") if h["layer"] == "policy" else None, content_hash=h.get("content_hash"))

def _retrieve(req: Query, top_k=5, k_policy=3, sources=("policy", "rbi")):
    timings = {}
    q, pii = mask(req.query)
    product = req.product
    if product == "rbi_only":                     # reply to a clarifying question: RBI clauses only (ADR-018)
        product, sources = None, [s for s in sources if s != "policy"]
    found = search(q, top_k, layers=tuple(sources), product=product, as_on=req.as_on,
                   k_policy=k_policy, timings=timings)
    found["query"], found["pii_masked"] = q, pii
    return found, [_chunk(h) for h in found["rows"]], timings

# ---------- endpoints
@app.get("/v1/health")
def health():
    return {"status": "ok", "api": API_VERSION, "contract": CONTRACT_VERSION, "kill_switch": kill_switch_on(),
            "policies": {p: [{"version": v["version"], "status": v["status"],
                              "effective_from": v["effective_from"], "effective_to": v["effective_to"]}
                             for v in vs] for p, vs in pv.registry().items()}}

@app.post("/v1/retrieve", response_model=RetrieveResponse)
def retrieve_endpoint(req: RetrieveRequest):
    rid, t0 = str(uuid.uuid4()), time.perf_counter()
    found, chunks, timings = _retrieve(req, req.top_k, req.k_policy, req.sources)
    _audit({"request_id": rid, "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "caller": "api", "endpoint": "retrieve", "question": found["query"], "pii_masked": found["pii_masked"], "contract": CONTRACT_VERSION,
            "as_on": found["as_on"], "products": list(found["products"]), "product_source": found["product_source"],
            "returned": [c.id for c in chunks], "latency_ms": int((time.perf_counter() - t0) * 1000)})
    return RetrieveResponse(api=API_VERSION, contract=CONTRACT_VERSION, request_id=rid, as_on=found["as_on"],
                            products=list(found["products"]), product_source=found["product_source"],
                            policy_status=found["policy_status"], notices=found["notices"], chunks=chunks,
                            timings_ms=timings, pii_masked=found["pii_masked"])

@app.post("/v1/answer", response_model=AnswerResponse)
def answer_endpoint(req: Query):
    t0 = time.perf_counter()
    if kill_switch_on():
        rid = str(uuid.uuid4())
        found, chunks, _ = _retrieve(req)
        msg = "Answer generation is switched off (kill switch). Showing the matching rules and clauses only."
        _audit({"request_id": rid, "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "caller": "api", "endpoint": "answer", "mode": "search_only", "question": found["query"], "pii_masked": found["pii_masked"],
                "contract": CONTRACT_VERSION, "as_on": found["as_on"], "returned": [c.id for c in chunks]})
        return AnswerResponse(api=API_VERSION, contract=CONTRACT_VERSION, request_id=rid, mode="search_only",
                              answer=None, refused=None, citations=[], notices=[msg] + found["notices"],
                              as_on=found["as_on"], products=list(found["products"]),
                              product_source=found["product_source"], chunks=chunks, cost_usd=0.0,
                              pii_masked=found["pii_masked"],
                              latency_ms=int((time.perf_counter() - t0) * 1000))
    from app.generate import answer
    text, cites, rec = answer(req.query, caller="api", product=req.product, as_on=req.as_on)
    if rec.get("mode") == "clarify":
        return AnswerResponse(api=API_VERSION, contract=CONTRACT_VERSION, request_id=rec["request_id"], mode="clarify",
                              answer=text, refused=False, citations=[], notices=[],
                              as_on=datetime.date.fromisoformat(rec["as_on"]), products=rec["products"],
                              product_source=rec["product_source"], cost_usd=0.0,
                              pii_masked=rec.get("pii_masked", []), clarify=rec["clarify"],
                              latency_ms=int((time.perf_counter() - t0) * 1000))
    citations = [Citation(chunk_id=(f'{c["doc_id"]}:{c["rule_id"]}@{c.get("policy_version")}' if c["layer"] == "policy"
                                    else f'{c["doc_id"]}:{c["clause_no"]}') if c.get("doc_id") else None,
                          rule_id=c.get("rule_id"), policy_version=c.get("policy_version"), doc_id=c.get("doc_id"),
                          clause_no=c.get("clause_no"), cited_text=c.get("cited_text") or "", link=c["source"])
                 for c in cites]
    return AnswerResponse(api=API_VERSION, contract=CONTRACT_VERSION, request_id=rec["request_id"], mode="answer",
                          answer=text, refused=rec["refused"], citations=citations, notices=rec["notices"],
                          as_on=datetime.date.fromisoformat(rec["as_on"]), products=rec["products"],
                          product_source=rec["product_source"], cost_usd=rec["cost_usd"],
                          pii_masked=rec.get("pii_masked", []),
                          latency_ms=rec["latency_ms"])

# ---------- ADR-022 (Week 7 S2): rules by date, masking - for Project 1B
ProductParam = Literal["home_loan", "lap", "vehicle_loan"]

def _not_in_force(product: str, as_on: datetime.date) -> str:
    nxt = pv.next_version(product, as_on)
    when = f' (v{nxt["version"]}, {nxt["status"]}, starts {pv.fmt(nxt["effective_from"])})' if nxt else ""
    return f'Demo Bank\'s {pv.NAMES[product]} policy is not in force on {pv.fmt(as_on)}{when}.'

@app.get("/v1/rules", response_model=RulesResponse, summary="Rules in force on a date (with params)")
def rules_endpoint(product: ProductParam,
                   as_on: datetime.date | None = Q(None, description="Date the rules must hold on. Default: today"),
                   section: str | None = Q(None, description="Only one policy section, e.g. eligibility, governance")):
    """Every rule of the policy version in force on the date, with params. From the policy files, never search.
    No version in force on the date: 200 with an empty list and a notice (the file is then checked on RBI only)."""
    as_on = as_on or datetime.date.today()
    v, rows = rules_mod.in_force(product, as_on, section)
    st = pv.status([product], as_on)[0]
    _audit({"timestamp": datetime.datetime.now().isoformat(timespec="seconds"), "caller": "api",
            "endpoint": "rules", "product": product, "as_on": as_on, "section": section, "contract": CONTRACT_VERSION,
            "policy_version": v["version"] if v else None, "returned": [r["id"] for r in rows]})
    return RulesResponse(api=API_VERSION, contract=CONTRACT_VERSION, product=product, as_on=as_on, in_force=st,
                         notices=[] if v else [_not_in_force(product, as_on)], rules=rows)

@app.get("/v1/rules/{rule_id}", response_model=RuleResponse, summary="One rule, version chosen by date",
         responses={404: {"description": "Unknown rule ID, no version in force, or rule not in that version"}})
def rule_endpoint(rule_id: str = Path(pattern=r"^DB-(HL|LAP|VL)-\d{3}$", examples=["DB-HL-030"]),
                  as_on: datetime.date | None = Q(None, description="Date the rule must hold on. Default: today")):
    """One rule as in force on the date: the version is chosen by date, never by search."""
    as_on = as_on or datetime.date.today()
    product, v, row = rules_mod.get(rule_id, as_on)
    _audit({"timestamp": datetime.datetime.now().isoformat(timespec="seconds"), "caller": "api",
            "endpoint": "rule", "rule_id": rule_id, "as_on": as_on, "contract": CONTRACT_VERSION,
            "policy_version": v["version"] if v else None, "found": bool(row)})
    if not product:
        raise HTTPException(404, f"{rule_id}: no Demo Bank product uses this prefix")
    if not v:
        raise HTTPException(404, _not_in_force(product, as_on))
    if not row:
        have = rules_mod.versions_with(rule_id)
        raise HTTPException(404, f'{rule_id} is not in {pv.NAMES[product]} policy v{v["version"]}, in force on '
                                 f'{pv.fmt(as_on)}' + (f' (it is in v{", v".join(have)})' if have else ""))
    return RuleResponse(api=API_VERSION, contract=CONTRACT_VERSION, as_on=as_on, rule=row)

@app.post("/v1/mask", response_model=MaskResponse, summary="Mask personal data in free text",
          responses={503: {"description": "Masking unavailable (e.g. NER model missing): nothing was processed"}})
def mask_endpoint(req: MaskRequest):
    """Mask personal data in free text (ADR-015 patterns + ADR-021 names and addresses). Fails closed: if masking
    cannot run, 503 and no text is returned. The audit log keeps entity types and length only, never the text."""
    rid = str(uuid.uuid4())
    try:
        masked, ents = mask(req.text)
    except Exception as e:                                       # e.g. OSError: spaCy model not installed
        _audit({"request_id": rid, "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "caller": "api", "endpoint": "mask", "error": type(e).__name__, "chars": len(req.text)})
        raise HTTPException(503, "Masking is unavailable, so nothing was processed. Do not send this text to a model.")
    _audit({"request_id": rid, "timestamp": datetime.datetime.now().isoformat(timespec="seconds"), "caller": "api",
            "endpoint": "mask", "contract": CONTRACT_VERSION, "chars": len(req.text), "pii_masked": ents})
    return MaskResponse(api=API_VERSION, contract=CONTRACT_VERSION, request_id=rid, masked=masked, entities=ents)
