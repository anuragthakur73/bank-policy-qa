# Week 6 S4 (ADR-021): compare name detectors on eval/pii_names_v1.jsonl and the golden questions.
# run: python -m eval.pii_ner_compare [option ...]    options: patterns, spacy_sm, spacy_md, spacy_lg
# Scores: name recall (name strings fully covered by a mask span), address-part recall, trap words masked
# (any "keep" string touched), golden questions changed by the NEW entities (must be 0), ms per question.
import json, sys, time
from functools import lru_cache
from app import pii

import os
SET = os.environ.get("PII_SET", "eval/pii_names_v1.jsonl")   # tuning set; held-out: eval/pii_names_v1_holdout.jsonl
ROWS = [json.loads(l) for l in open(SET, encoding="utf-8")]
GOLDEN = [json.loads(l)["question"] for l in open("eval/golden_v2_4.jsonl", encoding="utf-8")]

def adr015(text):                          # the Week 4 patterns only (PAN, Aadhaar, ...), names/addresses off
    os.environ["PII_NER"] = os.environ["PII_ADDRESS"] = "0"
    try:
        return pii.find(text)
    finally:
        del os.environ["PII_NER"], os.environ["PII_ADDRESS"]

def kind(row, item):
    if covered(row["text"], item, adr015(row["text"])):                     # PAN, account no. - already covered by ADR-015 patterns
        return "pattern"
    if row["id"][0] in "nh" or (row["id"] == "a06" and item == "Sunil Joshi"):
        return "name"
    return "address"

def covered(text, item, spans):
    i = text.find(item)
    assert i >= 0, (item, text)
    return all(any(s <= k < e for s, e, _ in spans) for k in range(i, i + len(item)) if not text[k].isspace())

def touched(text, item, spans):
    i = text.find(item)
    return any(s < i + len(item) and e > i for s, e, _ in spans)

@lru_cache
def _nlp(name):
    import spacy
    return spacy.load(name, disable=["lemmatizer"])

def spacy_person(name):
    def f(text):
        return [(e.start_char, e.end_char, "PERSON") for e in _nlp(name)(text).ents if e.label_ == "PERSON"]
    return f

def hybrid(model):
    def f(text):
        import os; os.environ["PII_NER_MODEL"] = model
        from app import pii_ner
        if pii_ner.NER_MODEL != model:
            pii_ner.NER_MODEL = model; pii_ner._nlp.cache_clear()
        return pii_ner.find(text)
    return f

OPTIONS = {"patterns": lambda t: [], "hybrid_md": hybrid("en_core_web_md"), "hybrid_lg": hybrid("en_core_web_lg"), "spacy_sm": spacy_person("en_core_web_sm"),
           "spacy_md": spacy_person("en_core_web_md"), "spacy_lg": spacy_person("en_core_web_lg")}

def evaluate(opt, f, show=True):
    f("warm up")
    hits = {"name": [0, 0], "address": [0, 0], "pattern": [0, 0]}
    misses, traps, ms = [], [], []
    for r in ROWS:
        t0 = time.perf_counter(); new = f(r["text"]); ms.append((time.perf_counter() - t0) * 1000)
        spans = adr015(r["text"]) + new
        for item in r["mask"]:
            k = kind(r, item); hits[k][1] += 1
            if covered(r["text"], item, spans): hits[k][0] += 1
            else: misses.append(f'{r["id"]}:{item}')
        traps += [f'{r["id"]}:{item}' for item in r["keep"] if touched(r["text"], item, new)]
    changed = []
    for q in GOLDEN:
        t0 = time.perf_counter(); new = f(q); ms.append((time.perf_counter() - t0) * 1000)
        if new: changed.append((q[:60], [q[s:e] for s, e, _ in new]))
    ms.sort()
    res = {"option": opt, **{k: f"{a}/{b}" for k, (a, b) in hits.items()}, "traps_masked": len(traps),
           "golden_changed": len(changed), "median_ms": round(ms[len(ms) // 2], 1)}
    if show:
        print(json.dumps(res)); print("  missed:", misses); print("  traps:", traps)
        for c in changed: print("  golden:", c)
    return res

if __name__ == "__main__":
    for o in sys.argv[1:] or OPTIONS:
        evaluate(o, OPTIONS[o])
