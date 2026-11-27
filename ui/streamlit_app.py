# run: streamlit run ui/streamlit_app.py
# Week 4 S5: product selector, "rule as on" date, validation and masking status, feedback buttons, kill switch.
# Week 5 S4 (ADR-018): if the product is unclear, the answer is a question with one button per product.
import datetime, json, os, sys, pathlib, uuid
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import streamlit as st
from app.generate import answer, clause_link
from app.pii import mask
from app.search import search
from app.api import kill_switch_on
from app import policy_versions as pv

PRODUCTS = {"Work out from my question": None, "Home loan": "home_loan", "Loan against property (LAP)": "lap", "Car loan (new cars)": "vehicle_loan"}
PII_NAMES = {"IN_PAN": "PAN", "IN_AADHAAR": "Aadhaar", "PHONE_NUMBER": "phone number", "EMAIL_ADDRESS": "email",
             "BANK_ACCOUNT": "account number", "CREDIT_CARD": "card number", "IN_PASSPORT": "passport",
             "IN_VOTER": "voter ID", "IN_VEHICLE_REGISTRATION": "vehicle number", "IN_GSTIN": "GSTIN",
             "PERSON": "name", "ADDRESS": "address"}

FEEDBACK_LOG = os.environ.get("FEEDBACK_LOG", "logs/feedback.jsonl")   # joins audit.jsonl on request_id

def save_feedback(request_id: str, rating: str, comment: str = ""):
    os.makedirs(os.path.dirname(FEEDBACK_LOG) or ".", exist_ok=True)
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"request_id": request_id, "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                            "rating": rating, "comment": mask(comment)[0]}, ensure_ascii=False) + "\n")

st.set_page_config(page_title="Bank Policy Q&A", page_icon="📘")
st.title("Bank Policy Q&A — preview")
starts = ", ".join(f'{p.replace("_", " ")} from {pv.fmt(vs[0]["effective_from"])}' for p, vs in pv.registry().items())
st.caption(f"Answers from **Demo Bank** policy (a fictional bank; synthetic rules; {starts}) and RBI (Commercial "
           "Banks) Credit Facilities and Responsible Business Conduct Directions, 2025, updated as on 1 Oct 2026. "
           "Check the cited rule and clause before acting. Not legal advice. Do not enter customer details: "
           "PAN, Aadhaar, phone and account numbers, names and addresses are masked, but masking can miss "
           "an unusual name or address.")

with st.form("ask"):
    q = st.text_input("Question", placeholder="e.g. What is the maximum LTV for a home loan of ₹50 lakh?")
    c1, c2 = st.columns(2)
    product = PRODUCTS[c1.selectbox("Product", list(PRODUCTS))]
    as_on = c2.date_input("Rule as on", value=datetime.date.today(), format="DD/MM/YYYY",
                          help="Answers use the Demo Bank policy version in force on this date.")
    asked = st.form_submit_button("Ask")

if asked and q:
    with st.spinner("Searching Demo Bank policy and RBI directions…"):
        if kill_switch_on():          # ADR-013: model off, show the matching rules and clauses only
            mq, pii = mask(q)
            found = search(mq, product=product, as_on=as_on)
            st.session_state["result"] = {"search_only": True, "rows": found["rows"], "notices": found["notices"],
                                          "pii": pii, "request_id": str(uuid.uuid4())}
        else:
            text, cites, rec = answer(q, caller="streamlit", product=product, as_on=as_on)
            st.session_state["result"] = {"search_only": False, "text": text, "cites": cites, "rec": rec,
                                          "q": q, "as_on": as_on}

