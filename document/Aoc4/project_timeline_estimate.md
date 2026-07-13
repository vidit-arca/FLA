# Project Estimation & Implementation Roadmap

## Statutory Compliance Automation Engine

### 1. Executive Summary

This document outlines the project timeline, scope of work, and integration strategy for the end-to-end automation of statutory compliance forms into a robust, rule-based extraction and validation engine.

### 2. Scope of Work & Deliverables

The automation engine follows a strict 5-step technical pipeline for every form:

1. **Data Ingestion:** Processing of Native PDFs, Scanned PDFs, and Excel files.
2. **Document Parsing:** Dynamic keyword mapping and table extraction.
3. **NLP Error Scanning:** Text scanning for mandatory compliance phrases and signatures.
4. **Rule Engine Application:** Evaluation of statutory thresholds and mathematical logic.
5. **Validation Output:** Row-linked failure notices and client-ready reporting.

---

### 3. Project Timeline & Estimation

#### Phase 1: Core Engines & Initial Forms (COMPLETED)

*Status: Successfully Built, Debugged, and Deployed*
*Time Taken: 2 Weeks*

| Module / Form                 | Key Deliverables                                                                                                                   | Status  |
| :---------------------------- | :--------------------------------------------------------------------------------------------------------------------------------- | :------ |
| **AOC-4 Module**        | OCR parsing of Board Reports & Financials, dynamic RPT extraction, Net Worth validation, and dynamic table mapping.                | ✅ Done |
| **FLA / Form 2**        | Overseas Direct Investment (ODI) extraction, Foreign Direct Investment (FDI) data mapping, native`.xlsx` and `.pdf` ingestion. | ✅ Done |
| **Common Error Engine** | NLP text scanning for Audit report signatures, CIN/DIN presence, Audit Trail validations.                                          | ✅ Done |
| **Compliance Sheet**    | Threshold evaluation for Small Company exemptions, CARO, CSR, XBRL.                                                                | ✅ Done |

#### Phase 2: Annual Return & Deposits (Upcoming)

*Estimated Timeline: 3 Weeks (Includes Development + 3-Stage Testing)*

| Module / Form            | Dev Effort | 3-Stage Testing (Unit, QA, UAT) | Key Automation Requirements                                                                         |
| :----------------------- | :--------- | :------------------------------ | :-------------------------------------------------------------------------------------------------- |
| **MGT-7 / MGT-7A** | 2 Weeks    | 1 Weeks                         | Extracting Shareholder data, mapping KMP details, calculating meeting attendances.                  |
| **DPT-3**          | 2 Week     | 1 Weeks                         | Parsing loan schedules, distinguishing exempt vs non-exempt deposits, mapping auditor certificates. |

#### Phase 3: Event-Based Filings (Upcoming)

*Estimated Timeline: 4 Weeks (Includes Development + 3-Stage Testing)*

| Module / Form    | Dev Effort | 3-Stage Testing (Unit, QA, UAT) | Key Automation Requirements                                                                                |
| :--------------- | :--------- | :------------------------------ | :--------------------------------------------------------------------------------------------------------- |
| **ADT-1**  | 2 Week     | 3 Days                          | Parsing Board Resolutions, extracting Auditor PAN/FRN, and calculating term limits.                        |
| **DIR-12** | 3 Week     | 3 Days                          | Cross-referencing DINs, scanning resignation/appointment letters, mapping dates to Board Resolutions.      |
| **INC-22** | 1 Week     | 2 Days                          | Extracting address details from utility bills/lease agreements and validating NOC signatures.              |
| **PAS-3**  | 1 Week     | 2 Days                          | Parsing Valuation Reports, mapping share allotment lists, calculating premium vs nominal value accurately. |

---

### 4. Integration Strategy & Codebase Merging

*Estimated Timeline: 1.5 Weeks*

A critical component of this project involves integrating the backend automation engine with the work of external development teams.

**Integration Workflow (Developer Codebase ➔ Main Branch):**

- **Code Audit & Conflict Resolution (3 Days):** Reviewing the external developer's codebase (frontend UI / API layers) to ensure architectural compatibility with the Python extraction engine.
- **API Hookup & Endpoint Mapping (4 Days):** Linking the Python validation backend to the frontend UI so users can upload zips of PDFs/Excels and see flagged errors visually.
- **End-to-End System Testing (3 Days):** Running complete payloads through the merged Main branch to ensure the external UI successfully triggers the Python parser and correctly displays the row-linked failure notices (e.g., `(5.3, 5.1) Sales Consolidation`).

---

### 5. Assumptions & Dependencies

- **Client Testing (UAT):** The 3-stage testing timeline assumes the client will provide sample, anonymized financial documents (PDF/Excel) for accurate User Acceptance Testing.
- **External Codebase Quality:** The 1.5-week integration estimate assumes the external developer's codebase follows standard RESTful API or modular architecture conventions.

### **Total Project Summary**

- **Completed Core Work:** ~2 Weeks of intensive data mapping, extraction logic, and debugging.
- **Estimated Remaining Work:** ~8.5 Weeks (Includes all future forms, strict 3-stage testing per form, and external codebase integration into Main).
