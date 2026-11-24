# Loan against property (LAP): SBI and ICICI Bank published terms (study, 24 Nov 2026)

Purpose: design input for the fictional Demo Bank LAP policy (policy/demo_bank/lap_v1.yaml). Paraphrased from the
banks' own pages (IDs in data/sources.yaml); aggregator sites were seen but not used as design sources. Terms of
reuse not checked: link only, no reproduced text. Figures can change; re-check before any public claim.

| Topic | SBI (SBI-LAP-S1..S3) | ICICI Bank (ICICI-LAP-S1..S3) |
|---|---|---|
| Nature / end use | Personal-purpose loan; any personal purpose except speculative; undertaking of purpose, no end-use documents | Personal or business needs (business expansion, education, medical, wedding, debt consolidation...); restrictions not stated |
| Borrowers | Employees, professionals, self-employed, IT assessees, NRIs; property in own name or spouse / children / parent / sibling | Salaried, self-employed professionals, business owners, NRIs; co-applicants such as spouse or family |
| Age | Repaid before the eldest borrower turns 70 | Blog: 20-65 salaried, 21-70 self-employed (FAQ silent) |
| Income | Net monthly income at least Rs 25,000 (Rs 3 lakh a year); rental income considered in select cases | Depends on income, property and credit history |
| Amount | Rs 10 lakh to Rs 7.5 crore (S2 page: LTV band up to Rs 5 crore) | No figure on own pages |
| LTV | 65% up to Rs 1 crore; 60% above Rs 1 crore | Up to 75% of market value, by property type |
| Repayment capacity | EMI/NMI 50% / 55% / 60% by annual income band (Rs 3-5 lakh, 5-10 lakh, above 10 lakh) | Not stated |
| Tenure | 5 to 15 years | Up to 15 years (shorter for industrial / special-use) |
| Property | Residential, and select commercial | Residential, commercial or industrial; clear and marketable title |
| Security | Equitable mortgage; for let-out commercial property, assignment of rent + tripartite agreement / POA | Mortgage; bank holds original documents until repayment |
| Rate | Daily reducing balance; rate on separate page | Floating, benchmark-linked |
| Processing fee | 1% of loan, max Rs 50,000, plus tax | Per schedule of charges |
| Prepayment | No prepayment penalties | Disclosed at sanction |
| Variants | - | Overdraft variant; pre-approved / instant LAP; special LTV for doctors |

## RBI points that bind LAP (indexed directions)
- RBI sets **no LTV ceiling** for LAP (the housing-finance LTV in CF 111 does not apply); margins are for the bank's
  Board-approved real-estate policy (CF 88).
- **No advance for purchase of gold** in any form (CF 36) - an end-use exclusion.
- **Prepayment** (RBC 353): no charge on floating-rate loans to individuals, for personal OR business purposes (and
  to MSEs), any source of funds, no lock-in, for loans sanctioned or renewed from 1 Jan 2026.
- **Floating-rate reset options** (RBC 349) for personal loans; **KFS** (RBC 348) for retail and MSME term loans;
  **penal charges** (RBC 351); **release of property documents** within 30 days (RBC 354-359); charges disclosed
  in the application (RBC 327).
- Not indexed, to verify later: priority-sector (MSME) classification of business-purpose LAP (FIDD directions).

## Design choices for Demo Bank (MY INFERENCE, for Anurag's review)
- Stay close to SBI on LTV and income, as the more conservative published policy; no industrial property, no
  overdraft, no NRI (same scope as the home-loan policy).
- Allow business purposes for individuals (as ICICI), since RBC 353(2) already covers them on prepayment.
