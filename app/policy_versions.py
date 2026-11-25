# Which Demo Bank policy version is in force on a date (Week 4 S2, ADR-010).
# Reads every policy file in policy/demo_bank (files with policy_version + rules). A version is in force from its
# effective_from until the day before the next version of the same product starts; the latest has no end date.
# Decision (Anurag, 25 Nov 2026): before a product's first version starts, its rules are NOT used; the answer says so
# and comes from RBI only. Rules that change in the next version get a deterministic "changes on" note.
import datetime, pathlib
from functools import lru_cache
import yaml
from app.product import NAMES

POLICY_DIR = "policy/demo_bank"
OPEN_END = 99991231

def to_date(x) -> datetime.date:
    return x if isinstance(x, datetime.date) else datetime.date.fromisoformat(str(x))

def date_n(d: datetime.date | None) -> int:
    """2027-01-01 -> 20270101, used for Qdrant integer range filters; None -> open end."""
    return OPEN_END if d is None else d.year * 10000 + d.month * 100 + d.day

def fmt(d: datetime.date) -> str:
    return f"{d.day} {d:%b %Y}"           # '1 Jan 2027' on Windows and Linux alike

def _norm(t: str) -> str:
    return " ".join(str(t).split())

@lru_cache
def registry(policy_dir: str = POLICY_DIR) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for p in sorted(pathlib.Path(policy_dir).glob("*.yaml")):
        pol = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not (isinstance(pol, dict) and pol.get("policy_version") and pol.get("rules")):
            continue                                  # e.g. conflict_fixtures.yaml
        out.setdefault(pol["product"], []).append({
            "path": p.as_posix(), "product": pol["product"], "version": str(pol["policy_version"]),
            "status": pol["status"], "effective_from": to_date(pol["effective_from"]),
            "rules": {r["rule_id"]: _norm(r["rule"]) for r in pol["rules"]},
            "titles": {r["rule_id"]: f'{r["section"]} {r["title"]}' for r in pol["rules"]}})
    for prod, vs in out.items():
        vs.sort(key=lambda v: v["effective_from"])
        starts = [v["effective_from"] for v in vs]
        assert len(set(starts)) == len(starts), f"{prod}: two versions start on the same date"
        for a, b in zip(vs, vs[1:]):
            a["effective_to"] = b["effective_from"] - datetime.timedelta(days=1)
        vs[-1]["effective_to"] = None
    return out

def version(product: str, policy_version: str) -> dict:
    return next(v for v in registry()[product] if v["version"] == str(policy_version))

def in_force(product: str, as_on: datetime.date) -> dict | None:
    for v in registry().get(product, []):
        if v["effective_from"] <= as_on and (v["effective_to"] is None or as_on <= v["effective_to"]):
            return v
    return None

def next_version(product: str, as_on: datetime.date) -> dict | None:
    return next((v for v in registry().get(product, []) if v["effective_from"] > as_on), None)

def status(products, as_on: datetime.date) -> list[dict]:
    out = []
    for p in products:
        cur, nxt = in_force(p, as_on), next_version(p, as_on)
        out.append({"product": p, "in_force": cur["version"] if cur else None,
                    "next": nxt["version"] if nxt else None, "next_status": nxt["status"] if nxt else None,
                    "next_from": nxt["effective_from"].isoformat() if nxt else None})
    return out

def changes_ahead(product: str, as_on: datetime.date, rule_ids) -> list[dict]:
    """Rules of the version in force that change or are withdrawn in the next version."""
    cur, nxt = in_force(product, as_on), next_version(product, as_on)
    if not (cur and nxt):
        return []
    out = []
    for rid in rule_ids:
        if rid not in cur["rules"]:
            continue
        kind = ("withdrawn" if rid not in nxt["rules"]
                else "changes" if nxt["rules"][rid] != cur["rules"][rid] else None)
        if kind:
            out.append({"rule_id": rid, "kind": kind, "version": nxt["version"], "from": nxt["effective_from"],
                        "status": nxt["status"]})
    return out

def notices(products, as_on: datetime.date, cited_rules) -> tuple[list[str], list[str]]:
    """-> (lines to put BEFORE the answer, lines to put AFTER it). Deterministic: no model involved."""
    from app.product import of_rule
    before, after = [], []
    for s in status(products, as_on):
        if s["in_force"] is None and s["next"]:
            when = (f'v{s["next"]} takes effect on' if s["next_status"] == "approved"
                    else f'draft v{s["next"]} is due to take effect on')
            before.append(f'Demo Bank\'s {NAMES[s["product"]]} policy is not in force on {fmt(as_on)} '
                          f'({when} {fmt(to_date(s["next_from"]))}), so its rules are not used below.')
    for p in products:
        for c in changes_ahead(p, as_on, [r for r in cited_rules if of_rule(r) == p]):
            verb = {"changes": "changes", "withdrawn": "is withdrawn"}[c["kind"]]
            if c["status"] != "approved":
                verb = {"changes": "is due to change", "withdrawn": "is due to be withdrawn"}[c["kind"]]
            draft = "" if c["status"] == "approved" else ", draft"
            after.append(f'Note: {c["rule_id"]} {verb} on {fmt(c["from"])} (policy v{c["version"]}{draft}); '
                         f'see the staff circular.')
    return before, after
