# Offline: the verdict parser (no API calls).
from app.conflict import parse_verdict, outcome

def test_parse_plain_json():
    v = parse_verdict('{"verdict": "looser", "rbi_para": "111", "reason": "80 per cent cap"}')
    assert v == {"verdict": "looser", "rbi_para": "111", "reason": "80 per cent cap", "omissions": []}

def test_parse_json_inside_text():
    assert parse_verdict('Here: {"verdict": "Complies", "rbi_para": "353", "reason": "x"} done')["verdict"] == "complies"

def test_malformed_becomes_unclear():
    assert parse_verdict("no json here")["verdict"] == "unclear"
    assert parse_verdict('{"verdict": "maybe"}')["verdict"] == "unclear"
    assert parse_verdict('{"verdict": ')["verdict"] == "unclear"

def test_outcome_mapping():
    assert outcome("complies") == "pass"
    assert parse_verdict('{"verdict": "stricter"}')["verdict"] == "unclear"   # v1 labels no longer accepted
    assert outcome("looser") == "FLAG" and outcome("unclear") == "review"
    assert outcome("cannot_check") == "cannot_check"

def test_omissions_parsed_and_cleaned():
    v = parse_verdict('{"verdict": "complies", "rbi_para": "349", "reason": "x", "omissions": ["349(6) simple statement", " ", 7]}')
    assert v["verdict"] == "complies" and v["omissions"] == ["349(6) simple statement", "7"]
    assert parse_verdict('{"verdict": "complies", "omissions": "not a list"}')["omissions"] == []


def test_override_needs_approver_and_only_softens_flag_or_review():
    from app.conflict import apply_override
    ok = {"conflict_override": {"reason": "tenure cap is a credit decision", "approved_by": "Anurag", "date": "2026-11-24"}}
    assert apply_override(ok, "FLAG")[0] == "overridden" and apply_override(ok, "review")[0] == "overridden"
    assert apply_override(ok, "pass") == ("pass", None)
    assert apply_override({"conflict_override": {"reason": "x", "approved_by": None}}, "FLAG")[0] == "FLAG"
    assert apply_override({}, "FLAG")[0] == "FLAG"
