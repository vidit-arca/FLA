# Implementation Plan — Text-Based DOM Rule Creation

## Goal
Implement a robust DOM rule extraction and batch processing system using the exact logic flow you described, avoiding the spatial coordinate bounding box issues.

## The Logic Flow We Are Aligned On

1. **Batch Upload Flow (Production):**
   - When PDFs are uploaded, **OCR will run** and the **DOM Tree will be built**.
   - The system checks the `idp_dom_extraction_rules` table in the DB.
   - If there is a DOM path for a variable in the form template, it will use the DOM path to extract the value instantly.
   - If the DOM path fails or doesn't exist, it falls back to the Qwen LLM.

2. **Magic Pen Flow (IDP Studio):**
   - If the batch flow missed something, the user goes to the IDP Studio and uses the Magic Pen.
   - The Magic Pen uses the **old approach** (crops the region, runs OCR, asks Qwen) to reliably extract the `variable` (e.g., "Trade payables") and the `value` (e.g., "12,10,692").
   - When the user clicks "Link Field", we use the text of that **variable** as an input to search the DOM tree for that specific PDF.
   - The system finds the matching DOM node, computes the structural DOM path, and **saves it in the DB**.
   - A single variable can have multiple fallback DOM paths (rules), and the batch flow will try them in order of success.

## Changes Required

### 1. `models.py`
- Add back the `DomExtractionRule` table (with `rule_id`, `template_name`, `variable_name`, `dom_path`, `success_count`, `created_at`).

### 2. `router.py`
- Add the helper to build a DOM tree from a PDF (`_build_dom_query_from_pdf_bytes`) and the helper to search DOM paths (`_try_dom_rules`).
- **Update `/extract/batch`**: Insert the DOM checking step *before* it calls Qwen.
- **Update `/api/idp/rules` (or add a new hook)**: When the frontend saves a rule from the magic pen, it sends `extracted_key` (the variable text). We will intercept this on the backend, build the DOM for the active PDF, find the text, and save the DOM path into the `DomExtractionRule` table alongside the old spatial rule. 

### 3. Frontend (`idpClient.js` & `IdpStudio.jsx`)
- To make this work smoothly, we need to send the PDF file to the backend when saving the rule so the backend can build the DOM. We will modify `saveRule` in the API client to accept the `pdfFile`, and pass it from `IdpStudio.jsx`.

## Open Questions

> [!NOTE]
> Are you ready to proceed with this implementation? Once you approve, I will write the code exactly according to this plan.
