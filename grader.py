#!/usr/bin/env python3
# grader.py
# Validates a contract JSON file against a predefined Pydantic schema.

import sys,re
import json
from typing import Optional, List
from pydantic import BaseModel, Field, ValidationError
from typing import Any, Dict, List, Tuple, Optional



# --------------------------
# SCHEMA DEFINITION (using Pydantic models)
# --------------------------

class Clause(BaseModel):
    text: str = Field(..., description="The full, normalized text of the clause.")
    label: str = Field(..., description="The label, title, or number (e.g., '(a)', '1.2.1'). Must be an empty string if no label exists.")
    index: int = Field(..., description="The 0-based index of the clause within its parent section.")

class Section(BaseModel):
    title: str = Field(..., description="The title of the section (e.g., 'Confidentiality').")
    number: Optional[str] = Field(..., description="The number of the section (e.g., '1.2', 'II'). Must be null if no number exists.")
    clauses: List[Clause] = Field(..., min_length=1, description="A list of all clauses within this section.")

class Contract(BaseModel):
    title: str = Field(..., description="The main title of the contract.")
    contract_type: str = Field(..., description="The type of agreement (e.g., 'Employment Agreement', 'Master Services Agreement').")
    effective_date: Optional[str] = Field(..., description="The effective date in YYYY-MM-DD format. Must be null if not found.")
    sections: List[Section] = Field(..., description="A list of all sections in the contract.")


def read_args():
    """Reads and validates command-line arguments."""
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <input.json>", file=sys.stderr)
        sys.exit(1)
    return sys.argv[1]


def pydantic_contract_validation(data):
    """Main function to load and validate the JSON file."""
    
    try:
        # The core validation step: attempt to parse the data into the Contract model.
        # If this succeeds, the schema is valid.
        Contract.model_validate(data)
        print("✅ Schema validation PASSED.")
    except ValidationError as e:
        # If it fails, Pydantic's ValidationError gives a detailed, human-readable report.
        print("❌ Schema validation FAILED. See errors below:", file=sys.stderr)
        print("--------------------------------------------------", file=sys.stderr)
        print(e, file=sys.stderr)
        print("--------------------------------------------------", file=sys.stderr)


def is_valid_against_pydantic_like_rules(cleaned: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Lightweight validation mirroring your Pydantic models' constraints:
    - title: non-empty str
    - contract_type: non-empty str
    - effective_date: None or 'YYYY-MM-DD'
    - sections: list
    - section.title: non-empty str
    - section.number: None or str
    - clauses: non-empty list
    - clause.text: non-empty str (normalized)
    - clause.label: str (possibly empty)
    - clause.index: consecutive 0..n-1 in each section
    """
    errs: List[str] = []

    def non_empty_str(x: Any) -> bool:
        return isinstance(x, str) and x.strip() != ""

    if not non_empty_str(cleaned.get("title", "")):
        errs.append("title invalid")
    if not non_empty_str(cleaned.get("contract_type", "")):
        errs.append("contract_type invalid")

    ed = cleaned.get("effective_date", None)
    if ed is not None:
        if not isinstance(ed, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ed):
            errs.append("effective_date not ISO YYYY-MM-DD or null")

    sections = cleaned.get("sections")
    if not isinstance(sections, list):
        errs.append("sections not a list")
        sections = []

    for si, sec in enumerate(sections):
        if not isinstance(sec, dict):
            errs.append(f"section[{si}] not an object")
            continue
        if not non_empty_str(sec.get("title", "")):
            errs.append(f"section[{si}].title invalid")
        num = sec.get("number", None)
        if num is not None and not isinstance(num, str):
            errs.append(f"section[{si}].number must be string or null")

        clauses = sec.get("clauses")
        if not isinstance(clauses, list) or len(clauses) == 0:
            errs.append(f"section[{si}].clauses missing or empty : {sec}")
            continue

        for ci, cl in enumerate(clauses):
            if not isinstance(cl, dict):
                errs.append(f"section[{si}].clauses[{ci}] not an object: {cl}")
                continue
            if not non_empty_str(cl.get("text", "")):
                errs.append(f"section[{si}].clauses[{ci}].text invalid")
            label = cl.get("label", "")
            if not isinstance(label, str):
                errs.append(f"section[{si}].clauses[{ci}].label must be string (empty allowed)")
            idx = cl.get("index")
            if not isinstance(idx, int):
                errs.append(f"section[{si}].clauses[{ci}].index must be int")
            elif idx != ci:
                errs.append(f"section[{si}].clauses[{ci}].index must be {ci}")

    return len(errs) == 0, errs


if __name__ == "__main__":
    json_path = read_args()

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Input file not found at '{json_path}'", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in '{json_path}'.\n   Details: {e}", file=sys.stderr)
        sys.exit(1)

    pydantic_contract_validation(data)
    is_passed, errors = is_valid_against_pydantic_like_rules(data)

    if is_passed:
        print("✅ No-Ambiguity checks PASSED.")
    else:
        print("❌ No-Ambiguity checks FAILED. See errors below:", file=sys.stderr)
        print("--------------------------------------------------", file=sys.stderr)
        for start, err in enumerate(errors):
            print(f"E{start+1} : {err}")
        print("--------------------------------------------------", file=sys.stderr)