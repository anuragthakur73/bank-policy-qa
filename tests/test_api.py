# Contract tests for /v1 (Week 4 S4). Search results are faked: no network, no API keys, no cost.
import datetime as dt
import pytest
from fastapi.testclient import TestClient
import app.api as api
import app.search as search_mod

def _row(layer, **kw):
    base = {"doc_id": "RBI-CB-CREDIT-FAC-2025", "clause_no": "111", "title": "Credit Facilities", "chapter": "VIII",
            "section": "B.6", "section_anchor": None, "version_label": "updated as on 2026-10-01",
            "version_as_on": "2026-10-01", "effective_from": "2025-11-28", "effective_to": None,
            "source_url": "https://rbi.org.in/x", "content_hash": "h", "parent_clause": None,
            "product": None, "policy_version": None, "policy_status": None, "rule_id": None, "bank_discretion": None,
            "vs_rbi": None, "rbi_ref": None, "params": None, "review": None, "synthetic": None,
            "layer": layer, "score": 0.8, "text": "111. Loan to value ratio ...", "trace": [],
            "retrieval": {"mode": "vector", "vector_rank": 1}, "rbi_scope": "home_loan"}
    return {**base, **kw}

POLICY = _row("policy", doc_id="DEMO-BANK-HOME-LOAN-POLICY", clause_no="DB-HL-009", rule_id="DB-HL-009",
              product="home_loan", policy_version="1.1.0", policy_status="draft", bank_discretion=False,
              vs_rbi="equal", synthetic=True, source_url="policy/demo_bank/home_loan_v1_1.yaml",
              effective_from="2027-01-01", rbi_scope=None, text="Loans above Rs 30 lakh up to Rs 75 lakh: 80%.",
              trace=[{"direction": "CF", "para": "111", "status": "found", "clause": _row("rbi")},
                     {"direction": "PMAY", "para": "3", "status": "not_indexed", "clause": None}])

@pytest.fixture
def client(monkeypatch):
    calls = []
    def fake_retrieve(q, k, layers, **kw):
        calls.append({"layers": layers, **kw})
        return ([POLICY] if "policy" in layers else []) + [_row("rbi")]
    monkeypatch.setattr(search_mod, "retrieve", fake_retrieve)
    audit = []
    monkeypatch.setattr(api, "_audit", audit.append)            # never write test records to logs/audit.jsonl
    monkeypatch.delenv("KILL_SWITCH", raising=False)
    c = TestClient(api.app); c.calls, c.audit = calls, audit
    return c

def test_health_and_openapi(client):
    h = client.get("/v1/health").json()
    assert h["api"] == "v1" and h["contract"] == api.CONTRACT_VERSION and h["kill_switch"] is False
    assert [v["version"] for v in h["policies"]["home_loan"]] == ["1.0.0", "1.1.0"]
    assert {"/v1/retrieve", "/v1/answer", "/v1/health"} <= set(client.get("/openapi.json").json()["paths"])

def test_retrieve_contract(client):
    r = client.post("/v1/retrieve", json={"query": "Max LTV for a home loan of Rs 50 lakh?", "product": "home_loan",
                                          "as_on": "2027-01-02"})
    assert r.status_code == 200
    b = r.json()
    assert b["products"] == ["home_loan"] and b["product_source"] == "given" and b["as_on"] == "2027-01-02"
    pol, rbi = b["chunks"]
    assert pol["id"] == "DEMO-BANK-HOME-LOAN-POLICY:DB-HL-009@1.1.0" and pol["source_type"] == "policy"
    assert pol["product"] == "home_loan" and pol["policy_status"] == "draft" and pol["synthetic"] is True
    assert pol["link"] == "policy/demo_bank/home_loan_v1_1.yaml#DB-HL-009"
    assert pol["trace"] == [{"direction": "CF", "para": "111", "status": "found", "chunk_id": "RBI-CB-CREDIT-FAC-2025:111"},
                            {"direction": "PMAY", "para": "3", "status": "not_indexed", "chunk_id": None}]
    assert rbi["id"] == "RBI-CB-CREDIT-FAC-2025:111" and rbi["rbi_scope"] == "home_loan"
    assert rbi["link"].startswith("https://rbi.org.in/x#:~:text=")
    assert client.calls[-1]["as_on"] == dt.date(2027, 1, 2) and client.calls[-1]["products"] == ("home_loan",)

