#!/usr/bin/env python3
# rules_parser.py
# Author: Aman Pathak (refactored into parser module)

import sys
import re
from typing import List, Tuple, Optional

# Optional imports
DATEUTIL_AVAILABLE = False
try:
    from dateutil import parser as date_parser
    DATEUTIL_AVAILABLE = True
except Exception:
    DATEUTIL_AVAILABLE = False

# PDF text extraction via PyMuPDF (fitz)
try:
    import fitz  # PyMuPDF
except Exception as e:
    print("Error: PyMuPDF (fitz) is required for PDF text extraction.", file=sys.stderr)
    raise

# ----------------------------
# Text extraction and helpers
# ----------------------------

def load_pdf_text_by_page(pdf_path: str) -> List[str]:
    """
    Returns a list of page texts (strings).
    Uses PyMuPDF to extract text in reading order.
    """
    all_pages = []
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                page_text = page.get_text("text", sort=True)
                all_pages.append(page_text)
    except Exception as e:
        print(f"Error opening or reading PDF {pdf_path}: {e}", file=sys.stderr)
        sys.exit(1)
    return all_pages


def normalize_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text or "").strip()


def normalize_whitespace_keep_newlines(text: str) -> str:
    if text is None:
        return ""
    t = text.replace('\r\n', '\n').replace('\r', '\n')
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = "\n".join(line.strip() for line in t.split('\n'))
    return t.strip()


def split_into_lines_by_page(pages: List[str]) -> List[List[str]]:
    out = []
    for p in pages:
        lines = p.split('\n')
        stripped = [ln.strip() for ln in lines]
        stabilized = []
        prev_empty = False
        for ln in stripped:
            is_empty = (ln == "")
            if is_empty and prev_empty:
                continue
            stabilized.append(ln)
            prev_empty = is_empty
        out.append(stabilized)
    return out

# ----------------------------
# Patterns and simple detectors
# ----------------------------

EXHIBIT_HEADER_RE = re.compile(r'^\s*(EXHIBIT|SCHEDULE|ANNEX)\s+[A-Z0-9.\-]+', re.IGNORECASE)
PAGE_MARKER_RE = re.compile(r'^\s*-?\s*\d+\s*-?\s*$', re.IGNORECASE)

SECTION_NUMBER_RE = re.compile(
    r'^\s*('
    r'(?:\d+(?:\.\d+)+)'
    r'|(?:\d+\.)'
    r'|(?:\d+\))'
    r'|(?:[IVXLCDM]+[.)])'
    r'|(?:[A-Za-z][.)])'
    r'|(?:\d+)(?=\s+[A-Z][A-Za-z])'
    r')\s+(.*)$',
    re.IGNORECASE
)

SECTION_HEADER_CANDIDATE_RE = re.compile(
    r'^\s*(?P<num>('
    r'(?:\d+(?:\.\d+)+)'
    r'|(?:\d+[.)])'
    r'|(?:[IVXLCDM]+[.)])'
    r'|(?:[A-Za-z][.)])'
    r'|(?:\d+)(?=\s+[A-Z][A-Za-z])'
    r'))\s+(?P<title>.*)$',
    re.IGNORECASE
)

CLAUSE_LABEL_RE = re.compile(
    r'^\s*(?P<label>('
    r'\((?:\d+|[a-z]|[ivxlcdm]+)\)'
    r'|(?:\d+(?:\.\d+)+)'
    r'|(?:\d+[.)])'
    r'|(?:[A-Za-z][.)])'
    r'|(?:[IVXLCDM]+[.)])'
    r'))\s+(?P<rest>.*)$',
    re.IGNORECASE
)

VERBISH_RE = re.compile(
    r'\b(shall|may|agrees?|agree|use|apply|permit|terminate|means?|includes?|'
    r'specif(?:y|ies)|located|notified|submit(?:ted)?|approved?|distribute|'
    r'market|sell|provide|deliver|perform)\b', re.IGNORECASE
)
PREAMBLE_BOUNDARY_RE = re.compile(r'^\s*(WHEREAS|NOW,\s*THEREFORE|THEREFORE)\b', re.IGNORECASE)

