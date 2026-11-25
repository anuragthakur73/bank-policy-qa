# One place that turns a question + product + as-on date into retrieved rows (Week 4 S4).
# Used by app/generate.py (answers) and app/api.py (/v1/retrieve for 1B and Project 2), so both apply the same
# product (ADR-009), date (ADR-010), keyword-slot (ADR-011) and RBI-scope (ADR-012) rules.
import datetime, os
from app import product as prod, policy_versions as pv
from app.retrieve import retrieve

def search(q: str, k: int = 5, layers=("policy", "rbi"), product: str | None = None, as_on=None,
           k_policy: int = 3, timings: dict | None = None) -> dict:
    as_on = pv.to_date(as_on) if as_on else datetime.date.today()
    mode = os.environ.get("RETRIEVAL_MODE", "vector")
    products, product_source = prod.resolve(q, product)
    live = tuple(p for p in products if pv.in_force(p, as_on))       # products with a version in force
    use_layers = tuple(l for l in layers if l != "policy" or live)    # none in force -> RBI only
    raw = retrieve(q, k, layers=use_layers, k_policy=k_policy, mode=mode, timings=timings, products=live,
                   as_on=as_on, asked_products=products)
    pre, _ = pv.notices(products, as_on, [])
    return {"rows": raw, "as_on": as_on, "products": products, "product_source": product_source,
            "layers": use_layers, "mode": mode, "policy_status": pv.status(products, as_on), "notices": pre}
