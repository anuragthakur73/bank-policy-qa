# Offline checks on the Demo Bank LAP policy v1.0 (format + text/params agree). No API calls.
import pathlib, re, yaml

LAP = yaml.safe_load(pathlib.Path("policy/demo_bank/lap_v1.yaml").read_text(encoding="utf-8"))
R = {r["rule_id"]: r for r in LAP["rules"]}
txt = lambda rid: " ".join(R[rid]["rule"].split())

def test_header_and_ids():
    assert LAP["product"] == "lap" and LAP["synthetic"] is True
    ids = [r["rule_id"] for r in LAP["rules"]]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"DB-LAP-\d{3}", i) for i in ids)

def test_rbi_bound_rules_have_ref_and_label():
    for r in LAP["rules"]:
        if not r["bank_discretion"]:
            assert r.get("rbi_ref") and r["vs_rbi"] in ("equal", "stricter"), r["rule_id"]

def test_ltv_text_matches_params():
    p = R["DB-LAP-007"]["params"]
    assert [b["max_ltv"] for b in p["residential"]] == [0.65, 0.60] and p["commercial"][0]["max_ltv"] == 0.55
    assert all(x in txt("DB-LAP-007") for x in ("65%", "60%", "55%", "Rs 1 crore"))

def test_cross_references_exist():
    for r in LAP["rules"]:
        for ref in re.findall(r"DB-LAP-\d{3}", r["rule"]):
            assert ref in R, f'{r["rule_id"]} refers to missing {ref}'

def test_prepayment_covers_business_purpose():
    assert "business" in txt("DB-LAP-013") and "353" in R["DB-LAP-013"]["rbi_ref"]["para"]

def test_deviation_score_floor_consistent():
    assert R["DB-LAP-005"]["params"]["deviation_floor"] == 700 and "700 to 719" in txt("DB-LAP-019")
