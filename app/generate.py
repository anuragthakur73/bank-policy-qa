# run: python -m app.generate   (smoke test: one answerable, one out-of-scope question)
# Retrieves clauses, asks Claude to answer ONLY from them with native citations,
# refuses when they don't answer, and appends one audit record per query to logs/audit.jsonl.
import json, os, time, uuid, datetime
from urllib.parse import quote
from dotenv import load_dotenv; load_dotenv()
import anthropic
from app.retrieve import retrieve, CONTRACT_VERSION

cl = anthropic.Anthropic()
PROMPT_VERSION = "answer-v0"
REFUSAL = "Not covered by the indexed documents."
SYSTEM = ("You answer questions from Indian bank lending staff using ONLY the search results provided. "
          "Cite the clause for every statement. Quote figures (percentages, amounts, days) exactly. "
          f"If the search results do not answer the question, reply exactly: '{REFUSAL}' "
          "Do not use outside knowledge, and do not guess.")
PRICE_IN, PRICE_OUT = 0.10, 0.50   # USD per 1M tokens, Claude Haiku 5.5 (financial-viability doc, 18 Nov 2026)

def clause_link(h: dict) -> str:
    """Opens the RBI page and highlights the clause (text fragment). Skips the '44.' number."""
    words = " ".join(h["text"].split()[1:9])
    return h["source_url"] + "#:~:text=" + quote(words, safe="").replace("-", "%2D")

def section_link(h: dict) -> str:
    """Fallback: RBI's own section anchor, e.g. #C4D."""
    return h["source_url"] + ("#" + h["section_anchor"] if h.get("section_anchor") else "")

def answer(q: str, k: int = 5, caller: str = "cli"):
    t0, rid = time.time(), str(uuid.uuid4())
    hits = retrieve(q, k)
    results = [{"type": "search_result", "source": clause_link(h),
                "title": f'{h["title"]}, para {h["clause_no"]} ({h["version_label"]})',
                "content": [{"type": "text", "text": h["text"]}],
                "citations": {"enabled": True}} for h in hits]
    model = os.environ.get("DEFAULT_MODEL", "claude-haiku-5-5")
    # Haiku 5.5 thinks by default (effort "medium") and thinking tokens count against max_tokens,
    # so a tight cap can end the reply before any answer text. Low effort is enough for grounded Q&A.
    msg = cl.messages.create(model=model, max_tokens=2000, system=SYSTEM,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": results + [{"type": "text", "text": q}]}])
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if msg.stop_reason == "max_tokens" and not text:
        text = "[no answer: hit max_tokens before any text]"
    by_source = {clause_link(h): h for h in hits}
    cites = []
    for b in msg.content:
        if b.type != "text":
            continue
        for c in (getattr(b, "citations", None) or []):
            src = getattr(c, "source", "")
            h = by_source.get(src, {})
            cites.append({"title": getattr(c, "title", ""), "source": src,
                          "fallback": section_link(h) if h else "",
                          "clause_no": h.get("clause_no"), "cited_text": getattr(c, "cited_text", "")})
    u = msg.usage
    rec = {"request_id": rid, "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
           "caller": caller, "question": q, "contract": CONTRACT_VERSION,
           "retrieved": [{"doc_id": h["doc_id"], "clause_no": h["clause_no"],
                          "version_as_on": h["version_as_on"], "score": h["score"]} for h in hits],
           "model": model, "prompt_version": PROMPT_VERSION, "stop_reason": msg.stop_reason,
           "tokens_in": u.input_tokens, "tokens_out": u.output_tokens,
           "cost_usd": round((u.input_tokens * PRICE_IN + u.output_tokens * PRICE_OUT) / 1e6, 6),
           "latency_ms": int((time.time() - t0) * 1000),
           "refused": REFUSAL in text, "cited_clauses": sorted({c["clause_no"] for c in cites if c["clause_no"]}),
           "human_action": None}
    os.makedirs("logs", exist_ok=True)
    with open("logs/audit.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return text, cites, rec

if __name__ == "__main__":
    for q in ["What is the maximum loan-to-value ratio for a gold loan of 3 lakh rupees?",
              "What documents are needed for video KYC?"]:   # 2nd should refuse: KYC not indexed yet
        text, cites, rec = answer(q)
        print("Q:", q); print("A:", text)
        for c in cites:
            print(f'  -> para {c["clause_no"]}: "{c["cited_text"][:70]}..."\n     {c["source"]}')
        print(f'  [{rec["latency_ms"]} ms | {rec["tokens_in"]} in / {rec["tokens_out"]} out | ${rec["cost_usd"]:.5f} | refused={rec["refused"]}]\n')
