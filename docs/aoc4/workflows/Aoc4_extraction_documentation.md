# AOC4 Extraction & Rule Engine Documentation

This document provides a comprehensive mapping of every compliance rule, its underlying data requirements, the specific regex patterns used to extract that data from the uploaded Excel files, and the logic the engines use to evaluate the rule.

---

## Part 1: Data Extraction Layer (`AOC4ExcelExtractor`)

The `excel_extractor.py` processes all uploaded `.xlsx` files. To optimize extraction and prevent false positives from irrelevant summary sheets, it **only scans sheets whose names contain specific keywords**. If none of these keywords are found in the sheet names, it will fall back to scanning all sheets.

**Targeted Sheet Keywords:**

- `balance sheet`
- `p&l`, `profit and loss`, `statement of profit`
- `notes`
- `related party`, `rpt`
- `revenue`
- `share capital`
- `financials`

Inside these targeted sheets, the engine searches the **row headers** for specific Regex keywords. When a match is found, it scans to the right (in the same row) to grab either a **Numeric Value** or a **Yes/No Boolean** (also supports 'Not Applicable' for boolean fields).

### 1. Unit Scale Multiplier (Hundreds, Lakhs, Crores)

Both the Excel Extractor and the unstructured text Parser actively scan the document text for scale indicators. If found, a mathematical multiplier is applied to **all** extracted numeric values before they are used in compliance checks.

| Detected Phrase (Regex Matches) | Multiplier Applied | Example Phrase in Document                  |
| :------------------------------ | :----------------- | :------------------------------------------ |
| `(?i)in hundreds?`            | `x 100`          | "All amounts are in Indian Rupees Hundreds" |
| `(?i)in thousands?`           | `x 1,000`        | "Amounts are in Thousands"                  |
| `(?i)in lakhs?`               | `x 100,000`      | "(in Lakhs)"                                |
| `(?i)in millions?`            | `x 1,000,000`    | "Amounts in Millions"                       |
| `(?i)in crores?`              | `x 10,000,000`   | "in Crores of Indian Rupees"                |
| *None found*                  | `x 1` (Actuals)  | -                                           |

### 2. Holding & Subsidiary Status Detection


### Step 1: Text Normalization

First, the engine takes the entire text from the financial PDF, converts it all to lowercase, and removes all weird spacing or newlines so it can search it cleanly.

### Step 2: High Confidence Keyword Search (Instant 'Yes')

It scans the entire document for a specific list of "High Confidence" legal phrases:

* `"holding company"`
* `"subsidiary company"`
* `"is a subsidiary"`
* `"ultimate holding company"`
* `"parent company:"`
* *(and a few others...)*

If it finds **even one** of these phrases anywhere in the text, it immediately knows it's a holding/subsidiary, flags it as `"yes"`, and stops.

### Step 3: Ownership Percentage Check (Instant 'Yes')

If Step 2 didn't find anything, it uses a powerful Regex formula: `(?:ownership|holding|subsidiary|investment).{0,50}?(\d{2,3}(?:\.\d+)?)\s*%`

This formula looks for words like *"ownership"* or  *"investment"* , and then scans the next 50 characters to see if there is a percentage (like `51%` or `99.9%`). If it extracts a percentage that is mathematically  **greater than 50.0%** , it immediately flags the company as `"yes"` and stops.

### Step 4: The 100-Point Accumulator (Indirect Clues)

If both Step 2 and Step 3 failed to find a definitive answer, it falls back to a scoring system. It scans for "Medium Confidence" accounting phrases:

* `"investment in subsidiaries"`
* `"investment in associates"`
* `"consolidated financial statements"`
* `"schedule of subsidiaries"`

For every one of these phrases it finds, it awards the company  **20 points** . If the total score hits  **100 points or more** , it flags the company as `"yes"`.

### Step 5: Default to 'No'

If the company fails the keyword check, fails the percentage check, and scores less than 100 points on the accounting clues, the engine safely concludes it is an independent company and returns `"no"`.

### 3. IND AS Applicability Detection

Because Indian Accounting Standards (IND AS) is a strict, legally mandated framework, companies cannot apply it implicitly. It must be explicitly stated in their financial notes. The engine determines this using a strict text scanner:

