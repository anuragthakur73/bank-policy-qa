# Keyword (BM25) search over the Demo Bank rules in force (Week 4 S2b, ADR-011).
# Built locally from the policy files: no network call, ~50 rules. Same tokenizer as the RBI keyword search.
from functools import lru_cache
from rank_bm25 import BM25Okapi
from app.keyword import tokenize
from app import policy_versions as pv

@lru_cache
def _index(product: str, version: str):
    v = pv.version(product, version)
    ids = list(v["rules"])
    return ids, BM25Okapi([tokenize(f'{v["titles"][i]} {v["rules"][i]}') for i in ids])

def search(question: str, product: str, as_on, k: int = 1) -> list[tuple[str, float]]:
    """Top-k (rule_id, score) among the product's rules in force on as_on; only positive scores."""
    v = pv.in_force(product, as_on)
    if not v:
        return []
    ids, bm = _index(product, v["version"])
    s = bm.get_scores(tokenize(question))
    order = sorted(range(len(ids)), key=lambda i: -s[i])
    return [(ids[i], round(float(s[i]), 3)) for i in order[:k] if s[i] > 0]

def merge(ranked: list, kw: list[tuple[str, float]], k: int) -> list[tuple]:
    """ranked: every eligible (doc, score) in vector order. Keep the vector top k, then add the keyword top hit
    if it is not already there. -> [(doc, score, retrieval_info)], at most k + 1 rows."""
    out = [(d, s, {"mode": "vector", "vector_rank": i}) for i, (d, s) in enumerate(ranked[:k], start=1)]
    if kw:
        rid, ks = kw[0]
        if rid not in {d.metadata["rule_id"] for d, _ in ranked[:k]}:
            for i, (d, s) in enumerate(ranked, start=1):
                if d.metadata["rule_id"] == rid:
                    out.append((d, s, {"mode": "keyword", "vector_rank": i, "keyword_rank": 1, "keyword_score": ks}))
                    break
    return out
