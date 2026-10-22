# AOC-4 Compliance Engine: Row-by-Row Logic Guide

### Sheet: *RPT and loans to Director*

This document provides a simple, row-by-row breakdown of the automation logic implemented for the **RPT and Loans to Director** compliance sheet.

---

## 1. Section 188: Related Party Transactions (RPT)

### Threshold Benchmarks & Data Extraction

The engine calculates limits based on the previous year's financial figures. However, it uses a smart fallback mechanism if prior year data is missing:

* **Row 6 (`Turnover @ 10%`)**: Calculates 10% of **Previous Year Turnover** (Falls back to Current Year Turnover if PY is missing).
* **Row 7 (`Networth @ 10%`)**: Calculates 10% of **Previous Year Net Worth** (Falls back to Current Year Net Worth if PY is missing).

### Transaction Materiality Table (Rows 11 to 20)

For each Related Party Transaction (RPT), the system extracts the transaction amount from the Notes to Accounts (RPT Disclosures) and compares it against the legal statutory threshold:

* **Excel Column F (Extracted Amount)**: Populated with the actual transaction value extracted from the RPT Note (e.g. `₹1,46,478.12`). If no transaction occurred, it records `0` / Nil.
* **Excel Column G (Materiality Verdict)**:
  * **`"Yes"`**: If Transaction Value is **equal to or greater than the Statutory Limit** (Material Transaction -> AOC-2 disclosure required). Status: **Failed**.
  * **`"No"`**: If Transaction Value is **less than the Statutory Limit** or `0` (Not Material -> AOC-2 disclosure not required). Status: **Passed**.

| Row # | Transaction Type | Statutory Threshold Limit | Data Source & Keywords Extracted into Col F | Output in Excel Col G (Materiality Verdict) |
| :---: | :--- | :--- | :--- | :--- |
| **Row 11** | **Sale of Goods** | **10% of Previous Year Turnover** | Scans RPT notes for: `sale of goods`, `sale of materials`, `supply of goods`, `sales to related parties`, `sale of products` | **Yes** (if 10% Turnover or more)<br>**No** (if less than 10% Turnover or Nil) |
| **Row 12** | **Purchase of Goods / Materials** | **10% of Previous Year Turnover** | Scans RPT notes for: `purchase of goods`, `purchase of materials`, `purchase or supply of goods`, `purchases from related parties`, `purchase of raw materials` | **Yes** (if 10% Turnover or more)<br>**No** (if less than 10% Turnover or Nil) |
| **Row 13** | **Sale of Property** | **10% of Previous Year Net Worth** | Scans RPT notes for: `sale of property`, `sale of fixed assets`, `sale of immovable property`, `sale of assets`, `sale of land`, `sale of building` | **Yes** (if 10% Net Worth or more)<br>**No** (if less than 10% Net Worth or Nil) |
| **Row 14** | **Purchase of Property** | **10% of Previous Year Net Worth** | Scans RPT notes for: `purchase of property`, `purchase of fixed assets`, `purchase of immovable property`, `purchase of assets`, `purchase of land`, `purchase of building` | **Yes** (if 10% Net Worth or more)<br>**No** (if less than 10% Net Worth or Nil) |
| **Row 15** | **Disposal of Property** | **10% of Previous Year Net Worth** | Scans RPT notes for: `disposal of property`, `dispose of property`, `transfer of property`, `disposal of assets`, `transfer of assets`, `disposal of fixed assets` | **Yes** (if 10% Net Worth or more)<br>**No** (if less than 10% Net Worth or Nil) |
| **Row 16** | **Availing of Services** | **10% of Previous Year Turnover** | Scans RPT notes for: `availing of services`, `availing of service`, `availing services`, `services availed`, `service charges paid`, `charges for availing services`, `charges paid for services`, `receiving of services`, `receiving services` | **Yes** (if 10% Turnover or more)<br>**No** (if less than 10% Turnover or Nil) |
| **Row 17** | **Rendering of Services** | **10% of Previous Year Turnover** | Scans RPT notes for: `rendering of services`, `rendering of service`, `rendering services`, `services rendered`, `service charges received`, `charges for rendering services`, `charges received for services`, `providing of services`, `providing services` | **Yes** (if 10% Turnover or more)<br>**No** (if less than 10% Turnover or Nil) |
| **Row 18** | **Lease / Rent** | **10% of Previous Year Turnover** | Scans RPT notes for: `lease`, `rent`, `rental`, `lease rent`, `lease payments`, `premises rent`, `office rent` | **Yes** (if 10% Turnover or more)<br>**No** (if less than 10% Turnover or Nil) |
| **Row 19** | **Appointment to Office of Profit** | **Exceeding ₹2.5 Lakhs per month** | Scans RPT notes for: `remuneration paid to directors`, `directors remuneration`, `managerial remuneration`, `remuneration to directors`, `monthly remuneration`, `annual remuneration`, `salary`, `appointment to any office`, `place of profit` | **Yes** (if over ₹2.5 Lakhs/month)<br>**No** (if up to ₹2.5 Lakhs/month or Nil) |
| **Row 20** | **Underwriting Remuneration** | **1% of Previous Year Net Worth** | Scans RPT notes for: `remuneration for underwriting`, `underwriting commission`, `underwriting remuneration`, `underwriting subscription`, `underwriting of securities` | **Yes** (if 1% Net Worth or more)<br>**No** (if less than 1% Net Worth or Nil) |

