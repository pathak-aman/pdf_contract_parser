# utils.py
# Contains helper functions for PDF text extraction and text normalization.

import re
import sys
from datetime import datetime
from typing import Optional

SCOPE_TO_FIND_EFFECTIVE_DATE = 2500
ISO_DATE_FORMAT = "%Y-%m-%d"

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF is not installed. Please run 'pip install PyMuPDF'.", file=sys.stderr)
    sys.exit(1)

try:
    from PIL import Image
    from pdf2image import convert_from_path
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

def normalize_text(text: str) -> str:
    """Normalizes whitespace and removes leading/trailing spaces."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def preprocess_ocr_numbers(text: str) -> str:
    """
    Normalize only numeric labels misread by OCR (e.g., 'i2.' -> '12.', 'iS.' -> '15.', 'i€.' -> '16.').
    Conservative:
      - Only operates on label-like tokens at start-of-line (e.g., '12.', '1)', '12)').
      - Skips pure Roman-numeral labels (II., IV., etc.).
      - Skips single-letter labels (A., B., G.) to avoid breaking lettered sections.
    """

    if not text:
        return text

    def safe_sub(pattern, repl, s, flags=0):
        try:
            return re.sub(pattern, repl, s, flags=flags)
        except re.error as e:
            print(f"WARN: preprocess_ocr_numbers regex failed: {pattern} -> {e}", file=sys.stderr)
            return s

    # Specific fix for the Euro sign misread as '6' at start-of-line (e.g., '€. PAYMENTS.')
    text = safe_sub(r"(?m)^\s*€(?P<punc>[.)])", r"6\g<punc>", text)

    # Map ambiguous characters to digits, but only inside label-like tokens.
    # We require at least 2 chars in the token to avoid converting 'G.' (legit lettered header).
    DIGIT_MAP = {
        'i': '1', 'I': '1', 'l': '1', '|': '1',
        'O': '0', 'o': '0',
        'S': '5', '$': '5',
        '€': '6',
        # These are more aggressive; keep only in mixed tokens with at least one digit/ambiguous '1'
        'Z': '2', 'z': '2',
        'B': '8', 'g': '8',
        'q': '9',
    }

    ROMAN_SET = set("IVXLCDMivxlcdm")

    def normalize_num_token(tok: str) -> str:
        # If token is pure Roman numerals, leave it (II., IV., etc.)
        if tok and all(ch in ROMAN_SET for ch in tok) and not any(ch.isdigit() for ch in tok):
            return tok.upper()
        if len(tok) == 1:
            # Single letters like 'A.' should be left as lettered headers
            if tok.isalpha():
                return tok
            # Lone symbols like '€' are handled by specific rule above; leave here
            return tok

        # Only normalize if the token contains at least one digit or an 'ambiguous 1' (i,I,l,|)
        ambiguous_one = any(ch in ('i','I','l','|') for ch in tok)
        if not any(ch.isdigit() for ch in tok) and not ambiguous_one:
            return tok  # looks like a pure word, skip

        out_chars = []
        changed = False
        for ch in tok:
            if ch in DIGIT_MAP:
                # Only allow aggressive maps (Z->2, B->8, q/g->9) if token already looks numeric-ish
                if ch in ('Z','z','B','q','g'):
                    if any(c.isdigit() for c in tok) or ambiguous_one:
                        out_chars.append(DIGIT_MAP[ch]); changed = True
                    else:
                        out_chars.append(ch)
                else:
                    out_chars.append(DIGIT_MAP[ch]); changed = True
            else:
                out_chars.append(ch)
        new_tok = "".join(out_chars)

        # Final guard: Require the normalized token to be all digits (e.g., '12'), otherwise keep original
        if new_tok.isdigit():
            return new_tok
        return tok

    # Case A: Start-of-line label with punctuation and space/title, e.g., 'i2. TRADEMARKS'
    def repl_header(m: re.Match) -> str:
        pre  = m.group('pre') or ''
        tok  = m.group('tok')
        punc = m.group('punc')
        post = m.group('post') or ' '
        rest = m.group('rest') or ''
        fixed = normalize_num_token(tok)
        return f"{pre}{fixed}{punc}{post}{rest}"

    pattern_header = r"(?m)^(?P<pre>\s*)(?P<tok>[A-Za-z0-9€|IlOSBqgZ]{1,4})(?P<punc>[.)])(?P<post>\s+)(?P<rest>.*)$"
    text = safe_sub(pattern_header, repl_header, text)

    # Case B: Orphan label line (no trailing text), e.g., 'i2.' on its own line
    def repl_orphan(m: re.Match) -> str:
        pre  = m.group('pre') or ''
        tok  = m.group('tok')
        punc = m.group('punc')
        fixed = normalize_num_token(tok)
        return f"{pre}{fixed}{punc}"

    pattern_orphan = r"(?m)^(?P<pre>\s*)(?P<tok>[A-Za-z0-9€|IlOSBqgZ]{1,4})(?P<punc>[.)])\s*$"
    text = safe_sub(pattern_orphan, repl_orphan, text)

    return text


def ocr_text_from_pdf(pdf_path: str) -> list[str]:
    """Performs OCR on each page of the PDF and returns the extracted text."""
    if not OCR_AVAILABLE:
        print("Error: OCR libraries are not installed. Please run 'pip install pdf2image pytesseract pillow'.", file=sys.stderr)
        sys.exit(1)

    try:
        images = convert_from_path(pdf_path, dpi = 300)
    except Exception as e:
        print(f"Error converting PDF to images for OCR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"INFO: Starting OCR...", file=sys.stderr)
    raw_pages = []
    processed_pages = []
    for i, image in enumerate(images):
        try:
            raw_text = pytesseract.image_to_string(image)
            clean_text = preprocess_ocr_numbers(raw_text)
            processed_pages.append(clean_text)
            raw_pages.append(raw_text)
            print(f"INFO: OCR processed page {i + 1}/{len(images)}", file=sys.stderr)
        except Exception as e:
            print(f"Error performing OCR on page {i+1}: {e}", file=sys.stderr)
            continue
    
    # For debugging, we could save raw OCR text if needed
    file = "outputs/debug_ocr_raw" + pdf_path.replace("/", "_").replace("\\", "_") + ".txt"
    with open(file, 'w', encoding='utf-8') as f:
        f.write("\n\n=== PAGE BREAK ===\n\n".join(raw_pages))
    print(f"INFO: Raw OCR text saved to {file}", file=sys.stderr)

    return processed_pages

def extract_text_from_pdf_pages(pdf_path: str) -> list[str]:
    """Extracts all text from a PDF document in reading order."""
    all_pages = []
    page_count = 0
    try:
        with fitz.open(pdf_path) as doc:
            page_count = doc.page_count
            for page in doc:
                page_text = page.get_text("text", sort=True) 
                all_pages.append(page_text)
    except Exception as e:
        print(f"WARN: PyMuPDF failed to open or read PDF {pdf_path}: {e}", file=sys.stderr)
        print("INFO: Attempting OCR fallback for all pages.", file=sys.stderr)

    total_chars = sum(len(p.strip()) for p in all_pages)
    if page_count > 0 and (total_chars / page_count) < 50:
        print("INFO: Digital text is sparse. Assuming scanned PDF and attempting OCR fallback.", file=sys.stderr)
        all_pages = ocr_text_from_pdf(pdf_path)

        # Store for debugging
        try:
            file = "outputs/debug_ocr_extracted" + pdf_path.replace("/", "_").replace("\\", "_") + ".txt"
            with open(file, 'w', encoding='utf-8') as f:
                f.write("\n\n=== PAGE BREAK ===\n\n".join(all_pages))
            print(f"INFO: OCR-extracted text saved to {file}", file=sys.stderr)
        except Exception as e:
            print(f"WARN: Could not save OCR debug file: {e}", file=sys.stderr)


    print(f"INFO: Successfully extracted text from {page_count} pages.", file=sys.stderr)
    return all_pages


    # print(full_text)
    return all_pages

def find_effective_date(text: str) -> Optional[str]:
    """Finds and formats the effective date using regex patterns."""
    patterns = [
        r"(?:effective|dated(?:\s+as\s+of)?)\s+the\s+\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+([A-Za-z]+,?\s+\d{4})",
        r"(?:effective|dated(?:\s+as\s+of)?)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
        r"(?:effective|dated(?:\s+as\s+of)?)\s+(\d{4}-\d{2}-\d{2})"
    ]
    search_text = text[:SCOPE_TO_FIND_EFFECTIVE_DATE]
    for pattern in patterns:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            date_str = match.group(1).replace(',', '')
            for fmt in ("%B %d %Y", "%b %d %Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(date_str, fmt).strftime(ISO_DATE_FORMAT)
                except ValueError:
                    continue
    return None