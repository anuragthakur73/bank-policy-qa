# run: python -m app.conflict [runs]   (every RBI-bound Demo Bank rule + the 5 test fixtures; default 3 runs)
# Bank-vs-RBI conflict check (ADR-006): for each rule, fetch the RBI paragraph(s) it cites (by number, via the
# policy trace) and ask Claude whether the bank rule CONTRADICTS RBI (blocking) and which RBI requirements
# it does not restate (non-blocking coverage list, merged over runs) - conflict-v3, ADR-006.
# Equal-vs-stricter is a human label (vs_rbi in the policy): it flipped between runs in conflict-v1.
# Fixtures are deliberately looser rules: the check must flag all of them.
import collections, datetime, json, os, pathlib, re, sys, time
import yaml
from dotenv import load_dotenv; load_dotenv()
import anthropic
from app.retrieve import trace

PROMPT_VERSION = "conflict-v3"
VERDICTS = {"complies", "looser", "unclear"}
POLICY = "policy/demo_bank/home_loan_v1.yaml"
FIXTURES = "policy/demo_bank/conflict_fixtures.yaml"
PRICE_IN, PRICE_OUT = 0.10, 0.50   # USD per 1M tokens, Claude Haiku 5.5
SYSTEM = ("You check a bank's lending rule against the RBI clause(s) it must comply with. Use ONLY the RBI text "
          "given. Read the bank rule carefully and do not claim it lacks something it states. "
          "VERDICT judges contradiction only: 'looser' = the bank rule permits something the RBI text forbids, "
          "sets a weaker limit, amount or deadline than RBI, or removes or restricts a choice or protection RBI "
          "gives the borrower. A rule that is silent on an RBI requirement is NOT looser: RBI applies to the bank "
          "anyway, so silence 'complies'. Being more restrictive or more protective than RBI also 'complies'. "
          "'unclear' = the RBI text given does not address the rule's subject. "
          "OMISSIONS lists, separately, EVERY RBI requirement in the text given that is relevant to the rule's "
          "subject but not stated in the rule; each as a short phrase with its para, e.g. '349(6) quarterly "
          "statement must be simple'. Empty list if none. Reply with JSON only, no other text: "
          '{"verdict": "complies|looser|unclear", "rbi_para": "<para relied on>", '
          '"reason": "<one sentence quoting the decisive RBI words>", "omissions": ["..."]}')

_client = None
def client():
    global _client
    _client = _client or anthropic.Anthropic()
    return _client

