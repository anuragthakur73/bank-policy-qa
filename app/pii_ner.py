# Week 6 S4 (ADR-021): person names and postal addresses, on top of the ADR-015 patterns in app/pii.py.
# Names: spaCy NER (PERSON) + three rules (honorific, role word such as "customer"/"borrower", initials), minus a
# filter for lending terms the model mistakes for names (EMI, FOIR, "Max tenure", "Kothrud branch").
# Addresses: rules only (no NER label for an Indian postal address): comma/" - " separated runs that contain a
# strong part (Flat/House/Plot/Door/Shop/Villa/Gat + number, number + street word, PIN code). A bare city or state
# ("a flat in Pune") is NOT masked: it identifies no one and can matter to the answer.
# Runs locally: no text leaves the machine. PII_NER=0 turns names off; PII_ADDRESS=0 turns addresses off.
import os, re
from functools import lru_cache

NER_MODEL = os.environ.get("PII_NER_MODEL", "en_core_web_lg")

# --- names -------------------------------------------------------------------------------------------------------
NAME_TOK = r"(?:[A-Z][a-zA-Z']+(?![\w])|[A-Z]\.)"           # whole words only: "PAN ABCDE1234F" is not a name
NAME = rf"{NAME_TOK}(?:\s+{NAME_TOK}){{0,3}}"
HONORIFIC = re.compile(rf"\b(?:Mr|Mrs|Ms|Smt|Shri|Sri|Dr|Fr|Kumari|Km)\.?\s+({NAME})")
ROLE = re.compile(rf"(?i:\b(?:customer|borrower|applicant|co-applicant|co-borrower|guarantor))(?:\s+(?:is|was|named))?"
                  rf"(?:\s+(?:a|an|the)\b[^,.]*?)?\s+({NAME})")
ROLE_NAME_FIELD = re.compile(r"(?i)\b(?:customer|borrower|applicant)?\s*name\s*[:\-]\s*([a-z][a-z']+(?:\s+[a-z][a-z']+){0,3})")
SUBJECT = re.compile(rf"\b(?:Can|Is|Does|Will|Should|Could)\s+({NAME_TOK}(?:\s+{NAME_TOK}){{1,3}})(?:'s)?\s+(?:get|take|apply|"
                     rf"avail|be|have|prepay|pay|use|borrow|qualify|afford|close|transfer)\b")
INITIALS = re.compile(r"\b((?:[A-Z]\.\s?){1,3}[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})")
# lending vocabulary and occasions: a PERSON span containing one of these is a false alarm
NOT_NAME = {"emi", "emis", "foir", "ltv", "kyc", "noc", "lap", "nps", "cibil", "max", "min", "tenure", "loan", "rate",
            "fee", "charge", "branch", "bank", "office", "road", "nagar", "market", "society", "colony", "chaturthi",
            "jayanti", "navratri", "diwali", "holi", "eid", "pongal", "onam", "puja", "yojana", "rbi", "sarfaesi",
            "ombudsman", "karta", "huf", "ev", "suv", "nri", "navami", "ramzan", "christmas", "dussehra", "ganeshotsav",
            "sankranti", "maruti", "suzuki", "tata", "mahindra", "hyundai", "kia", "honda", "toyota", "skoda",
            "volkswagen", "renault", "nissan", "bmw", "mercedes", "audi", "jeep", "citroen", "byd", "seltos",
            "creta", "nexon", "swift", "xuv700"}
FOLLOW_NOT_NAME = re.compile(r"^\s+(?:branch|office|road|nagar|market|bank|colony|society)\b", re.I)

@lru_cache
def _nlp():
    import spacy
    return spacy.load(NER_MODEL, disable=["lemmatizer", "parser"])

def _ok_name(text, s, e):
    toks = re.findall(r"[A-Za-z']+", text[s:e])
    if not toks or any(t.lower() in NOT_NAME for t in toks):
        return False
    if all(t.isupper() and len(t) <= 5 for t in toks):        # acronyms: EMI, KYC
        return False
    return not FOLLOW_NOT_NAME.match(text[e:])

def name_spans(text):
    spans = [(x.start_char, x.end_char) for x in _nlp()(text).ents if x.label_ == "PERSON"]
    for rx in (HONORIFIC, ROLE, ROLE_NAME_FIELD, INITIALS, SUBJECT):
        spans += [(m.start(1), m.end(1)) for m in rx.finditer(text)]
    out = []
    for s, e in spans:
        while e > s and text[e - 1] in ".,'": e -= 1           # "D'Souza." -> keep the name only
        if text[e - 2:e] == "'s": e -= 2                       # "Pooja Reddy's" -> the name
        if _ok_name(text, s, e):
            out.append((s, e, "PERSON"))
    return out

# --- addresses -----------------------------------------------------------------------------------------------------
NUM = r"[A-Z]?-?\d+[A-Za-z]?(?:[/-]\d+)*"
STREET = (r"road|rd|marg|lane|street|cross|main|nagar|colony|sector|layout|society|chs|apartments?|apts?|towers?|"
          r"heights|residency|complex|market|niwas|sadan|bhavan|enclave|vihar|village|taluka|tehsil|chowk|peth|"
          r"gali|mohalla|palava|meadows|park|floor")
