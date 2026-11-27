# Week 6 S3: one static HTML page with the evaluation story of Project 1A.
# run: python -m eval.report            -> docs/eval/index.html   (offline: no API calls; needs the spaCy model)
# Every score is RECOMPUTED from the per-question rows of the stored eval reports, with today's scorer and today's
# golden files, and compared with the summary stored in each report: where they differ, the page says so and why.
# (Week 5's report files say "headline 22/24"; the Week 5 summary said 22/22 after a scorer fix - both are shown.)
import datetime, html, json, os, pathlib, re, statistics
from collections import Counter

REPORTS = pathlib.Path("eval/reports")
OUT = pathlib.Path("docs/eval/index.html")
MILESTONES = [   # (label, report file, context) - the runs the weekly summaries quote
    ("Week 3", "2026-11-25_0050_answer-v2_vector_golden_v2.json", "given"),
    ("Week 4", "2026-11-26_2343_answer-v3_vector_product-given_golden_v2_1.json", "given"),
    ("Week 5", "2026-11-27_2149_answer-v5_vector_product-given_golden_v2_3_graph.json", "given"),
    ("Week 5", "2026-11-27_2157_answer-v5_vector_product-text_golden_v2_3_graph.json", "text"),
    ("Week 6", "2026-11-28_0012_answer-v6_vector_product-given_golden_v2_4_graph.json", "given"),
    ("Week 6", "2026-11-28_0020_answer-v6_vector_product-text_golden_v2_4_graph.json", "text"),
]
GOLDENS = ["golden_v2", "golden_v2_1", "golden_v2_2", "golden_v2_3", "golden_v2_4"]
METRICS = [  # (key, label, what it means)
    ("hit_at_5", "RBI paragraph in top 5", "the expected RBI clause is among the first 5 RBI search results"),
    ("cited_ok", "RBI paragraph cited", "the answer cites the expected RBI clause"),
    ("rule_hit", "Bank rule found", "the expected Demo Bank rule was sent to the model"),
    ("rule_cited", "Bank rule cited", "the answer cites the expected Demo Bank rule"),
    ("product_ok", "Right-product rules only", "every cited bank rule belongs to the product asked about"),
    ("answer_ok", "Key figures present", "every must-have figure appears in the answer"),
    ("headline_ok", "First figure right", "the first figure in the answer is the expected one"),
    ("verdict_ok", "Opening yes/no right", "the answer opens with the expected Yes or No"),
    ("version_ok", "Right policy version", "cited rules are the version in force on the as-on date"),
    ("notice_ok", "Not-in-force notice", "the answer starts with the expected notice"),
    ("pii_ok", "No personal data logged", "no raw PAN/Aadhaar/phone in the logged question or answer"),
    ("refusal_ok", "Refused exactly when it should", "refuses when the documents don't answer, and only then"),
    ("clarify_ok", "Asked 'which product?' exactly when it should", "asks only when the product is unclear"),
]
GROUPS = [("g", "RBI, first test set"), ("r", "RBI only"), ("p", "Home loan policy"), ("l", "LAP"), ("c", "Car loan"),
          ("x", "Cross-product"), ("k", "Clarify step"), ("v", "Dates, versions, PII"), ("i", "Real interview questions")]
LESSONS = [
    ("An eval bug invented a problem", "\"RBI search finds the right clause 7/14\" was a scoring bug (scored after "
     "de-duplication). A second script scoring the same thing exposed it.", "Week 3"),
    ("Slow answers were the network, not the code", "12-31 s answers were Qdrant Cloud over a poor connection; found "
     "only after timing each stage.", "Week 3"),
    ("One shared index gave a wrong answer", "A LAP question got the home-loan LTV (75% instead of 65%). Fixed by a "
     "product filter and product-scoped RBI clauses (ADR-009, ADR-012).", "Week 3-4"),
    ("An audit log must store the output", "The log kept the question but not the answer text, which is what a "
     "reviewer needs when an answer is wrong; since Week 4 it stores both.", "Week 4"),
    ("A one-run move of +-2 is noise", "Model-scored metrics move by 1-2 between identical runs; compare runs, not "
     "single numbers.", "Week 4"),
    ("A strict check made answers worse", "\"Cite every source you name\" made retries name unretrieved sources; two "
     "correct answers were refused. Block only what is actually wrong (ADR-017).", "Week 5"),
    ("Asking beats guessing", "A free, rule-based \"which product?\" took product accuracy from 37/47 to 52/52 when the "
     "product came from the question text (ADR-018).", "Week 5"),
    ("The metric can't see the user's screen", "About 75 of 975 citation links highlighted the wrong paragraph, "
     "invisible to every score; found by checking RBI's page and clicking (ADR-019).", "Week 5"),
    ("Evaluate the test set too", "p17, c03, c10 \"failures\" were golden-set or scorer errors, not system errors.",
     "Week 5"),
    ("A closed list needs saying", "\"Can an HUF apply?\" was hedged until the prompt said an eligibility list is "
     "complete; a banker's review set the expected answer (v09, answer-v6).", "Week 6"),
    ("The builder's test set shares the builder's blind spots", "Name masking: 100% on the set its rules were built "
     "on, 95% on held-out questions; a banker's own 7 questions found a case neither set had (ADR-021).", "Week 6"),
]

