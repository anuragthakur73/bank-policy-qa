# Offline: the diff must list exactly the v1.1 changes (Session 3 "done when"); the number guard must catch invented figures.
from app.policy_diff import load, diff, verify, Item

OLD, NEW = load("policy/demo_bank/home_loan_v1.yaml"), load("policy/demo_bank/home_loan_v1_1.yaml")
CH = diff(OLD, NEW)

def test_exactly_the_v1_1_changes():
    got = {(c["rule_id"], c["change"]) for c in CH}
    added = {"DB-HL-032", "DB-HL-033", "DB-HL-034"}
    changed = {"DB-HL-001", "DB-HL-002", "DB-HL-003", "DB-HL-004", "DB-HL-017", "DB-HL-018", "DB-HL-025", "DB-HL-028"}
    assert got == {(r, "added") for r in added} | {(r, "changed") for r in changed}

def test_review_fields_are_not_changes():
    # review / review_note / design_basis changed on many rules but are not policy substance
    assert all(set(c["fields"]) <= {"rule", "params", "rbi_ref", "scheme_ref", "bank_discretion", "vs_rbi", "section", "title"} for c in CH)

def test_label_change_detected():
    c = next(c for c in CH if c["rule_id"] == "DB-HL-002")
    assert "vs_rbi" in c["fields"]

def test_verify_catches_missing_extra_and_invented_numbers():
    sub = [c for c in CH if c["rule_id"] in ("DB-HL-004", "DB-HL-032")]
    good = [Item(rule_id="DB-HL-004", what_changed="NPS subscribers now repay by age 70.", staff_action="Accept PRAN statement."),
            Item(rule_id="DB-HL-032", what_changed="Composite loan LTV on combined cost; Rs 44 lakh example.", staff_action="Cap plot part.")]
    assert verify(sub, good) == []
    bad = [Item(rule_id="DB-HL-004", what_changed="NPS subscribers now repay by age 72.", staff_action="-"),
           Item(rule_id="DB-HL-999", what_changed="x", staff_action="y")]
    problems = " ".join(verify(sub, bad))
    assert "missing ['DB-HL-032']" in problems and "DB-HL-999" in problems and "'72'" in problems
