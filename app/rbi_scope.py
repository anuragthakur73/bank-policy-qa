# Which Demo Bank product an RBI clause is limited to (Week 4, ADR-012).
# Most RBI clauses in the corpus apply to lending generally (KFS, penal charges, pre-payment, ...). Some sections apply
# to one kind of loan only. If such a clause is retrieved for a question about another product, the model may apply
# it anyway: d4 (25 Nov 2026) gave the housing-loan LTV cap (CF para 111, 75%) as the LTV for a LAP.
# Scope only matters once the product is known; questions about no named product keep every clause.
import re

# (doc_id, first para, last para, product it is limited to, label). Paras compared by their leading number.
SCOPES = [
    ("RBI-CB-CREDIT-FAC-2025", 89, 124, "home_loan", "CF Chapter VIII B - Housing Finance"),
]

def scope(doc_id: str, clause_no: str) -> str | None:
    """The product a clause is limited to, or None if it is not limited to one of our products."""
    m = re.match(r"\d+", str(clause_no or ""))
    if not m:
        return None
    n = int(m[0])
    for doc, lo, hi, product, _ in SCOPES:
        if doc == doc_id and lo <= n <= hi:
            return product
    return None

def applies(doc_id: str, clause_no: str, products) -> bool:
    s = scope(doc_id, clause_no)
    return s is None or not products or s in products
