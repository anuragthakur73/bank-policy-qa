# ADR-024 (Week 8 S2): eval/check_1b_snapshots.py - the CI job that keeps Project 1B's saved rules in step with this
# repo. Offline: the API runs in-process; 1B is a stub checkout in tmp_path. The real comparison against a
# loan-precheck checkout runs when ../loan-precheck exists (Anurag's PC) or PRECHECK_REPO points to one.
import json, os, pathlib, textwrap
import pytest
from eval import check_1b_snapshots as C

ROOT = pathlib.Path(__file__).parent.parent

def stub_1b(tmp_path, body):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "rules_snapshot").mkdir()
    (tmp_path / "scripts" / "snapshot_rules.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp_path

def test_in_process_get_serves_health_and_rules():
    get = C.client_get()
    h = get("/v1/health")
    assert h["api"] == "v1" and {"home_loan", "vehicle_loan", "lap"} <= set(h["policies"])
    b = get("/v1/rules", {"product": "home_loan", "as_on": "2027-01-15"})
    assert b["in_force"]["in_force"] == "1.1.0" and any(r["rule_id"] == "DB-HL-030" for r in b["rules"])

def test_uses_1b_check_and_reports_no_drift(tmp_path, capsys):
    p = stub_1b(tmp_path, """
        def check(get, folder):
            assert get("/v1/health")["api"] == "v1" and folder.name == "rules_snapshot"
            return []
    """)
    assert C.main(["--precheck", str(p)]) == 0
    assert capsys.readouterr().out.startswith("no drift:")

def test_drift_exits_1_and_writes_the_step_summary(tmp_path, capsys, monkeypatch):
    p = stub_1b(tmp_path, """
        def check(get, folder):
            return ["home_loan v1.1.0 DB-HL-011: params.foir_bands[1].max_foir 0.55 saved, 0.58 live"]
    """)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert C.main(["--precheck", str(p)]) == 1
    out = capsys.readouterr().out
    assert "DRIFT: 1 difference(s)" in out and "max_foir 0.55 saved, 0.58 live" in out
    assert "python -m scripts.snapshot_rules" in out and "max_foir" in summary.read_text(encoding="utf-8")

def test_not_a_1b_checkout_exits_2(tmp_path, capsys):
    assert C.main(["--precheck", str(tmp_path / "nothing")]) == 2
    assert "not found" in capsys.readouterr().out
    old = stub_1b(tmp_path, "def snapshot(get):\n    return []\n")      # 1B before Week 8 S2: no check()
    assert C.main(["--precheck", str(old)]) == 2
    assert "no check()" in capsys.readouterr().out

def _real_1b():
    for c in (os.environ.get("PRECHECK_REPO"), ROOT.parent / "loan-precheck"):
        if c and (pathlib.Path(c) / "scripts" / "snapshot_rules.py").is_file():
            return pathlib.Path(c)
    return None

@pytest.mark.skipif(_real_1b() is None, reason="no loan-precheck checkout next to this repo (PRECHECK_REPO)")
def test_real_1b_snapshots_match_this_repo():
    mod = C.load_1b_check(_real_1b())
    if not hasattr(mod, "check"):
        pytest.skip("loan-precheck older than Week 8 S2")
    assert mod.check(C.client_get(), _real_1b() / "rules_snapshot") == []
