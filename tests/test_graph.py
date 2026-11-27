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

def test_also_named_line_added_by_code(fake):         # ADR-017: named, retrieved, not cited -> warn + link, no retry
    ref = [{"severity": "warn", "check": "named_retrieved_not_cited", "detail": "names RBI para 39 (retrieved)",
            "ref": {"label": "RBI CF para 39", "link": "https://rbi.org.in/x#39"}}]
    r = both(fake, [("12 months under para 39.", ref)])
    for name in ("plain", "graph"):
        (text, cites, rec), calls = r[name]
        assert calls["model"] == 1 and rec["validation"]["action"] == "pass", name
        assert text.endswith("Also named in this answer (linked by the system, not quoted): RBI CF para 39 (https://rbi.org.in/x#39)")
        assert rec["named_refs"] == [ref[0]["ref"]] and rec["refused"] is False

def test_linked_rule_gets_its_change_notice_but_is_not_counted_as_cited(fake):
    # c07 (27 Nov): a rule the answer names and the system links must get the same "due to change" note as a cited
    # rule; cited_rules still records only what the model cited (ADR-017 option b). DB-HL-004 changes on 1 Jan 2027
    # (home loan v1.1); the model's own citation, DB-HL-009, does not change.
    ref = [{"severity": "warn", "check": "named_retrieved_not_cited", "detail": "names rule DB-HL-004 (retrieved)",
            "ref": {"label": "DB-HL-004", "link": "policy/demo_bank/home_loan_v1.yaml#DB-HL-004", "rule_id": "DB-HL-004"}}]
    args = dict(q="Max age for a pensioner?", k=5, caller="test", layers=("policy", "rbi"), product="home_loan",
                as_on="2026-12-15")
    fake([("70 under DB-HL-004; LTV per DB-HL-009.", ref)])
    text, _, rec = gen._answer_plain(**args)
    assert rec["cited_rules"] == ["DB-HL-009"] and rec["linked_rules"] == ["DB-HL-004"] and rec["linked_rbi"] == []
    assert any(n.startswith("Note: DB-HL-004 is due to change on 1 Jan 2027") for n in rec["notices"])
    assert text.endswith(rec["notices"][-1])
    fake([("70 under DB-HL-004; LTV per DB-HL-009.", [])])     # same answer, no link -> no note for DB-HL-004
    _, _, rec = gen._answer_plain(**args)
    assert rec["linked_rules"] == [] and not any("DB-HL-004" in n for n in rec["notices"])
