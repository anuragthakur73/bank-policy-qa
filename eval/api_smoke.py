# run: python -m eval.api_smoke   (live retrieval through the /v1 API in-process; no Claude call, ~$0.0001)
# Week 4 S4: the contract 1B will call, checked against the real index.
import os
from fastapi.testclient import TestClient
from app.api import app

c = TestClient(app)
ok = 0
def check(name, cond, detail):
    global ok
    ok += bool(cond); print(f'{"PASS" if cond else "FAIL"} {name}\n   {detail}')

b = c.post("/v1/retrieve", json={"query": "What is the maximum LTV for a home loan of Rs 50 lakh?",
                                 "product": "home_loan", "as_on": "2027-01-02"}).json()
pol = [x for x in b["chunks"] if x["source_type"] == "policy"]
check("home loan, as on 2 Jan 2027: v1.1 rules incl. DB-HL-009 traced to CF 111",
      pol and {x["policy_version"] for x in pol} == {"1.1.0"} and any(x["rule_id"] == "DB-HL-009" and
      any(t["chunk_id"] == "RBI-CB-CREDIT-FAC-2025:111" for t in x["trace"]) for x in pol),
      [x["id"] for x in b["chunks"]])

b = c.post("/v1/retrieve", json={"query": "What is the maximum LTV for a home loan of Rs 50 lakh?",
                                 "product": "home_loan", "as_on": "2026-12-15"}).json()
check("home loan, as on 15 Dec 2026: v1.0 rules only", {x["policy_version"] for x in b["chunks"]
                                                         if x["source_type"] == "policy"} == {"1.0.0"},
      [x["id"] for x in b["chunks"] if x["source_type"] == "policy"])

b = c.post("/v1/retrieve", json={"query": "What is the maximum LTV on a loan against a self-occupied flat?",
                                 "product": "lap", "as_on": "2026-12-15"}).json()
check("LAP before it starts: notice, no rules, no housing-finance paras (ADR-012)",
      b["notices"] and all(x["source_type"] == "rbi" and x["rbi_scope"] is None for x in b["chunks"]),
      (b["notices"], [x["id"] for x in b["chunks"]]))

os.environ["KILL_SWITCH"] = "1"
b = c.post("/v1/answer", json={"query": "Can a loan against property be given as an overdraft?",
                               "product": "lap", "as_on": "2027-01-02"}).json()
check("kill switch: search only, DB-LAP-009 among the chunks, no model call",
      b["mode"] == "search_only" and b["answer"] is None and any(x["rule_id"] == "DB-LAP-009" for x in b["chunks"]),
      (b["mode"], b["cost_usd"], [x["id"] for x in b["chunks"]][:5]))
del os.environ["KILL_SWITCH"]
print(f"\n{ok}/4 API checks passed")
