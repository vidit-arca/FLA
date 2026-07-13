# AOC4 & FLA Automation: Debugging & Refinement Timeline

This document outlines the end-to-end timeline and specific technical steps taken to debug the AOC4 form extraction, refine it into a robust rule-based engine, and expand the FLA module's capabilities. 

---

## Week 1 - Day 1: PDF Analysis & Requirement Gathering

- **Feedback Analysis:** We began by conducting a full review of the `AOC4_data_logics with comments.pdf` document to capture manual team feedback and specific edge cases.
- **Automated Extraction:** We deployed a `PyMuPDF` script to dynamically scrape all sticky notes and text annotations embedded inside the PDF to ensure no comments were missed.
- **Data Mapping:** We successfully mapped the feedback directly to the extraction variables. For example, expanding `net_worth` to include "capital + reserve & surplus", and refining the `borrowings` keywords. 

---

## Week 1 - Day 2: Core AOC4 Engine Refactoring & Debugging

Following the requirements gathering, we systematically debugged the engine to transition away from brittle, hardcoded rules to dynamic, robust keyword mapping.

- **`excel_extractor.py` (Data Layer):** 
  - Injected new keyword arrays into the RPT and Financial Metrics mapping (e.g., added "rent" to `rpt_lease`, added "salary" to `rpt_monthly_remun`, and added "loan from bank" to `borrowings`).
  - Debugged the boolean parser (`_clean_boolean`) to properly support and return `"not applicable"` states, rather than forcefully defaulting to missing or False.
- **`parser.py` (Document Layer):** 
  - Added a Regex-powered CIN extractor. 
  - Built a dynamic `is_listed` rule that automatically determines a company's listed status if the extracted CIN begins with the letter `L`.
- **`aoc4_error_checker.py` (Validation Layer):** 
  - Debugged the "Previous year figures" engine by removing hardcoded strings (`31st march 2025`) and replacing them with future-proof Regex (`31st march 20\d\d`). 
  - Added "promoter" keyword support to the >5% shareholding checks.
- **Documentation:**
  - Completely rewrote `Aoc4_extraction_documentation.md` to serve as a comprehensive dictionary for the new rule-based engine.

---

## Week 1 - Day 3 & Day 4: Expanding FLA Form Input Flexibility

- **Format Investigation (Day 3):** Verified the existing extraction capabilities for the Financials and ODI details, confirming support for native Markdown and OCR JSON formats. Identified that the engine lacked native Excel handling for Financials.
- **Excel Native Integration (Day 4):** Architected and deployed a `pandas` based extractor into `parser.py`.
- **Dynamic Header Scanning (Day 4):** Instead of mapping hardcoded cell coordinates for Excel, we built a 15-row dynamic scanner that locates table headers (e.g., "Particulars", "PY", "FY") and dynamically maps the data straight into the existing OCR rules engine.

---

## Week 1 - Day 5: Enhancing Validation Traceability

- **Mathematical Flagging:** Evaluated the mathematical validation outputs and identified a need for better traceability back to the source documents.
- **Engine Updates:** Debugged `validator.py` and updated the `log_check` naming conventions for all 9 core mathematical checks. 
- **Row Mapping Integration:** Added exact row numbers (e.g., `(3.5, 3.2, 3.3, 3.4)`) into the rule flags. This ensures that any validation failure instantly points the review team to the exact rows inside the financial blocks (e.g., `(5.3, 5.1, 5.2) Total Sales Consolidation`).

---

### Project Summary
Over the course of this week, by translating the manual PDF comments into dynamic Regex arrays, upgrading the boolean logic, and adding native Excel table extraction, the AOC4 and FLA engines have been transformed into highly resilient, automated rule engines capable of adapting to changing document formats and future financial years.