CUE_NUM = re.compile(rf"(?i)\b(?:flat|house|h\.?\s?no|door|plot|shop|villa|bungalow|gat|survey|unit|room|block|"
                     rf"plot)\b(?:\s*(?:no\.?|number|#))?(?:\s+at)?\s*[:.]?\s*{NUM}")
NUM_STREET = re.compile(rf"(?i)\b(?:\d+(?:st|nd|rd|th)?|{NUM})\s+(?:[A-Z][\w']*\s+){{0,3}}(?:{STREET})\b|"
                        rf"\b(?:{STREET})\s+(?:\d+|[IVX]+)\b", )
PIN = re.compile(r"(?<![\d,.])[1-9]\d{2}\s?\d{3}(?![\d,])")
MONEY_BEFORE = re.compile(r"(?i)(?:rs\.?|inr|₹|salary|income|amount|loan|emi|price|value)\b[^,]{0,12}$")
CAPS = re.compile(r"^(?:[A-Z][\w'.]*|\d+(?:st|nd|rd|th)?)(?:\s+(?:[A-Z][\w'.]*|\d+(?:st|nd|rd|th)?))*$")
BARE_NUM = re.compile(rf"^{NUM}$")
ABBREV = re.compile(r"(?i)(?:\bno|\bdr|\bmr|\bmrs|\bms|\bsmt|\bfr|\bst|\b[a-z])\.$")

PIN_BEFORE = re.compile(r"(?:\b[A-Z][a-z]+|(?i:\bpin(?:\s?code)?)\s*[:.-]?|^|-)\s*$")
def _pins(seg, off):
    return [(off + m.start(), off + m.end()) for m in PIN.finditer(seg)
            if PIN_BEFORE.search(seg[:m.start()]) and not MONEY_BEFORE.search(seg[:m.start()])]

def _classify(seg):
    s = seg.strip()
    if CUE_NUM.search(s) or NUM_STREET.search(s) or _pins(s, 0):
        return "strong"
    if re.search(rf"\b(?:at|is|address|no\.?)\s*:?\s*{NUM}$", s) and re.search(r"\d", s.split()[-1]):
        return "weak"                                          # "The flat is at A-404", "address 22"
    if BARE_NUM.match(s) or re.search(rf"(?i)\b(?:{STREET})\b", s) and CAPS.match(s) or CAPS.match(s) and len(s.split()) <= 4:
        return "weak"
    return None

def _sentences(text):
    a = 0
    for m in re.finditer(r"[.?!](?=\s|$)", text):
        if not ABBREV.search(text[:m.end()]):
            yield a, m.start(); a = m.end()
    yield a, len(text)

def address_spans(text):
    out = []
    for a, b in _sentences(text):
        segs, pos = [], a
        for m in re.finditer(r",|\s-\s|;|:", text[a:b] + ","):
            end = a + m.start()
            segs.append((pos, end)); pos = a + m.end()
        segs = [(s, e) for s, e in segs if s < e]
        kinds = [_classify(text[s:e]) for s, e in segs]
        i = 0
        while i < len(segs):
            j = i
            while j < len(segs) and kinds[j]: j += 1
            # a run may not START with plain capitalised words (a name, "Customer Ramesh Sharma") before its first
            # strong part; leading house numbers ("22", "A-404") and street words ("Baner Road") are kept
            while i < j and kinds[i] == "weak" and not re.search(rf"\d|(?i:\b(?:{STREET})\b)", text[segs[i][0]:segs[i][1]]):
                i += 1
            if i == j:
                i = j + 1; continue
            run = range(i, j)
            if any(kinds[k] == "strong" for k in run) and (j - i >= 2 or kinds[i] == "strong"):
                # trim the first segment to where the address starts, the last to its PIN if any
                s0, e0 = segs[i]; first = text[s0:e0]
                starts = [m.start() for rx in (CUE_NUM, NUM_STREET) for m in rx.finditer(first)]
                tail = re.search(rf"(?:{NUM}|[A-Z][\w'.]*)(?:\s+(?:{NUM}|[A-Z][\w'.]*))*\s*$", first)
                if tail: starts.append(tail.start())
                start = s0 + (min(starts) if starts else 0)
                sl, el = segs[j - 1]
                pins = _pins(text[sl:el], sl)
                end = pins[-1][1] if pins else el
                out.append((start, end, "ADDRESS"))
            i = j + 1 if j == i else j
    return out