def is_exhibit_header(line: str) -> bool:
    return bool(EXHIBIT_HEADER_RE.match(line.strip()))

def is_page_marker(line: str) -> bool:
    return bool(PAGE_MARKER_RE.match(line.strip()))

def looks_like_title(line: str) -> bool:
    up = line.strip()
    if len(up) <= 3:
        return False
    is_upper = up == up.upper()
    no_terminal_period = not up.endswith(".")
    length_ok = len(up) <= 120
    return is_upper and no_terminal_period and length_ok

def is_all_caps_or_titleish(line: str) -> bool:
    letters = re.sub(r'[^A-Za-z]', '', line)
    if len(letters) >= 4:
        uppercase_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if uppercase_ratio >= 0.8 and len(line) <= 120:
            return True
    words = line.split()
    if 1 <= len(words) <= 12:
        titled = sum(1 for w in words if w and w[0].isupper())
        if titled / max(1, len(words)) >= 0.8 and len(line) <= 120:
            return True
    return False

def is_titleish_header(text: str) -> bool:
    t = text.strip()
    if not t or len(t) > 120:
        return False
    if VERBISH_RE.search(t):
        return False
    words = [w for w in re.split(r'\s+', t) if w]
    if len(words) < 2:
        return False
    letters = re.sub(r'[^A-Za-z]', '', t)
    if len(letters) >= 4:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio >= 0.8:
            return True
    titled = sum(1 for w in words if w[0].isupper())
    return (titled / max(1, len(words))) >= 0.8

def is_small_integer_token(tok: str) -> bool:
    try:
        return 0 < int(tok) < 100
    except Exception:
        return False

def looks_valid_section_title(line: str) -> bool:
    if re.search(r'^Page\s+\d+\s*$', line, flags=re.IGNORECASE):
        return False
    return True

def normalize_section_number(number: Optional[str]) -> Optional[str]:
    if number is None:
        return None
    return number.strip()

def try_peek_next_title(doc_lines: List[Tuple[int, str]], start_idx: int) -> str:
    j = start_idx
    while j < len(doc_lines):
        _, ln = doc_lines[j]
        raw = ln.strip()
        if raw:
            return raw
        j += 1
    return ""

def build_clause_label(m: re.Match) -> str:
    return normalize_whitespace(m.group(1))

# ----------------------------
# Title/type and sectioning
# ----------------------------

def guess_title_and_type(pages_lines: List[List[str]]) -> Tuple[str, str]:
    first_page = pages_lines[0] if pages_lines else []
    candidates = [ln.strip() for ln in first_page if ln.strip()]

    for ln in candidates[:15]:
        if is_exhibit_header(ln):
            continue
        if looks_like_title(ln) and re.search(
            r'\b(AGREEMENT|CONTRACT|LEASE|AMENDMENT|ADDENDUM|NDA|STATEMENT OF WORK|SOW)\b',
            ln, re.IGNORECASE
        ):
            title = ln.strip()
            return normalize_whitespace(title), derive_contract_type_from_title(title)

    for ln in candidates[:15]:
        if is_exhibit_header(ln):
            continue
        if looks_like_title(ln):
            title = ln.strip()
            return normalize_whitespace(title), derive_contract_type_from_title(title)

    for ln in candidates:
        if is_exhibit_header(ln):
            continue
        title = ln.strip()
        return normalize_whitespace(title), derive_contract_type_from_title(title)

    return "Agreement", "Agreement"

def derive_contract_type_from_title(title: str) -> str:
    t = title.strip()
    patterns = [
        r'(Master [A-Za-z ]*Agreement)',
        r'([A-Za-z ]*Agreement)',
        r'([A-Za-z ]*Contract)',
        r'([A-Za-z ]*Lease)',
        r'(Non[- ]Disclosure Agreement|NDA)',
        r'(Statement of Work|SOW)',
        r'(Amendment|Addendum)'
    ]
    for pat in patterns:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
    return "Agreement"

