# schema.py
# Defines the Pydantic data models for the contract structure.

"""
Output Schema (exact):
{
  "title": "Contract Title",
  "contract_type": "Agreement Type",
  "effective_date": "YYYY-MM-DD or null",
  "sections": [
    {
      "title": "Section Title",
      "number": "Section Number or null",
      "clauses": [
        {
          "text": "Clause text",
          "label": "Label, title, and number/letter assigned to this if any, otherwise empty string.",
          "index": 0
        }
      ]
    }
  ]
}

"""

from typing import Optional, List
from pydantic import BaseModel, Field

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