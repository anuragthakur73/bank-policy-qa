# ADR-022 (Week 7 S2): /v1/rules, /v1/rules/{rule_id}, /v1/mask and the new chunk fields. Reads the real policy
# files; search and the model are made to fail if touched. No network, no API keys.
import hashlib
import pytest
from fastapi.testclient import TestClient
import app.api as api
import app.search as search_mod
from tests.test_api import _row

@pytest.fixture
def client(monkeypatch):
    def no_search(*a, **k):
        raise AssertionError("rules must come from the policy files, never from search")
    monkeypatch.setattr(search_mod, "retrieve", no_search)
    audit = []
    monkeypatch.setattr(api, "_audit", audit.append)
    c = TestClient(api.app); c.audit = audit
    return c

def rule(client, rid, day):
    return client.get(f"/v1/rules/{rid}", params={"as_on": day})

# ---- the S2 done-when: loan file F11 checked on two dates gets two different deviation rules
def test_f11_two_dates_two_versions_of_db_hl_030(client):
    dec, jan = rule(client, "DB-HL-030", "2026-12-15").json()["rule"], rule(client, "DB-HL-030", "2027-01-15").json()["rule"]
    assert (dec["policy_version"], jan["policy_version"]) == ("1.0.0", "1.1.0")
    assert dec["params"]["allowed"] != jan["params"]["allowed"]
    assert "tenure_years" not in dec["params"]["allowed"]                 # F11 15 Dec: tenure +1 not deviable
    assert jan["params"]["allowed"]["tenure_years"] == 2                  # F11 15 Jan: deviable, up to 2 years
    assert dec["params"]["max_deviations_per_loan"] == jan["params"]["max_deviations_per_loan"] == 2
    assert "DB-HL-009" in jan["params"]["prohibited_rule_ids"]            # LTV never deviable
    assert dec["id"] == "DEMO-BANK-HOME-LOAN-POLICY:DB-HL-030@1.0.0" and dec["effective_to"] == "2026-12-31"
    assert jan["policy_status"] == "draft" and jan["effective_to"] is None

@pytest.mark.parametrize("day,ver", [("2026-12-01", "1.0.0"), ("2026-12-31", "1.0.0"), ("2027-01-01", "1.1.0")])
def test_version_switches_on_the_effective_date(client, day, ver):
    assert rule(client, "DB-HL-009", day).json()["rule"]["policy_version"] == ver

def test_rules_list_in_force(client):
    b = client.get("/v1/rules", params={"product": "home_loan", "as_on": "2027-01-15"}).json()
    assert b["in_force"]["in_force"] == "1.1.0" and b["notices"] == []
    ids = [r["rule_id"] for r in b["rules"]]
    assert len(ids) == len(set(ids)) == 34 and all(r["id"].endswith("@1.1.0") for r in b["rules"])
    r9 = next(r for r in b["rules"] if r["rule_id"] == "DB-HL-009")
    assert r9["params"] and r9["bank_discretion"] is False and r9["link"] == "policy/demo_bank/home_loan_v1_1.yaml#DB-HL-009"
    assert r9["content_hash"] == hashlib.sha256(r9["text"].encode()).hexdigest()   # same recipe as the index
    gov = client.get("/v1/rules", params={"product": "home_loan", "as_on": "2027-01-15", "section": "governance"}).json()
    assert "DB-HL-030" in [r["rule_id"] for r in gov["rules"]] and {r["section"] for r in gov["rules"]} == {"governance"}
    dec = client.get("/v1/rules", params={"product": "home_loan", "as_on": "2026-12-15"}).json()
    assert len(dec["rules"]) == 31 and dec["in_force"]["next"] == "1.1.0"

def test_rule_text_matches_policy_registry(client):
    from app import policy_versions as pv
    for prod, vs in pv.registry().items():
        for v in vs:
            b = client.get("/v1/rules", params={"product": prod, "as_on": v["effective_from"].isoformat()}).json()
            assert {r["rule_id"]: r["text"] for r in b["rules"]} == v["rules"]

def test_before_product_starts(client):
    b = client.get("/v1/rules", params={"product": "lap", "as_on": "2026-12-15"}).json()
    assert b["rules"] == [] and b["in_force"]["in_force"] is None
    assert b["notices"] == ["Demo Bank's Loan Against Property (LAP) policy is not in force on 15 Dec 2026 "
                            "(v1.0.0, draft, starts 1 Jan 2027)."]
    r = rule(client, "DB-LAP-001", "2026-12-15")
    assert r.status_code == 404 and "not in force on 15 Dec 2026" in r.json()["detail"]
    assert rule(client, "DB-HL-001", "2026-11-30").status_code == 404

