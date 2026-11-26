# Checks an answer against what was retrieved, before staff see it (Week 4 S3, ADR-014).
# Pure functions, no model or network: every check is deterministic and unit-tested.
# severity "fail" -> generate.py retries once, then refuses. severity "warn" -> logged only (figures, until its
# false-alarm rate on golden_v2 is known).
# ADR-017 (27 Nov 2026): a rule ID or RBI para named but not cited is only BLOCKING when it was not retrieved
# (named_not_retrieved). Named, retrieved, not cited -> warn (named_retrieved_not_cited) with a "ref"; the answer
# then gets a code-written "Also named" line linking it. g002 / p03: correct first drafts named a retrieved source
# without citing it; the retry named a source that was NOT retrieved and was refused.
import re
from app import policy_versions as pv
from app.rbi_scope import applies

RULE_ID = re.compile(r"\bDB-[A-Z]+-\d{3}\b")
# "para 111", "paragraph 44", "paras 352 and 353", "paragraphs 114-118", "CF 111", "RBC para 353"
PARA_LIST = re.compile(r"\b(?:para(?:graph)?s?\.?|(?:CF|RBC)(?:\s+paras?\.?)?)\s+"
                       r"((?:\d+[A-Z]{0,2}(?:\([\w]+\))?(?:\s*(?:,|and|&|to|-|–)\s*)?)+)", re.I)
FIGURE = re.compile(r"(?:rs\.?|₹|inr)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:%|per\s*cent|percent|lakh|crore|"
                    r"years?|months?|(?:working\s+)?days?)", re.I)

MARKUP = re.compile(r"<\s*/?\s*(?:span|cite)\b[^>]*>|\bindex=\"\d+-\d+\"", re.I)

def _norm(t: str) -> str:
    return " ".join(str(t or "").replace("**", "").split()).lower()

def named_paras(text: str) -> set[str]:
    out = set()
    for m in PARA_LIST.finditer(text):
        out |= set(re.findall(r"\d+[A-Z]{0,2}", m[1]))
    return out

def figures(text: str) -> set[str]:
    return {(a or b).replace(",", "") for a, b in FIGURE.findall(text) if (a or b).strip(",")}

def _has_number(n: str, text: str) -> bool:
    return re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", text.replace(",", "")) is not None

def validate(text: str, cites: list[dict], hits: list[dict], products, as_on, question: str = "") -> list[dict]:
    """-> list of {check, severity, detail}. Empty = passed. A refusal is not checked."""
    from app.generate import clause_link, REFUSAL
    if text.replace("*", "").strip() == REFUSAL:          # a bare refusal; any extra remarks after it are checked
        return []
    by_source = {clause_link(h): h for h in hits}
    issues = []
    def add(check, severity, detail, ref=None):
        issues.append({"check": check, "severity": severity, "detail": detail, **({"ref": ref} if ref else {})})
    # g001 (26 Nov): the model wrote <span index="10-1">...</span> into the text instead of a real citation
    if MARKUP.search(text):
        add("citation_markup_in_text", "fail", "the answer contains citation markup instead of citations")
    if not cites:
        add("no_citations", "fail", "the answer cites no search result")
    cited_hits = []
    for c in cites:
        i = c.get("hit_index")
        h = hits[i] if isinstance(i, int) and 0 <= i < len(hits) else by_source.get(c.get("source"))
        if not h:
            add("cited_not_retrieved", "fail", f'cites "{c.get("source")}", which was not among the search results')
            continue
        cited_hits.append(h)
        if c.get("cited_text") and _norm(c["cited_text"]) not in _norm(h["text"]):
            add("quote_not_in_source", "fail", f'quote not found in {h.get("rule_id") or h["clause_no"]}')
        if h.get("layer") == "policy":
            cur = pv.in_force(h["product"], as_on)
            if not cur or cur["version"] != h.get("policy_version"):
                add("version_not_in_force", "fail",
                    f'{h["rule_id"]} v{h.get("policy_version")} is not the version in force on {as_on} '
                    f'({"v" + cur["version"] if cur else "none in force"})')
            if products and h["product"] not in products:
                add("wrong_product", "fail", f'{h["rule_id"]} is a {h["product"]} rule; question is about {list(products)}')
        elif not applies(h["doc_id"], h["clause_no"], products):
            add("wrong_product", "fail", f'RBI para {h["clause_no"]} applies only to another product; question is '
                                         f'about {list(products)}')
    cited_rules = {h["rule_id"] for h in cited_hits if h.get("layer") == "policy"}
    # paras that a cited rule implements (its rbi_ref, traced from the policy file - a fact, not a model claim)
    implemented = {str(h["clause_no"]) for h in hits if h.get("traced_from") in cited_rules}
    cited_paras = {str(h["clause_no"]) for h in cited_hits if h.get("layer") != "policy"}
    cited_text_all = " ".join(h["text"] for h in cited_hits)        # a reference inside a cited source counts
    rule_hits = {h["rule_id"]: h for h in hits if h.get("layer") == "policy"}
    def para_hit(p):
        return next((h for h in hits if h.get("layer") != "policy"
                     and (str(h["clause_no"]) == p or re.match(rf"{re.escape(p)}\b", str(h["clause_no"])))), None)
    for rid in sorted(set(RULE_ID.findall(text)) - cited_rules):
        if rid in cited_text_all:
            continue
        if rid in rule_hits:
            add("named_retrieved_not_cited", "warn", f"names rule {rid} (retrieved) without citing it",
                ref=_ref(rule_hits[rid]))
        else:
            add("named_not_retrieved", "fail", f"names rule {rid}, which is not among the search results")
    for p in sorted(named_paras(text)):
        if not any(cp == p or re.match(rf"{re.escape(p)}\b", cp) for cp in cited_paras) and not _has_number(p, cited_text_all):
            h = para_hit(p)
            if p in implemented:   # p02: "DB-HL-010 implements RBI para 113" - rule cited, para retrieved via its trace
                add("implemented_para_not_cited", "warn", f"names RBI para {p} (implemented by a cited rule) without citing it",
                    ref=_ref(h) if h else None)
            elif h:
                add("named_retrieved_not_cited", "warn", f"names RBI para {p} (retrieved) without citing it", ref=_ref(h))
            else:
                add("named_not_retrieved", "fail", f"names RBI para {p}, which is not among the search results")
    sources = cited_text_all + " " + question
    for n in sorted(figures(text)):
        if not _has_number(n, sources):
            add("figure_not_in_sources", "warn", f"figure {n} is not in the cited sources or the question")
    return issues

SHORT = {"RBI-CB-CREDIT-FAC-2025": "CF", "RBI-CB-RBC-2025": "RBC"}

def _ref(h: dict) -> dict:
    from app.generate import clause_link
    label = h["rule_id"] if h.get("layer") == "policy" else f'RBI {SHORT.get(h["doc_id"], h["doc_id"])} para {h["clause_no"]}'
    return {"label": label, "link": clause_link(h)}

def named_refs(issues: list[dict]) -> list[dict]:
    """Sources the answer names that were retrieved but not cited (ADR-017): linked by code, not quoted by the model."""
    out, seen = [], set()
    for i in issues:
        r = i.get("ref")
        if r and i["check"] in ("named_retrieved_not_cited", "implemented_para_not_cited") and r["label"] not in seen:
            seen.add(r["label"]); out.append(r)
    return out

def blocking(issues: list[dict]) -> list[dict]:
    return [i for i in issues if i["severity"] == "fail"]
