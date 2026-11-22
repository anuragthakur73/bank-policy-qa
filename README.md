# bank-policy-qa

Clause-cited answers to RBI lending-rule questions, for branch, retail-credit and DSA staff at Indian banks.
Every answer cites the exact paragraph of the RBI Master Direction, links to it, and says
"Not covered by the indexed documents." when the documents don't support an answer.

**Current coverage:** RBI (Commercial Banks – Credit Facilities) Directions, 2025, updated as on 1 Oct 2026.
**Current evaluation:** see `eval/reports/` (golden set v0, 10 questions).

## Run
```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; pip install -r requirements.txt
copy .env.example .env   # add your keys
python -m ingest.parse_html credit_facilities   # needs the RBI page saved to data/raw/
python -m ingest.index credit_facilities
streamlit run ui/streamlit_app.py
python -m eval.run_eval
```

## Next
Date-aware answers ("rule as on date X"), KYC Directions, hybrid search + reranking, `/retrieve` API.
Design decisions: `docs/adr/`.
