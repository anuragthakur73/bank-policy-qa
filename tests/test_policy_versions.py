import datetime as dt
import pytest
from app import policy_versions as pv
from app.retrieve import policy_filter

D = dt.date

def test_registry_dates():
    hl = pv.registry()["home_loan"]
    assert [v["version"] for v in hl] == ["1.0.0", "1.1.0"]
    assert hl[0]["effective_to"] == D(2026, 12, 31) and hl[1]["effective_to"] is None
    assert pv.registry()["lap"][0]["effective_from"] == D(2027, 1, 1)

@pytest.mark.parametrize("product,day,exp", [
    ("home_loan", D(2026, 11, 30), None), ("home_loan", D(2026, 12, 1), "1.0.0"),
    ("home_loan", D(2026, 12, 31), "1.0.0"), ("home_loan", D(2027, 1, 1), "1.1.0"),
    ("lap", D(2026, 12, 31), None), ("lap", D(2027, 1, 1), "1.0.0")])
def test_in_force_boundaries(product, day, exp):
    v = pv.in_force(product, day)
    assert (v["version"] if v else None) == exp

def test_changes_ahead():
    got = {c["rule_id"]: c["kind"] for c in pv.changes_ahead("home_loan", D(2026, 12, 15),
                                                             ["DB-HL-003", "DB-HL-004", "DB-HL-006", "DB-HL-032"])}
    assert got == {"DB-HL-003": "changes", "DB-HL-004": "changes"}     # 006 unchanged; 032 not in v1.0
    assert pv.changes_ahead("home_loan", D(2027, 1, 2), ["DB-HL-004"]) == []

def test_notices():
    pre, post = pv.notices(("home_loan", "lap"), D(2026, 11, 25), [])
    assert pre[0].startswith("Demo Bank's Home Loan policy is not in force on 25 Nov 2026 (v1.0.0 takes effect on 1 Dec 2026)")
    assert "(draft v1.0.0 is due to take effect on 1 Jan 2027)" in pre[1] and post == []
    pre, post = pv.notices(("home_loan",), D(2026, 12, 15), ["DB-HL-004", "DB-HL-006"])
    assert pre == [] and post == ["Note: DB-HL-004 is due to change on 1 Jan 2027 (policy v1.1.0, draft); see the staff circular."]

def test_policy_filter():
    f = policy_filter("lap", D(2027, 1, 2))
    keys = [(c.key, c.match.value if c.match else None, c.range.lte if c.range else None, c.range.gte if c.range else None)
            for c in f.must]
    assert keys == [("metadata.product", "lap", None, None), ("metadata.effective_from_n", None, 20270102, None),
                    ("metadata.effective_to_n", None, None, 20270102)]
    assert policy_filter() is None

def test_every_version_indexable():
    # each rule in every version gets a non-overlapping window; no two versions of a product in force on one day
    for prod, vs in pv.registry().items():
        for a, b in zip(vs, vs[1:]):
            assert a["effective_to"] < b["effective_from"]