*(Note: If any transaction verdict is **"Yes"**, Form AOC-2 disclosure is triggered).*

---

## 2. Section 185(1): Loans to Directors & Private Company Exemptions

| Row # | Particulars / Field | What System Checks | Output Value |
| :---: | :--- | :--- | :--- |
| **Row 25** | **Loans to directors or interested persons** | Overall applicability check (Numerical value, NLP, or fallback to Compliance Sheet). | **Applicable** (if any loans present)<br>**Not Applicable** (if no loans) |
| **Row 26** | **Loan to Directors / Holding Co / Partner / Relative** | Checks if loan is given to an **individual person** (e.g. *Mr. Vidit*, *Ms. Gayathri*). | **Yes** (if individual loan found)<br>**No** (if no loan given) |
| **Row 27** | **Loan to any firm where director/relative is partner** | Checks for direct loans to partnership firms. | **Yes** (if firm loan detected)<br>**No** (if no firm loan detected)<br>**NA** (if AOC-2 is Not Applicable) |
| **Row 29** | **No other body corporate has invested in its share capital** *(GSR 464E Condition 1)* | Uses NLP to check if company is a subsidiary or if shares are held by corporate entities. | **yes body corporate** (if body corporate invested)<br>**Yes** (if 100% individual shareholders) |
| **Row 30** | **Borrowings is less than 2x PUC or 50 Cr** *(GSR 464E Condition 2)* | Compares total borrowings against the lower of (2 times Paid-up Capital or ₹50 Crore). | **yes loan is exceeding** (if limit breached)<br>**Yes** (if borrowings within limit) |
| **Row 31** | **No default in repayment of borrowings** *(GSR 464E Condition 3)* | Bank repayment default status. | **manual check** |
| **Row 32** | **Even if one condition is YES, Private companies cannot provide loans to directors...** | Evaluates if private company exemption is valid. | **since both condition is yes - Non- compliance** (if both violated)<br>**Non- compliance** (if 1 violated)<br>**Not applicable** (if conditions satisfied or no loans) |

---

## 3. Section 185(2): Loans to Director-Interested Entities

The system scans recipient names for corporate keywords: **Pvt Ltd, Ltd, LLP, LLC, Firm, HUF, Inc, Corp, Enterprise, Ventures, GmbH, Pte, Pty, plc, co** (e.g. *"Vidit Pvt Ltd"*, *"Gayathri Firm"*).

