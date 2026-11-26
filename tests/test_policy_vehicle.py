# Offline checks on the Demo Bank new-car loan policy v1.0 (format + text/params agree). No API calls.
import pathlib, re, yaml

VL = yaml.safe_load(pathlib.Path("policy/demo_bank/vehicle_loan_v1.yaml").read_text(encoding="utf-8"))
R = {r["rule_id"]: r for r in VL["rules"]}
txt = lambda rid: " ".join(R[rid]["rule"].split())

def test_header_and_ids():
    assert VL["product"] == "vehicle_loan" and VL["synthetic"] is True and VL["status"] == "draft"
    ids = [r["rule_id"] for r in VL["rules"]]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"DB-VL-\d{3}", i) for i in ids)

def test_rbi_bound_rules_have_ref_and_label():
    for r in VL["rules"]:
        if not r["bank_discretion"]:
            assert r.get("rbi_ref") and r["vs_rbi"] in ("equal", "stricter"), r["rule_id"]

def test_cross_references_exist():
    for r in VL["rules"]:
        for ref in re.findall(r"DB-VL-\d{3}", r["rule"]):
            assert ref in R, f'{r["rule_id"]} refers to missing {ref}'

def test_anurag_decisions_27_nov():
    assert R["DB-VL-007"]["params"]["max_finance_pct_of_on_road"] == 0.90 and "90%" in txt("DB-VL-007")
    assert R["DB-VL-003"]["params"]["max_age_at_maturity"] == {"salaried": 65, "self_employed": 70}
    assert R["DB-VL-010"]["params"]["rate_type"] == "fixed" and R["DB-VL-012"]["params"]["rate_type"] == "fixed"

def test_foreclosure_is_fixed_rate_and_on_amount_prepaid():
    # RBC 353(1) bans charges only on floating-rate loans; 353(5): charge on the amount prepaid
    t = txt("DB-VL-012")
    assert "fixed-rate" in t and "floating-rate" in t and "amount prepaid" in t
    assert [s["pct"] for s in R["DB-VL-012"]["params"]["slabs"]] == [0.03, 0.02, 0.0]
    assert all(x in t for x in ("3%", "2%", "24 months")) and "353" in R["DB-VL-012"]["rbi_ref"]["para"]

def test_deviation_floor_consistent():
    assert R["DB-VL-005"]["params"]["deviation_floor"] == 680 and "680 to 699" in txt("DB-VL-020")