res = st.session_state.get("result")
if res and not res["search_only"] and res["rec"].get("mode") == "clarify":
    st.info(res["text"])
    opts = res["rec"]["clarify"]["options"]
    cols = st.columns(len(opts))
    for col, o in zip(cols, opts):
        if col.button(o["label"], key=f'clar_{o["value"]}_{res["rec"]["request_id"]}'):
            with st.spinner("Searching Demo Bank policy and RBI directions…"):
                text, cites, rec = answer(res["q"], caller="streamlit", product=o["value"], as_on=res["as_on"])
            rec["clarified_from"] = res["rec"]["request_id"]
            st.session_state["result"] = {"search_only": False, "text": text, "cites": cites, "rec": rec,
                                          "q": res["q"], "as_on": res["as_on"]}
            st.rerun()
    st.caption("Tip: choose the product in the Product box to skip this question.")
    res = None
if res and res["search_only"]:
    st.error("Answer generation is switched off (kill switch). Showing the matching rules and clauses only.")
    for n in res["notices"]:
        st.info(n)
    for h in res["rows"]:
        label = (f'Demo Bank rule {h["rule_id"]} (v{h.get("policy_version")}, fictional)' if h["layer"] == "policy"
                 else f'RBI para {h["clause_no"]}')
        st.markdown(f'**{label}** — [open]({clause_link(h)})\n\n> {h["text"][:300]}')
elif res:
    text, cites, rec = res["text"], res["cites"], res["rec"]
    if rec.get("pii_masked"):
        names = sorted({PII_NAMES.get(x, x) for x in rec["pii_masked"]})
        st.info("Masked before searching: " + ", ".join(names) + ". The question was answered without them.")
    (st.warning if rec["refused"] else st.success)(text)
    action = rec.get("validation", {}).get("action")
    if action == "passed_after_retry":
        st.caption("✔ Citations checked: the first draft failed a check and was rewritten.")
    elif action == "refused_after_retry":
        st.caption("Refused because the citations could not be verified after a retry.")
    elif action == "pass" and not rec["refused"]:
        st.caption("✔ Citations checked.")
    rules = [c for c in cites if c["layer"] == "policy"]
    rbi = [c for c in cites if c["layer"] != "policy"]
    seen = set()
    if rules:
        st.subheader("Demo Bank rule (fictional)")
        for c in rules:
            if c["rule_id"] in seen:
                continue
            seen.add(c["rule_id"])
            st.markdown(f'**{c["rule_id"]}** (policy v{c.get("policy_version")}) — `{c["source"]}`\n\n'
                        f'> {c["cited_text"][:300]}')
    if rbi:
        st.subheader("RBI")
        for c in rbi:
            key = (c["doc_id"], c["clause_no"])
            if key in seen:
                continue
            seen.add(key)
            name = "Credit Facilities" if c["doc_id"] == "RBI-CB-CREDIT-FAC-2025" else "Responsible Business Conduct"
            st.markdown(f'**{name} — para {c["clause_no"]}** — [open highlighted clause]({c["source"]}) · '
                        f'[section]({c["fallback"]})\n\n> {c["cited_text"][:300]}')
        st.caption("If RBI's language page appears, choose English and click the link again.")

    st.divider()
    rid = rec["request_id"]
    if st.session_state.get("rated") == rid:
        st.caption("Thanks — feedback recorded.")
    else:
        st.write("Was this answer right and useful?")
        comment = st.text_input("What was wrong or missing? (optional)", key=f"c_{rid}")
        b1, b2, _ = st.columns([1, 1, 4])
        if b1.button("👍 Yes", key=f"up_{rid}"):
            save_feedback(rid, "up", comment); st.session_state["rated"] = rid; st.rerun()
        if b2.button("👎 No", key=f"down_{rid}"):
            save_feedback(rid, "down", comment); st.session_state["rated"] = rid; st.rerun()
    st.caption(f'as on {pv.fmt(datetime.date.fromisoformat(rec["as_on"]))} · {", ".join(rec["products"])} '
               f'({rec["product_source"]}) · {rec["latency_ms"]/1000:.1f} s · ${rec["cost_usd"]:.5f} · '
               f'model {rec["model"]} · prompt {rec["prompt_version"]} · request {rid[:8]}')