In addition to exact recipient names, the NLP engine scans the full transaction text for phrases like:
* `"loan to [entity]"`
* `"advance to [entity]"`
* `"guarantee for [entity]"`

| Row # | Particulars / Field | Output if Entity Loan Given | Output if No Entity Loan |
| :---: | :--- | :---: | :---: |
| **Row 33** | **Has company given loan/guarantee to interested persons (entities)** | **Yes** | **No** |
| **Row 34** | Private company where director is director/member | **manual check** | **No** |
| **Row 35** | Body corporate where director holds 25% or more voting power | **manual check** | **No** |
| **Row 36** | Body corporate whose Board acts on director's directions | **manual check** | **No** |
| **Row 38** | Special resolution is passed in general meeting | **manual check** | **NA** |
| **Row 39** | Loans utilised for principal business activities | **manual check** | **NA** |

---

## 4. Section 185(3): Statutory Exemptions

| Row # | Exemption Category | What System Checks | Output Value |
| :---: | :--- | :--- | :--- |
| **Row 42** | **Loan to Managing Director (MD) or Whole-Time Director (WTD)** | **1. Loan Check:** Checks if loan is given to a director (from Balance Sheet Assets / RPT / Input Sheet).<br>**2. Designation Check:** If loan exists, checks DIR-12 / Signatory Details / Input Sheet designations (`MD`, `WTD`, `Executive Director`). | **Yes** (if loan is given AND recipient is MD/WTD)<br>**No** (if loan is given but recipient is non-executive/ordinary director)<br>**NA** (if no loan is given to any director) |
| **Row 43** | **Conditions of service extended to all employees** | Standard employee loan policy. | **Manual check** |
| **Row 44** | **Scheme approved by special resolution** | Approved employee loan scheme. | **Manual check** |
| **Row 45** | **Ordinary course of business (NBFC / Banking)** | Scans "Significant Accounting Policies" / "Nature of Business" for NBFC/banking terms. | **Yes** (if NBFC/Banking)<br>**No** (if regular business)<br>**read the financials** (fallback manual check) |
| **Row 46** | **Loan/Guarantee by Holding Co to Wholly Owned Subsidiary (WOS)** | Checks if recipient is an entity (e.g. *"Vidit Pvt"*) or company is Holding Co. Scans RPT notes for Wholly Owned Subsidiary (WOS) status as a fallback. | **Yes** (if confirmed WOS in RPT/FS)<br>**check if the entity is WOS** (with RPT note as fallback)<br>**NA** (if no loans/guarantees) |
| **Row 47** | **Guarantee/Security by Holding Co for loan to Subsidiary** | Scans for `"guarantee"` / `"security provided"`, while **ignoring `"security deposits"`**. | **check if guarantee is for subsidiary**<br>(or **NA** if no loans) |

---

## 5. Section 186: Loans, Guarantees & Investments

### Activity Triggers & Thresholds

* **Row 48 (`Loan, guarantee given`)**: Detects numerical loans/guarantees OR uses NLP to identify if any loan/guarantee is given to any person or body corporate -> **Yes** / **No**.
* **Row 49 (`Securities acquired / Investments`)**: Checks if `investments > 0` -> **Yes** / **No**.
* **Row 51 (`60% Limit`)**: 60% of (Paid-up Capital + Free Reserves + Securities Premium).
* **Row 52 (`100% Limit`)**: 100% of (Free Reserves + Securities Premium).
* **Overall Limit**: Higher of Row 51 and Row 52.

### Limit Adherence (Rows 53 & 54)

| Row # | Particulars | Within Limit (Less than or equal to Limit) | Exceeding Limit (Greater than Limit) | No Loans/Investments |
| :---: | :--- | :---: | :---: | :---: |
| **Row 53** | **If within limits, include in Board report** | **Yes** | **No** | **NA** |
| **Row 54** | **If exceeding limit, mention in MGT 8 & AGM/EGM** | **No** | **check SR** | **NA** |