# --- localities tied to the customer or the property (Week 6 S4b; Anurag's set, option A) -------------------------
# "resident of Kharadi in Pune", "from Salt Lake", "flat in Springdale in Walker, Pune": place words after a residence
# or property cue are masked up to the first city/state, which is kept ("a flat in Pune" identifies no one).
CITIES = {"mumbai", "navi mumbai", "thane", "pune", "nashik", "nasik", "nagpur", "aurangabad", "kolhapur", "satara",
          "solapur", "amravati", "delhi", "new delhi", "delhi ncr", "ncr", "noida", "gurugram", "gurgaon", "faridabad",
          "ghaziabad", "bengaluru", "bangalore", "mysuru", "mysore", "mangaluru", "chennai", "coimbatore", "madurai",
          "hyderabad", "secunderabad", "visakhapatnam", "vijayawada", "kolkata", "howrah", "ahmedabad", "surat",
          "vadodara", "rajkot", "jaipur", "jodhpur", "udaipur", "lucknow", "kanpur", "varanasi", "agra", "indore",
          "bhopal", "patna", "ranchi", "bhubaneswar", "cuttack", "guwahati", "chandigarh", "ludhiana", "amritsar",
          "kochi", "cochin", "thiruvananthapuram", "trivandrum", "kozhikode", "goa", "panaji", "dehradun", "shimla",
          "srinagar", "jammu", "raipur", "nanded", "latur", "jalgaon", "ahmednagar", "sangli", "lonavala",
          "maharashtra", "karnataka", "kerala", "tamil nadu", "telangana", "andhra pradesh", "gujarat", "rajasthan",
          "uttar pradesh", "madhya pradesh", "bihar", "west bengal", "odisha", "assam", "punjab", "haryana",
          "jharkhand", "chhattisgarh", "uttarakhand", "himachal pradesh", "india", "dubai", "uae", "usa", "uk",
          "singapore", "canada", "australia", "abroad"}
LOC_CUE_ANYCASE = re.compile(r"(?i)\b(?:resident of|residing (?:at|in)|r/o|r\.o\.|lives? (?:in|at)|living (?:in|at)|"
                             r"stay(?:s|ing)? (?:in|at)|native of)\s+")
LOC_CUE_CAPS = re.compile(r"(?i)\b(?:from|based in|located (?:in|at)|situated (?:in|at)|(?:flat|house|property|plot|"
                          r"bungalow|shop|land|apartment|villa|row house|office)\s+(?:is\s+)?(?:in|at))\s+")
LOC_STOP = {"want", "wants", "wanted", "is", "are", "was", "were", "he", "she", "they", "can", "could", "and", "who",
            "which", "has", "have", "had", "for", "to", "with", "but", "the", "a", "an", "our", "his", "her", "their",
            "another", "other", "same", "near", "will", "would", "should", "does", "do", "did", "of", "on", "by",
            "floating", "fixed", "next", "last", "this", "that", "under", "over", "in", "at", "or", "versus", "vs", "rs", "inr", "lakh", "lakhs", "crore", "crores"}
ORG = re.compile(r"(?i)\b(?:bank|finance|financial|ltd|limited|corporation|corp|industries|company|pvt|nbfc|"
                 r"rbi|insurance|services)\b")

def _place_pieces(text, start, caps):
    """Place-word pieces from `start`: split at ',' and ' in '; stop at a stop word, a city or punctuation."""
    pieces, pos = [], start
    while True:
        m = re.match(r"\s*([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,3})", text[pos:])
        if not m:
            break
        words = m.group(1).split()
        keep = []
        for w in words:
            if w.lower().strip(".") in LOC_STOP or (caps and not w[0].isupper()):
                break
            keep.append(w)
        if not keep:
            break
        piece = " ".join(keep)
        ps = pos + m.start(1); pe = ps + len(piece)
        if piece.lower().strip(".") in CITIES or ORG.search(piece) or all(w.isupper() for w in keep):
            break                                              # a city / state / bank / acronym ends the run
        # a city at the end of the piece ("Ram Nagar Pune"): keep it
        for n in (2, 1):
            if len(keep) > n and " ".join(keep[-n:]).lower() in CITIES:
                pe = ps + len(" ".join(keep[:-n])); pieces.append((ps, pe)); return pieces
        pieces.append((ps, pe))
        nxt = re.match(r"(?:\s*,\s*|\s+in\s+)", text[pe:])
        if not nxt:
            break
        pos = pe + nxt.end()
    return pieces

PERSON_HINT = re.compile(r"(?i)\b(?:customer|cust|borrower|applicant|co-applicant|guarantor|he|she|his|her|him|"
                         r"they|their)\b")

def locality_spans(text, has_name=False):
    # "resident of" / "r/o" always describes a person; "from" / "flat in" only when a person is in the question
    # ("Can a loan be given for a flat in Lavasa?" identifies no one)
    out, person = [], has_name or bool(PERSON_HINT.search(text))
    for rx, caps in ((LOC_CUE_ANYCASE, False), (LOC_CUE_CAPS, True)):
        if caps and not person:
            continue
        for m in rx.finditer(text):
            pieces = _place_pieces(text, m.end(), caps)
            if pieces:
                out.append((pieces[0][0], pieces[-1][1], "ADDRESS"))
    return out

def find(text):
    spans = []
    if os.environ.get("PII_NER", "1") != "0":
        spans += name_spans(text)
    if os.environ.get("PII_ADDRESS", "1") != "0":
        spans += address_spans(text) + locality_spans(text, has_name=bool(spans))
    return spans