def test_rule_missing_from_the_version_in_force(client):
    from app import rules
    only_new = sorted(set(r["rule_id"] for r in rules.in_force("home_loan", __import__("datetime").date(2027, 1, 15))[1])
                      - set(r["rule_id"] for r in rules.in_force("home_loan", __import__("datetime").date(2026, 12, 15))[1]))
    assert only_new                                                       # v1.1 added rules
    r = rule(client, only_new[0], "2026-12-15")
    assert r.status_code == 404 and r.json()["detail"].endswith("(it is in v1.1.0)")
    assert rule(client, "DB-HL-999", "2027-01-15").status_code == 404

@pytest.mark.parametrize("path,params", [
    ("/v1/rules/DB-XX-001", {}), ("/v1/rules/db-hl-030", {}), ("/v1/rules/DB-HL-030", {"as_on": "15-01-2027"}),
    ("/v1/rules", {"product": "gold_loan"}), ("/v1/rules", {"product": "rbi_only"}), ("/v1/rules", {})])
def test_rules_reject_bad_input(client, path, params):
    assert client.get(path, params=params).status_code == 422

def test_rules_audited(client):
    rule(client, "DB-HL-030", "2027-01-15")
    a = client.audit[-1]
    assert a["endpoint"] == "rule" and a["policy_version"] == "1.1.0" and a["found"] is True

# ---- /v1/mask
def test_mask_endpoint(client):
    raw = "Customer Ramesh Sharma, PAN ABCDE1234F, mobile 98765 43210, wants Rs 40 lakh for 20 years"
    b = client.post("/v1/mask", json={"text": raw}).json()
    assert "ABCDE1234F" not in b["masked"] and "Ramesh" not in b["masked"] and "98765" not in b["masked"]
    assert {"IN_PAN", "PERSON", "PHONE_NUMBER"} <= set(b["entities"]) and "Rs 40 lakh" in b["masked"]
    a = client.audit[-1]
    assert a["endpoint"] == "mask" and a["chars"] == len(raw)
    assert not any(s in str(a) for s in ("Ramesh", "ABCDE1234F", "98765"))   # the log never holds the text

def test_mask_fails_closed(client, monkeypatch):
    def broken(text):
        raise OSError("[E050] Can't find model 'en_core_web_lg'")
    monkeypatch.setattr(api, "mask", broken)
    r = client.post("/v1/mask", json={"text": "Customer Ramesh Sharma"})
    assert r.status_code == 503 and "Ramesh" not in r.text and "masked" not in r.json()
    assert client.post("/v1/mask", json={"text": ""}).status_code == 422

# ---- new fields on /v1/retrieve chunks
def test_retrieve_chunks_carry_params_and_rule_section(monkeypatch):
    pol = _row("policy", doc_id="DEMO-BANK-HOME-LOAN-POLICY", clause_no="DB-HL-011", rule_id="DB-HL-011",
               product="home_loan", policy_version="1.1.0", policy_status="draft", bank_discretion=True,
               chapter="limits", section="FOIR", params={"foir_max_pct": [{"nmi_upto": 50000, "pct": 50}]},
               source_url="policy/demo_bank/home_loan_v1_1.yaml", rbi_scope=None, synthetic=True)
    monkeypatch.setattr(search_mod, "retrieve", lambda q, k, layers, **kw: [pol, _row("rbi")])
    monkeypatch.setattr(api, "_audit", lambda rec: None)
    b = TestClient(api.app).post("/v1/retrieve", json={"query": "FOIR limit?", "product": "home_loan",
                                                       "as_on": "2027-01-15"}).json()
    p, r = b["chunks"]
    assert p["rule_section"] == "limits" and p["chapter"] == "limits" and p["section"] == "FOIR"   # old fields kept
    assert p["params"] == {"foir_max_pct": [{"nmi_upto": 50000, "pct": 50}]} and p["bank_discretion"] is True
    assert r["rule_section"] is None and r["params"] is None
    assert p["content_hash"] == "h"                                     # passed through from the index payload
    assert b["contract"] == "v0.7"

def test_openapi_lists_new_paths(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/v1/rules", "/v1/rules/{rule_id}", "/v1/mask"} <= set(paths)
