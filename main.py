# main.py
# Main entry point for the contract parsing CLI tool.

import sys
import json
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file (for GOOGLE_API_KEY)
load_dotenv()

# Import our refactored components
from utils import extract_text_from_pdf
from parsers import parse_with_llm, parse_with_rules

def main():
    """Main function to orchestrate the parsing process."""
    parser = argparse.ArgumentParser(description="Parse a contract PDF into a structured JSON file.")
    parser.add_argument("input_pdf", help="A path to a PDF contract.")
    parser.add_argument("output_json", help="A path where the program must write the structured output.")
    
    # The original spec requires exactly two arguments, so we can check that.
    if len(sys.argv) != 3:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    
    print(f"INFO: Reading and extracting text from {args.input_pdf}...", file=sys.stderr)
    full_text = extract_text_from_pdf(args.input_pdf)
    
    if not full_text.strip():
        print("ERROR: Could not extract any text from the PDF.", file=sys.stderr)
        final_output = {"title": "Extraction Failed", "contract_type": "Unknown", "effective_date": None, "sections": []}
    else:
        # First, try the LLM-based parser
        # final_output = parse_with_llm(full_text)
        print("INFO: Skipping LLM to test rule")
        final_output = None

        
        # If the LLM parser fails or is unavailable, fall back to the rule-based one
        if final_output is None:
            print("INFO: LLM path failed or skipped. Using rule-based fallback parser.", file=sys.stderr)
            final_output = parse_with_rules(full_text)

    # Write the final JSON output
    try:
        with open(args.output_json, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)
        print(f"SUCCESS: Structured data successfully written to {args.output_json}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Could not write to output file {args.output_json}: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()