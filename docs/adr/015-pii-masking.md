# ADR-015: Mask personal data in questions before search, model and audit log

Date: 26 Nov 2026 · Status: accepted (Week 4 S5)

## Context
Branch staff paste loan-file details into questions ("Customer PAN ..., Aadhaar ..., wants Rs 50 lakh"). A policy
question never needs the identifiers, but today they would be embedded (OpenAI), sent to Claude (Anthropic) and
written to logs/audit.jsonl. DPDP Act 2023: personal data should be processed only as needed for the purpose.
Interview finding (discovery round 1): 7/7 staff may not use outside AI tools - data leaving the bank is the concern.

## Decision
1. `app/pii.py`: Presidio's pattern recognisers, used directly (no spaCy language model download):
   IN_PAN, IN_AADHAAR (checksum), IN_PASSPORT, IN_VOTER, IN_VEHICLE_REGISTRATION, IN_GSTIN, CREDIT_CARD,
   EMAIL_ADDRESS, PHONE_NUMBER (region IN). Plus two context patterns: a 12-digit number next to "Aadhaar"/"UID"
   even when the checksum fails (a typo is still personal data), and 9-18 digits next to "account"/"a/c".
2. The question is masked FIRST in `generate.answer` and in the API (`/v1/retrieve`, `/v1/answer`): the embedding,
   the search, the model and the audit log only see "<IN_PAN>" etc. Audit records the entity types masked, never the
   values. Feedback comments are masked too.
3. Answers are not masked: the model only sees the masked question, so it cannot repeat the customer's data, and
   masking answers would hide real figures from the documents (e.g. a grievance helpline number).
4. PAN is accepted at any score: without the NLP engine Presidio cannot raise PAN's score from context words (0.1),
   and the PAN pattern (5 letters, 4 digits, 1 letter) rarely matches ordinary text.

## Checked
All 51 golden_v2 questions are unchanged by masking (no false alarms on amounts like "Rs 50,00,000", rates, tenures,
"CF para 219G", rule IDs). Unit tests prove the raw values never reach search, model or log.

## Not covered (known gap)
Person names and addresses need an NER model (spaCy en_core_web_lg, ~400 MB, or a hosted service); not added. The
screen tells staff not to enter customer details and that names are not masked. Revisit before any pilot with real
users (build plan Week 7).

## Dependency
presidio-analyzer brings in the spaCy library (not its models). Install: pip install presidio-analyzer.
