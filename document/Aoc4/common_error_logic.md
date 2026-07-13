# Common Error Engine - Rules & Extraction Logic

The table below outlines the exact logic and extraction strategies implemented in the `AOC4CommonErrorEngine` for checking the **Common Error** sheet against the uploaded documents.

Unlike the Private Compliance Engine (which primarily relies on mathematical formulas from Excel), the Common Error Engine relies entirely on **Text Parsing (NLP / Regex)** of the PDFs and Word Documents (e.g., Auditor's Report, Board's Report, Financial Statements).

### General Behavior
If a rule evaluates to **"No"**, the engine will output a specific `extracted_reason` detailing exactly which keywords or headings were missing from the document.

---

## 1. Custom Hardcoded Rules

| Requirement / Rule | Implemented Search Logic & Keywords | Typical Source Document |
| :--- | :--- | :--- |
| **Auditor Report Headings** | Checks for all 10 required SA 700 headings:<br>• Opinion<br>• Basis for Opinion<br>• Emphasis of matter<br>• Key Audit Matters<br>• Other Information<br>• Responsibility of Management<br>• Auditor's responsibility<br>• Other matters<br>• Report on other legal & regulatory requirements<br>• Internal Financial Controls | Auditor's Report |
| **CARO Applicability** | Searches the text for `"Companies Auditor's Report Order"` or `"CARO"`. | Auditor's Report |
| **Schedule III Format** | Relies on the table-parser output (`has_schedule_iii_format`) to detect Schedule III structured financial tables. | Financials |
| **CIN & DIN Disclosure** | Requires both `"CIN"` (or `"Corporate Identity Number"`) AND `"DIN"` to be present in the document. | Board's Report |
| **Previous Year Figures** | Checks for `"previous year"`, `"prior year"`, or explicit dates matching `"31st march 20XX"`. | Financials |
| **Shareholding > 5%** | Searches for the number `"5%"` appearing alongside keywords `"shareholder"`, `"holding"`, or `"promoter"`. | Notes to Accounts |
| **Statutory Register** | Checks if `"statutory register"` is explicitly mentioned. | Board's Report |
| **Authorised & Paid-up Capital** | Checks for `"authorised capital"` / `"authorized capital"`, and `"paid up capital"`. | Balance Sheet Notes |
| **Reconciliation of Shares** | Requires the keyword `"reconciliation"` to appear alongside `"shares outstanding"`, `"number of shares"`, or `"beginning of the year"`. | Notes to Accounts |
| **Cash Flow Statement** | Checks for `"cash flow statement"` or `"statement of cash flows"`. | Financials |
| **Significant Accounting Policies**| Checks for `"significant accounting policies"`. | Notes to Accounts |
| **EPS & Diluted EPS** | Checks for `"eps"`, `"earnings per share"`, or `"basic"` + `"diluted"`. | P&L Statement |
| **Signatures** | Checks for `"director"` alongside `"auditor"`, `"partner"`, or `"chartered accountant"`. | Financials |
| **UDIN** | Searches for the keyword `"UDIN"` or any regex match for an **18-digit number**. | Auditor's Report |
| **Auditor Seal / FRN** | Checks for `"firm registration number"`, `"frn"`, `"seal"`, or `"membership no"`. | Auditor's Report |
| **Forex and RPT** | For Forex: `"foreign exchange"`, `"forex"`, `"foreign currency"`.<br>For RPT: `"related party"`, `"rpt"`. | Notes to Accounts |
| **Audit Trail / Edit Log** | Checks for combinations of `"accounting software"`, `"audit trail"`, `"edit log"`, `"tampered with"`, `"operated throughout the year"`, and `"preserved"`.<br>*(If missing, automatically flags user to send financials back to client).* | Auditor's / Board's Report |
| **CSR Activities** | Checks for `"corporate social responsibility"` or `"csr"` across various sub-rules (shortfall, nature of activities, etc.). | Board's Report |
| **Manual Team Checks** | Rules mentioning `"board resolutions was issued"` or `"directors were abroad"` are forced to **No** with the reason: `"Manual Check Required"`. | Various |

---

## 2. Global "Fuzzy Fallback" Engine

For the remaining **100+ rules** in the template that do not have custom logic (e.g., "Disclosure of MSME dues", "Reporting on Frauds"), the engine automatically uses the **Fuzzy Fallback**.

**How it works:**
1. The engine strips punctuation, removes common fluff words (like `"whether audit report has the following fields"` or `"details of"`), and creates a highly specific `"search_key"`.
2. It runs a global text search across all uploaded documents for this `search_key`.
3. If found, it outputs **Yes**.
4. If missing, it outputs **No** and reports exactly which `search_key` it couldn't find (e.g., `Why it is No: Keyword not found in documents: 'disclosure of msme'`).
