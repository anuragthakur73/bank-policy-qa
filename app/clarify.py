# Ask which product a question is about, instead of answering for every product (Week 5 S4, ADR-018).
# Deterministic and free: no model call. Asked only when ALL hold:
#   - the caller gave no product (screen selector / API / loan file) and the question names none (app/product.py);
#     a question naming two products ("home loan vs LAP") is answered for both, as before;
#   - the question is not about a topic Demo Bank policy does not cover, where the answer is RBI's (gold loans, FDs,
#     digital lending, education loans, project finance, cash credit, NPAs, KYC...), and does not ask what RBI says;
#   - the policy layer is in use and at least two products have a version in force on the as-on date (with one, the
#     answer is that product's; with none, it is RBI only).
# Evidence (27 Nov, golden_v2_2, product from text): every multi-product answer (p04-p15, i04) and the unstable i01
# came from questions that pass these tests; all RBI-only questions (g, r) mention such a topic.
import re
from app import product as prod

RBI_ONLY = "rbi_only"          # the reply that means "just the RBI rule"
_OTHER_TOPICS = [
    r"\bgold\b", r"\bjewel(?:le)?ry\b", r"\bsilver\b",
    r"\bfixed deposits?\b", r"\bterm deposits?\b", r"\bdeposit receipts?\b", r"\bfds?\b",
    r"\bdigital (?:loans?|lending)\b", r"\bcooling[- ]off\b",
    r"\beducation loans?\b", r"\bstudents?\b", r"\bpersonal loans?\b", r"\bcredit cards?\b", r"\bmicro ?finance\b",
    r"\bproject financ\w*\b", r"\binfrastructure\b", r"\bbuilders?\b", r"\bdevelopers?\b", r"\bhousing projects?\b",
    r"\bown (?:shares|securities)\b", r"\bshares?\b", r"\bsecurities\b", r"\bdebentures?\b", r"\bmutual funds?\b",
    r"\bcash credit\b", r"\bnbfcs?\b", r"\bexport\w*\b", r"\bpcfc\b", r"\bmsmes?\b", r"\bmses?\b",
    r"\bnpas?\b", r"\bnon[- ]performing\b", r"\bkyc\b",
]
_ASKS_RBI = [r"\brbi\b", r"\breserve bank\b", r"\bmaster directions?\b"]

def other_topic(question: str) -> bool:
    q = question.lower()
    return any(re.search(rx, q) for rx in _OTHER_TOPICS + _ASKS_RBI)

def needed(question: str, product: str | None, layers, live_products) -> dict | None:
    """-> {"missing": ["product"], "question": ..., "options": [...]} or None (answer as usual)."""
    if product or "policy" not in layers or len(live_products) < 2:
        return None
    if prod.detect(question) or other_topic(question):
        return None
    options = [{"value": p, "label": prod.NAMES[p]} for p in live_products] + \
              [{"value": RBI_ONLY, "label": "RBI rule only (no product)"}]
    names = [prod.NAMES[p] for p in live_products]
    text = ("Which product is this about: " + ", ".join(names[:-1]) + " or " + names[-1] +
            "? Or do you only need the RBI rule? Choose one and I will answer for that product.")
    return {"missing": ["product"], "question": text, "options": options}
