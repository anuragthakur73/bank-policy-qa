# run: python -m ingest.link_fragments        (Week 5 S5, ADR-019; offline, reads data/raw + data/parsed)
# Builds data/parsed/link_fragments.json: for every RBI clause, the text-fragment phrase that highlights THAT clause
# on RBI's page. Until now a link used the clause's first 8 words (ADR-003). Two failures, found 27 Nov 2026:
#   1. shared links - 10 groups of clauses start with the same 8 words (CF 108/109, RBC 46/173/351 ...): the browser
#      highlights the first one on the page (r04: a para 109 citation highlighted 108);
#   2. block breaks - on RBI's page a heading line ("38. A bank shall not:") is its own block and "(1) Avail loans..."
#      the next; a text fragment is matched inside one block, so an 8-word phrase running across the break matches
#      nothing and the page just opens at the top (54 clauses).
# Fix: take the phrase from the page's own block for that clause, grow it until it occurs exactly once on the page,
# never crossing a block; if the whole block is not unique, add the para number as a prefix ("38.-,A bank shall
# not:"). Clauses that still cannot be made unique keep the section-anchor link and are listed.
# The output stays in data/parsed/ (gitignored, like the parsed text: RBI terms, ADR-003).
import collections, json, pathlib, re, sys
from bs4 import BeautifulSoup

PAGES = [("data/raw/credit_facilities_2025.html", "data/parsed/credit_facilities.jsonl"),
         ("data/raw/rbc_2025.html", "data/parsed/responsible_business_conduct.jsonl")]
OUT = pathlib.Path("data/parsed/link_fragments.json")
MIN_WORDS = 4
_BLOCKS = ["p", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "div", "blockquote"]

def page_blocks(html: str) -> list[str]:
    """Leaf block elements' text, whitespace-collapsed, in page order (what a text fragment can match within)."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    out = []
    for el in soup.find_all(_BLOCKS):
        if el.find(_BLOCKS + ["table"]):
            continue
        t = " ".join(el.get_text(" ").split())
        if t:
            out.append(t)
    return out

def _lc(s: str) -> str:
    return s.lower()

def label(clause_no: str) -> str:
    """Number as printed before the clause: '108' -> '108.', '4(xiva)' -> '(xiva)'."""
    m = re.match(r"^\d+[A-Z]{0,2}(\(.+\))$", clause_no)
    return m[1].split(")(")[-1].join("()") if m and ")(" in m[1] else (m[1] if m else f"{clause_no}.")

def _key(s: str) -> str:
    """Loose form for LOCATING a block: letters and digits only (hyphen variants, quotes, brackets ignored)."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())

_AMEND = re.compile(r"^\d+\s*\[\s*")          # "1 [(ia) ..." - amendment footnote marker before the clause

def find_block(blocks: list[str], clause_no: str, text: str):
    """-> (block index, words after the number, number in the same block?). The returned words are the PAGE's own
    words (exact characters), so the phrase built from them is what the browser will find."""
    words = text.split()[1:]
    lab = label(clause_no)
    kt = _key(lab + " " + " ".join(words[:60]))          # the clause as it starts, number included
    kt_body = _key(" ".join(words[:60]))
    def same_start(kb, kt):                              # one is a prefix of the other, at least label + 1 word
        return len(kb.split()) >= 2 and (kt.startswith(kb + " ") or kt == kb or kb.startswith(kt))
    for i, b in enumerate(blocks):
        body = _AMEND.sub("", b)
        kb = _key(body)
        if kb.startswith(_key(lab) + " ") and same_start(kb, kt):     # "9. Disclosures to borrowers" (heading only)
            return i, body.split()[len(lab.split()):], True
        if i and _key(_AMEND.sub("", blocks[i - 1])) == _key(lab) and same_start(kb, kt_body):
            return i, body.split(), False
    # 303: RBI's HTML puts a section heading and the paragraph in one block ("F.3 Interest ... 303. The bank is
    # free ..."): find the number inside the block; the number then always goes in as the prefix.
    want = _key(lab + " " + " ".join(words[:6]))
    for i, b in enumerate(blocks):
        toks = b.split()
        for j, t in enumerate(toks):
            if t == lab and _key(" ".join(toks[j:j + 7])).startswith(want):
                return i, toks[j + 1:], "mid"
    return None, None, None

def build(blocks: list[str], clause_no: str, text: str) -> dict:
    if re.match(r"^\S+\s+\*{3,}", text):            # "60. *****]": paragraph deleted by amendment
        return {"status": "deleted"}
    i, bw, same_block = find_block(blocks, clause_no, text)
    if i is None:
        return {"status": "block_not_found"}
    low = [_lc(b) for b in blocks]
    def count(phrase):
        p = _lc(phrase)
        return sum(b.count(p) for b in low)
    for n in range(min(MIN_WORDS, len(bw)), len(bw) + 1):
        start = " ".join(bw[:n])
        if same_block != "mid" and n >= min(8, len(bw)) and count(start) == 1:   # >= the old 8-word phrase
            return {"status": "ok", "start": start, "prefix": None, "words": n}
    if same_block:
        lab = label(clause_no)
        for n in range(min(MIN_WORDS, len(bw)), len(bw) + 1):
            start = " ".join(bw[:n])
            if count(f"{lab} {start}") == 1:
                return {"status": "ok", "start": start, "prefix": lab, "words": n}
    return {"status": "not_unique"}

def main():
    out, stats, problems = {}, collections.Counter(), collections.defaultdict(list)
    for raw, parsed in PAGES:
        blocks = page_blocks(pathlib.Path(raw).read_text(encoding="utf-8"))
        for line in open(parsed, encoding="utf-8"):
            c = json.loads(line)
            if c.get("omitted"):
                continue
            r = build(blocks, c["clause_no"], c["text"])
            old = " ".join(c["text"].split()[1:9])
            r["old_start"] = old
            out[f'{c["doc_id"]}|{c["clause_no"]}'] = r
            kind = r["status"] if r["status"] != "ok" else ("prefix" if r["prefix"] else
                   ("same_as_before" if r["start"] == old else "changed"))
            stats[kind] += 1
            if r["status"] != "ok":
                problems[r["status"]].append(f'{c["doc_id"]}:{c["clause_no"]}')
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print("clauses:", sum(stats.values()), dict(stats))
    for k, v in problems.items():
        print(f"{k} ({len(v)}):", ", ".join(v[:40]))
    print("written", OUT)
    return 0 if not problems else 1

if __name__ == "__main__":
    sys.exit(main())