def _scorer():
    """first_figure / opening_verdict from eval/run_eval.py without importing it (importing runs the eval)."""
    src = pathlib.Path("eval/run_eval.py").read_text(encoding="utf-8")
    ns = {"re": re}; exec(src[src.index("_IGNORE ="):src.index("GOLDEN =")], ns)
    return ns["first_figure"], ns.get("opening_verdict")

FIRST_FIGURE, OPENING_VERDICT = _scorer()

def golden(name):
    return {r["id"]: r for r in (json.loads(l) for l in open(f"eval/{name}.jsonl", encoding="utf-8") if l.strip())}

# code-written notices (app/policy_versions.notices) are skipped before scoring, as run_eval does with rec["notices"]
NOTICE = re.compile(r"^(?:Demo Bank's .+? policy is not in force on .+?so its rules are not used below\.|Note: DB-[A-Z]+-\d+ .+)$")
def model_text(answer):
    return "\n\n".join(p for p in answer.split("\n\n") if not NOTICE.match(p.strip()))

def frac(vals):
    vals = [v for v in vals if v is not None]
    return (sum(vals), len(vals)) if vals else None

def rescore(fname):
    d = json.loads((REPORTS / fname).read_text(encoding="utf-8"))
    gname = re.search(r"(golden_v2(?:_\d)?)", fname).group(1)
    g = golden(gname)
    rows, notes = [], []
    for r in d["rows"]:
        r = dict(r); gr = g.get(r["id"], {})
        ref = gr.get("expect_refusal", False)
        notices_free = model_text(r.get("answer", ""))
        # headline / verdict: today's scorer against today's golden file (answers are stored to 400 chars)
        old_h = r.get("headline_ok")
        if gr.get("headline") and not ref:
            r["headline_ok"] = FIRST_FIGURE(notices_free, gr["question"]) == gr["headline"].replace(",", "")
        else:
            r["headline_ok"] = None
        if old_h != r["headline_ok"]:
            why = ("headline dropped from the golden set" if not gr.get("headline") else
                   "not scored at the time; headline added to the golden set later" if old_h is None else "scorer fix")
            notes.append(f'{r["id"]}: first figure {old_h} -> {r["headline_ok"]} ({why})')
        if OPENING_VERDICT and gr.get("verdict") and not ref and not gr.get("manual_review"):
            r["verdict_ok"] = OPENING_VERDICT(notices_free) == gr["verdict"]
        else:
            r.setdefault("verdict_ok", None)
        r["question"] = gr.get("question", "")
        rows.append(r)
    by_why = {}
    for n in notes:
        rid, why = n.split(": ", 1)[0], n.rsplit("(", 1)[1].rstrip(")")
        by_why.setdefault(why, []).append(n.split(" (")[0])
    notes = [f'{"; ".join(v) if len(v) < 4 else f"{len(v)} questions"} ({w})' for w, v in by_why.items()]
    scores = {k: frac([r.get(k) for r in rows]) for k, _, _ in METRICS}
    stored = d["summary"]
    diffs = []
    for k, label, _ in METRICS:
        s = stored.get(k); new = f"{scores[k][0]}/{scores[k][1]}" if scores[k] else "-"
        if s not in (None, "-", new) or (s in (None, "-") and new != "-" and k not in ("verdict_ok",)):
            diffs.append(f"{label}: stored {s or '-'}, rescored {new}")
    lat = sorted(r["latency_ms"] for r in rows)
    return {"file": fname, "golden": gname, "n": len(rows), "rows": rows, "scores": scores, "diffs": diffs,
            "notes": notes, "cost": sum(r["cost_usd"] for r in rows), "median_s": lat[len(lat) // 2] / 1000,
            "p90_s": lat[int(len(lat) * 0.9)] / 1000, "validation": Counter(r.get("validation", "-") for r in rows),
            "named_not_cited": stored.get("named_not_cited"),
            "retries": stored.get("retries", {}), "prompt": stored.get("prompt_version", re.search(r"answer-v\d", fname).group(0))}

def golden_changes():
    out, prev = [], None
    for name in GOLDENS:
        cur = golden(name)
        if prev is None:
            out.append((name, len(cur), f"{len(cur)} questions", "", ""))
        else:
            add = sorted(set(cur) - set(prev))
            changed = sorted(k for k in set(cur) & set(prev) if cur[k] != prev[k])
            fields = Counter(f for k in changed for f in set(cur[k]) | set(prev[k]) if cur[k].get(f) != prev[k].get(f))
            out.append((name, len(cur), ", ".join(add) or "-", ", ".join(changed) or "-",
                        ", ".join(f"{f} ({n})" for f, n in fields.most_common()) or "-"))
        prev = cur
    return out

def masking():
    os.environ.setdefault("PII_SET", "eval/pii_names_v1.jsonl")
    import importlib
    from eval import pii_ner_compare as cmp
    res = []
    for label, path in (("Tuning set (rules built on it)", "eval/pii_names_v1.jsonl"),
                        ("Held-out set (written after round 1)", "eval/pii_names_v1_holdout.jsonl"),
                        ("A banker's own questions (independent at first)", "eval/pii_names_v1_anurag.jsonl")):
        cmp.ROWS = [json.loads(l) for l in open(path, encoding="utf-8")]
        r = cmp.evaluate("hybrid_lg", cmp.OPTIONS["hybrid_lg"], show=False)
        res.append((label, len(cmp.ROWS), r))
    return res

# --- HTML ----------------------------------------------------------------------------------------------------------
e = html.escape
def cell(f, good=None):
    if not f: return '<td class="na">-</td>'
    a, b = f; pct = a / b
    cls = "ok" if a == b else ("warn" if pct >= 0.9 else "bad")
    return f'<td class="{cls}">{a}/{b}</td>'

def mark(v):
    return {True: '<td class="ok">✓</td>', False: '<td class="bad">✗</td>'}.get(v, '<td class="na"></td>')

def page(runs, gch, mask):
    latest = [r for (lab, _, ctx), r in zip(MILESTONES, runs) if lab == MILESTONES[-1][0]]
    head = "".join(f'<th>{e(lab)}<br><span class="sub">{e(r["golden"])} · {r["n"]} Qs · '
                   f'{"product given" if ctx == "given" else "product from text"} · {e(r["prompt"])}</span></th>'
                   for (lab, _, ctx), r in zip(MILESTONES, runs))
    body = ""
    for k, label, desc in METRICS:
        if not any(r["scores"][k] for r in runs): continue
        body += f'<tr><th class="m" title="{e(desc)}">{e(label)}<span class="sub">{e(desc)}</span></th>' + \
                "".join(cell(r["scores"][k]) for r in runs) + "</tr>"
    body += '<tr class="sep"><th class="m">Cost of the whole run</th>' + "".join(f'<td>${r["cost"]:.3f}</td>' for r in runs) + "</tr>"
    body += '<tr><th class="m">Median / 90th-percentile latency</th>' + "".join(f'<td>{r["median_s"]:.1f} s / {r["p90_s"]:.1f} s</td>' for r in runs) + "</tr>"
    body += '<tr><th class="m">Answer checker: passed / after retry / refused<span class="sub">ADR-014, from Week 4</span></th>' + "".join(
        (f'<td>{r["validation"].get("pass", 0)} / {r["validation"].get("passed_after_retry", 0)} / {r["validation"].get("refused", 0)}</td>'
         if set(r["validation"]) - {"-"} else '<td class="na">-</td>') for r in runs) + "</tr>"
    diffs = "".join(f'<li><b>{e(lab)} ({"given" if ctx == "given" else "text"})</b>: ' + e("; ".join(r["diffs"] + r["notes"])) + "</li>"
                    for (lab, _, ctx), r in zip(MILESTONES, runs) if r["diffs"] or r["notes"])
    # per-question table, latest week, both contexts side by side
    g, t = latest
    tm = {r["id"]: r for r in t["rows"]}
    keys = ["cited_ok", "rule_cited", "product_ok", "answer_ok", "headline_ok", "verdict_ok", "refusal_ok", "clarify_ok"]
    short = {"cited_ok": "RBI", "rule_cited": "Rule", "product_ok": "Prod", "answer_ok": "Fig", "headline_ok": "1st",
             "verdict_ok": "Y/N", "refusal_ok": "Ref", "clarify_ok": "Ask"}
    qrows = ""
    for r in g["rows"]:
        rt = tm.get(r["id"], {})
        fail = any(r.get(k) is False or rt.get(k) is False for k in keys)
        grp = next((n for p, n in GROUPS if r["id"].startswith(p)), "")
        qrows += (f'<tr class="{"fail" if fail else ""}"><td class="id">{e(r["id"])}</td><td class="grp">{e(grp)}</td>'
                  f'<td class="q" title="{e(r.get("answer", ""))}">{e(r["question"])}</td>'
                  + "".join(mark(r.get(k)) for k in keys) + '<td class="gap"></td>'
                  + "".join(mark(rt.get(k)) for k in keys)
                  + f'<td class="num">{r["latency_ms"] / 1000:.1f}</td><td class="num">{r["cost_usd"] * 100:.2f}¢</td></tr>')
    qhead = "".join(f"<th>{short[k]}</th>" for k in keys)
    gtab = "".join(f"<tr><td>{e(n)}</td><td class='num'>{c}</td><td>{e(a)}</td><td>{e(ch)}</td><td>{e(f)}</td></tr>" for n, c, a, ch, f in gch)
    mtab = "".join(f"<tr><td>{e(l)}</td><td class='num'>{n}</td>{cell(tuple(map(int, r['name'].split('/'))))}"
                   f"{cell(tuple(map(int, r['address'].split('/'))))}<td class='{'ok' if r['traps_masked'] == 0 else 'bad'}'>{r['traps_masked']}</td>"
                   f"<td class='{'ok' if r['golden_changed'] == 0 else 'bad'}'>{r['golden_changed']} of 77</td><td>{r['median_ms']} ms</td></tr>"
                   for l, n, r in mask)
    lessons = "".join(f'<li><b>{e(a)}</b> <span class="sub">{e(w)}</span><br>{e(b)}</li>' for a, b, w in LESSONS)
    nnc = " · ".join(f'{lab} {ctx}: {r["named_not_cited"] if r["named_not_cited"] is not None else "not measured"}'
                     for (lab, _, ctx), r in zip(MILESTONES, runs))
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30), "IST")
    now = datetime.datetime.now(ist).strftime("%d %b %Y %H:%M IST")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bank Policy Q&amp;A — evaluation report</title><style>