def parse_verdict(text: str) -> dict:
    """First JSON object in the reply; anything malformed becomes 'unclear'."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    v = str(d.get("verdict", "")).strip().lower()
    om = d.get("omissions") or []
    om = [str(x).strip() for x in om if str(x).strip()] if isinstance(om, list) else []
    return {"verdict": v if v in VERDICTS else "unclear",
            "rbi_para": str(d.get("rbi_para", "")), "reason": str(d.get("reason", ""))[:400],
            "omissions": om[:15]}

def check(rule_text: str, rbi_ref: dict) -> dict:
    t0 = time.time()
    tr = trace({"rbi_ref": rbi_ref})
    found = [t for t in tr if t["status"] == "found"]
    if not found:
        return {"verdict": "cannot_check", "rbi_para": "", "trace": [(t["para"], t["status"]) for t in tr],
                "reason": "cited RBI text is not in the index", "omissions": [], "cost_usd": 0.0, "latency_ms": 0}
    rbi = "\n\n".join(f'[{t["direction"]} para {t["para"]}] {t["clause"]["text"]}' for t in found)
    msg = client().messages.create(
        model=os.environ.get("DEFAULT_MODEL", "claude-haiku-5-5"), max_tokens=1500, system=SYSTEM,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": f"RBI TEXT:\n{rbi}\n\nBANK RULE:\n{' '.join(rule_text.split())}"}])
    out = parse_verdict("".join(b.text for b in msg.content if b.type == "text"))
    u = msg.usage
    out.update(trace=[(t["para"], t["status"]) for t in tr],
               cost_usd=round((u.input_tokens * PRICE_IN + u.output_tokens * PRICE_OUT) / 1e6, 6),
               latency_ms=int((time.time() - t0) * 1000))
    return out

def outcome(verdict: str) -> str:
    return {"complies": "pass", "looser": "FLAG"}.get(verdict, "review" if verdict == "unclear" else verdict)

def check_n(rule_text: str, rbi_ref: dict, runs: int) -> dict:
    """Majority verdict over N runs; ties or split votes are reported, never hidden."""
    res = [check(rule_text, rbi_ref) for _ in range(runs)]
    if res[0]["verdict"] == "cannot_check":
        return {**res[0], "votes": {}, "stable": True}
    votes = collections.Counter(r["verdict"] for r in res)
    top, n = votes.most_common(1)[0]
    verdict = top if n > runs / 2 else "unclear"          # no majority -> human review
    pick = next(r for r in res if r["verdict"] == top)
    # coverage list: union over runs, de-duplicated case-insensitively, in first-seen order
    seen, omissions = set(), []
    for r in res:
        for o in r.get("omissions", []):
            if o.lower() not in seen:
                seen.add(o.lower()); omissions.append(o)
    return {**pick, "verdict": verdict, "votes": dict(votes), "stable": len(votes) == 1, "omissions": omissions,
            "cost_usd": round(sum(r["cost_usd"] for r in res), 6),
            "latency_ms": sum(r["latency_ms"] for r in res)}

if __name__ == "__main__":
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    pol = yaml.safe_load(open(POLICY, encoding="utf-8"))
    fix = yaml.safe_load(open(FIXTURES, encoding="utf-8"))
    rows = []
    for r in pol["rules"]:
        if r["bank_discretion"] or not r.get("rbi_ref"):
            continue
        res = check_n(r["rule"], r["rbi_ref"], runs)
        rows.append({"kind": "policy", "id": r["rule_id"], "declared": r["vs_rbi"], **res, "outcome": outcome(res["verdict"])})
    for f in fix["fixtures"]:
        res = check_n(f["rule"], f["rbi_ref"], runs)
        caught = res["verdict"] == "looser" or (f["expect"] == "possible_conflict" and res["verdict"] == "unclear")
        rows.append({"kind": "fixture", "id": f["fixture_id"], "declared": f["expect"], **res,
                     "outcome": "caught" if caught else "MISSED"})
    for x in rows:
        warn = "" if x.get("stable", True) else f'  UNSTABLE {x["votes"]}'
        print(f'{x["outcome"]:<12} {x["id"]:<10} {x["verdict"]:<10} trace {x["trace"]}{warn} | {x["reason"][:80]}')
    pol_rows = [x for x in rows if x["kind"] == "policy"]
    fx_rows = [x for x in rows if x["kind"] == "fixture"]
    summary = {"prompt_version": PROMPT_VERSION, "runs_per_rule": runs,
               "policy_rules_checked": len(pol_rows),
               "policy_outcomes": {o: sum(x["outcome"] == o for x in pol_rows) for o in sorted({x["outcome"] for x in pol_rows})},
               "policy_flagged_looser": [x["id"] for x in pol_rows if x["outcome"] == "FLAG"],
               "unstable": [(x["id"], x["votes"]) for x in rows if not x.get("stable", True)],
               "coverage_gaps_non_blocking": {x["id"]: x["omissions"] for x in pol_rows if x.get("omissions")},
               "fixtures_caught": f'{sum(x["outcome"] == "caught" for x in fx_rows)}/{len(fx_rows)}',
               "total_cost_usd": round(sum(x["cost_usd"] for x in rows), 5)}
    pathlib.Path("eval/reports").mkdir(parents=True, exist_ok=True)
    path = f"eval/reports/{datetime.date.today()}_{PROMPT_VERSION}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "rows": rows}, fh, indent=2, ensure_ascii=False)
    print("\n", json.dumps(summary, indent=1), "\nreport:", path)
