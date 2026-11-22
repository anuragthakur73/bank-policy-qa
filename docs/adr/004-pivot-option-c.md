# ADR-004: Pivot to Option C — bank-policy layer now, head-office user tested in parallel

Date: 22 Nov 2026 · Status: accepted

## Context
Discovery round 1 (7 interviews, likely one bank): all three assumptions failed.
- Frontline lookups are rare (0–3 a week), but 3 of 7 had costly incidents, 2 of them caused by a rule changing.
- Main answer source is the bank's own policy (4/7) or mixed (3/7); never mainly public documents (0/7).
- 7/7 learn of RBI changes only through internal circulars; 7/7 cannot use ChatGPT or outside tools at work.
Full comparison of options A, B and C: https://claude.ai/artifact/2hMoVgznucxEJ2W66mSJN5

## Decision
1. Build a clearly fictional "Demo Bank" product-policy layer (home loan, LAP, vehicle, education) on top of the RBI layer.
   Every bank rule records the RBI clause it implements, or `bank_discretion: true`.
2. Add a bank-vs-RBI conflict check and a "what changed" digest.
3. Test the head-office user (credit policy / compliance / audit) with 2–3 interviews; add an RBI version diff
   for 2–3 directions only if 2 of 3 describe frequent change-tracking pain.
4. Design for bank-hosted deployment (outside tools are banned): model-agnostic, data stays in India.

## Rules
- Synthetic policy is labelled `synthetic: true` and based only on *published* bank material from banks other than
  Union Bank — never on memory of internal circulars.
- The RBI layer, `/retrieve` contract, audit log and evaluation stay as they are; policy is a second collection.

## Consequences
- ~+2 weeks and +20–25 hours; portfolio end moves from 18 Apr to ~2 May 2027.
- 1B pre-check agent checks bank product rules with an RBI trace; Project 2 uses the policy layer as its rule source.
- The per-seat SaaS pricing assumption must be rewritten as a bank licence before Project 3.