:root{{--fg:#1d1d1f;--mut:#6b6b70;--line:#e4e4e7;--ok:#0f7b3f;--okbg:#e9f6ee;--warn:#8a5a00;--warnbg:#fdf3dc;--bad:#b42318;--badbg:#fdecea;--bg:#fff}}
@media (prefers-color-scheme:dark){{:root{{--fg:#ececef;--mut:#a0a0a8;--line:#33333a;--ok:#5fd394;--okbg:#12301f;--warn:#f0c060;--warnbg:#3a2d10;--bad:#ff8a80;--badbg:#3d1714;--bg:#16161a}}}}
body{{font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg);max-width:1180px;margin:0 auto;padding:32px 20px 80px}}
h1{{font-size:28px;margin:0 0 4px}} h2{{font-size:20px;margin:40px 0 8px;padding-top:8px;border-top:1px solid var(--line)}}
p,li{{max-width:820px}} .sub{{display:block;color:var(--mut);font-size:12px;font-weight:400}} .lead{{color:var(--mut)}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}} th,td{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
thead th{{font-size:13px;position:sticky;top:0;background:var(--bg)}} th.m{{font-weight:600;width:28%}}
td.ok{{color:var(--ok);background:var(--okbg);font-weight:600}} td.warn{{color:var(--warn);background:var(--warnbg);font-weight:600}}
td.bad{{color:var(--bad);background:var(--badbg);font-weight:600}} td.na{{color:var(--mut)}} td.num{{text-align:right;white-space:nowrap}}
tr.sep th,tr.sep td{{border-top:2px solid var(--line)}} .q{{max-width:420px}} .id{{font-family:ui-monospace,Consolas,monospace;font-size:13px}}
.grp{{color:var(--mut);font-size:12px;white-space:nowrap}} td.gap{{border:none;width:10px}}
#qt td.ok,#qt td.bad,#qt td.na{{text-align:center;width:28px;padding:6px 2px}} #qt th{{text-align:center;font-size:12px}}
.only-fail tr:not(.fail){{display:none}} label{{font-size:14px;color:var(--mut)}} code{{font-family:ui-monospace,Consolas,monospace;font-size:13px}}
.note{{background:var(--warnbg);padding:10px 14px;border-radius:8px;font-size:14px}} ul.lessons li{{margin-bottom:10px}}
</style></head><body>
<h1>Bank Policy Q&amp;A — evaluation report</h1>
<p class="lead">Project 1A. Generated {e(now)} by <code>python -m eval.report</code> from the stored eval runs in
<code>eval/reports/</code>. Every score below is recomputed from the per-question rows with today's scorer and
golden files; where that differs from the summary stored in the report, it is listed under the table.</p>

<h2>How it improved, week by week</h2>
<p>One run per week: the run each weekly summary quotes. The golden set grew from 51 to 77 questions, so later
columns are harder tests, not just better scores. Hover a metric for its definition.</p>
<table><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table>
<div class="note"><b>Stored summary vs recomputed:</b><ul>{diffs or "<li>No differences.</li>"}</ul>
Correction found by this page (28 Nov 2026): the Week 5 summary quoted "first figure 22/22"; that was the count from
the earlier golden_v2_2 run. The golden_v2_3 runs score 23/23.</div>
<p class="sub">ADR-020 counter (bank-rule questions answered with no bank rule cited although one was named): {e(nnc)}</p>

<h2>Every question, latest run</h2>
<p>{e(latest[0]["golden"])}, {latest[0]["n"]} questions. Left block: product given by the screen; right block:
product read from the question. ✓ pass, ✗ fail, blank = not scored for that question. Hover a question to see
the start of the answer.</p>
<label><input type="checkbox" onclick="document.getElementById('qt').classList.toggle('only-fail',this.checked)"> Show only questions with a failure</label>
<table id="qt"><thead><tr><th>ID</th><th>Group</th><th>Question</th>{qhead}<th class="gap"></th>{qhead}<th>s</th><th>cost</th></tr></thead><tbody>{qrows}</tbody></table>
<p class="sub">RBI = RBI paragraph cited · Rule = bank rule cited · Prod = right product · Fig = key figures · 1st = first figure
· Y/N = opening yes/no · Ref = refusal correct · Ask = clarifying question correct. Latency and cost are for the
product-given run.</p>

<h2>How the test set changed</h2>
<p>A score is only as good as its questions, so every change to the golden set is listed. Changed questions were
edited in place (for example, a <code>clarify</code> expectation added in v2_3).</p>
<table><thead><tr><th>Golden set</th><th>Questions</th><th>Added</th><th>Changed</th><th>Fields changed (count)</th></tr></thead><tbody>{gtab}</tbody></table>

<h2>Name and address masking (ADR-021)</h2>
<p>Recomputed now with the current rules. The honest number is the held-out set <i>before</i> the second round of
fixes, recorded in ADR-021: names 20/21 (95.2%), address parts 25/27 (92.6%), 3 words wrongly masked. After the
fixes every set below was used to tune the rules, so 100% here proves little; the next independent check is a
fresh set from a banker.</p>
<table><thead><tr><th>Test set</th><th>Rows</th><th>Names masked</th><th>Address parts masked</th><th>Words wrongly masked</th><th>Golden questions changed</th><th>Median time</th></tr></thead><tbody>{mtab}</tbody></table>

<h2>What we got wrong, and what it taught</h2>
<ul class="lessons">{lessons}</ul>

<p class="sub">Source: github repo bank-policy-qa · eval/report.py · run notes in eval/reports/failures.md · decisions in docs/adr/.</p>
</body></html>"""

if __name__ == "__main__":
    runs = [rescore(f) for _, f, _ in MILESTONES]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page(runs, golden_changes(), masking()), encoding="utf-8")
    for (lab, f, ctx), r in zip(MILESTONES, runs):
        print(lab, ctx, r["golden"], "diffs:", r["diffs"] or "-", "| notes:", r["notes"] or "-")
    print("wrote", OUT)
