# run: streamlit run ui/streamlit_app.py
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import streamlit as st
from app.generate import answer

st.set_page_config(page_title="Bank Policy Q&A", page_icon="📘")
st.title("Bank Policy Q&A — preview")
st.caption("Answers only from RBI (Commercial Banks – Credit Facilities) Directions, 2025, "
           "updated as on 1 Oct 2026. Check the cited clause before acting. Not legal advice.")

q = st.text_input("Ask about an RBI lending rule",
                  placeholder="e.g. What is the maximum LTV for a gold loan of ₹3 lakh?")
if q:
    with st.spinner("Searching the directions…"):
        text, cites, rec = answer(q, caller="streamlit")
    (st.warning if rec["refused"] else st.success)(text)
    if cites:
        st.subheader("Sources")
        seen = set()
        for c in cites:
            if c["clause_no"] in seen:
                continue
            seen.add(c["clause_no"])
            st.markdown(f'**Para {c["clause_no"]}** — [open highlighted clause]({c["source"]}) · '
                        f'[section]({c["fallback"]})\n\n> {c["cited_text"][:300]}')
        st.caption("If RBI's language page appears, choose English and click the link again.")
    st.caption(f'{rec["latency_ms"]/1000:.1f} s · ${rec["cost_usd"]:.5f} · '
               f'model {rec["model"]} · prompt {rec["prompt_version"]} · request {rec["request_id"][:8]}')
