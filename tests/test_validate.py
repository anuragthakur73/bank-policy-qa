# S3 (ADR-014): planted bad answers must be caught; good answers must pass. No model, no network.
import datetime as dt
from app.generate import clause_link, REFUSAL
from app.validate import validate, blocking, named_paras, figures, named_refs

JAN, DEC = dt.date(2027, 1, 2), dt.date(2026, 12, 15)
HL = ("home_loan",)

def pol(rid, ver, product="home_loan", text="Loans above Rs 30 lakh up to Rs 75 lakh: up to 80% of the property cost."):
    path = {"home_loan": {"1.0.0": "home_loan_v1.yaml", "1.1.0": "home_loan_v1_1.yaml"}, "lap": {"1.0.0": "lap_v1.yaml"}}
    return {"layer": "policy", "doc_id": "DEMO-BANK", "clause_no": rid, "rule_id": rid, "product": product,
            "policy_version": ver, "source_url": f"policy/demo_bank/{path[product][ver]}", "text": text}

def rbi(no, text="111. In the case of housing loans above Rs 30 lakh and up to Rs 75 lakh, the LTV ratio shall not exceed 80 per cent."):
    return {"layer": "rbi", "doc_id": "RBI-CB-CREDIT-FAC-2025", "clause_no": no,
            "source_url": "https://rbi.org.in/cf", "text": text}

def cite(h, quote):
    return {"source": clause_link(h), "cited_text": quote, "layer": h["layer"], "rule_id": h.get("rule_id"),
            "clause_no": h["clause_no"], "doc_id": h["doc_id"]}

R009, P111 = pol("DB-HL-009", "1.1.0"), rbi("111")
HITS = [R009, P111]
GOOD = "The maximum LTV is 80% under DB-HL-009, which implements RBI para 111."
GOOD_CITES = [cite(R009, "up to 80% of the property cost"), cite(P111, "the LTV ratio shall not exceed 80 per cent")]

def checks(issues):
    return sorted({i["check"] for i in blocking(issues)})

def test_good_answer_passes():
    assert validate(GOOD, GOOD_CITES, HITS, HL, JAN, "Max LTV for a Rs 50 lakh home loan?") == []

def test_refusal_not_checked():
    assert validate(REFUSAL, [], HITS, HL, JAN) == []

def test_planted_wrong_id():                       # cites something that was never retrieved
    bad = GOOD_CITES + [{"source": "policy/demo_bank/home_loan_v1_1.yaml#DB-HL-099", "cited_text": "x", "layer": None}]
    assert checks(validate(GOOD, bad, HITS, HL, JAN)) == ["cited_not_retrieved"]

def test_planted_quote_not_in_source():
    bad = [cite(R009, "up to 90% of the property cost"), GOOD_CITES[1]]
    assert checks(validate(GOOD, bad, HITS, HL, JAN)) == ["quote_not_in_source"]

def test_planted_wrong_version():                  # v1.1 rule cited for a date when v1.0 is in force
    assert checks(validate(GOOD, GOOD_CITES, HITS, HL, DEC)) == ["version_not_in_force"]

def test_planted_wrong_product_rule():
    r = pol("DB-LAP-007", "1.0.0", "lap", "Residential: 65% up to Rs 1 crore.")
    issues = validate("LTV is 65% under DB-LAP-007.", [cite(r, "65% up to Rs 1 crore")], [r], HL, JAN)
    assert checks(issues) == ["wrong_product"]

def test_planted_housing_para_for_lap():           # d4 (ADR-012)
    issues = validate("RBI caps it at 80% (para 111).", [GOOD_CITES[1]], [P111], ("lap",), DEC)
    assert checks(issues) == ["wrong_product"]

def test_named_retrieved_not_cited_is_warn_with_link():   # p09 / g005 pattern; ADR-017 (g002, p03, 27 Nov)
    text = "No foreclosure charge under DB-HL-017. The rule implements RBI paragraphs 352 and 353."
    r = pol("DB-HL-017", "1.1.0", text="No foreclosure charge on floating-rate home loans to individuals.")
    issues = validate(text, [cite(r, "No foreclosure charge")], [r, rbi("352", "352. x"), rbi("353", "353. y")], HL, JAN)
    assert blocking(issues) == [] and [i["check"] for i in issues] == ["named_retrieved_not_cited"] * 2
    assert [x["label"] for x in named_refs(issues)] == ["RBI CF para 352", "RBI CF para 353"]

def test_named_not_retrieved_still_blocks():        # g002 retry named para 34, p03 retry para 349: not retrieved
    r = pol("DB-HL-017", "1.1.0", text="No foreclosure charge on floating-rate home loans to individuals.")
    issues = validate("No charge under DB-HL-017 (see also para 349 and DB-HL-099).", [cite(r, "No foreclosure charge")],
                      [r], HL, JAN)
    assert [i["detail"] for i in blocking(issues)] == ["names rule DB-HL-099, which is not among the search results",
                                                       "names RBI para 349, which is not among the search results"]
    assert named_refs(issues) == []

