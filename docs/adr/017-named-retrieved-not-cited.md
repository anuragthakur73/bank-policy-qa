# ADR-017: A retrieved source that is named but not cited is a warning with a code-added link, not a retry

Date: 27 Nov 2026 · Status: accepted by Anurag 27 Nov 2026 (Week 5 S3); confirm on the next golden_v2_2 run

## Context
ADR-014 made "names a rule or RBI para but does not cite it" blocking: retry once, then refuse. In the 02:45 plain
run it refused two correct answers. g002 ("12 months", bullet gold loan) named para 39 and p03 ("repo + 2.60%")
named DB-HL-005 and DB-HL-007 without citing them; all three were retrieved. The retry note ("cite a result for
every rule ID and RBI paragraph you name") then produced drafts naming para 34 (g002) and para 349 (p03), which
were NOT retrieved, so both were refused. The graph run passed both first time. Same family as p02 (26 Nov,
already relaxed for paras a cited rule implements). Not the same as r04 (23:47 on 26 Nov), which was the shared
citation-link bug fixed in ADR-014.

## Options (Anurag chose B)
- A. Attach a citation in code. Rejected: a native citation means the model quoted that source for that statement;
  code cannot know which statement the name supports, so the citation would claim more than is true.
- B. Warn, and add a code-written line "Also named in this answer (linked by the system, not quoted): ..." with the
  clause links. Block only names that were not retrieved. Chosen.
- C. Keep blocking, change only the retry note. Keeps ~10 extra model calls per run and the refusal risk.

## Decision
1. `app/validate.py`: named_not_cited is split. `named_not_retrieved` (fail) - a rule ID or RBI para named that is not
   among the search results. `named_retrieved_not_cited` (warn, with a ref) - named and retrieved, not cited.
   `implemented_para_not_cited` stays a warn and now also carries a ref.
2. `app/generate.py` `_finish` (both flows): unless the answer is a refusal, append one line listing those refs with
   their links; record them as `named_refs` in the audit.
3. Retry note adds: do not name any rule ID or RBI paragraph that is not among the results (answer-v5; only retry
   calls see it).

## Done when
Next golden_v2_2 run (graph): no correct first draft refused for naming a retrieved source; refusals 71/71;
fewer retries than 02:53 (passed_after_retry); named_not_retrieved still blocks (tests/test_validate.py).

## Trade-off
Staff now see a source the model named without quoting. The line says so, and the link opens the clause, so a
reader can check it; it is not presented as a citation. An unretrieved name is still caught.