def segment_sections(lines_by_page: List[List[str]], known_title: Optional[str] = None) -> List[dict]:
    VERBISH_LOCAL = re.compile(
        r'\b(shall|may|agrees?|agree|use|apply|permit|terminate|means?|includes?|'
        r'specif(?:y|ies)|located|notified|submit(?:ted)?|approved?|distribute|'
        r'market|sell|provide|deliver|perform|reimburse|incurred|participat(?:e|ing)|'
        r'subject|reserved|understand(?:s)?|deliver(?:y)?)\b',
        re.IGNORECASE
    )

    def is_short_title(text: str) -> bool:
        t = text.strip()
        if not t or len(t) > 120:
            return False
        if VERBISH_LOCAL.search(t):
            return False
        words = [w for w in re.split(r'\s+', t) if w]
        if len(words) == 1:
            w = words[0]
            if re.search(r'[.,;:!?]$', w):
                return False
            if not (w[0].isupper() or w.isupper()):
                return False
            return True
        return len(words) <= 8

    def split_short_heading(rest: str) -> Tuple[Optional[str], str]:
        m = re.match(r'^\s*(?P<head>[^.:;:\-\u2013\u2014]{1,80}?)\s*[.:;:\-\u2013\u2014]\s*(?P<trail>.*)$', rest)
        if not m:
            return None, rest
        head = m.group('head').strip()
        trail = m.group('trail').strip()
        return (head if head else None), trail

    clause_re = re.compile(
        r'^\s*(?P<label>('
        r'\((?:\d+|[a-z]|[ivxlcdm]+)\)'
        r'|(?:\d+(?:\.\d+)+)'
        r'|(?:\d+[.)])'
        r'|(?:[A-Za-z][.)])'
        r'|(?:[IVXLCDM]+[.)])'
        r'))\s+(?P<rest>.*)$',
        re.IGNORECASE
    )

    doc_lines = []
    for page_idx, page_lines in enumerate(lines_by_page):
        for ln in page_lines:
            doc_lines.append((page_idx, ln))

    sections = []
    current_section = None

    def start_section(title: str, number: Optional[str]):
        return {
            "title": normalize_whitespace(title) if title else "",
            "number": normalize_section_number(number),
            "clauses": []
        }

    i = 0
    N = len(doc_lines)
    while i < N:
        _, line = doc_lines[i]
        raw = line.strip()
        if not raw or is_page_marker(raw) or is_exhibit_header(raw):
            i += 1
            continue

        if known_title and raw.upper() == known_title.strip().upper():
            i += 1
            continue

        m = SECTION_HEADER_CANDIDATE_RE.match(raw)
        if m:
            num = m.group("num").rstrip(".)")
            remainder = m.group("title").strip()

            if re.fullmatch(r'\d+', num) and not is_small_integer_token(num):
                pass
            else:
                if is_titleish_header(remainder):
                    current_section = start_section(remainder, num)
                    sections.append(current_section)
                    i += 1
                    continue

        if is_titleish_header(raw) and looks_valid_section_title(raw) and not is_exhibit_header(raw):
            current_section = start_section(raw, None)
            sections.append(current_section)
            i += 1
            continue

        if current_section is None:
            current_section = start_section("General", None)
            sections.append(current_section)

        lm = clause_re.match(raw)
        if lm:
            label_raw = lm.group("label")
            rest = (lm.group("rest") or "").strip()

            num_token = re.sub(r'[.)]$', '', label_raw)
            if num_token.isdigit() and is_short_title(rest):
                current_section = start_section(rest, num_token)
                sections.append(current_section)
                i += 1
                continue

            if num_token.isdigit():
                head, tail = split_short_heading(rest)
                if head and is_short_title(head):
                    current_section = start_section(head, num_token)
                    sections.append(current_section)
                    if tail:
                        m2 = clause_re.match(tail)
                        if m2:
                            sub_label = normalize_whitespace(m2.group("label"))
                            sub_rest = normalize_whitespace(m2.group("rest") or "")
                            current_section["clauses"].append({"text": sub_rest, "label": sub_label, "index": 0})
                        else:
                            current_section["clauses"].append({"text": normalize_whitespace(tail), "label": "", "index": 0})
                    i += 1
                    continue

            label = normalize_whitespace(label_raw)
            text = normalize_whitespace(rest)
            current_section["clauses"].append({"text": text, "label": label, "index": 0})
            i += 1
            continue

        if not current_section["clauses"]:
            current_section["clauses"].append({"text": normalize_whitespace(raw), "label": "", "index": 0})
        else:
            prev = current_section["clauses"][-1]
            prev["text"] = normalize_whitespace(prev["text"] + " " + raw)

        i += 1

    for sec in sections:
        for idx, cl in enumerate(sec["clauses"]):
            cl["index"] = idx

    return [s for s in sections if (s["clauses"] or s["title"])]

