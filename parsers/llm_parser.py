# parsers/llm_parser.py
# Contains the parsing logic using LangChain and a Large Language Model.

import sys
from schema import Contract 

MAX_CHARS = 10000 * 18
system_prompt_template = """
You are a highly accurate legal document parsing expert. Your task is to analyze the provided contract text and convert it into a structured JSON object. Adhere to the following schema and rules EXACTLY.

JSON Schema:
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
          "label": "Label, title, and number/letter assigned to this clause if any, otherwise an empty string.",
          "index": 0
        },
        ...
      ]
    },
    ...
  ]
}

Rules:
1.  `title`: The main title of the document.
2.  `effective_date`: Extract the effective date and format it as YYYY-MM-DD. If no date is found, the value MUST be `null`.
3.  `sections`: The list of major sections or articles. Sections must be in the document's reading order.
4.  `sections[n].number`: The number of the section (e.g., "1", "1.2", "II"). If the section has no number, the value MUST be `null`.
5.  `clauses`: The list of clauses within a section, in reading order.
6.  `clauses[n].label`: The label of the clause (e.g., "1.2 (a) Definitions", "(b)"). If there is no label, the value MUST be an empty string `""`. DO NOT use null here.
7.  `clauses[n].index`: A 0-based integer index that resets to 0 for each new section.
8.  `clauses[n].text`: The full text of the clause. Normalize all internal whitespace to a single space.
9.  The output must be a single, valid JSON object and nothing else.
"""


try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_google_genai import ChatGoogleGenerativeAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

def parse_with_llm(full_text: str):
    """
    Parses contract text using a LangChain chain with Google Gemini.
    Returns a dictionary matching the Contract schema or None on failure.
    """
    if not LANGCHAIN_AVAILABLE:
        print("INFO: LangChain/Google libraries not found. Skipping LLM.", file=sys.stderr)
        return None

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)
        structured_llm = llm.with_structured_output(Contract)

        if len(full_text) > MAX_CHARS:
            print(f"WARN: Input text is very long. Truncating to {MAX_CHARS} chars for LLM.", file=sys.stderr)
            full_text = full_text[:MAX_CHARS]

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_template.replace('{', '{{').replace('}', '}}')),
            ("human", "Please parse the following contract text:\n\n---\n\n{contract_text}")
        ])
        chain = prompt | structured_llm

        print("INFO: Attempting to parse with LLM...", file=sys.stderr)
        result = chain.invoke({"contract_text": full_text})
        print("INFO: LLM parsing successful.", file=sys.stderr)
        return result.model_dump()
    
    except Exception as e:
        # This will catch API key errors, network issues, etc.
        print(f"ERROR: LangChain/LLM parsing failed: {e}. Falling back to rule-based parser.", file=sys.stderr)
        return None
    


