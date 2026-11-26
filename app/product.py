# Which Demo Bank product a question is about (Week 4 S1, ADR-009).
# Order: product given by the caller (screen selector / API / loan file) > keywords in the question > unclear.
# Unclear -> search every product, each with its own quota; the answer labels each part by product.
import re

PRODUCTS = ("home_loan", "lap", "vehicle_loan")
NAMES = {"home_loan": "Home Loan", "lap": "Loan Against Property (LAP)", "vehicle_loan": "Car Loan"}
PREFIX = {"DB-HL": "home_loan", "DB-LAP": "lap", "DB-VL": "vehicle_loan"}      # rule ID prefix -> product

_PATTERNS = {
    "lap": [r"\blap\b", r"\bloans? against (?:an? |the |his |her |their |my )?[\w-]*\s?"
            r"(?:property|properties|flat|house|shop|office|premises|building)",
            r"\bmortgage loans?\b", r"\bproperty loans?\b"],
    "home_loan": [r"\bhome[- ]loans?\b", r"\bhousing loans?\b", r"\bcomposite loans?\b",
                  r"\bhome (?:improvement|extension|construction) loans?\b"],
    # Week 5 S2: new-car loan v1.0. Two-wheeler and used-car words also map here, so the answer can say
    # they are not covered (DB-VL-001) instead of borrowing a home-loan or LAP rule.
    "vehicle_loan": [r"\b(?:car|vehicle|auto|motor|four[- ]wheeler|two[- ]wheeler|ev|suv|muv) loans?\b",
                     r"\bloans? (?:to buy|for|to purchase) (?:an? |the |my |his |her |their )?(?:new |used |electric )?"
                     r"(?:car|suv|muv|vehicle|ev|scooter|bike)\b",
                     r"\b(?:new|used|second[- ]hand|electric) cars?\b",          # c10: "finance on a new car"
                     r"\bon[- ]road price\b", r"\bhypothecat\w*", r"\brepossess\w*", r"\bex[- ]showroom\b"],
}

def detect(question: str) -> list[str]:
    """Products named in the question, in PRODUCTS order. Empty list = none named."""
    q = question.lower()
    return [p for p in PRODUCTS if any(re.search(rx, q) for rx in _PATTERNS[p])]

def resolve(question: str, product: str | None = None) -> tuple[tuple[str, ...], str]:
    """-> (products to search, source). source: given | detected | unclear."""
    if product:
        if product not in PRODUCTS:
            raise ValueError(f"product must be one of {PRODUCTS}, got {product!r}")
        return (product,), "given"
    found = detect(question)
    if len(found) == 1:
        return (found[0],), "detected"
    return PRODUCTS, "unclear"          # none named, or two or more named (e.g. "home loan vs LAP")

def of_rule(rule_id: str) -> str | None:
    return PREFIX.get(rule_id.rsplit("-", 1)[0])
