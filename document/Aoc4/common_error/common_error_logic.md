# Common Error Sheet - NLP Extraction Rules

The table below outlines the exact Natural Language Processing (NLP) logic and keyword combinations currently implemented in the `AOC4CommonErrorEngine` for the **Common Error** sheet.

The engine concatenates the entire textual content of all uploaded documents (Financials, Board Reports, Audit Reports) into a single lowercase text block and evaluates the presence of these statutory keywords.

### General Audit & Format Rules

| Requirement | Implemented NLP Logic / Keywords | Target Result |
| :--- | :--- | :--- |
| **Audit Report Format** | Checks for all 10 standard headings: `Opinion`, `Basis of Opinion/for opinion`, `Emphasis of matter`, `Key Audit Matters`, `Other Information`, `Responsibility of Management`, `Auditor's responsibility`, `Other matters`, `Report on other legal...`, `Internal Financial Controls`. | **Yes** if ALL are found, else **No** with missing list. |
| **CARO** | Strips punctuation and checks for `companies auditor s report order` OR `caro`. | **Yes** if found. |
| **Schedule III** | Validates if the tabular layout detector (`excel_extractor`) flagged `has_schedule_iii_format` as Yes. | **Yes** if tabular structure aligns with Schedule III. |
| **CIN & DIN** | Checks for (`cin` OR `corporate identity number`) AND `din`. | **Yes** if both found, else lists missing. |
| **Previous year figures** | Checks for `previous year` OR `prior year` OR `31st march 20XX` date regex. | **Yes** if found. |

### Share Capital Notes

| Requirement | Implemented NLP Logic / Keywords | Target Result |
| :--- | :--- | :--- |
| **Shareholding > 5%** | Checks for `5%` AND (`shareholder` OR `holding` OR `promoter`). | **Yes** if found. |
| **Statutory Register** | Checks for `statutory register`. | **Yes** if found, else defaults to No (Manual). |
| **Authorised Capital** | Checks for `authorised capital`, `authorized capital`, OR `authorised share capital`. | **Yes** if found. |
| **Paid up capital** | Checks for `paid up capital`, `paid-up capital`, OR `paid up share capital`. | **Yes** if found. |
| **Reconciliation of shares** | Checks for `reconciliation` AND (`shares outstanding` OR `number of shares` OR `beginning of the year`). | **Yes** if both combinations found. |
| **Promoter holding** | Checks for `promoter holding`, `promoter's holding`, OR `shares held by promoters`. | **Yes** if found. |

### Financial Statements & Policies

| Requirement | Implemented NLP Logic / Keywords | Target Result |
| :--- | :--- | :--- |
| **Cash flow statement** | Checks for `cash flow statement` OR `statement of cash flows`. | **Yes** if found. |
| **Significant Accounting Policies**| Checks for `significant accounting policies` OR `summary of significant accounting policies`. | **Yes** if found. |
| **EPS & Diluted EPS** | Checks for `eps` OR `earnings per share` OR (`basic` AND `diluted`). | **Yes** if found. |
| **RPT & Forex** | Checks for (`related party` OR `rpt`) AND/OR (`foreign exchange` OR `forex` OR `foreign currency`) depending on the exact row being evaluated. | **Yes** if matched. |

### Signatures & Auditor Details

| Requirement | Implemented NLP Logic / Keywords | Target Result |
| :--- | :--- | :--- |
| **Signed by directors/auditors** | Checks for `director` AND (`auditor` OR `partner` OR `chartered accountant`). | **Yes** if found. |
| **UDIN** | Checks for `udin` OR a strict 18-digit number regex (`\b\d{18}\b`). | **Yes** if found. |
| **Seal of the auditor** | Checks for `firm registration number`, `frn`, `seal`, OR `membership no`. | **Yes** if found. |

### Audit Trail Features

| Requirement | Implemented NLP Logic / Keywords | Target Result |
| :--- | :--- | :--- |
| **Accounting Software/Trail** | Checks for `accounting software` AND `audit trail`. | **Yes** if found. |
| **Edit Log** | Checks for `edit log` OR `recording audit trail`. | **Yes** if found. |
| **Operated throughout year** | Checks for exact phrase `operated throughout the year`. | **Yes** if found. |
| **Tampered with** | Checks for exact phrase `tampered with`. | **Yes** if found. |
| **Preservation of records** | Checks for `preserv` AND `audit trail`. | **Yes** if found. |

### Corporate Social Responsibility (CSR)

| Requirement | Implemented NLP Logic / Keywords | Target Result |
| :--- | :--- | :--- |
| **CSR Mandatory Phrases** | The engine checks for standard CSR phrasing such as: `amount required to be spent`, `amount of expenditure incurred`, `shortfall at the end of the year`, `reason for shortfall`, etc. | **Yes** if exact phrases are found in the text. |
