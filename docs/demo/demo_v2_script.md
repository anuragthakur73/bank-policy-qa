# Demo video v2 — script (about 90 seconds)

Record: Streamlit (`streamlit run ui/streamlit_app.py`) + one terminal. 1080p, browser zoom 110%, close other tabs.
Say "Demo Bank is fictional" on screen at least once. Never show .env or API keys.

| # | Time | On screen | Voice-over (say it in your own words) |
|---|---|---|---|
| 1 | 0–8 s | Title card: "Bank Policy Q&A — Demo Bank (fictional) + RBI Directions" | "I interviewed 7 loan officers. None can use ChatGPT at work, and most of their questions are about their bank's own policy, not RBI." |
| 2 | 8–18 s | Streamlit home, caption visible | "So this answers from a bank's policy and the RBI directions behind it. The bank, Demo Bank, is fictional; its 31 rules are written from public SBI and ICICI material." |
| 3 | 18–38 s | Ask: **What is the maximum LTV for a home loan of Rs 50 lakh?** Click the RBI link; para 111 highlights | "Answer first: 80 percent. It names the bank rule, DB-HL-009, and the RBI paragraph it implements, para 111. One click opens RBI's own page at that paragraph." |
| 4 | 38–52 s | Ask: **Customer wants to close his floating-rate home loan after 1 year. Is there a foreclosure charge?** | "No charge. Bank rule DB-HL-017, traced to the RBI conduct directions, para 353." |
| 5 | 52–60 s | Ask a real interview question: **how much is the stamp duty for a particular document?** → "Not covered" | "This is a real question from an interview. Stamp duty is state law and isn't loaded, so it refuses instead of guessing." |
| 6 | 60–78 s | Terminal: `python -m app.conflict`, scroll to `fixtures_caught: 5/5` | "Every bank rule is checked against its RBI paragraph. Its first run caught three real gaps in the policy I had drafted. Five planted non-compliant rules are caught every run." |
| 7 | 78–90 s | Card with results (below) | "Tested on 33 questions, 7 of them real officer questions. About a tenth of a rupee per answer. Next: hybrid search and LAP, vehicle and education policies." |

## Results card (step 7)
- 33-question test set: 26 drafted by me, 7 real loan-officer questions
- Right bank rule found 20/20, cited 16/16 (where scored) · refusals correct 29/29
- Real questions: 3 policy gaps found, nothing invented
- ~$0.001 per answer · 12 s average (speed is the next fix)

## Don'ts
- Don't say "100% accurate": the set is small and mostly written by me.
- Don't name any employer or show real bank documents.
