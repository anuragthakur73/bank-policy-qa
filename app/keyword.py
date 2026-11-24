# run: python -m app.keyword "your question"   (keyword search only, no network needed if data/parsed exists)
# BM25 keyword search over the RBI clauses, built by hand with rank_bm25 (the LangChain version is in
# app/retrieve_lc.py). Same text as the vector index: "chapter > section" header + clause text (ingest/index.py).
# Why: vector search misses exact-term questions ("LTV", "KFS", "penal charge") - Week 2 hit@5 was 7/14.
import glob, json, os, pathlib, re, sys
from functools import lru_cache
from rank_bm25 import BM25Okapi

PARSED = pathlib.Path("data/parsed")
# Words that carry no meaning for search. Domain words that appear everywhere ("bank", "loan") are left
# to BM25's IDF, except a few that only add noise to questions.
STOP = set("""a an the of to in on for and or is are be by with as at from that this these which it its any
shall may can will not no if under per such than there their what how when does do we our us he she his her
they them i you your me my rs lakh crore wants want""".split())
# Bank shorthand <-> RBI wording, so a question in either form matches the clause.
SYNONYMS = [(r"loan[\s-]*to[\s-]*value", "ltv"), (r"key facts? statements?", "kfs"),
            (r"\bemis?\b", "emi instalment"), (r"\bforeclos\w*", "foreclosure prepayment"),
            (r"\bpre-?payment\b", "prepayment foreclosure"),
            (r"\btitle deeds?\b", "title deeds property documents")]
# NOTE: the KFS and title-deed entries were added after seeing golden_v1 misses (p15, p13), so those two
# questions no longer test keyword search blind. New jargon goes here only from real staff questions.

def tokenize(text: str) -> list[str]:
    s = text.lower()
    for pat, rep in SYNONYMS:
        s = re.sub(pat, f" {rep} ", s)
    return [w for w in re.findall(r"[a-z0-9]+", s) if w not in STOP]

def page_content(meta: dict) -> str:
    """Identical to the text ingest/index.py embeds, so both searches score the same thing."""
    header = " > ".join(x for x in (meta.get("chapter"), meta.get("section")) if x)
    text = meta.get("clause_text") or meta.get("text", "")
    return f"{header}\n{text}" if header else text

def _from_parsed() -> list[dict]:
    rows = []
    for p in sorted(PARSED.glob("*.jsonl")):
        for line in p.open(encoding="utf-8"):
            r = json.loads(line)
            if r.get("omitted"):
                continue
            r["clause_text"] = r.pop("text")
            rows.append(r)
    return rows

def _from_qdrant() -> list[dict]:
    """Fallback when data/parsed is absent (it is gitignored, e.g. on a fresh clone or a server)."""
    from dotenv import load_dotenv; load_dotenv()
    from qdrant_client import QdrantClient
    c = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
    rows, offset = [], None
    while True:
        pts, offset = c.scroll("clauses_v1", limit=256, offset=offset, with_payload=True)
        rows += [p.payload["metadata"] for p in pts]
        if offset is None:
            return rows

@lru_cache
def corpus() -> tuple[list[dict], BM25Okapi, dict]:
    rows = _from_parsed() if any(PARSED.glob("*.jsonl")) else _from_qdrant()
    bm = BM25Okapi([tokenize(page_content(r)) for r in rows])
    by_key = {(r["doc_id"], r["clause_no"]): r for r in rows}
    return rows, bm, by_key

def search(question: str, k: int = 20) -> list[tuple[dict, float]]:
    rows, bm, _ = corpus()
    scores = bm.get_scores(tokenize(question))
    top = sorted(range(len(rows)), key=lambda i: -scores[i])[:k]
    return [(rows[i], float(scores[i])) for i in top if scores[i] > 0]

def clause(doc_id: str, clause_no: str) -> dict | None:
    """Local lookup of one clause (used by the policy trace instead of a Qdrant call per paragraph)."""
    return corpus()[2].get((doc_id, clause_no))

def rrf(rankings: list[list[str]], c: int = 60, weights: list[float] | None = None) -> dict[str, float]:
    """Reciprocal rank fusion: score = sum(weight / (c + rank)), rank starting at 1. Higher is better."""
    weights = weights or [1.0] * len(rankings)
    out: dict[str, float] = {}
    for w, ranking in zip(weights, rankings):
        for rank, key in enumerate(ranking, start=1):
            out[key] = out.get(key, 0.0) + w / (c + rank)
    return out

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "For how long is the Key Facts Statement valid?"
    print("tokens:", tokenize(q))
    for m, s in search(q, 5):
        print(f'{s:6.2f}  {m["doc_id"]} para {m["clause_no"]}: {m["clause_text"][:90]}')
