import json, pathlib, pytest

P = pathlib.Path("data/parsed/credit_facilities.jsonl")

@pytest.mark.skipif(not P.exists(), reason="run the parser first")
def test_parsed_clauses():
    rows = [json.loads(l) for l in P.open(encoding="utf-8")]
    nos = [r["clause_no"] for r in rows]
    assert len(rows) > 50
    assert len(nos) == len(set(nos)), "duplicate clause numbers"
    assert all(len(r["text"]) >= 9 for r in rows)
    p44 = next(r for r in rows if r["clause_no"] == "44")
    assert "LTV" in p44["text"] and "85 per cent" in p44["text"]
    assert all(r["version_as_on"] == "2026-10-01" for r in rows)
