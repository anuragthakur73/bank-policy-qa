# Offline checks on the Demo Bank policy files: no network, no API keys.
import pathlib, yaml
from app.retrieve import paras

POL = pathlib.Path("policy/demo_bank/home_loan_v1.yaml")
FIX = pathlib.Path("policy/demo_bank/conflict_fixtures.yaml")

def load(p=POL):
    return yaml.safe_load(p.read_text(encoding="utf-8"))

def test_header_is_synthetic():
    d = load()
    assert d["synthetic"] is True and d["bank"].startswith("Demo Bank")
    assert d["product"] == "home_loan" and d["rules"]

def test_rule_ids_unique_and_well_formed():
    ids = [r["rule_id"] for r in load()["rules"]]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("DB-HL-") for i in ids)

def test_required_fields():
    for r in load()["rules"]:
        for f in ("section", "title", "rule", "bank_discretion", "vs_rbi", "design_basis", "review"):
            assert f in r, (r["rule_id"], f)
        if not r["bank_discretion"]:
            assert r.get("rbi_ref") or r.get("scheme_ref"), r["rule_id"] + ": needs rbi_ref or scheme_ref"

def test_never_looser_than_rbi():
    assert {r["vs_rbi"] for r in load()["rules"]} <= {"equal", "stricter", "not_applicable"}

def test_ltv_matches_rbi_para_111():
    r = next(r for r in load()["rules"] if r["rule_id"] == "DB-HL-009")
    bands = [(b["max_loan"], b["max_ltv"]) for b in r["params"]["ltv_bands"]]
    assert bands == [(3000000, 0.90), (7500000, 0.80), (None, 0.75)]

def test_fixtures_not_in_policy():
    texts = {" ".join(r["rule"].split()) for r in load()["rules"]}
    assert not any(f["rule"] in texts for f in load(FIX)["fixtures"])

def test_paras_parser():
    assert paras("90, 93, 95") == ["90", "93", "95"]
    assert paras("114-118") == ["114", "115", "116", "117", "118"]
    assert paras("349(3)") == ["349"]
    assert paras("352, 353") == ["352", "353"]
    assert paras(None) == []