# ----------------------------
# Dates
# ----------------------------

DATE_PATTERNS = [
    r'([Jj]anuary|[Ff]ebruary|[Mm]arch|[Aa]pril|[Mm]ay|[Jj]une|[Jj]uly|[Aa]ugust|[Ss]eptember|[Oo]ctober|[Nn]ovember|[Dd]ecember)\s+\d{1,2},\s+\d{4}',
    r'\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4}',
    r'\b\d{4}-\d{2}-\d{2}\b',
    r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'
]

EFFECTIVE_DATE_CUES = [
    r'effective as of',
    r'effective date',
    r'dated as of',
    r'becomes effective on',
    r'effective on'
]

def try_parse_date_to_iso(s: str) -> Optional[str]:
    s = s.strip()
    if not s:
        return None
    if DATEUTIL_AVAILABLE:
        try:
            dt = date_parser.parse(s, dayfirst=False, yearfirst=False, fuzzy=True)
            return dt.date().isoformat()
        except Exception:
            return None
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', s)
    if m:
        return s
    return None

def extract_effective_date(pages_text: List[str]) -> Optional[str]:
    full_text = "\n".join(pages_text[:3]) if pages_text else ""
    snippet = full_text.lower()
    pos = len(snippet)
    for cue in EFFECTIVE_DATE_CUES:
        m = re.search(cue, snippet)
        if m and m.start() < pos:
            pos = m.start()

    date_candidates = []
    search_region = full_text
    for pat in DATE_PATTERNS:
        for dm in re.finditer(pat, search_region, flags=re.IGNORECASE):
            date_candidates.append(dm.group(0))

    if date_candidates:
        for cand in date_candidates:
            iso = try_parse_date_to_iso(cand)
            if iso:
                return iso

    full_doc = "\n".join(pages_text)
    for pat in DATE_PATTERNS:
        dm = re.search(pat, full_doc, flags=re.IGNORECASE)
        if dm:
            iso = try_parse_date_to_iso(dm.group(0))
            if iso:
                return iso
    return None

# ----------------------------
# Output assembly
# ----------------------------

def assemble_output_json(title: str, contract_type: str, effective_date: Optional[str], sections: List[dict]) -> dict:
    out_sections = []
    for sec in sections:
        sec_title = normalize_whitespace(sec.get("title", ""))
        sec_number = sec.get("number", None)
        if sec_number is not None:
            sec_number = str(sec_number).strip() or None

        out_clauses = []
        for idx, cl in enumerate(sec.get("clauses", [])):
            text = normalize_whitespace(cl.get("text", ""))
            label = cl.get("label", "")
            if label is None:
                label = ""
            label = normalize_whitespace(label)
            out_clauses.append({
                "text": text,
                "label": label if label else "",
                "index": idx
            })

        out_sections.append({
            "title": sec_title,
            "number": sec_number if sec_number is not None else None,
            "clauses": out_clauses
        })

    return {
        "title": normalize_whitespace(title) if title else "",
        "contract_type": normalize_whitespace(contract_type) if contract_type else "",
        "effective_date": effective_date if effective_date is not None else None,
        "sections": out_sections
    }

# ----------------------------
# Public entrypoint
# ----------------------------


def parse_pdf_to_contract(pages_text: list[str]) -> dict:
    """
    Orchestrates the entire parsing pipeline and returns the JSON-serializable dict.
    """
    # pages_text = load_pdf_text_by_page(pdf_path)
    lines_by_page = split_into_lines_by_page(pages_text)
    title, contract_type = guess_title_and_type(lines_by_page)
    sections = segment_sections(lines_by_page, known_title=title)
    effective_date = extract_effective_date(pages_text)
    return assemble_output_json(title, contract_type, effective_date, sections)