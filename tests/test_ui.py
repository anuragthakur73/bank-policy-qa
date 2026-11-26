# S5: the Streamlit screen, driven headless with AppTest. answer() is faked: no network, no cost.
import pytest
st_testing = pytest.importorskip("streamlit.testing.v1")

REC = {"request_id": "req-12345678", "refused": False, "pii_masked": ["IN_PAN"], "validation": {"action": "passed_after_retry"},
       "as_on": "2026-12-15", "products": ["home_loan"], "product_source": "given", "latency_ms": 4200,
       "cost_usd": 0.0012, "model": "claude-haiku-5-5", "prompt_version": "answer-v3"}
CITE = {"layer": "policy", "rule_id": "DB-HL-009", "policy_version": "1.0.0", "source": "policy/demo_bank/home_loan_v1.yaml#DB-HL-009",
        "cited_text": "80% for loans above Rs 30 lakh up to Rs 75 lakh", "doc_id": "DEMO-BANK", "clause_no": "DB-HL-009"}

@pytest.fixture
def app(monkeypatch, tmp_path):
    import app.generate as gen
    calls = []
    def fake_answer(q, **kw):
        calls.append({"q": q, **kw}); return "80% under DB-HL-009.", [CITE], dict(REC)
    monkeypatch.setattr(gen, "answer", fake_answer)
    monkeypatch.delenv("KILL_SWITCH", raising=False)
    at = st_testing.AppTest.from_file("ui/streamlit_app.py", default_timeout=30)
    at.calls = calls
    return at

def test_selector_and_date_reach_answer(app):
    import datetime
    app.run()
    app.text_input[0].input("Max LTV for Rs 50 lakh? PAN ABCDE1234F")
    app.selectbox[0].select("Home loan")
    app.date_input[0].set_value(datetime.date(2026, 12, 15))
    app.button[0].click().run()
    assert app.calls[-1]["product"] == "home_loan" and app.calls[-1]["as_on"] == datetime.date(2026, 12, 15)
    assert any("80% under DB-HL-009" in s.value for s in app.success)
    assert any("Masked before searching: PAN" in i.value for i in app.info)
    assert any("first draft failed a check" in c.value for c in app.caption)
    assert any("policy v1.0.0" in m.value for m in app.markdown)

def test_feedback_written_and_not_reasked(app, monkeypatch, tmp_path):
    import json
    log = tmp_path / "feedback.jsonl"
    monkeypatch.setenv("FEEDBACK_LOG", str(log))   # never write test feedback to logs/
    app.run()
    app.text_input[0].input("Max LTV?"); app.button[0].click().run()
    app.text_input[1].input("cited rule fine, PAN ABCDE1234F")
    [b for b in app.button if b.label.startswith("👍")][0].click().run()
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["rating"] == "up" and rec["request_id"] == "req-12345678" and "ABCDE1234F" not in rec["comment"]
    assert len(app.calls) == 1                     # clicking feedback did not re-ask the model
    assert any("Thanks" in c.value for c in app.caption)
