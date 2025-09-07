import json
import re
import copy
from typing import Optional, List
from pydantic import BaseModel, Field, ValidationError

# --- Pydantic Models  ---

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

# --- The Sanitization Script ---

def clean_and_validate_contract(data: dict) -> dict:
    """
    Cleans a contract dictionary to conform to the specified schema.

    This function directly modifies the dictionary in place to fix:
    - Date formats
    - Whitespace normalization
    - `None` vs. `""` for labels
    - `None` vs. string for section numbers
    - Clause indexing
    """
    # Create a deep copy to avoid modifying the original input dictionary
    cleaned_data = copy.deepcopy(data)
    sections_to_remove = []

    # 1. Fix top-level fields
    if 'effective_date' in cleaned_data and cleaned_data['effective_date'] is not None:
        date_str = str(cleaned_data['effective_date'])
        # If date is not in YYYY-MM-DD format, set to null as per the rule.
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            cleaned_data['effective_date'] = None

    # 2. Filter out sections with empty clauses before processing
    if 'sections' in cleaned_data:
        # This line removes any section where the 'clauses' list is empty.
        # print("Initial sections count:", len(cleaned_data['sections']))
        cleaned_data['sections'] = [s for s in cleaned_data['sections'] if s.get('clauses')]
        # print("Sections count after removing empty clauses:", len(cleaned_data['sections']))


    # 2. Iterate through sections and clauses
    for section in cleaned_data.get('sections', []):

        # Fix section number: must be string or null
        if 'number' in section and section['number'] is not None:
            section['number'] = str(section['number']).strip()

        # Fix clauses within the section
        for i, clause in enumerate(section.get('clauses', [])):
            # Rule: Enforce 0-based indexing for clauses within the section
            clause['index'] = i

            # Rule: Fix label - must be a string, "" if not present. Cannot be null.
            if clause.get('label') is None:
                clause['label'] = ""
            else:
                clause['label'] = str(clause['label']).strip()

            # Rule: Normalize whitespace in text
            if 'text' in clause and isinstance(clause['text'], str):
                # Replace multiple whitespace characters with a single space
                normalized_text = re.sub(r'\s+', ' ', clause['text'])
                clause['text'] = normalized_text.strip()
    
    for section in sections_to_remove:
        cleaned_data['sections'].remove(section)
    
    return cleaned_data
