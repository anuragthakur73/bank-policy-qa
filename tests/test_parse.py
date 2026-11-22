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

@pytest.mark.skipif(not P.exists(), reason="run the parser first")
def test_definitions_split():
    rows = {json.loads(l)["clause_no"]: json.loads(l) for l in P.open(encoding="utf-8")}
    assert "Consumption Loan" in rows["4(viii)"]["text"]
    assert rows["4(viii)"]["parent_clause"] == "4"
    assert len(rows["4"]["text"]) < 500          # header only; terms are separate records
    assert rows["44"]["chapter"].startswith("Chapter IV")

R = pathlib.Path("data/parsed/responsible_business_conduct.jsonl")

@pytest.mark.skipif(not R.exists(), reason="run the parser on the RBC directions first")
def test_parsed_rbc_has_lending_paras():
    rows = [json.loads(l) for l in R.open(encoding="utf-8")]
    nos = {r["clause_no"] for r in rows}
    # paragraphs Demo Bank rules cite: KFS, reset, penal, prepayment, document return, grievance
    for p in ("346", "348", "349", "351", "352", "353", "354", "355", "358", "359"):
        assert p in nos, f"para {p} missing"
    assert all(r["doc_id"] == "RBI-CB-RBC-2025" for r in rows)
    p353 = next(r for r in rows if r["clause_no"] == "353")
    assert "pre-payment" in p353["text"].lower() or "prepayment" in p353["text"].lower()
