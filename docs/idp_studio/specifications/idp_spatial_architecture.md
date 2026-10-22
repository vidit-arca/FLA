# IDP Studio: Architecture & Workflow Documentation

This document outlines the core operational workflow and the underlying self-learning architecture of the IDP (Intelligent Document Processing) engine. This architecture solves the "53 compliance forms" problem by replacing fragile hardcoded rule engines with a dynamic, user-trained spatial and structural memory system.

---

## 1. The Output Workflow: "What happens after mapping?"

Once a user has mapped a document layout for a specific form, the system is fully trained for that layout. The operational workflow for end-users processing documents at scale looks like this:

### Step 1: Bulk Ingestion
Users can drag and drop multiple input documents (e.g., hundreds of financial PDFs) into the system. 
- The backend identifies the layout fingerprint of each document.
- It automatically applies the previously saved rules to extract the data instantly.

### Step 2: The Review Dashboard
Extracted data is not blindly saved. It is presented in a dedicated **Review & Export Dashboard** within the UI.
- The dashboard displays a clean, structured table matching the uploaded Excel template schema.
- **Confidence Highlighting:**
  - **Green:** Fields that were extracted perfectly using deterministic spatial rules.
  - **Red/Yellow:** Fields where the system was uncertain (e.g., a completely new layout was detected, triggering the AI fallback). These require a quick human visual check.

### Step 3: Final Export
Once the user reviews and is satisfied with the data, they click **Export**.
- The system generates the final Excel document matching the original blank template.
- Alternatively, the data can be pushed directly via API integration to an ERP or accounting system.

---

## 2. The Rule Engine: Spatial & PDF DOM Learning

The true power of this system is that it generates a deterministic, highly resilient rule engine without a developer writing a single line of code. We can achieve this using two complementary self-learning methods: **Spatial Anchoring** and **PDF DOM Learning**.

### Approach A: Spatial Anchoring (Coordinate Resilience)
This handles unstructured blobs of text and simple forms.
1. **Frontend Trigger:** The user draws a box around `150,000` and tags it as `Total Revenue`.
2. **Anchor Detection:** The backend analyzes the OCR text layer and finds a static anchor, like `"Revenue from Operations"`, sitting exactly 50 pixels to the left.
3. **The Memory:** It saves the rule: *Find "Revenue from Operations", move exactly 50px right, and extract.*
- **Limitation:** If a table adds a massive paragraph inside a cell, it might shift coordinates unpredictably, breaking strict `(x, y)` math.

### Approach B: PDF DOM Learning (Structural Resilience)
This is the ultimate solution for complex tables (which are rampant in financial documents). PDFs do not have a true HTML DOM, but we can generate a "Logical DOM" or Graph (Headers -> Tables -> Rows).

1. **Frontend Trigger:** The user clicks on `150,000` in a table.
2. **DOM Path Generation:** Instead of looking at X/Y pixels, the backend analyzes the hierarchical structure of the document. It generates a "Document Object Model (DOM) Path", similar to an HTML XPath.
3. **The Memory:** It saves a structural rule rather than a spatial one:
   > *Rule for Total Revenue: Go to **Header("Profit & Loss Statement")** -> Enter **Table(1)** -> Find **Row** where Column(0) contains "Total Revenue" -> Extract **Column(1)**.*
4. **Why DOM Learning is Superior:** If a company adds 10 new rows of expenses above "Total Revenue", or if the table gets pushed to page 3, a spatial coordinate rule might fail. But a DOM rule will **never fail**, because it relies on the logical reading order and table structure, not physical pixels.

---

## 3. The Self-Learning Loop: "How does the system get smarter?"

The "Self-Learning" aspect of the engine ensures that manual effort approaches zero over time, across all 53 forms. It is driven by two distinct mechanisms:

### Mechanism A: The Global Lexicon (Cross-Form Learning)
Many fields are identical across different forms (e.g., `CIN Number`, `Director Name`, `Total Assets`).
- **The Concept:** When a user maps a field for *Form 1*, they assign it a global tag (e.g., `company_cin`). The Structural/Spatial Rule is saved to a central **Global Dictionary** in the database.
- **The Automation:** The next day, the user uploads *Form 2*, which also requires the `company_cin`. Because the system has already "learned" the rule for `company_cin` from Form 1, it automatically extracts it and populates Form 2. The user only maps a data point *once*, and the engine learns it for all 53 forms.

### Mechanism B: Zero-Shot AI Fallback & Human Correction
When the system encounters a completely new layout it has never seen before, it uses an LLM (Ollama/Triton) to take a "best guess" at mapping the fields.
- **The AI Guess:** The AI extracts the data and presents it to the user in the Review Dashboard, highlighted in Yellow.
- **The Correction Loop:** If the AI guessed incorrectly, the user corrects it using the Magic Pen. If the AI was correct, the user simply clicks **Approve**.
- **The Learning Moment:** The second the user clicks Approve or corrects the box, the backend instantly generates a permanent Spatial/DOM Rule for that layout. The system has now *learned*. 
- The next time that same layout is uploaded, it skips the slow AI LLM entirely and uses its deterministic, lightning-fast Memory. The AI is only a crutch used to bootstrap the system's deterministic memory!
