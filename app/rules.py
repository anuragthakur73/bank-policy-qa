# Demo Bank rules by product, rule ID and as-on date (Week 7 S2, ADR-022). For Project 1B's code checks.
# Read from the policy files in policy/demo_bank - never from search, so the answer is the version in force on the
# date (ADR-010), not the rule that happens to rank highest. No network, no model, no index.
# content_hash is computed exactly as ingest/index_policy.py does, so a caller can tell whether a /v1/retrieve chunk
# (which comes from the index) matches the file.
import datetime, hashlib, pathlib
from functools import lru_cache
import yaml
from app import policy_versions as pv
from app.product import of_rule

def doc_id(product: str) -> str:
    return f"DEMO-BANK-{product.upper().replace('_', '-')}-POLICY"        # same as ingest/index_policy.py

def _plain(x):
    """YAML dates -> ISO strings, recursively, so params are plain JSON."""
    if isinstance(x, (datetime.date, datetime.datetime)):
        return x.isoformat()
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_plain(v) for v in x]
    return x

@lru_cache
def _file_rules(path: str) -> dict[str, dict]:
    pol = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    return {r["rule_id"]: r for r in pol["rules"]}

def _row(v: dict, r: dict) -> dict:
    text = " ".join(r["rule"].split())
    return {"id": f'{doc_id(v["product"])}:{r["rule_id"]}@{v["version"]}', "rule_id": r["rule_id"],
            "product": v["product"], "policy_version": v["version"], "policy_status": v["status"],
            "effective_from": v["effective_from"].isoformat(),
            "effective_to": v["effective_to"].isoformat() if v["effective_to"] else None,
            "section": r["section"], "title": r["title"], "text": text, "params": _plain(r.get("params")),
            "bank_discretion": r.get("bank_discretion"), "vs_rbi": r.get("vs_rbi"),
            "rbi_ref": _plain(r.get("rbi_ref")), "review": r.get("review"), "synthetic": True,
            "link": f'{v["path"]}#{r["rule_id"]}',
            "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()}

def in_force(product: str, as_on: datetime.date, section: str | None = None) -> tuple[dict | None, list[dict]]:
    """-> (version in force or None, its rules in file order, optionally one section only)."""
    v = pv.in_force(product, as_on)
    if not v:
        return None, []
    rows = [_row(v, r) for r in _file_rules(v["path"]).values()]
    return v, [r for r in rows if section is None or r["section"] == section]

def get(rule_id: str, as_on: datetime.date) -> tuple[str | None, dict | None, dict | None]:
    """-> (product from the ID prefix, version in force, the rule in that version). Any part can be None."""
    product = of_rule(rule_id)
    if not product:
        return None, None, None
    v = pv.in_force(product, as_on)
    if not v:
        return product, None, None
    r = _file_rules(v["path"]).get(rule_id)
    return product, v, _row(v, r) if r else None

def versions_with(rule_id: str) -> list[str]:
    """Policy versions (any date) that contain the rule - for a helpful 404."""
    product = of_rule(rule_id)
    return [v["version"] for v in pv.registry().get(product, []) if rule_id in _file_rules(v["path"])]
