# The LangGraph answer flow (Week 5 S3, ADR-016) against the plain flow. Search, model and validator are faked:
# no network, no API keys, no cost. The point: same inputs -> same answer, citations, validation record and calls.
import pytest
import app.generate as gen
import app.graph as graph
import app.search as search_mod
from tests.test_api import POLICY, _row

class Usage:
    input_tokens, output_tokens = 1000, 100
class Msg:
    usage, stop_reason = Usage(), "end_turn"

FAIL = [{"severity": "fail", "check": "no_citations", "detail": "no citations"}]
WARN = [{"severity": "warn", "check": "figure_not_in_sources", "detail": "figure 20"}]

@pytest.fixture
def fake(monkeypatch, tmp_path):
    """script: list of (answer text, validator issues) per model call."""
    calls = {"model": 0, "retry_notes": []}
    monkeypatch.setattr(search_mod, "retrieve", lambda q, k, layers, **kw: ([POLICY] if "policy" in layers else []) + [_row("rbi")])
    monkeypatch.setattr(gen, "AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.delenv("KILL_SWITCH", raising=False)
    def setup(script):
        calls["model"], calls["retry_notes"] = 0, []
        it_text, it_issues = iter([t for t, _ in script] * 2), iter([i for _, i in script] * 2)
        def ask(model, results, q, hits, retry_note=None):
            calls["model"] += 1; calls["retry_notes"].append(retry_note)
            cite = {"title": "", "source": "s", "hit_index": 0, "fallback": "", "layer": "policy",
                    "doc_id": POLICY["doc_id"], "clause_no": "DB-HL-009", "rule_id": "DB-HL-009",
                    "policy_version": "1.1.0", "cited_text": "80%"}
            return Msg(), next(it_text), [cite]
        fake_validate = lambda *a, **k: next(it_issues)
        monkeypatch.setattr(gen, "_ask", ask)
        monkeypatch.setattr(gen, "validate", fake_validate)
        monkeypatch.setattr(graph, "validate", fake_validate)
        return calls
    return setup

KEYS = ("products", "product_source", "refused", "partly_refused", "cited_rules", "cited_rule_versions", "validation",
        "model_calls", "tokens_in", "tokens_out", "cost_usd", "notices", "answer", "retrieved", "rbi_search", "as_on")

def both(fake, script, **kw):
    out = {}
    for name, fn in (("plain", gen._answer_plain), ("graph", None)):
        calls = fake(script)
        args = dict(q="Max LTV for a home loan of Rs 50 lakh?", k=5, caller="test", layers=("policy", "rbi"),
                    product=kw.get("product", "home_loan"), as_on="2027-01-02")
        res = fn(**args) if fn else graph.run(**args)
        out[name] = (res, dict(calls))
    return out

@pytest.mark.parametrize("case,script,action,n_calls", [
    ("pass", [("80% under DB-HL-009.", [])], "pass", 1),
    ("warn only", [("80% under DB-HL-009.", WARN)], "pass", 1),
    ("retry then pass", [("bad", FAIL), ("80% under DB-HL-009.", [])], "passed_after_retry", 2),
    ("retry then refuse", [("bad", FAIL), ("still bad", FAIL)], "refused_after_retry", 2),
])
def test_graph_matches_plain(fake, case, script, action, n_calls):
    r = both(fake, script)
    (tp, cp, rp), calls_p = r["plain"]
    (tg, cg, rg), calls_g = r["graph"]
    assert tp == tg and cp == cg, case
    assert {k: rp[k] for k in KEYS} == {k: rg[k] for k in KEYS}, case
    assert rg["validation"]["action"] == action and rg["model_calls"] == n_calls
    assert calls_p == calls_g                       # same number of model calls, same retry notes
    assert rp["pipeline"] == "plain" and rg["pipeline"] == "graph"

def test_graph_trace_records_the_path(fake):
    r = both(fake, [("bad", FAIL), ("still bad", FAIL)])
    (text, cites, rec), calls = r["graph"]
    assert rec["graph_trace"] == ["mask", "route", "retrieve", "generate", "validate", "generate", "validate",
                                  "refuse", "finish"]
    assert text == gen.REFUSAL and cites == [] and rec["validation"]["draft_1"] == "bad"
    assert calls["retry_notes"][1] == FAIL          # the retry is told what the check found
    assert rec["graph_route"]["products"] == ["home_loan"] and rec["graph_route"]["in_force"] == ["home_loan"]

def test_validator_log_mode_never_retries(fake, monkeypatch):
    monkeypatch.setattr(gen, "VALIDATOR", "log")
    r = both(fake, [("bad", FAIL)])
    for name in ("plain", "graph"):
        (text, _, rec), calls = r[name]
        assert text == "bad" and rec["model_calls"] == 1 and rec["validation"]["action"] == "flagged", name

def test_kill_switch_is_an_edge(fake, monkeypatch):
    calls = fake([("must not be used", [])])
    monkeypatch.setenv("KILL_SWITCH", "1")
    text, cites, rec = graph.run("Max LTV for a home loan of Rs 50 lakh?", product="home_loan", as_on="2027-01-02")
    assert calls["model"] == 0 and rec["mode"] == "search_only" and rec["graph_trace"] == ["mask", "search_only"]
    assert text == graph.KILL_MESSAGE and cites == [] and rec["cost_usd"] == 0.0 and rec["rows"]

def test_pii_masked_before_anything(fake):
    fake([("80% under DB-HL-009.", [])])
    _, _, rec = graph.run("Customer PAN ABCDE1234F wants a home loan of Rs 50 lakh", product="home_loan",
                          as_on="2027-01-02")
    assert "ABCDE1234F" not in rec["question"] and rec["graph_route"]["pii_masked"]

def test_answer_switch(fake, monkeypatch):
    fake([("80% under DB-HL-009.", [])])
    monkeypatch.setenv("PIPELINE", "graph")
    assert gen.answer("Max LTV for a home loan of Rs 50 lakh?", product="home_loan", as_on="2027-01-02")[2]["pipeline"] == "graph"
    monkeypatch.setenv("PIPELINE", "plain")
    assert gen.answer("Max LTV for a home loan of Rs 50 lakh?", product="home_loan", as_on="2027-01-02")[2]["pipeline"] == "plain"