def test_named_rule_retrieved_not_cited_is_warn():  # p03 first draft: DB-HL-005 / 007 retrieved, not cited
    a = pol("DB-HL-013", "1.1.0", text="Repo plus 2.60% for scores 750-799.")
    b = pol("DB-HL-007", "1.1.0", text="Minimum score 700.")
    issues = validate("Repo + 2.60% under DB-HL-013; the score meets DB-HL-007.", [cite(a, "Repo plus 2.60%")], [a, b], HL, JAN)
    assert blocking(issues) == [] and named_refs(issues)[0]["label"] == "DB-HL-007"

def test_reference_inside_cited_rule_is_ok():      # l08: DB-LAP-009 text itself mentions DB-LAP-003
    r = pol("DB-LAP-009", "1.0.0", "lap", "LAP is a term loan over 3 to 15 years, within the maturity age in DB-LAP-003.")
    assert validate("Up to 15 years under DB-LAP-009, within DB-LAP-003.", [cite(r, "3 to 15 years")], [r],
                    ("lap",), JAN) == []

def test_planted_wrong_figure_is_warned():
    issues = validate("The maximum LTV is 85% under DB-HL-009 (para 111).", GOOD_CITES, HITS, HL, JAN)
    assert blocking(issues) == [] and [i["detail"] for i in issues] == ["figure 85 is not in the cited sources or the question"]

def test_question_figure_ok_derived_figure_warned():   # 50 is in the question; 40 (= 80% x 50) is worked out
    assert validate(GOOD + " For your Rs 50 lakh loan that is Rs 40 lakh.", GOOD_CITES, HITS, HL, JAN,
                    "Max LTV for a Rs 50 lakh home loan?")[0]["detail"] == "figure 40 is not in the cited sources or the question"

def test_parsers():
    assert named_paras("RBI paragraphs 352 and 353; CF 111; para 4(xxxvi); paras 114-118") == {"352", "353", "111", "4", "114", "118"}
    assert figures("80%, Rs 2,500, 15 working days, 0.75 per cent, DB-HL-009, para 111") == {"80", "2500", "15", "0.75"}

def test_shared_link_mapped_by_index(monkeypatch):   # r04: CF 108 and 109 share a text-fragment link
    import app.generate as gen
    monkeypatch.setattr(gen, "_fragments", lambda: {})  # the old 8-word links (ADR-003); ADR-019 makes them differ
    a = rbi("108", "108. The bank may grant term loans to housing intermediary agencies against the direct loans sanctioned by the latter.")
    b = rbi("109", "109. The bank may grant term loans to housing intermediary agencies against loans to NRIs also.")
    assert clause_link(a) == clause_link(b)        # the collision itself
    c = {**cite(b, "against loans to NRIs also"), "hit_index": 1}
    assert validate("Yes, under para 109.", [c], [a, b], HL, JAN) == []

def test_para_implemented_by_cited_rule_is_warn_only():   # p02, 26 Nov: refused a correct answer before this
    r = pol("DB-HL-010", "1.1.0", text="Stamp duty is added to the cost only where the house costs up to Rs 10 lakh.")
    p113 = {**rbi("113", "113. ... not include stamp duty ... up to Rs 10 lakh"), "traced_from": "DB-HL-010"}
    issues = validate("Yes, under DB-HL-010, which implements RBI para 113.", [cite(r, "up to Rs 10 lakh")], [r, p113], HL, JAN)
    assert blocking(issues) == [] and issues[0]["check"] == "implemented_para_not_cited"
    p44 = rbi("44", "44. gold loan LTV")                         # retrieved by search, not implemented by a cited rule
    issues = validate("Yes, under DB-HL-010; see also para 44.", [cite(r, "up to Rs 10 lakh")], [r, p113, p44], HL, JAN)
    assert blocking(issues) == [] and [i["check"] for i in issues] == ["named_retrieved_not_cited"]   # ADR-017: was blocking
    issues = validate("Yes, under DB-HL-010; see also para 45.", [cite(r, "up to Rs 10 lakh")], [r, p113, p44], HL, JAN)
    assert checks(issues) == ["named_not_retrieved"]

def test_refusal_with_extra_remarks():                    # g010
    from app.generate import is_refusal
    t = REFUSAL + "\n\nTwo related points may help: ..."
    assert is_refusal(t) and not is_refusal("**Home Loan:** Yes.\n\n**LAP:** " + REFUSAL)

def test_uncited_answer_and_leaked_markup_block():       # g001, 26 Nov
    t = 'The maximum LTV is 80%: <span index="10-1">> 2.5 lakh & <= 5 lakh: 80 per cent</span>.'
    assert checks(validate(t, [], HITS, HL, JAN)) == ["citation_markup_in_text", "no_citations"]
    assert "no_citations" not in checks(validate(GOOD, GOOD_CITES, HITS, HL, JAN))
