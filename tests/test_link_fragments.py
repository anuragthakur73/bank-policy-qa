# S5 (ADR-019): text-fragment phrases that highlight the right clause. Small fake RBI page; no network.
import app.generate as gen
from ingest.link_fragments import page_blocks, build

PAGE = """<html><body>
<p>108. The bank may grant term loans to housing intermediary agencies against the direct loans sanctioned by the latter.</p>
<p>109. The bank may grant term loans to housing intermediary agencies against loans to NRIs also.</p>
<p>38. A bank shall not:</p><p>(1) Avail loans by re-pledging gold.</p>
<p>40. A bank shall not:</p><p>(1) Lend against its own shares.</p>
<p>F.3 Interest on Export Credit in Foreign Currency 303. The bank is free to determine interest rates.</p>
<p>(1) For the purpose of these Directions,</p><p>1 [(ia) ‘Acquisition Finance’ shall mean a facility provided to an eligible borrower.</p>
<p>9. Disclosures to borrowers</p><p>(1) A bank shall provide a Key Fact Statement.</p>
</body></html>"""
B = page_blocks(PAGE)

def test_shared_start_grows_until_unique():          # r04: 108 and 109 share their first 8 words
    a = build(B, "108", "108. The bank may grant term loans to housing intermediary agencies against the direct loans")
    b = build(B, "109", "109. The bank may grant term loans to housing intermediary agencies against loans to NRIs also.")
    assert a["status"] == b["status"] == "ok" and a["start"] != b["start"]
    assert a["start"].endswith("against the") and b["start"].endswith("against loans")

def test_heading_block_is_not_crossed():             # 38: old phrase ran into "(1) Avail loans by"
    r = build(B, "38", "38. A bank shall not: (1) Avail loans by re-pledging gold.")
    assert r["start"] == "A bank shall not:" and r["prefix"] == "38."   # same heading in 40 -> number as prefix

def test_heading_only_block_unique():
    r = build(B, "9", "9. Disclosures to borrowers (1) A bank shall provide a Key Fact Statement.")
    assert r == {**r, "status": "ok", "start": "Disclosures to borrowers", "prefix": None}

def test_number_in_the_middle_of_a_block():          # 303: heading and para merged in RBI's HTML
    r = build(B, "303", "303. The bank is free to determine interest rates.")
    assert r["status"] == "ok" and r["prefix"] == "303." and r["start"].startswith("The bank is free")

def test_amendment_marker_and_subclause_label():     # 4(ia): "1 [(ia) ‘Acquisition Finance’ ..."
    r = build(B, "4(ia)", "(ia) ‘Acquisition Finance’ shall mean a facility provided to an eligible borrower.")
    assert r["status"] == "ok" and r["start"].startswith("‘Acquisition Finance’ shall mean")

def test_deleted_para():
    assert build(B, "60", "60. *****] 19 [ Chapter VA")["status"] == "deleted"

def test_clause_link_uses_the_map(monkeypatch):
    monkeypatch.setattr(gen, "_fragments", lambda: {
        "D|38": {"status": "ok", "prefix": "38.", "start": "A bank shall not:"},
        "D|60": {"status": "deleted"}})
    h = {"layer": "rbi", "doc_id": "D", "clause_no": "38", "source_url": "https://rbi.org.in/x", "text": "38. A bank shall not: (1) x"}
    assert gen.clause_link(h) == "https://rbi.org.in/x#:~:text=38.-,A%20bank%20shall%20not%3A"
    assert gen.clause_link({**h, "clause_no": "60", "section_anchor": "C5A"}) == "https://rbi.org.in/x#C5A"
    assert gen.clause_link({**h, "clause_no": "61", "text": "61. Self-help groups may borrow"}).endswith(
        "#:~:text=Self%2Dhelp%20groups%20may%20borrow")       # not in the map: old 8-word phrase
