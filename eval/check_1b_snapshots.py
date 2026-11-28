# run: python -m eval.check_1b_snapshots --precheck ../loan-precheck      (Week 8 S2, ADR-024; CI: 1b-snapshots.yml)
# Does Project 1B (loan-precheck) still check loan files against the rules THIS repo serves?
# 1B checks files offline against saved copies of GET /v1/rules (loan-precheck/rules_snapshot/). If a policy file
# here changes and 1B's copies are not refreshed, 1B gives wrong results (e.g. F12 shown as a deviation instead of
# Not Eligible). This compares 1B's committed copies with what this repo's /v1 serves now, in-process (FastAPI
# TestClient: no server, no network), using 1B's own check() so both repos mean the same thing by "drift".
# Exit 0: no drift. Exit 1: drift (each difference listed). Exit 2: 1B checkout not usable.
import argparse, importlib.util, os, pathlib, sys
from fastapi.testclient import TestClient

def client_get(app=None):
    """get(path, params) -> JSON, against this repo's API in-process (same answers as uvicorn would give)."""
    if app is None:
        from app.api import app
    c = TestClient(app)
    def get(path, params=None):
        r = c.get(path, params=params)
        r.raise_for_status()
        return r.json()
    return get

def load_1b_check(precheck: pathlib.Path):
    """1B's scripts/snapshot_rules.py (stdlib only), loaded by path: one definition of drift for both repos."""
    p = precheck / "scripts" / "snapshot_rules.py"
    if not p.is_file():
        raise FileNotFoundError(f"{p} not found: is --precheck a loan-precheck checkout?")
    spec = importlib.util.spec_from_file_location("precheck_snapshot_rules", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "check"):
        raise AttributeError(f"{p} has no check(); 1B older than Week 8 S2?")
    return mod

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--precheck", default="../loan-precheck", help="path to a loan-precheck checkout")
    a = ap.parse_args(argv)
    root = pathlib.Path(a.precheck).resolve()
    try:
        mod = load_1b_check(root)
    except (FileNotFoundError, AttributeError) as e:
        print(f"cannot check: {e}")
        return 2
    folder = root / "rules_snapshot"
    problems = mod.check(client_get(), folder)
    files = sorted(folder.glob("*.json"))
    lines = []
    if problems:
        lines.append(f"DRIFT: {len(problems)} difference(s) between loan-precheck/rules_snapshot/ and this repo's /v1/rules")
        lines += [f"  - {x}" for x in problems]
        lines.append("Fix: start this API (uvicorn app.api:app), then in loan-precheck run "
                     "`python -m scripts.snapshot_rules`, the tests and `python -m scripts.live_golden`; commit and "
                     "push the snapshots; re-run this workflow.")
    else:
        lines.append(f"no drift: {len(files)} policy versions in loan-precheck/rules_snapshot/ match this repo's /v1/rules")
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### 1B rule snapshots\n\n```\n" + "\n".join(lines) + "\n```\n")
    return 1 if problems else 0

if __name__ == "__main__":
    sys.exit(main())
