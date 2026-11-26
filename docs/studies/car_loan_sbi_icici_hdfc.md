# New car loans: SBI, ICICI Bank and HDFC Bank published terms (study, 27 Nov 2026)

Purpose: design input for the fictional Demo Bank new-car loan policy (policy/demo_bank/vehicle_loan_v1.yaml).
Paraphrased from the banks' own pages (IDs in data/sources.yaml). BankBazaar pages were seen but not used as design
sources: their SBI figures contradict each other (90%, 85% and 100% of on-road price). Terms of reuse not checked:
link only, no reproduced text. Figures can change; re-check before any public claim.
Scope (Anurag, 27 Nov 2026): new passenger cars only; used cars and two-wheelers later.

| Topic | SBI (SBI-VL-S1) | ICICI Bank (ICICI-VL-S1..S3) | HDFC Bank (HDFC-VL-S1) |
|---|---|---|---|
| Vehicles | New passenger cars, MUVs, SUVs | New car (also used, refinance, loan against car, top-up) | New car; EV variant |
| Finance | Up to 100% of on-road price (registration + insurance included) | Rs 1 lakh up to 100% of on-road price | Up to 100% on-road, selected models |
| Tenure | Up to 7 years | 12 to 84 months | 12 months to 7 years; up to 8 years for EVs |
| Age | 21 to 70 | - | Salaried: from 21, not over 60 at maturity; self-employed: not over 65 at maturity |
| Income | Rs 3 lakh p.a. (co-applicant can be added); agriculture Rs 4 lakh | Depends on income and obligations | Salaried: Rs 3 lakh p.a. incl. spouse/co-applicant; 2 years' work, 1 with current employer |
| Max loan | 48 x net monthly income (salaried); 4 x net profit/taxable income (self-employed); 3 x (agri) | - | - |
| Rate | Daily reducing balance; extra 0.25% off for electric/strong hybrid (SBI blog, Nov 2025) | New car, quarter ended Sep 2026: 8.00% to 11.20%, mean 8.92% | - |
| Processing fee | Separate page (Demo Bank: flat Rs 1,000 + GST, Anurag 27 Nov) | Up to Rs 8,500 + GST; documentation Rs 500; stamp duty at actuals | - |
| Pre-payment | None; no foreclosure charge after 2 years (first 2 years not stated) | Foreclosure 3% (up to 12 months), 2% (13-24), nil after 24; part prepayment 3% up to 24 months, min one EMI | Fixed-rate loans may attract a foreclosure fee (ICICI FAQ wording) |
| Penal | - | 5% + GST p.a. on overdue EMI | - |
| Other | No advance EMI; optional life cover | Margin-money receipt from the dealer before disbursal; RC collection fee; repossession charges at actuals | Co-applicant income allowed |

## RBI points that bind a car loan (indexed RBC directions, updated as on 1 Oct 2026)
- **Pre-payment (RBC 353):** 353(1)-(2) ban charges only on floating-rate loans; 353(5): other loans per the bank's
  approved policy, and for term loans the charge must be on the amount prepaid. Demo Bank's car loans are fixed rate.
- **Disclosure (RBC 327)** of all fees, refund if not disbursed, pre-payment charges and all-in cost; **KFS (RBC 348)**;
  **penal charges (RBC 351)**.
- **Repossession (RBC 450)**: the contract's repossession clause must cover notice period, its waiver, procedure,
  final chance to repay before sale, return of the vehicle and the sale procedure; **recovery agents (RBC 442,
  445, 448)**: authorisation, no calls before 8 a.m. or after 7 p.m., IIBF DRA certificate.
- **Release of documents (RBC 354-359)**: release documents and remove registered charges within 30 days of full
  repayment; Rs 5,000 a day for delay attributable to the bank. For a car, the charge is the hypothecation recorded on
  the RC (MY INFERENCE: the RBC text says "any registry" and does not name the RTO).
- Not indexed: Motor Vehicles Act / CMV Rules (hypothecation entry and its removal).

## Design choices
- Decided by Anurag (27 Nov 2026): fixed rate with a foreclosure fee; 90% of on-road price for every borrower;
  maturity age 65 salaried, 70 self-employed.
- MY INFERENCE, for review: ICICI's foreclosure slabs (applied to part prepayment too, not ICICI's separate 3% up to
  24 months); SBI's income multiples; penal charge 3% p.a. as for home loan and LAP (not ICICI's 5%); 7-year tenure
  for EVs too (Anurag 27 Nov: confirmed, 7 years only); repossession only after 3 overdue EMIs and a 15-day notice.