@pytest.mark.parametrize("body", [
    {"query": "ok?", "product": "gold_loan"}, {"query": "x"}, {"query": "LTV?", "top_k": 50},
    {"query": "LTV?", "as_on": "15-12-2026"}, {"query": "LTV?", "sources": []}, {"query": "LTV?", "sources": ["web"]}])
def test_retrieve_rejects_bad_input(client, body):
    assert client.post("/v1/retrieve", json=body).status_code == 422

def test_before_policy_starts_rbi_only(client):
    b = client.post("/v1/retrieve", json={"query": "Max LTV on a loan against a flat?", "product": "lap",
                                          "as_on": "2026-12-15"}).json()
    assert client.calls[-1]["layers"] == ("rbi",) and client.calls[-1]["asked_products"] == ("lap",)
    assert b["policy_status"][0]["in_force"] is None and b["notices"][0].startswith("Demo Bank's Loan Against Property")
    assert [c["source_type"] for c in b["chunks"]] == ["rbi"]

def test_kill_switch_search_only(client, monkeypatch):
    import app.generate as gen
    monkeypatch.setattr(gen, "answer", lambda *a, **k: pytest.fail("model must not be called with the kill switch on"))
    monkeypatch.setenv("KILL_SWITCH", "1")
    assert client.get("/v1/health").json()["kill_switch"] is True
    b = client.post("/v1/answer", json={"query": "Max LTV for a home loan of Rs 50 lakh?", "as_on": "2027-01-02"}).json()
    assert b["mode"] == "search_only" and b["answer"] is None and b["cost_usd"] == 0.0
    assert b["notices"][0].startswith("Answer generation is switched off") and len(b["chunks"]) == 2
    assert client.audit[-1]["mode"] == "search_only"                 # kill-switch use is itself audited

def test_answer_mode(client, monkeypatch):
    import app.generate as gen
    rec = {"request_id": "r1", "refused": False, "notices": [], "as_on": "2027-01-02", "products": ["home_loan"],
           "product_source": "detected", "cost_usd": 0.0011, "latency_ms": 5000}
    cite = {"layer": "policy", "doc_id": "DEMO-BANK-HOME-LOAN-POLICY", "clause_no": "DB-HL-009", "rule_id": "DB-HL-009",
            "policy_version": "1.1.0", "cited_text": "80%", "source": "policy/demo_bank/home_loan_v1_1.yaml#DB-HL-009"}
    monkeypatch.setattr(gen, "answer", lambda q, **k: ("80% under DB-HL-009.", [cite], rec))
    b = client.post("/v1/answer", json={"query": "Max LTV for a home loan of Rs 50 lakh?"}).json()
    assert b["mode"] == "answer" and b["answer"].startswith("80%") and b["refused"] is False
    assert b["citations"][0]["chunk_id"] == "DEMO-BANK-HOME-LOAN-POLICY:DB-HL-009@1.1.0"

def test_answer_clarify_mode(client, monkeypatch):            # S4, ADR-018
    import app.generate as gen
    rec = {"request_id": "r1", "mode": "clarify", "as_on": "2027-01-02", "products": ["home_loan", "lap", "vehicle_loan"],
           "product_source": "unclear", "pii_masked": [],
           "clarify": {"missing": ["product"], "question": "Which product?", "options": [{"value": "lap", "label": "LAP"}]}}
    monkeypatch.setattr(gen, "answer", lambda q, **k: ("Which product?", [], rec))
    b = client.post("/v1/answer", json={"query": "What is the minimum credit score?"}).json()
    assert b["mode"] == "clarify" and b["clarify"]["options"][0]["value"] == "lap" and b["cost_usd"] == 0.0

def test_retrieve_rbi_only(client):
    b = client.post("/v1/retrieve", json={"query": "Penal interest on overdue EMI?", "product": "rbi_only"}).json()
    assert client.calls[-1]["layers"] == ("rbi",) and all(c["source_type"] == "rbi" for c in b["chunks"])
