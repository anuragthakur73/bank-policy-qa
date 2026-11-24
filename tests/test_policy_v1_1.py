# Offline checks on policy v1.1 (format + the changes made from interview questions). No API calls.
import pathlib, yaml

V10 = yaml.safe_load(pathlib.Path("policy/demo_bank/home_loan_v1.yaml").read_text(encoding="utf-8"))
V11 = yaml.safe_load(pathlib.Path("policy/demo_bank/home_loan_v1_1.yaml").read_text(encoding="utf-8"))
R = {r["rule_id"]: r for r in V11["rules"]}

def test_header():
    assert V11["policy_version"] == "1.1.0" and V11["synthetic"] is True
    assert str(V11["effective_from"]) > str(V10["effective_from"])

def test_ids_kept_and_unique():
    ids = [r["rule_id"] for r in V11["rules"]]
    assert len(ids) == len(set(ids))
    assert {r["rule_id"] for r in V10["rules"]} <= set(ids), "a v1.0 rule id disappeared (ids are never reused)"

def test_rbi_bound_rules_have_ref_and_label():
    for r in V11["rules"]:
        if not r["bank_discretion"]:
            assert r.get("rbi_ref") or r.get("scheme_ref"), r["rule_id"]
            if r.get("rbi_ref"):                                         # scheme rules are not RBI-checked
                assert r["vs_rbi"] in ("equal", "stricter"), r["rule_id"]

def test_interview_gaps_now_covered():
    assert "composite" in R["DB-HL-032"]["rule"]                       # I02
    assert "NPS" in R["DB-HL-004"]["rule"]                             # I04
    assert "floor" in R["DB-HL-033"]["rule"]                           # I05
    assert "second house" in R["DB-HL-034"]["rule"]                    # I06
    assert "partnership_firm" in R["DB-HL-003"]["params"]["excluded_applicants"]   # I07

def test_composite_example_arithmetic():
    # plot 20 + construction 35 = 55 lakh; 80% band -> 44 lakh; plot part 80% of 20 -> 16 lakh
    assert round(0.80 * 55, 1) == 44.0 and round(0.80 * 20, 1) == 16.0
    assert "Rs 44 lakh" in " ".join(R["DB-HL-032"]["rule"].split())
