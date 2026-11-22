# Discovery interview guide — Project 1A (Bank Policy Q&A)

Version 1 · 22 Nov 2026 · Interviewer: Anurag

## Purpose
Test the three weakest assumptions behind 1A before building more:

| # | Hypothesis | Evidence we need | Go signal (target, my inference) |
|---|---|---|---|
| H1 | Frontline staff look up lending rules often, and it costs time or causes errors | Frequency, minutes per lookup, wrong-rule incidents | ≥ 5 of 8 people: ≥ 3 lookups a week, or a real wrong/outdated-rule incident |
| H2 | Public RBI / government documents answer most of their questions | Real questions, tagged public vs internal policy | ≥ 50% of logged questions answerable from public documents |
| H3 | "The rule as on a past date" matters | Stories of amendments, old sanctions, audits | ≥ 3 of 8 people describe a real date-specific need |

If H2 < 50%: add a clearly labelled *synthetic* bank-policy layer (never real internal policy).

## Who and how many
**8–10 interviews; decide after the first 5, stop when 2 interviews in a row add no new question type.**

| Role | Count | Why |
|---|---|---|
| Branch officer / loan officer (retail assets) | 3 | Primary user |
| RACPC / central processing / credit processor | 2 | Highest rule-lookup volume, file returns |
| DSA executive / DSA owner | 2 | Secondary user; also sources for NBFCs (tests NBFC scope) |
| Credit reviewer, auditor or compliance officer | 1 | Sees the cost of wrong rules |
| Branch manager / regional retail head | 1 (optional) | Buyer view: adoption, approvals, tools allowed |

Mix banks (PSU, private) and cities if you can; at least 2 people outside your own bank.

## Rules
- Ask about **past behaviour**, not opinions ("last time you…", not "would you use…"). Friends are kind; stories are not.
- **No internal documents, circulars, screenshots, customer data or bank names in notes.** Say this at the start.
- Ask permission to take notes; anonymise as I1, I2… Names live only in `notes/interviews/tracker.csv` (gitignored).
- Don't pitch until the last 3 minutes. Talk ≤ 20% of the time.
- Write notes within 1 hour, while it's fresh.

## Script (20 minutes)
**Opening (1 min):** "I'm building a small tool for bank staff who look up RBI lending rules. I want to learn how you do it today. Please don't share anything internal — I only need your experience. OK if I take notes? I won't record your name or bank."

**A. Context (2 min)**
1. What's your role, and which loan products do you handle?
2. Roughly how many files or customers a week?

**B. Last three lookups (8 min) — the core**
3. Think of the last time you had to check a rule or guideline. What exactly was the question? *(write it word for word)*
4. Where did you look? (circular, intranet, senior, WhatsApp group, Google, ChatGPT…)
5. How long did it take? Were you sure of the answer at the end?
6. And the time before that? *(repeat 3–5 for up to 3 lookups)*
7. How many times in a normal week does this happen?

**C. Cost of getting it wrong (3 min)**
8. Has a file come back, a query been raised, or an audit point come up because an old or wrong rule was applied? What happened? *(no names)*
9. When two people give you different answers, how do you settle it?

**D. Rules changing over time (3 min)**
10. When RBI changes a rule, how do you find out? How long until everyone follows the new rule?
11. Have you ever needed the rule as it stood on an earlier date — for example, a loan sanctioned before an amendment, or an audit of an old file?

**E. Sources and tools (2 min)**
12. Of your usual questions, which are answered by RBI or scheme documents, and which only by your bank's own policy?
13. Are tools like ChatGPT allowed at work? Would you be allowed to use an outside tool for this?
14. Would you ask these questions in English, Hindi or another language?

**Close (1 min)**
15. Could you note down the rule questions you look up over one normal day and send them to me? *(the 1-day tally)*
16. Who else should I talk to? *(referrals)*
17. *(Only now, if they ask)* Show the demo and ask: "What would stop you using this?"

## After each interview
1. Fill `notes/interviews/I0X.md` from the template.
2. Add every real question to `notes/interviews/questions.csv`.
3. Update `notes/interviews/tracker.csv`.
4. Add one quote or surprise to `notes/project3.md`.
