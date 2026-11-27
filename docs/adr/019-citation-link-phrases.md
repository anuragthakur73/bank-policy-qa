# ADR-019: Citation links use a phrase that is unique on RBI's page and inside one block

Date: 27 Nov 2026 · Status: accepted 27 Nov 2026 (Week 5 S5) - live check ALL OK, 6 links highlighted correctly in a browser
Supersedes the phrase rule in ADR-003 (links still go straight to the clause; Anurag's decision stands).

## Context
ADR-003 linked each RBI citation as `<page>#:~:text=<first 8 words of the clause>`. Checked against the saved RBI
pages on 27 Nov 2026 (975 indexed clauses):
1. Shared links: 10 groups (21 clauses) start with the same 8 words - CF 108/109, CF 400/423, RBC 46/173/351, RBC
   157/158, 219/296, 287/308, 291/310, 300/301, 360/362, 423/426. A browser highlights the first match, so a
   citation of RBC 351 (penal charges, cited in most answers) highlighted RBC 46. r04 (Week 3-4) was this.
2. Block breaks: RBI's page puts many headings on their own line ("38. A bank shall not:" then "(1) Avail loans...").
   A text fragment is matched within one block, so an 8-word phrase that runs across the break matches nothing and
   the page opens at the top. 54 clauses.
3. Smaller: amendment markers ("1 [(ia) ..."), a heading and a paragraph merged in one block (CF 303), and 3 paras
   deleted by amendment (CF 60, 170, 219 - "*****]").

## Decision
1. `ingest/link_fragments.py` (offline, from data/raw + data/parsed) writes `data/parsed/link_fragments.json`: for each
   clause, words taken from the page's own block for that clause, grown from 8 until the phrase occurs exactly once on
   the page and never crossing a block; if a whole block is not unique, the para number is added as a prefix
   (`38.-,A bank shall not:`). Result: 972/975 ok (880 unchanged, 80 longer or re-cut, 12 with a number prefix), 3 deleted -> section-anchor
   link, 0 shared.
2. `clause_link` uses the file; without it (fresh checkout) it falls back to the old 8 words. Kept in data/parsed/
   (gitignored) like the parsed text: RBI's terms (ADR-003).
3. `eval/check_rbi_links.py` re-checks every phrase against the LIVE pages (catches RBI editing a clause) and lists 6
   links to click by hand - a script cannot see the highlight.

## Done when
check_rbi_links: every phrase ok on both live pages (or, if RBI serves the language page, the offline run is clean on
a freshly saved copy); the 6 sample links (CF 108, 109, 38, 303, 111; RBC 351) each highlight the paragraph named.

## Trade-off
Some links are long (CF 108/109 share 20 words before they differ). If RBI edits a clause, its phrase can stop
matching: the page then opens at the top, as with a section link - the live check is how we notice.

## Result (27 Nov 2026)
- `eval/check_rbi_links.py` on the live pages: 514 Credit Facilities + 458 Responsible Business Conduct phrases, each
  exactly once within one block - RESULT: ALL OK.
- Browser check (Claude desktop app's built-in browser, Chromium): CF 108, CF 109, CF 38, CF 303 (prefix "303."),
  CF 111 and RBC 351 each highlighted only the paragraph named. Opening a second fragment on the SAME page without a
  reload can leave the earlier highlight visible (seen with 108 then 109); a fresh load shows only the right one.
  First visit still lands on RBI's home page until its cookie is set (ADR-003); the screen keeps its one-line note.
