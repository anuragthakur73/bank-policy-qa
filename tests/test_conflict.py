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
