# Checks an answer against what was retrieved, before staff see it (Week 4 S3, ADR-014).
# Pure functions, no model or network: every check is deterministic and unit-tested.
# severity "fail" -> generate.py retries once, then refuses. severity "warn" -> logged only (figures, until its
# false-alarm rate on golden_v2 is known).
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
    def add(check, severity, detail):
        issues.append({"check": check, "severity": severity, "detail": detail})
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
    for rid in sorted(set(RULE_ID.findall(text)) - cited_rules):
        if rid not in cited_text_all:
            add("named_not_cited", "fail", f"names rule {rid} but does not cite it")
    for p in sorted(named_paras(text)):
        if not any(cp == p or re.match(rf"{re.escape(p)}\b", cp) for cp in cited_paras) and not _has_number(p, cited_text_all):
            if p in implemented:   # p02: "DB-HL-010 implements RBI para 113" - rule cited, para retrieved via its trace
                add("implemented_para_not_cited", "warn", f"names RBI para {p} (implemented by a cited rule) without citing it")
            else:
                add("named_not_cited", "fail", f"names RBI para {p} but does not cite it")
    sources = cited_text_all + " " + question
    for n in sorted(figures(text)):
        if not _has_number(n, sources):
            add("figure_not_in_sources", "warn", f"figure {n} is not in the cited sources or the question")
    return issues

def blocking(issues: list[dict]) -> list[dict]:
    return [i for i in issues if i["severity"] == "fail"]
