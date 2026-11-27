# run: python -m eval.check_rbi_links      (Week 5 S5, ADR-019; fetches the two live RBI pages, no API key, $0)
# Checks every citation phrase in data/parsed/link_fragments.json against RBI's page AS IT IS TODAY:
#   ok          phrase (with its prefix) occurs exactly once on the page, inside one block -> the link highlights it
#   missing     phrase not on the page any more (RBI changed the text: re-download data/raw and re-run ingest)
#   ambiguous   phrase occurs more than once (the browser would highlight the first)
# Then prints 6 links to click by hand: a script cannot see the highlight itself.
# If RBI answers with its language-choice page (no cookie), the script says so and stops: choose English in a
# browser, save the page as data/raw/<name>.html, and run `python -m ingest.link_fragments` (the same check offline).
import collections, json, sys
import requests
from ingest.link_fragments import page_blocks, OUT

URLS = {"RBI-CB-CREDIT-FAC-2025": "https://www.rbi.org.in/ScriptS/BS_ViewMasDirections.aspx?id=13156",
        "RBI-CB-RBC-2025": "https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13140"}
TITLE = {"RBI-CB-CREDIT-FAC-2025": "credit facilities", "RBI-CB-RBC-2025": "responsible business conduct"}
SAMPLES = [("RBI-CB-CREDIT-FAC-2025", "108"), ("RBI-CB-CREDIT-FAC-2025", "109"), ("RBI-CB-RBC-2025", "351"),
           ("RBI-CB-CREDIT-FAC-2025", "38"), ("RBI-CB-CREDIT-FAC-2025", "303"), ("RBI-CB-CREDIT-FAC-2025", "111")]

def main():
    frag = json.load(open(OUT, encoding="utf-8"))
    bad = 0
    for doc, url in URLS.items():
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0 (link check; bank-policy-qa)"})
        html = r.text
        if TITLE[doc] not in html.lower():
            print(f"{doc}: RBI returned another page (HTTP {r.status_code}, {len(html)} bytes) - probably the "
                  "language choice. Save the page from a browser into data/raw and run `python -m ingest.link_fragments`.")
            bad += 1
            continue
        low = [b.lower() for b in page_blocks(html)]
        stats, problems = collections.Counter(), collections.defaultdict(list)
        for key, f in frag.items():
            d, clause = key.split("|", 1)
            if d != doc or f.get("status") != "ok":
                continue
            phrase = ((f["prefix"] + " ") if f.get("prefix") else "") + f["start"]
            n = sum(b.count(phrase.lower()) for b in low)
            kind = "ok" if n == 1 else ("missing" if n == 0 else "ambiguous")
            stats[kind] += 1
            if kind != "ok":
                problems[kind].append(clause)
        print(f"{doc}: {dict(stats)}", *(f"\n  {k}: {', '.join(v[:30])}" for k, v in problems.items()))
        bad += sum(len(v) for v in problems.values())
    from app.generate import clause_link
    print("\nClick these (choose English if RBI asks), check the highlighted paragraph is the one named:")
    rows = {}
    for path in ("data/parsed/credit_facilities.jsonl", "data/parsed/responsible_business_conduct.jsonl"):
        for line in open(path, encoding="utf-8"):
            c = json.loads(line); rows[(c["doc_id"], c["clause_no"])] = c
    for doc, clause in SAMPLES:
        c = rows[(doc, clause)]
        print(f"  {doc.split('-')[3]} para {clause}: {clause_link({**c, 'layer': 'rbi'})}")
    print("\nRESULT:", "ALL OK" if not bad else f"{bad} problem(s)")
    return 0 if not bad else 1

if __name__ == "__main__":
    sys.exit(main())
