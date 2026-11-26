# Mask personal data in questions and answers before they reach the model, the search index or the audit log
# (Week 4 S5, ADR-015). DPDP Act 2023: the tool needs no customer identifiers to answer a policy question.
# Presidio pattern recognisers (no spaCy language model needed): IN_PAN, IN_AADHAAR (with checksum), IN_PASSPORT,
# IN_VOTER, IN_VEHICLE_REGISTRATION, IN_GSTIN, CREDIT_CARD, EMAIL_ADDRESS, PHONE_NUMBER (India).
# Plus two custom patterns that need a context word: an Aadhaar-like 12-digit number next to "Aadhaar"/"UID" even if
# its checksum fails (a typo is still personal data), and a bank account number next to "account"/"a/c".
# NOT covered: person names and addresses (need an NER model; see ADR-015).
import re
from functools import lru_cache

CUSTOM = [
    ("IN_AADHAAR", re.compile(r"(?i)\b(?:aadhaa?r|uid(?:ai)?)\b[^\d]{0,15}(\d{4}\s?\d{4}\s?\d{4})\b")),
    ("BANK_ACCOUNT", re.compile(r"(?i)\b(?:a/c|acct|account)\b(?:\s*(?:no\.?|number|num))?\s*[:#-]?\s*(\d{9,18})\b")),
]

@lru_cache
def _recognizers():
    import logging
    logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
    from presidio_analyzer import predefined_recognizers as pr
    rs = [pr.InPanRecognizer(), pr.InAadhaarRecognizer(), pr.InPassportRecognizer(), pr.InVoterRecognizer(),
          pr.InVehicleRegistrationRecognizer(), pr.InGstinRecognizer(), pr.CreditCardRecognizer(),
          pr.EmailRecognizer(), pr.PhoneRecognizer(supported_regions=("IN",))]
    return rs

def find(text: str) -> list[tuple[int, int, str]]:
    """Non-overlapping (start, end, entity) spans, longest first on overlap."""
    spans = []
    for r in _recognizers():
        spans += [(x.start, x.end, x.entity_type) for x in r.analyze(text, r.supported_entities, None) if x.score > 0]
    for ent, rx in CUSTOM:
        spans += [(m.start(1), m.end(1), ent) for m in rx.finditer(text)]
    out = []
    for s, e, ent in sorted(spans, key=lambda x: (x[0], -(x[1] - x[0]))):
        if not out or s >= out[-1][1]:
            out.append((s, e, ent))
    return out

def mask(text: str) -> tuple[str, list[str]]:
    """-> (masked text, entity types found). Raw values are never returned or logged."""
    if not text:
        return text, []
    spans = find(text)
    for s, e, ent in reversed(spans):
        text = text[:s] + f"<{ent}>" + text[e:]
    return text, [ent for _, _, ent in spans]
