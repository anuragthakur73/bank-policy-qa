import pytest
from app.product import detect, resolve, of_rule, PRODUCTS

@pytest.mark.parametrize("q,exp", [
    ("What is the maximum LTV on a loan against a self-occupied flat for a loan of Rs 80 lakh?", ["lap"]),
    ("Can a loan against property be given as an overdraft?", ["lap"]),
    ("What is the processing fee on a LAP?", ["lap"]),
    ("Is a mortgage loan allowed for a let-out shop?", ["lap"]),
    ("What is the minimum credit score for a home loan?", ["home_loan"]),
    ("in case of a home loan takeover, the second applicant is a partnership company", ["home_loan"]),
    ("Customer wants a composite loan of Rs 40 lakh to buy a plot", ["home_loan"]),
    ("Is the housing loan LTV different for a plot?", ["home_loan"]),
    ("Can the applicant's grandfather join as a co-applicant?", []),
    ("what will be the max age is case of a pensioner under NPS ?", []),
    ("Is the overlap of two rules a problem?", []),          # 'lap' inside a word must not match
    # Week 5 S2: new-car loan
    ("What is the processing fee on a car loan?", ["vehicle_loan"]),
    ("How much of the on-road price of a new car can we finance?", ["vehicle_loan"]),
    ("Customer wants a loan to buy a new SUV", ["vehicle_loan"]),
    ("What is the maximum finance on a new car?", ["vehicle_loan"]),                   # c10, text run 27 Nov
    ("What is the maximum LTV for a Demo Bank vehicle loan?", ["vehicle_loan"]),       # p17
    ("When can the bank repossess a car if the borrower stops paying EMIs?", ["vehicle_loan"]),
    ("Can we give a two-wheeler loan under the car loan policy?", ["vehicle_loan"]),
    ("Is the car parking space included in the home loan?", ["home_loan"]),   # 'car' alone is not a car loan
    ("Is a credit card outstanding counted in FOIR?", []),                   # 'card' must not match 'car'
    ("Car loan vs home loan: which has the higher processing fee?", ["home_loan", "vehicle_loan"]),
])
def test_detect(q, exp):
    assert detect(q) == exp

def test_resolve_order():
    q = "What is the minimum credit score for a home loan?"
    assert resolve(q, "lap") == (("lap",), "given")               # caller's product wins over the text
    assert resolve(q) == (("home_loan",), "detected")
    assert resolve("Who approves a FOIR deviation?") == (PRODUCTS, "unclear")
    assert resolve("Is the LTV for a home loan higher than for LAP?") == (PRODUCTS, "unclear")
    with pytest.raises(ValueError):
        resolve(q, "gold_loan")

def test_of_rule():
    assert of_rule("DB-HL-032") == "home_loan" and of_rule("DB-LAP-007") == "lap" and of_rule("X-1") is None
    assert of_rule("DB-VL-012") == "vehicle_loan"

def test_first_figure_ignores_ids_and_paras():
    # run_eval calls the API at import time; load only its helper by reading the source
    src = open("eval/run_eval.py", encoding="utf-8").read()
    start, end = src.index("_IGNORE ="), src.index("GOLDEN =")
    ns = {"re": __import__("re")}; exec(src[start:end], ns)
    ff = ns["first_figure"]
    assert ff("The maximum LTV is **75%**, under rule DB-HL-009 (65% for LAP)") == "75"
    assert ff("Under Demo Bank rule DB-LAP-007 (implements para 111), the LTV is 65%.") == "65"
    assert ff("Under RBC 353 a refundable deposit of Rs 2,500 is allowed") == "2500"
    assert ff("Not covered by the indexed documents.") is None
    assert ff("The rule implements RBI paragraphs 352 and 353. Charge is 2%") == "2"

def test_golden_product_context_matches_rules():
    import json
    from app.product import of_rule
    for f in ("eval/golden_v2.jsonl", "eval/golden_v2_2.jsonl"):
        for l in open(f, encoding="utf-8"):
            r = json.loads(l)
            if r.get("expected_rules") and "product" in r:      # v05 has no product: detected from its text
                assert {of_rule(x) for x in r["expected_rules"]} == {r["product"]}, (f, r["id"])

def test_partial_refusal_is_not_a_refusal():
    from app.generate import is_refusal, REFUSAL
    assert is_refusal(REFUSAL) and is_refusal(f"**{REFUSAL}**")
    assert not is_refusal(f"**Home Loan:** Yes, under DB-HL-021.\n\n**LAP:** {REFUSAL}")

def test_first_figure_skips_numbers_from_question():
    src = open("eval/run_eval.py", encoding="utf-8").read()
    ns = {"re": __import__("re")}; exec(src[src.index("_IGNORE ="):src.index("GOLDEN =")], ns)
    q = "Applicant's net monthly income is Rs 80,000. What is the maximum FOIR?"
    assert ns["first_figure"]("For Rs 80,000 net monthly income, the maximum FOIR is 55%.", q) == "55"
