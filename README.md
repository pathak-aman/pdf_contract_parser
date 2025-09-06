# PDF Contract Parser CLI

A command-line tool to parse contract PDFs into structured JSON. This tool is designed to be robust, performant, and extensible.

## Features

-   **Hybrid Text Extraction:** Uses the high-performance PyMuPDF library for text-based PDFs and falls back to Tesseract OCR for scanned documents.
-   **Schema-Compliant Output:** Generates JSON that strictly adheres to the required output schema.
-   **Graceful Degradation:** Ensures a valid, best-effort JSON output (a flat list of text) is produced even if advanced parsing or external dependencies fail.

## Output Schema:
```json
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
        },
        {

        },
      ]
    },
    {

    }
  ]
}
```

## Setup

### 1. System Dependencies

This tool relies on Tesseract for OCR and Poppler for PDF-to-image conversion. On a Debian-based system (like Ubuntu on WSL), install them with:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils
```

### 2. Python Environment 
It is recommended to use a virtual environment. 

``` bash
# Create and activate a conda environment
conda create --name pdf_parser python=3.9 -y
conda activate pdf_parser

# Install all required Python packages
pip install -r requirements.txt
```


### 3. Usage 
Run the script from the command line, providing a path to the input PDF and the desired output JSON file. 

```bash
python aman_pathak.py <input.pdf> <output.json>
```

Example: 
```bash
python aman_pathak.py ./test_data/contract_1.pdf ./output/contract_1.json
``` 