1. **Strict Legal Keyword Scan:**
   It iterates through a hardcoded list of exactly four phrases that Indian companies legally use to declare IND AS:
   - `"indian accounting standard"`
   - `"ind as"`
   - `"ind-as"`
   - `"companies (indian accounting standards) rules"`

2. **Boundary Validation:**
   To prevent false positives (e.g., matching the letters "ind as" inside a phrase like "blind as"), the engine enforces strict Regex Word Boundaries (`\b`).

If any exact match is found, it automatically flags the company as `Yes` (which subsequently forces an XBRL filing requirement). Otherwise, it safely defaults to `No`.

### 4. Numeric Financial Metrics

| Extracted Variable                | Regex Keywords Searched For                                                                                                    | Output Type |
| :-------------------------------- | :----------------------------------------------------------------------------------------------------------------------------- | :---------- |
| `turnover`                      | `revenue from operations?`, `total turnover`, `sales turnover`, `gross turnover`                                       | Float       |
| `prev_turnover`                 | `previous year turnover`, `turnover.*previous year`                                                                        | Float       |
| `paid_up_capital`               | `paid.?up capital`, `paid.?up share capital`, `subscribed and paid.?up`, `equity share capital`                        | Float       |
| `net_worth`                     | `^net worth`, `total equity`, `capital + reserve & surplus`                                                              | Float       |
| `prev_net_worth`                | `previous year net worth`, `net worth.*previous year`                                                                      | Float       |
| `reserves_and_surplus`          | `reserves & surplus`, `reserves and surplus`, `other equity`                                                             | Float       |
| `borrowings`                    | `total borrowing`, `borrowing`, `loan from bank`, `loan from director`, `secured loan`, `unsecured loan`           | Float       |
| `net_profit_before_tax`         | `profit before tax`, `profit/loss before tax`, `pbt`                                                                     | Float       |
| `total_loans_investments_given` | `loans and advances given`, `investments made`, `total loans.*given`, `current investment`, `non current investment` | Float       |

### 3. RPT Specific Transaction Metrics

| Extracted Variable                | Regex Keywords Searched For                                           | Output Type |
| :-------------------------------- | :-------------------------------------------------------------------- | :---------- |
| `rpt_sale_goods`                | `sale of goods.*related party`, `sale of goods`                   | Float       |
| `rpt_purchase_goods`            | `purchase of goods.*related party`, `purchase or supply of goods` | Float       |
| `rpt_sale_property`             | `sale of property.*related party`, `sale of property`             | Float       |
| `rpt_purchase_property`         | `purchase of property.*related party`, `purchase of property`     | Float       |
| `rpt_dispose_property`          | `dispose of property`, `disposal of property`                     | Float       |
| `rpt_availing_service`          | `availing of service`, `availing.*service`                        | Float       |
| `rpt_rendering_service`         | `rendering of service`, `rendering.*service`                      | Float       |
| `rpt_lease`                     | `lease.*related party`, `^lease$`, `rent`                       | Float       |
| `rpt_monthly_remun`             | `monthly remuneration`, `appointment to any office`, `salary`   | Float       |
| `rpt_remuneration_underwriting` | `remuneration for underwriting`, `underwriting.*subscription`     | Float       |

### 4. Boolean Flags (Yes/No Questions)

| Extracted Variable                     | Regex Keywords Searched For                                                                | Output Type                     |
| :------------------------------------- | :----------------------------------------------------------------------------------------- | :------------------------------ |
| `has_schedule_iii_format`            | *Checks if Balance Sheet contains all 7 major structural headers*                        | "yes" / "no"                    |
| `is_subsidiary_or_holding`           | `subsidiary or holding`, `is subsidiary`                                               | "yes" / "no" / "not applicable" |
| `is_listed`                          | `is listed`, `listed company` (also inferred if CIN begins with 'L')                   | "yes" / "no"                    |
| `is_ind_as`                          | `ind as applicable`, `ind as`, `indian accounting standard`, `accounting standard` | "yes" / "no"                    |
| `has_loans_investments_guarantees`   | `has the company given loan.*guarantee`, `loans.*investments.*guarantees`              | "yes" / "no"                    |
| `has_loans_to_directors`             | `loan to directors`, `has the company given any loan to directors`                     | "yes" / "no"                    |
| `body_corporate_investors`           | `body corporate has invested`, `invested in its share capital`                         | "yes" / "no"                    |
| `borrowing_defaults`                 | `default in repayment`, `borrowing default`                                            | "yes" / "no"                    |
| `has_bribe` / `has_internal_audit` | `internal audit applicable`, `bribe`                                                   | "yes" / "no"                    |

