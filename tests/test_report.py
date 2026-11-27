# Week 6 S3: the eval report recomputes scores from rows; they must match what the weekly summaries quote.
import pytest
pytest.importorskip("spacy")
from eval import report as R

def _run(label, ctx):
    f = next(f for l, f, c in R.MILESTONES if l == label and c == ctx)
    return R.rescore(f)["scores"]

def test_week6_rescored_matches_summary():
    s = _run("Week 6", "given")
    assert s["refusal_ok"] == (77, 77) and s["rule_cited"] == (52, 52) and s["cited_ok"] == (28, 29)
    assert s["verdict_ok"] == (1, 1) and s["headline_ok"] == (23, 23)

def test_week5_first_figure_is_23_of_23_not_22():   # the Week 5 summary's 22/22 came from golden_v2_2
    assert _run("Week 5", "given")["headline_ok"] == (23, 23)

def test_notice_is_skipped_before_scoring():         # v01 starts with a code-written "not in force" notice
    t = "Demo Bank's Home Loan policy is not in force on 25 Nov 2026 (v1.0.0 takes effect on 1 Dec 2026), so its rules are not used below.\n\nThe maximum LTV is 80%."
    assert R.model_text(t) == "The maximum LTV is 80%."
