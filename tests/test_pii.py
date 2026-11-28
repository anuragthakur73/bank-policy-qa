# S5 (ADR-015): personal data never reaches the search, the model or the audit log. No network, no API keys.
import json
from types import SimpleNamespace as NS
import pytest
from app.pii import mask

RAW = ["ABCDE1234F", "2345 6789 0124", "98765 43210", "ramesh@example.com", "123456789012", "4111 1111 1111 1111"]
Q = ("Customer PAN ABCDE1234F, Aadhaar 2345 6789 0124, mobile 98765 43210, email ramesh@example.com, "
     "a/c no 123456789012, card 4111 1111 1111 1111 - what is the max LTV for a home loan of Rs 50 lakh?")

def test_mask_all_types():
    m, found = mask(Q)
    assert not any(r in m for r in RAW)
    assert sorted(set(found)) == ["BANK_ACCOUNT", "CREDIT_CARD", "EMAIL_ADDRESS", "IN_AADHAAR", "IN_PAN", "PHONE_NUMBER"]
    assert "Rs 50 lakh" in m and "home loan" in m                    # the question itself survives

def test_email_masking_needs_no_network(tmp_path):
    """ADR-023: on a machine with an empty tldextract cache, masking an email must not try to download the Public
    Suffix List. Runs in a fresh process with HOME / cache dirs pointed at an empty folder and sockets blocked."""
    import os, subprocess, sys
    code = ("import socket\n"
            "def no_net(*a, **k): raise RuntimeError('network call attempted')\n"
            "socket.getaddrinfo = no_net; socket.create_connection = no_net\n"
            "from app.pii import mask\n"
            "m, found = mask('email ramesh@example.co.in about the KFS')\n"
            "assert found == ['EMAIL_ADDRESS'] and 'ramesh' not in m, (m, found)\n")
    env = {**os.environ, "HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "XDG_CACHE_HOME": str(tmp_path),
           "TLDEXTRACT_CACHE": str(tmp_path / "tld")}
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]

def test_aadhaar_typo_masked_by_context_only():
    assert mask("Aadhaar 2345 6789 0123")[0] == "Aadhaar <IN_AADHAAR>"   # checksum fails, but next to "Aadhaar"
    assert mask("a loan of 234567890123 rupees")[1] == []                # 12 digits without context: left alone

@pytest.mark.parametrize("q", ["Rs 50,00,000 for 240 months at 8.5%", "FOIR 55% on Rs 1,00,000 NMI",
                               "KFS valid for 3 working days", "CF para 219G and RBC 353", "DB-LAP-009 tenure 3 to 15 years"])
def test_no_false_alarms(q):
    assert mask(q) == (q, [])

def test_golden_questions_untouched():
    rows = [json.loads(l) for l in open("eval/golden_v2.jsonl", encoding="utf-8")]
    assert [r["id"] for r in rows if mask(r["question"])[1]] == []

def test_answer_path_masks_before_search_model_and_log(monkeypatch, tmp_path):
    import app.generate as gen
    from app import policy_versions as pv
    pv.registry()                                           # load policy files before leaving the repo folder
    seen = {}
    def fake_search(q, k, **kw):
        seen["search"] = q
        return {"rows": [], "as_on": pv.to_date("2027-01-02"), "mode": "vector", "products": ("home_loan",),
                "product_source": "detected", "layers": ("rbi",), "policy_status": [], "notices": []}
    def fake_ask(model, results, q, hits, retry_note=None):
        seen["model"] = q
        return NS(usage=NS(input_tokens=10, output_tokens=5), stop_reason="end_turn"), gen.REFUSAL, []
    monkeypatch.setattr(gen, "search", fake_search); monkeypatch.setattr(gen, "_ask", fake_ask)
    monkeypatch.chdir(tmp_path)                             # audit record goes to a temp folder, not logs/
    text, cites, rec = gen.answer(Q)
    log = (tmp_path / "logs" / "audit.jsonl").read_text(encoding="utf-8")
    for where in (seen["search"], seen["model"], log):
        assert not any(r in where for r in RAW)
    assert "IN_PAN" in rec["pii_masked"] and "<IN_PAN>" in rec["question"]

def test_api_retrieve_masks(monkeypatch):
    from fastapi.testclient import TestClient
    import app.api as api, app.search as sm
    got, audit = {}, []
    monkeypatch.setattr(sm, "retrieve", lambda q, k, layers, **kw: got.setdefault("q", q) and [])
    monkeypatch.setattr(api, "_audit", audit.append)
    b = TestClient(api.app).post("/v1/retrieve", json={"query": Q, "as_on": "2027-01-02"}).json()
    assert "IN_PAN" in b["pii_masked"] and not any(r in got["q"] for r in RAW)
    assert not any(r in json.dumps(audit, default=str) for r in RAW)

# --- Week 6 S4 (ADR-021): names and addresses ---------------------------------------------------------------------
def _rows(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]

@pytest.mark.parametrize("path", ["eval/pii_names_v1.jsonl", "eval/pii_names_v1_holdout.jsonl"])
def test_names_and_addresses_masked_traps_kept(path):
    for r in _rows(path):
        m, _ = mask(r["text"])
        for item in r["mask"]:
            # every name and every address part is gone (house numbers are checked as part of their address)
            assert item not in m or item.isdigit(), (r["id"], item, m)
        for item in r["keep"]:
            assert item in m, (r["id"], item, m)

def test_person_and_address_tokens():
    m, found = mask("Customer Ramesh Kumar Sharma, Flat 302, Sai Krupa Apartments, Baner Road, Pune 411045. Max LTV?")
    assert "Ramesh" not in m and "411045" not in m and "Baner" not in m and "Max LTV?" in m
    assert set(found) == {"PERSON", "ADDRESS"}

def test_city_alone_is_not_an_address():
    assert mask("Is the LTV different for a flat in Mumbai versus a flat in Pune?")[1] == []

def test_golden_v2_4_untouched():
    new = [r["id"] for r in _rows("eval/golden_v2_4.jsonl") if {"PERSON", "ADDRESS"} & set(mask(r["question"])[1])]
    assert new == []          # v06/v07 keep their ADR-015 PAN/Aadhaar/phone masks; no name or address anywhere

def test_switches_turn_names_and_addresses_off(monkeypatch):
    q = "Customer Ramesh Sharma of 45 Laxmi Road, Pune 411030 wants a car loan."
    monkeypatch.setenv("PII_NER", "0"); monkeypatch.setenv("PII_ADDRESS", "0")
    assert mask(q) == (q, [])

def test_anurag_set_localities_option_a():   # Week 6 S4b: localities tied to the customer/property masked, city kept
    test_names_and_addresses_masked_traps_kept("eval/pii_names_v1_anurag.jsonl")

@pytest.mark.parametrize("q", ["Can a loan be given for a flat in Lavasa or Amby Valley?",     # no person: generic place
                               "Can he transfer his home loan from HDFC Bank?",               # a bank, not a place
                               "She wants to switch from floating to fixed.",
                               "The customer is from Rs 40 lakh bracket?"])
def test_locality_rule_leaves_these_alone(q):
    assert "ADDRESS" not in mask(q)[1]