---

## Part 2: Step 1 - Common Errors (PDF/Word Extraction)

The **Common Error Engine** scans the extracted text (usually from the auditor's report PDF/Word) for specific phrases.

| Row Name (Requirement)          | Logic / Threshold                                                                                              | Source Searched  |
| :------------------------------ | :------------------------------------------------------------------------------------------------------------- | :--------------- |
| **Audit Report Fields**   | Must contain "opinion", "basis of opinion", "responsibilities of management", and "auditor's responsibilities" | Document Text    |
| **CARO**                  | Must contain "companies auditor s report order" or "caro"                                                      | Document Text    |
| **Schedule III**          | Validates structural format of Balance Sheet in Excel (Checks for 7 primary headings)                          | Financials Excel |
| **CIN/DIN Mention**       | Must contain ("cin" or "corporate identity number") AND "din"                                                  | Document Text    |
| **Previous year figures** | Must contain "previous year", "prior year", or regex`31st march 20\d\d`                                      | Document Text    |
| **Shareholding > 5%**     | Must contain "5%" AND ("shareholder", "holding", or "promoter")                                                | Document Text    |
| **Cash flow statement**   | Must contain "cash flow statement" or "statement of cash flows"                                                | Document Text    |
| **EPS & diluted EPS**     | Must contain "eps" or "earnings per share"                                                                     | Document Text    |
| **UDIN**                  | Must contain "udin" or an 18-digit number                                                                      | Document Text    |
| **Seal of the auditor**   | Must contain "firm registration number", "frn", "seal", or "membership no"                                     | Document Text    |
| **Audit Trail features**  | Evaluates software usage, edit log presence, preservation of logs. Marks as failed if "No".                    | Document Text    |
| **CSR Rules**             | Looks for "corporate social responsibility", "csr expense", or "csr"                                           | Document Text    |
| **Manual Checks**         | Defaulted to "No" to force the team to manually verify board resolutions.                                      | Manual           |

*(Note: Data for Common Errors is mapped to **Column C** & **Column D** of the `Common Error` sheet in the output Excel).*

---

## Part 3: Step 2 - Compliance Review

The **Compliance Engine** utilizes the *numeric* data extracted from the financial Excel files to evaluate statutory thresholds.

| Row Name (Requirement)                    | Extracted Variables Used                                         | Logic / Threshold                                                                                            |
| :---------------------------------------- | :--------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------- |
| **Is it a Small Company?**          | `turnover`, `paid_up_capital`, `is_subsidiary_or_holding`  | Turnover < 100Cr AND PUC < 10Cr AND NOT Subsidiary/Holding                                                   |
| **CARO Applicability**              | `paid_up_capital`, `reserves`, `borrowings`, `turnover`  | Exempt if Small Company/OPC. Private Co exempt if (PUC+Reserves) <= 1Cr, Borrowings <= 1Cr, Turnover <= 10Cr |
| **Corporate Social Responsibility** | `net_worth`, `turnover`, `net_profit_before_tax`           | Applicable if NW >= 500Cr, OR Turnover >= 1000Cr, OR Net Profit >= 5Cr                                       |
| **Rotation of Auditors**            | `paid_up_capital`, `company_type`, `is_listed`             | Applicable if Listed, Public, or Private Co with PUC >= 50Cr                                                 |
| **XBRL filing**                     | `paid_up_capital`, `turnover`, `is_listed`, `is_ind_as`  | Applicable if Listed, IND AS, PUC >= 5Cr, OR Turnover >= 100Cr                                               |
| **Vigil Mechanism**                 | `borrowings`                                                   | Applicable if Borrowings > 50Cr                                                                              |
| **Internal Financial Controls**     | `turnover`, `borrowings`, `company_type`                   | Exempt for Private Co if Turnover < 50Cr AND Borrowings < 25Cr                                               |
| **Internal Audit**                  | `turnover`, `borrowings`                                     | Applicable if Turnover >= 200Cr OR Borrowings >= 100Cr                                                       |
| **IND AS applicability**            | `net_worth`, `is_ind_as`, `is_listed`                      | Applicable if Listed, explicitly IND AS, OR NW >= 250Cr                                                      |
| **MGT 8 Applicability**             | `paid_up_capital`, `turnover`, `is_listed`                 | Applicable if Listed, PUC >= 10Cr, OR Turnover >= 50Cr                                                       |
| **Certification of MGT 7**          | (Derived from Small Company check)                               | Not Applicable if Small Company                                                                              |
| **Secretarial Audit**               | `paid_up_capital`, `turnover`, `borrowings`, `is_listed` | Applicable if Listed, Borrowings >= 100Cr, OR Public Co with PUC >= 50Cr / Turnover >= 250Cr                 |
| **KMP appointment**                 | `paid_up_capital`, `company_type`, `is_listed`             | Applicable if Listed OR PUC >= 10Cr                                                                          |
| **Loan Investment Guarantee 186**   | `has_loans_investments_guarantees`                             | If Yes, marks as "Failed" (Check for Boards Approval)                                                        |

*(Note: Data for Compliance Review is mapped to **Column C** ("Complied or not" for Current Year) in the `Compliance sheet for private` sheet).*

---

## Part 4: Step 3 - RPT & Loans Review

The **RPT & Loans Engine** compares exact transaction values against statutory limits derived from the company's financials (Turnover / Net Worth).

### Section 188: Related Party Transactions (Materiality)

| Transaction                         | Extracted Variable                | Limit Logic              |
| :---------------------------------- | :-------------------------------- | :----------------------- |
| **Sale of Goods**             | `rpt_sale_goods`                | 10% of`prev_turnover`  |
| **Purchase of Goods**         | `rpt_purchase_goods`            | 10% of`prev_turnover`  |
| **Sale of property**          | `rpt_sale_property`             | 10% of`prev_net_worth` |
| **Purchase of property**      | `rpt_purchase_property`         | 10% of`prev_net_worth` |
| **Dispose of Property**       | `rpt_dispose_property`          | 10% of`prev_net_worth` |
| **Availing of service**       | `rpt_availing_service`          | 10% of`prev_turnover`  |
| **Rendering of Service**      | `rpt_rendering_service`         | 10% of`prev_turnover`  |
| **Lease**                     | `rpt_lease`                     | 10% of`prev_turnover`  |
| **Appointment to office**     | `rpt_monthly_remun`             | 2.5 Lakhs (per month)    |
| **Underwriting Remuneration** | `rpt_remuneration_underwriting` | 1% of`prev_net_worth`  |

*If the actual transaction value exceeds the limit, it is flagged as "Applicable" (Material Transaction).*

### Section 185/186: Loans to Directors

| Row Name (Requirement)                              | Extracted Variable Used                                                          | Logic                                                                                    |
| :-------------------------------------------------- | :------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------- |
| **Has Company given loan to body corporate?** | `has_loans_to_directors`                                                       | Returns Yes/No                                                                           |
| **Has Company acquired securities?**          | `has_loans_investments_guarantees`                                             | Returns Yes/No                                                                           |
| **60% of PUC & Free reserve**                 | `paid_up_capital`, `reserves_and_surplus`, `total_loans_investments_given` | Calculates limit:`(PUC + Reserves) * 0.6`. Flagged if total loans given exceeds limit. |
| **100% of Free reserves**                     | `reserves_and_surplus`, `total_loans_investments_given`                      | Calculates limit:`Reserves * 1.0`. Flagged if total loans given exceeds limit.         |

*(Note: Data for RPT & Loans Review is mapped to **Column F** ("Actuals") and **Column G** ("Material Transaction - Yes/No") in the `RPT and loans to Director` sheet).*
