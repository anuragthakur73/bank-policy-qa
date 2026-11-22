# run: python -m ingest.check_links
import json
from urllib.parse import quote
from bs4 import BeautifulSoup

soup = BeautifulSoup(open("data/raw/credit_facilities_2025.html", encoding="utf-8").read(), "html.parser")
ids = [t["id"] for t in soup.find_all(id=True)]
names = [a["name"] for a in soup.find_all("a", attrs={"name": True})]
print(len(ids), "id attributes, e.g.", ids[:15])
print(len(names), "<a name> anchors, e.g.", names[:15])

for l in open("data/parsed/credit_facilities.jsonl", encoding="utf-8"):
    c = json.loads(l)
    if c["clause_no"] == "44":
        words = " ".join(c["text"].split()[1:9])
        print("\nA) Section anchor (RBI's own):\n" + c["source_url"] + "#" + c["section_anchor"])
        print("\nB) Text fragment (highlights para 44):\n" + c["source_url"] + "#:~:text=" + quote(words, safe="").replace("-", "%2D"))
