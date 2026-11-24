# run: python -m app.policy_diff policy/demo_bank/home_loan_v1.yaml policy/demo_bank/home_loan_v1_1.yaml [--no-llm]
# "What changed" between two Demo Bank policy versions, as a one-page circular for branches (ADR-008).
#   1. diff()      plain code, rule by rule: added / changed / removed, and which fields changed. This is the truth.
#   2. explain()   Claude (via LangChain ChatAnthropic + structured output) writes, per changed rule, one line on what
#                  changed and one on what branch staff must do differently - from the old and new rule text only.
#   3. verify()    the LLM output must cover exactly the diff's rule IDs, and every number it writes must appear
#                  in that rule's old or new text. Fails -> one retry -> plain-text fallback. Nothing invented ships.
import datetime, json, pathlib, re, sys
import yaml
from pydantic import BaseModel, Field

SUBSTANTIVE = ("rule", "params", "rbi_ref", "scheme_ref", "bank_discretion", "vs_rbi", "section", "title")
MODEL, PROMPT_VERSION = "claude-haiku-5-5", "diff-v1"
PRICE_IN, PRICE_OUT = 0.10, 0.50   # USD per 1M tokens, Claude Haiku 5.5

def norm(x):
    return " ".join(x.split()) if isinstance(x, str) else x

def load(path: str) -> dict:
    pol = yaml.safe_load(open(path, encoding="utf-8"))
    pol["by_id"] = {r["rule_id"]: r for r in pol["rules"]}
    return pol

def basis(r: dict) -> str:
    ref = r.get("rbi_ref") or {}
    if r.get("scheme_ref"):
        return f'Scheme: {r["scheme_ref"].get("scheme", "")}'
    if r.get("bank_discretion") or not ref:
        return "Bank discretion"
    return f'RBI {ref.get("direction")} para {ref.get("para")}'

def diff(old: dict, new: dict) -> list[dict]:
    """Every rule whose substance differs, in the new policy's order (removed rules last)."""
    out = []
    for rid, n in new["by_id"].items():
        o = old["by_id"].get(rid)
        if o is None:
            out.append({"rule_id": rid, "change": "added", "fields": ["rule"], "old": None, "new": n})
            continue
        fields = [f for f in SUBSTANTIVE if norm(o.get(f)) != norm(n.get(f))]
        if fields:
            out.append({"rule_id": rid, "change": "changed", "fields": fields, "old": o, "new": n})
    for rid, o in old["by_id"].items():
        if rid not in new["by_id"]:
            out.append({"rule_id": rid, "change": "removed", "fields": ["rule"], "old": o, "new": None})
    return out

# ---------- LLM explanation (LangChain) ----------
class Item(BaseModel):
    rule_id: str
    what_changed: str = Field(description="One sentence: what the rule now says that it did not say before (or that it was removed). Plain English, figures exactly as in the rule text.")
    staff_action: str = Field(description="One short sentence: what branch / processing staff must now do differently. 'No change in practice' if the change only restates an existing RBI duty.")

class Digest(BaseModel):
    items: list[Item]

SYSTEM = ("You write a change circular for branch lending staff of Demo Bank, a fictional Indian bank. For EACH rule "
          "given, compare OLD and NEW text and write what changed and what staff must do differently. Use ONLY the "
          "rule texts given; do not add conditions, figures or reasons that are not in them. Copy figures exactly. "
          "Return exactly one item per rule_id given, no others.")

def _prompt(changes: list[dict]) -> str:
    blocks = []
    for c in changes:
        o = norm(c["old"]["rule"]) if c["old"] else "(none - new rule)"
        n = norm(c["new"]["rule"]) if c["new"] else "(removed)"
        blocks.append(f'RULE {c["rule_id"]} [{c["change"]}; fields changed: {", ".join(c["fields"])}]\nOLD: {o}\nNEW: {n}')
    return "\n\n".join(blocks)

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
def numbers(text: str) -> set[str]:
    return {m.replace(",", "") for m in NUM.findall(text or "")}

def verify(changes: list[dict], items: list[Item]) -> list[str]:
    """Problems with the LLM output; empty list = OK."""
    problems = []
    want, got = [c["rule_id"] for c in changes], [i.rule_id for i in items]
    if sorted(want) != sorted(got):
        problems.append(f"rule IDs differ: missing {sorted(set(want) - set(got))}, extra {sorted(set(got) - set(want))}")
    src = {c["rule_id"]: numbers(" ".join(filter(None, [norm((c["old"] or {}).get("rule")), norm((c["new"] or {}).get("rule")), c["rule_id"]])))
           for c in changes}
    for i in items:
        extra = numbers(i.what_changed + " " + i.staff_action) - src.get(i.rule_id, set())
        if extra:
            problems.append(f"{i.rule_id}: figures not in the rule text: {sorted(extra)}")
    return problems

