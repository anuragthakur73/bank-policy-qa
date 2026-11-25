from app.rbi_scope import scope, applies
CF, RBC = "RBI-CB-CREDIT-FAC-2025", "RBI-CB-RBC-2025"

def test_housing_finance_is_home_loan_only():
    assert scope(CF, "111") == "home_loan" and scope(CF, "89") == "home_loan" and scope(CF, "124") == "home_loan"
    assert scope(CF, "88") is None and scope(CF, "125") is None          # A. real estate general; C. CRE
    assert scope(CF, "44") is None and scope(RBC, "111") is None          # gold loans; same number, other direction
    assert scope(CF, "4(xxxvi)") is None and scope(CF, None) is None

def test_applies():
    assert not applies(CF, "111", ("lap",))                               # d4
    assert applies(CF, "111", ("home_loan",)) and applies(CF, "111", ("home_loan", "lap"))   # unclear keeps it
    assert applies(CF, "111", None) and applies(CF, "111", ())            # product unknown: no filter
    assert applies(RBC, "353", ("lap",))                                  # pre-payment applies to every loan
