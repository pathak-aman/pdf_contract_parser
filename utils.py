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

def normalize_text(text: str) -> str:
    """Normalizes whitespace and removes leading/trailing spaces."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts all text from a PDF document in reading order."""
    full_text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page_no, page in enumerate(doc, start=1):
                full_text += page.get_text("text", sort=True) + "\n"
    except Exception as e:
        print(f"Error opening or reading PDF {pdf_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Total pages in the pdf: {page_no}")
    # print(full_text)
    return full_text

def extract_text_from_pdf_pages(pdf_path: str) -> str:
    """Extracts all text from a PDF document in reading order."""
    all_pages = []
    try:
        with fitz.open(pdf_path) as doc:
            for page_no, page in enumerate(doc, start=1):
                page_text = page.get_text("text", sort=True) 
                all_pages.append(page_text)
    except Exception as e:
        print(f"Error opening or reading PDF {pdf_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Total pages in the pdf: {page_no}")
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