def explain(changes: list[dict]) -> tuple[list[Item], dict]:
    from dotenv import load_dotenv; load_dotenv()
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(model=MODEL, max_tokens=4000, output_config={"effort": "low"})
    chain = llm.with_structured_output(Digest, method="json_schema", include_raw=True)
    meta = {"model": MODEL, "prompt_version": PROMPT_VERSION, "attempts": 0, "problems": [], "tokens_in": 0, "tokens_out": 0}
    for _ in range(2):
        meta["attempts"] += 1
        res = chain.invoke([("system", SYSTEM), ("human", _prompt(changes))])
        u = res["raw"].usage_metadata or {}
        meta["tokens_in"] += u.get("input_tokens", 0); meta["tokens_out"] += u.get("output_tokens", 0)
        items = res["parsed"].items if res["parsed"] else []
        problems = verify(changes, items) if res["parsed"] else ["no parsed output"]
        meta["problems"].append(problems)
        if not problems:
            break
    else:
        items = fallback(changes)
        meta["fallback"] = True
    meta["cost_usd"] = round((meta["tokens_in"] * PRICE_IN + meta["tokens_out"] * PRICE_OUT) / 1e6, 6)
    return items, meta

def fallback(changes: list[dict]) -> list[Item]:
    word = {"added": "New rule", "changed": "Changed: " , "removed": "Rule withdrawn"}
    return [Item(rule_id=c["rule_id"],
                 what_changed=(f'{word[c["change"]]}{", ".join(c["fields"]) if c["change"] == "changed" else ""}'
                               f' - read the rule text in the annex.'),
                 staff_action="See the annex.") for c in changes]

# ---------- circular ----------
LABEL = {"added": "New", "changed": "Changed", "removed": "Withdrawn"}
def cell(s: str) -> str:
    return norm(s).replace("|", "/")

def render(old: dict, new: dict, changes: list[dict], items: list[Item], meta: dict) -> str:
    by = {i.rule_id: i for i in items}
    eff = new["effective_from"]
    lines = [
        f'# Demo Bank (fictional) · Circular: Home Loan Policy v{old["policy_version"]} → v{new["policy_version"]}',
        "",
        f'**Effective from:** {eff} · **Prepared:** {datetime.date.today()} · **Status of v{new["policy_version"]}:** {new["status"]}',
        f'**Summary:** {sum(c["change"] == "added" for c in changes)} new, {sum(c["change"] == "changed" for c in changes)} changed, '
        f'{sum(c["change"] == "removed" for c in changes)} withdrawn; {len(new["rules"]) - sum(c["change"] != "removed" for c in changes)} rules unchanged.',
        "",
        "| Rule | | What changed | What staff do differently | Basis |",
        "|---|---|---|---|---|",
    ]
    for c in changes:
        r = c["new"] or c["old"]; i = by[c["rule_id"]]
        lines.append(f'| **{c["rule_id"]}** {cell(r["title"])} | {LABEL[c["change"]]} | {cell(i.what_changed)} | '
                     f'{cell(i.staff_action)} | {basis(r)} |')
    lines += ["", "Questions: Regional Credit Head. Full rule text in the annex; the policy file is the authority.",
              "", "*Demo Bank is fictional; this circular is synthetic, generated from the policy files and "
              f'checked against them (model {meta.get("model", "none")}, {meta.get("prompt_version", "-")}'
              f'{", fallback text" if meta.get("fallback") else ""}).*',
              "", "---", "", "## Annex: new rule text", ""]
    for c in changes:
        r = c["new"] or c["old"]
        lines.append(f'**{c["rule_id"]} {r["title"]}** ({LABEL[c["change"]]}; {basis(r)})  ')
        lines.append(norm(c["new"]["rule"]) if c["new"] else "_Withdrawn._")
        lines.append("")
    return "\n".join(lines)

def main(argv):
    use_llm = "--no-llm" not in argv
    paths = [a for a in argv if not a.startswith("--")]
    old, new = load(paths[0]), load(paths[1])
    changes = diff(old, new)
    items, meta = explain(changes) if use_llm and changes else (fallback(changes), {"fallback": True})
    md = render(old, new, changes, items, meta)
    name = f'home_loan_v{old["policy_version"]}_to_v{new["policy_version"]}'
    pathlib.Path("docs/circulars").mkdir(parents=True, exist_ok=True)
    pathlib.Path(f"docs/circulars/{name}.md").write_text(md, encoding="utf-8")
    report = {"old": paths[0], "new": paths[1], "meta": meta,
              "changes": [{"rule_id": c["rule_id"], "change": c["change"], "fields": c["fields"],
                           **by_item(items, c["rule_id"])} for c in changes]}
    pathlib.Path(f"eval/reports/{datetime.datetime.now():%Y-%m-%d_%H%M}_diff_{name}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(md.split("## Annex")[0]); print("meta:", json.dumps(meta, default=str)); print(f"written: docs/circulars/{name}.md")

def by_item(items, rid):
    i = next(x for x in items if x.rule_id == rid)
    return {"what_changed": i.what_changed, "staff_action": i.staff_action}

if __name__ == "__main__":
    main(sys.argv[1:])
