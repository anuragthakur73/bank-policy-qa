# S4 (ADR-018): ask which product when it is unclear, instead of answering for every product. No network, no cost.
import json
import pytest
import app.generate as gen
import app.graph as graph
import app.search as search_mod
from app.clarify import needed, other_topic, RBI_ONLY
from tests.test_graph import fake, Msg   # noqa: F401  (fixture reused)

ALL = ["home_loan", "lap", "vehicle_loan"]
POL = ("policy", "rbi")

@pytest.mark.parametrize("q", ["What is the minimum credit score?", "What penal charge applies if an EMI is paid late?",
                               "how much is the stamp duty for a particular document?",
                               "what will be the max age is case of a pensioner under NPS ?"])
def test_asks_when_no_product_and_policy_question(q):
    c = needed(q, None, POL, ALL)
    assert c["missing"] == ["product"] and [o["value"] for o in c["options"]] == ALL + [RBI_ONLY]
    assert "Home Loan" in c["question"] and "Car Loan" in c["question"] and "RBI" in c["question"]

@pytest.mark.parametrize("q,product,layers,live", [
    ("What is the minimum credit score?", "lap", POL, ALL),                         # caller gave the product
    ("What is the minimum credit score for a home loan?", None, POL, ALL),          # named in the question
    ("Home loan vs car loan: which has the longer maximum tenure?", None, POL, ALL),  # two named: answer both
    ("Customer wants a gold loan of Rs 4 lakh. What is the maximum LTV?", None, POL, ALL),  # RBI-only topic
    ("What happens to uncollected penal charges when the account becomes an NPA?", None, POL, ALL),
    ("Does RBI allow penal interest on an overdue EMI?", None, POL, ALL),           # asks what RBI says
    ("What is the minimum credit score?", None, ("rbi",), ALL),                     # RBI-only reply already given
    ("What is the maximum loan amount?", None, POL, ["home_loan"]),                  # one product in force (k05)
    ("What is the maximum loan amount?", None, POL, []),                             # none in force -> RBI only
])
def test_does_not_ask(q, product, layers, live):
    assert needed(q, product, layers, live) is None

def test_other_topics_cover_the_rbi_only_golden_questions():
    for l in open("eval/golden_v2_3.jsonl", encoding="utf-8"):
        r = json.loads(l)
        c = needed(r["question"], None, POL, ALL)
        if r.get("clarify") in ("text_only", "always"):
            assert c, r["id"]
        if r.get("clarify") == "never" and r.get("as_on") is None:
            assert c is None, r["id"]
    assert not other_topic("Can the applicant's grandfather join as a co-applicant?")

def test_graph_asks_without_search_or_model(fake, monkeypatch):
    calls = fake([("must not be used", [])])
    monkeypatch.setattr(search_mod, "retrieve", lambda *a, **k: pytest.fail("no search before the product is known"))
    text, cites, rec = graph.run("What is the minimum credit score?", as_on="2027-01-02")
    assert calls["model"] == 0 and cites == [] and rec["mode"] == "clarify" and rec["cost_usd"] == 0.0
    assert rec["graph_trace"] == ["mask", "route", "clarify"] and text == rec["clarify"]["question"]
    log = [json.loads(l) for l in open(gen.AUDIT_LOG, encoding="utf-8")]
    assert log[-1]["mode"] == "clarify" and log[-1]["request_id"] == rec["request_id"]

def test_reply_answers_for_the_chosen_product(fake):
    fake([("720 under DB-LAP-005.", [])])
    _, _, rec = gen.answer("What is the minimum credit score?", product="lap", as_on="2027-01-02")
    assert rec.get("mode") != "clarify" and rec["products"] == ["lap"] and rec["graph_trace"][-1] == "finish"

def test_rbi_only_reply_drops_the_policy_layer(fake, monkeypatch):
    seen = []
    fake([(gen.REFUSAL, [])])                 # sets a fake search; replaced below to record the layers
    monkeypatch.setattr(search_mod, "retrieve", lambda q, k, layers, **kw: seen.append(layers) or [])
    _, _, rec = gen.answer("how much is the stamp duty for a particular document?", product=RBI_ONLY, as_on="2027-01-02")
    assert seen and all("policy" not in l for l in seen) and rec.get("mode") != "clarify"

def test_pii_masked_in_the_clarify_record(fake):
    fake([("x", [])])
    _, _, rec = graph.run("Customer PAN ABCDE1234F: what is the minimum credit score?", as_on="2027-01-02")
    assert rec["mode"] == "clarify" and "ABCDE1234F" not in rec["question"] and rec["pii_masked"]

def test_clarify_off_switch(fake, monkeypatch):
    fake([("Home Loan: 700. LAP: 720. Car Loan: 700.", [])])
    monkeypatch.setenv("CLARIFY", "0")
    _, _, rec = graph.run("What is the minimum credit score?", as_on="2027-01-02")
    assert rec.get("mode") != "clarify" and rec["model_calls"] == 1
