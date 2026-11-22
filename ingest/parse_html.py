# run: python -m ingest.parse_html credit_facilities
import json, re, sys, hashlib, yaml
from bs4 import BeautifulSoup

key = sys.argv[1]
src = yaml.safe_load(open("data/sources.yaml", encoding="utf-8"))["documents"][key]
soup = BeautifulSoup(open(src["raw_path"], encoding="utf-8").read(), "html.parser")
anchor_re = re.compile(r"^C\d")                      # RBI section anchors: "C4" = Chapter IV, "C4D" = its section D
lines, prev, anchor = [], None, None
for el in soup.find_all(["p", "td", "li"]):
    a = el.find("a", id=anchor_re)
    if a: anchor = a["id"]
    t = el.get_text(" ", strip=True)
    if t and t != prev:            # skip empties and nested duplicates
        lines.append((t, anchor)); prev = t

num = re.compile(r"^(\d+[A-Z]*)\.(?:\s+|$)")              # "44.", "60A.", "219Z.", or "4." alone
chapter_re = re.compile(r"^Chapter [IVXLC]+\b")           # "Chapter IV - Lending against ..."
section_re = re.compile(r"^[A-Z]\.(?:\d+)?\s")             # "A. Short Title", "F.3 Period of credit"
inline_num = re.compile(r"\s(\d+[A-Z]*)\.\s")              # heading merged with next para: "F.3 ... 303. The bank"

clauses, cur, chapter, section = [], None, None, None
for t, anchor in lines:
    if chapter_re.match(t) and len(t) < 150:
        chapter, section = t, None; continue
    if section_re.match(t):
        m = inline_num.search(t)
        if m:                                   # split "F.3 Heading 303. text"
            section, t = t[:m.start()].strip(), t[m.start():].strip()
        elif len(t) < 150:
            section = t; continue
    m = num.match(t)
    if m:
        cur = {"clause_no": m.group(1), "chapter": chapter, "section": section,
               "section_anchor": anchor, "text": t}
        clauses.append(cur)
    elif cur:
        cur["text"] += " " + t

meta = {k: src[k] for k in ("doc_id", "title", "issuer", "applies_to", "version_label",
                            "version_as_on", "effective_from", "effective_to", "source_url")}
with open(f"data/parsed/{key}.jsonl", "w", encoding="utf-8") as f:
    for c in clauses:
        c["omitted"] = bool(re.fullmatch(r"\d+[A-Z]*\.\s*(\d+\s*)?\[?\*+\]?", c["text"]))  # "51. *****"
        c.update(meta, content_hash=hashlib.sha256(c["text"].encode("utf-8")).hexdigest()[:12])
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
print(len(clauses), "clauses")
