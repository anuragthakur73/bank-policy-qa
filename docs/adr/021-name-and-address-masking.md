# ADR-021: Mask person names and postal addresses before search, model and audit log

Date: 28 Nov 2026 · Status: accepted (Week 6 S4) - done-when met offline; live check pending (Windows)

## Context
ADR-015 masked identifiers with fixed patterns (PAN, Aadhaar, phone, account, ...) but not names or addresses, the
two details staff are most likely to type ("Customer Ramesh Sharma of Flat 302, Baner Road, Pune 411045 ...").
Listed as "before any pilot"; Anurag moved it into Week 6. Targets (Anurag, 27 Nov): name recall >= 95%; mask
addresses too; a model download is acceptable. Data must not leave the machine, so no hosted NER service.

## Options compared (eval/pii_ner_compare.py; tuning set eval/pii_names_v1.jsonl, 65 rows; held-out set
eval/pii_names_v1_holdout.jsonl, 45 rows, written after the first round of rules)
| Option | Tuning: names / address parts / traps masked | Held-out (before 2nd-round fixes) | Golden Qs changed | Size |
|---|---|---|---|---|
| ADR-015 patterns only | 1/34 / 1/41 / 0 | - | 0 | - |
| spaCy en_core_web_sm alone | 24/34 / - / 3 | - | 1 | 15 MB |
| spaCy en_core_web_md alone | 30/34 / - / 5 | - | 2 | 55 MB |
| spaCy en_core_web_lg alone | 32/34 / - / 4 | 18/21 / 1/27 / 3 | 1 ("max") | 425 MB |
| md + rules | 31/33 / 39/40 / 1 | 20/21 / 25/27 / 2 | 0 | 55 MB |
| **lg + rules (chosen)** | 33/33 / 39/40 / 0 | **20/21 (95.2%) / 25/27 (92.6%) / 3** | 0 | 425 MB |
| lg + rules after 2nd-round fixes | 33/33 / 40/40 / 0 | 21/21 / 27/27 / 0 (no longer independent) | 0 | 425 MB |
Transformer NER (Hugging Face) and PyTorch could not be downloaded from the Cowork shell, so they were not tested.
"Address parts" are the pieces that must vanish (house number, building, street, locality, PIN).

## Decision
1. `app/pii_ner.py`, called from `app/pii.find()`, so every path that masked before (answer, /v1 API, audit log,
   feedback comments) now also masks names (`<PERSON>`) and addresses (`<ADDRESS>`).
2. Names: spaCy en_core_web_lg PERSON entities, plus rules: honorific (Mr/Smt/Dr/Fr...), role word
   (customer/borrower/applicant/guarantor, "name:"), initials ("R. K. Sharma"), question subject ("Can Baljit Singh
   Dhillon get ..."). Filter: a span with a lending term, occasion or vehicle make (EMI, tenure, branch, Chaturthi,
   Kia, Seltos ...) or only short acronyms is dropped.
3. Addresses: rules only (no NER label fits an Indian postal address): comma / " - " separated runs with at least
   one strong part (Flat/House/Plot/Door/Shop/Villa/Gat/Survey + number, number + street word, PIN after a place
   name). A bare city or state is not masked: it identifies no one and can matter to the answer. A PIN-like number
   after money words ("salary of 450000") is not a PIN.
4. Fails closed: if the spaCy model is missing, masking raises instead of passing a name through.
5. Switches: PII_NER=0 (names off), PII_ADDRESS=0 (addresses off), PII_NER_MODEL (default en_core_web_lg).
6. Answers are still not masked (ADR-015 point 3).

## Checked (offline, 28 Nov)
0 of 77 golden_v2_4 questions get a name or address mask. ~5 ms per question after a one-time ~2 s model load.
Offline tests: 178 passed (UI tests skipped in the Linux shell).

## Limits
- Both test sets were written by Claude; the 95.2% held-out figure is the honest one. Next: a set written by
  Anurag in his own branch style, never used for tuning.
- Rules are tuned to English-script Indian names; Hindi/Marathi script and unusual single names will be missed.
- spaCy model is ~425 MB on disk; CI (Week 7) must download it.

## Consequences
+ Names and addresses no longer reach OpenAI embeddings, Claude or the audit log in the tested forms.
- A missed name still leaks; the screen keeps telling staff not to enter customer details.
