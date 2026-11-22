# run: streamlit run ui/streamlit_app.py
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import streamlit as st
from app.generate import answer

st.set_page_config(page_title="Bank Policy Q&A", page_icon="📘")
st.title("Bank Policy Q&A — preview")
st.caption("Answers from **Demo Bank**'s home loan policy (a fictional bank; synthetic rules) and RBI "
           "(Commercial Banks) Credit Facilities and Responsible Business Conduct Directions, 2025, updated as "
           "on 1 Oct 2026. Check the cited rule and clause before acting. Not legal advice.")

q = st.text_input("Ask about a Demo Bank home loan rule or an RBI lending rule",
                  placeholder="e.g. What is the maximum LTV for a home loan of ₹50 lakh?")
if q:
    with st.spinner("Searching Demo Bank policy and RBI directions…"):
        text, cites, rec = answer(q, caller="streamlit")
    (st.warning if rec["refused"] else st.success)(text)
    rules = [c for c in cites if c["layer"] == "policy"]
    rbi = [c for c in cites if c["layer"] != "policy"]
    seen = set()
    if rules:
        st.subheader("Demo Bank rule (fictional)")
        for c in rules:
            if c["rule_id"] in seen:
                continue
            seen.add(c["rule_id"])
            st.markdown(f'**{c["rule_id"]}** — `{c["source"]}`\n\n> {c["cited_text"][:300]}')
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
    st.caption(f'{rec["latency_ms"]/1000:.1f} s · ${rec["cost_usd"]:.5f} · '
               f'model {rec["model"]} · prompt {rec["prompt_version"]} · request {rec["request_id"][:8]}')
