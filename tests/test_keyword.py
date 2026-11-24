import pathlib, pytest
from app import keyword

HAS = any(pathlib.Path("data/parsed").glob("*.jsonl"))

def test_tokenize_synonyms():
    assert "ltv" in keyword.tokenize("maximum loan-to-value ratio")
    assert "kfs" in keyword.tokenize("Is the Key Facts Statement valid?")
    assert "the" not in keyword.tokenize("the LTV")

def test_rrf_order():
    f = keyword.rrf([["a", "b", "c"], ["b", "c", "a"]])
    assert max(f, key=f.get) == "b"                      # 1/62 + 1/61 beats 1/61 + 1/63
    assert abs(f["a"] - (1 / 61 + 1 / 63)) < 1e-12

@pytest.mark.skipif(not HAS, reason="run the parser first")
def test_keyword_finds_exact_terms():
    top = lambda q: [m["clause_no"] for m, _ in keyword.search(q, 5)]
    assert "44" in top("What is the maximum LTV for a gold loan of Rs 4 lakh?")
    assert "348" in top("For how long is the Key Facts Statement valid?")

@pytest.mark.skipif(not HAS, reason="run the parser first")
def test_local_clause_lookup():
    assert keyword.clause("RBI-CB-CREDIT-FAC-2025", "44")["clause_text"].startswith("44.")
    assert keyword.clause("RBI-CB-CREDIT-FAC-2025", "no-such") is None
