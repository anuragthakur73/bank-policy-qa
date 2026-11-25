import datetime as dt
from types import SimpleNamespace as NS
from app import policy_keyword as pk

D = dt.date(2027, 1, 2)
doc = lambda rid: NS(metadata={"rule_id": rid})

def test_overdraft_found_by_keyword():          # l07: 8th of 20 by vector search
    assert pk.search("Can a loan against property be given as an overdraft?", "lap", D)[0][0] == "DB-LAP-009"

def test_only_rules_in_force():
    assert pk.search("overdraft", "lap", dt.date(2026, 12, 15)) == []            # LAP not in force yet
    assert pk.search("composite loan plot construction", "home_loan", dt.date(2026, 12, 15))[0][0] != "DB-HL-032"
    assert pk.search("composite loan plot construction", "home_loan", D)[0][0] == "DB-HL-032"

def test_merge_adds_keyword_hit_once():
    ranked = [(doc(f"R{i}"), 1 - i / 100) for i in range(1, 21)]
    out = pk.merge(ranked, [("R8", 3.97)], 3)
    assert [d.metadata["rule_id"] for d, _, _ in out] == ["R1", "R2", "R3", "R8"]
    assert out[-1][2] == {"mode": "keyword", "vector_rank": 8, "keyword_rank": 1, "keyword_score": 3.97}
    assert len(pk.merge(ranked, [("R2", 5.0)], 3)) == 3          # already in the top 3: nothing added
    assert len(pk.merge(ranked, [], 3)) == 3                    # no positive keyword score
