# PDF Contract Parser CLI
[![LangChain](https://img.shields.io/badge/LangChain-1c3c3c.svg?logo=langchain&logoColor=white)](#) [![Google Gemini](https://img.shields.io/badge/Google%20Gemini-886FBF?logo=googlegemini&logoColor=fff)](#)
![Python Version](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=flat-square&logo=python&logoColor=white)
![OCR Engine](https://img.shields.io/badge/OCR-Tesseract-555.svg?style=flat-square)
![Project Status](https://img.shields.io/badge/Project-Complete-4BC51D?style=flat-square)



This is a command-line tool that parses contract PDFs and outputs a structured JSON that conforms to a predefined schema. The tool is designed for high accuracy and resilience, handling both digital and scanned documents.

The primary entry point for the assessment is the single executable script [main.py](main.py)

## Key Features

-   **Dual-Parser Architecture:** Utilizes a state-of-the-art LLM for high-accuracy parsing with a robust, deterministic rules-based parser as a fallback.
-   **OCR Support:** Automatically detects and processes scanned (image-based) PDFs using the Tesseract OCR engine.
-   **Graceful Degradation:** Guarantees a valid, best-effort JSON output even if the LLM is unavailable or the document is poorly formatted.
-   **Schema Fidelity:** Employs a final validation and auto-fixing layer to ensure all outputs strictly adhere to the required JSON schema, including data types and key names.

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

### 3. Set Up Environment Variables:
  For the LLM parser to function, you need a Google Gemini API key.
  - Create a `.env` file in the root directory.
  - Add your API key to the file:
        ```
        GOOGLE_API_KEY='your-google-api-key-here'
        ```

### 4. Usage 
Run the script from the command line, providing a path to the input PDF and the desired output JSON file. 

```bash
python main.py <input.pdf> <output.json>
```

Example: 
```bash
python main.py ./test_data/contract_1.pdf ./output/contract_1.json
``` 


## Architectural Decisions & Implementation Details

This section explains the core design choices made during the development of the parser.

### 1. Core Hypothesis: A Digital-First Design Backed by Data

The project's architecture is built on the hypothesis that the **majority of modern commercial contracts are digitally native, single column with linear ordering**, not scanned images. This premise is strongly supported by large-scale legal datasets. For example, the **Contract Understanding Atticus Dataset (CUAD)**, https://www.atticusprojectai.org/cuad, a corpus of over 500 commercial agreements used to train legal AI, consists almost entirely of digitally created PDFs.

-   **Implication: A "Fast Path / Slow Path" Architecture.** This observation dictates a digital-first design.
    -   The **"fast path"** is optimized for these common digital files. We use the highly efficient `PyMuPDF` library to extract clean, structured text in seconds, preserving the document's original layout.
    -   The **"slow path"** is a necessary fallback for the exceptional cases, such as older, physically scanned documents. It uses a full OCR pipeline, which is more computationally expensive and is triggered only when the fast path fails to yield meaningful text.


### 2. Dual-Parser Architecture: LLM + Rules

To achieve both high semantic accuracy and 100% reliability, the tool employs a dual-parser strategy.

-   **LLM Parser (Primary):** The script first attempts to parse the document using a Large Language Model (Google Gemini). LLMs excel at understanding the semantic context of legal documents, correctly identifying nuanced section breaks, and excluding irrelevant content like exhibits or tables of contents without explicit rules. This provides the highest quality output.

-   **Rules-Based Parser (Fallback):** If the LLM call fails (due to a missing API key, network error, or API downtime), the system **gracefully degrades** to a deterministic, rules-based parser. This ensures the tool always produces a valid, best-effort output, fulfilling a key project requirement.

-   **`auto_fix.py` (Final Guarantee):** Regardless of which parser is used, the resulting dictionary is passed through a final `clean_and_validate_contract` function. This layer enforces the strict schema rules (e.g., ensuring `label` is `""` and not `null`, formatting dates correctly) and serves as a final guarantee of schema fidelity.

### 3. The Rules-Based Parser

The rules-based parser is designed to be as robust as possible without being overly complex. Its logic is sequential:

1.  **Title & Date Extraction:** It begins by using heuristics to find the document's title and effective date from the first few pages. For titles, it prefers shorter, all-caps lines, a common convention in contracts.
2.  **Section Segmentation:** The core of the parser is a "strong section" regex. It iterates through the document looking for canonical headers (e.g., `6. PAYMENTS.`, `ARTICLE II. DEFINITIONS`). This pattern is intentionally strict, requiring a number/Roman numeral, a dot, and an all-caps title to avoid misclassifying body text.
3.  **Clause Segmentation:** Once a section is identified, the parser analyzes the text within that section's boundaries. It uses a separate, more permissive regex to find clause labels (e.g., `(a)`, `(i)`, `1.2.`).
4.  **Content Aggregation:** Any line of text that does not match a section or clause pattern is appended to the text of the most recently identified clause. This correctly handles multi-line paragraphs.

### 4. OCR Support for Scanned Documents

Handling scanned, image-based PDFs is critical for a robust solution.

1.  **Automatic Detection:** The script first attempts the fast digital extraction. If a multi-page PDF yields a very low character-per-page count, it automatically triggers the OCR fallback.
    ```python
    # Heuristic: < 50 chars/page suggests scanned content

    if page_count > 0 and (len(digital_text.strip()) / page_count) < 50:
        print("INFO: Digital text is sparse. Assuming scanned PDF and attempting OCR fallback.")
        return ocr_text_from_pdf_pages(pdf_path)
    ```
2.  **Extraction Pipeline:** It uses the `pdf2image` library to convert each PDF page into an image, then runs each image through the `pytesseract` OCR engine to "read" the text.

3.  **Critical Preprocessing (`preprocess_ocr_numbers`):** Raw OCR output is messy and lacks the structural integrity of digital text. To solve this, a dedicated preprocessing function cleans the OCR text. This function is the key to making OCR work with the rule-based system:
    -   **It "glues" orphan labels** (e.g., a line containing only `3.`) to the following line of text, recreating the `label -> text` structure.
    -   **It corrects common OCR errors** like misreading `12.` as `i2.` or `6.` as `€.`.
    -   **It re-introduces line breaks** before likely clause and section headers to give the parser's regex anchors (`^`) a chance to work.

## Sample Output

1. Here is an example of the structured JSON generated by the parser for a digital PDF.
    ```json
    {
      "title": "ENDORSEMENT AGREEMENT",
      "contract_type": "Endorsement Agreement",
      "effective_date": "2000-01-01",
      "sections": [
        {
          "title": "DEFINITIONS",
          "number": "1",
          "clauses": [
            {
              "text": "\"Contract Period\" shall mean that period of time commencing on January 1, 2000 and concluding December 31, 2003, unless terminated sooner as provided herein.",
              "label": "(a)",
              "index": 0
            },
            {
              "text": "\"Contract Year\" shall mean the consecutive 12-month period beginning on any January 1st during the Contract Period.",
              "label": "(b)",
              "index": 1
            },
            {
              "text": "\"Products\" shall mean casual apparel consisting of men's pants, shirts, sweaters, windshirts and raingear.",
              "label": "(c)",
              "index": 2
            }, ...
          ]
        }, ...
      ]
    }     
    ```

2. Here is an example of the structured JSON generated by the parser for a scannned PDF using OCR. Notice how the inaccuracy of OCR affects the accuracy of the output. Here `18` was detected as `28` by the OCR. 
This can be corrected by additional post processing which are currently out of the scope.

    ```json
      ...
          {
          "title": "SPECIAL RIGHT OF TERMINATION",
          "number": "16",
          "clauses": [
            {
              "text": "Company shall have the right to terminate this Agreement upon written notice to Licensor if the commercial value of the Duval Identification is substantially reduced because Duval {(i) has engaged in illegal or immoral conduct resulting in a felony conviction; or (ii) fails an officially sanctioned drug test or is criminally convicted of any drug related offense. Any termination pursuant to this paragraph shall become etiective on the 20th day next following the date of receipt by Licensor of Company's written notice to so terminate. -€-",
              "label": "",
              "index": 0
            }
          ]
        },
        {
          "title": "LIMITED LIABILITY. Notwithstanding anything to the contrary herein,",
          "number": "17",
          "clauses": [
            {
              "text": "in the event Company incurs any expenses, damages or other liabilities (aincluding, without limitation, reasonable attorneys' fees) in connection with the performance or non-performance of any term or provision hereof, Licensor's liability to Company shall not exceed the remuneration, excluding reimbursement of expenses, actually paid to Licensor by Company. In no event will Licensor be liable for any indirect, incidental, reliance, special or consequential damages arising out of the performance or non-performance of this Agreement, whether or mot Licensor had been advised of the possibility of such damages. It is understood that Duval is not & party hereto and has no liability hereunder but is an intended specific third party creditor beneficiary hereof.",
              "label": "",
              "index": 0
            }
          ]
        },
        {
          "title": "WAIVER",
          "number": "28",
          "clauses": [
            {
              "text": "The failure of either party at any time or times to demand strict performance by the other of any of the terms, covenants or conditions set forth herein shall not be construed as a continuing waiver or relinquishment thereof and each may at any time demand strict and complete performance by the other of said terms, covenants and conditions. Any waiver of such rights must be set forth in writing.",
              "label": "",
              "index": 0
            }
          ]
        },
        {
          "title": "SEVERABILITY",
          "number": "19",
          "clauses": [
            {
              "text": "I= any provision of this Agreement shall be declared illegal, invalid, void or unenforceable by any judicial or administrative authority, the validity of any other provision and of the entire Agreement shall not be affected thereby-",
              "label": "",
              "index": 0
            }
          ]
        }, ...
      ```