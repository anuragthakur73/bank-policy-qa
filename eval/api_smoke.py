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

# ---- Week 7 S2 (ADR-022): params on chunks, rules by date, masking
b = c.post("/v1/retrieve", json={"query": "What is the maximum LTV for a home loan of Rs 50 lakh?",
                                 "product": "home_loan", "as_on": "2027-01-02"}).json()
r9 = next((x for x in b["chunks"] if x["rule_id"] == "DB-HL-009"), None)
check("retrieve: DB-HL-009 chunk carries params and rule_section (index has params)",
      r9 and r9["params"] and r9["rule_section"], (r9 or {}).get("params"))

dec = c.get("/v1/rules/DB-HL-030", params={"as_on": "2026-12-15"}).json()["rule"]
jan = c.get("/v1/rules/DB-HL-030", params={"as_on": "2027-01-15"}).json()["rule"]
check("F11: DB-HL-030 is v1.0.0 on 15 Dec 2026 and v1.1.0 on 15 Jan 2027, with different 'allowed'",
      (dec["policy_version"], jan["policy_version"]) == ("1.0.0", "1.1.0")
      and dec["params"]["allowed"] != jan["params"]["allowed"], (dec["params"]["allowed"], jan["params"]["allowed"]))

m = c.post("/v1/mask", json={"text": "Customer Ramesh Sharma, PAN ABCDE1234F, wants Rs 40 lakh"}).json()
check("mask: name and PAN masked, amount kept", "Ramesh" not in m["masked"] and "ABCDE1234F" not in m["masked"]
      and "Rs 40 lakh" in m["masked"], m["masked"])
N = 7

# Index freshness (information, not a check): rules whose indexed text or params differ from the policy file.
# Re-index (python -m ingest.index_policy) when this lists anything - Week 7 S3.
from app.retrieve import _store
st = _store("policy")
indexed = {f'{m.get("doc_id")}:{m.get("rule_id")}@{m.get("policy_version")}': (m.get("content_hash"), m.get("params"))
           for m in ((p.payload or {}).get("metadata") or {} for p in
                     st.client.scroll(st.collection_name, limit=500, with_payload=True)[0])}
stale, missing = [], []
for prod, day in (("home_loan", "2026-12-15"), ("home_loan", "2027-01-15"), ("lap", "2027-01-15"),
                  ("vehicle_loan", "2027-01-15")):
    for r in c.get("/v1/rules", params={"product": prod, "as_on": day}).json()["rules"]:
        if r["id"] not in indexed:
            missing.append(r["id"])
        elif indexed[r["id"]] != (r["content_hash"], r["params"]):
            stale.append(r["id"])
print(f"\n{ok}/{N} API checks passed")
print("Index behind the policy files (text or params changed):", stale or "none")
print("In the files, not in the index:", missing or "none")
