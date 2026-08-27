# AOC-4 Compliance Engine: Row-by-Row Logic Guide

### Sheet: *RPT and loans to Director*

This document provides a simple, row-by-row breakdown of the automation logic implemented for the **RPT and Loans to Director** compliance sheet.

---

## 1. Section 188: Related Party Transactions (RPT)

### Threshold Benchmarks

* **Row 6 (`Turnover @ 10%`)**: Calculates $10\%$ of Previous Year Turnover.
* **Row 7 (`Networth @ 10%`)**: Calculates $10\%$ of Previous Year Net Worth.

### Transaction Materiality Table (Rows 11 to 20)

|      Row #      | Transaction Type                | Statutory Limit           | What System Checks                  | Output                                                           |
| :--------------: | :------------------------------ | :------------------------ | :---------------------------------- | :--------------------------------------------------------------- |
| **Row 11** | Sale of Goods                   | $10\%$ of PY Turnover   | Value in RPT Notes                  | **Yes** (if $\ge$ limit) / **No** (if $<$ limit) |
| **Row 12** | Purchase of Goods/Materials     | $10\%$ of PY Turnover   | Value in RPT Notes                  | **Yes** (if $\ge$ limit) / **No** (if $<$ limit) |
| **Row 13** | Sale of Property                | $10\%$ of PY Net Worth  | Value in RPT Notes                  | **Yes** (if $\ge$ limit) / **No** (if $<$ limit) |
| **Row 14** | Purchase of Property            | $10\%$ of PY Net Worth  | Value in RPT Notes                  | **Yes** (if $\ge$ limit) / **No** (if $<$ limit) |
| **Row 15** | Disposal of Property            | $10\%$ of PY Net Worth  | Value in RPT Notes                  | **Yes** (if $\ge$ limit) / **No** (if $<$ limit) |
| **Row 16** | Availing of Service             | $10\%$ of PY Turnover   | Value in RPT Notes                  | **Yes** (if $\ge$ limit) / **No** (if $<$ limit) |
| **Row 17** | Rendering of Service            | $10\%$ of PY Turnover   | Value in RPT Notes                  | **Yes** (if $\ge$ limit) / **No** (if $<$ limit) |
| **Row 18** | Lease                           | $10\%$ of PY Turnover   | Value in RPT Notes                  | **Yes** (if $\ge$ limit) / **No** (if $<$ limit) |
| **Row 19** | Appointment to Office of Profit | $>$ ₹2.5 Lakhs / month | Remuneration to relatives/directors | **Yes** (if $>$ ₹2.5L/mo) / **No**                |
| **Row 20** | Underwriting Remuneration       | $1\%$ of PY Net Worth   | Underwriting Commission             | **Yes** (if $\ge$ limit) / **No**                  |

*(Note: If any transaction is **Yes**, AOC-2 disclosure is required).*

---

## 2. Section 185(1): Loans to Directors & Private Company Exemptions

|      Row #      | Particulars / Field                                                                            | What System Checks                                                                               | Output Value                                                                                                                                                                      |
| :--------------: | :--------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Row 25** | **Loans to directors or interested persons**                                             | Overall applicability check.                                                                     | **Applicable** (if any loans present)**Not Applicable** (if no loans)                                                                                                 |
| **Row 26** | **Loan to Directors / Holding Co / Partner / Relative**                                  | Checks if loan is given to an**individual person** (e.g. *Mr. Vidit*, *Ms. Gayathri*). | **Yes** (if individual loan found)**No** (if no loan given)                                                                                                           |
| **Row 27** | **Loan to any firm where director/relative is partner**                                  | Checks for direct loans to partnership firms.                                                    | **No** / **Yes**                                                                                                                                                      |
| **Row 29** | **No other body corporate has invested in its share capital** *(GSR 464E Condition 1)* | Checks Master Data / Shareholder list for corporate shareholders.                                | **yes body corporate** (if body corporate invested)**Yes** (if 100% individual shareholders)                                                                          |
| **Row 30** | **Borrowings is less than 2x PUC or 50 Cr** *(GSR 464E Condition 2)*                   | Compares total borrowings against$\min(2 \times \text{PUC}, \text{₹50 Cr})$.                  | **yes loan is exceeding** (if limit breached)**Yes** (if borrowings within limit)                                                                                     |
| **Row 31** | **No default in repayment of borrowings** *(GSR 464E Condition 3)*                     | Bank repayment default status.                                                                   | **manual check**                                                                                                                                                            |
| **Row 32** | **Even if one condition is YES, Private companies cannot provide loans to directors...** | Evaluates if private company exemption is valid.                                                 | **since both condition is yes - Non- compliance** (if both violated)**Non- compliance** (if 1 violated)**Not applicable** (if conditions satisfied or no loans) |

---

## 3. Section 185(2): Loans to Director-Interested Entities

The system scans recipient names for corporate keywords: **Pvt Ltd, Ltd, LLP, LLC, Firm, HUF, Inc, Corp, Enterprise, Ventures** (e.g. *"Vidit Pvt Ltd"*, *"Gayathri Firm"*).

|      Row #      | Particulars / Field                                                         | Output if Entity Loan Given | Output if No Entity Loan |
| :--------------: | :-------------------------------------------------------------------------- | :-------------------------- | :----------------------- |
| **Row 33** | **Has company given loan/guarantee to interested persons (entities)** | **Yes**               | **No**             |
| **Row 34** | Private company where director is director/member                           | **manual check**      | **No**             |
| **Row 35** | Body corporate where director holds$\ge 25\%$ voting power                | **manual check**      | **No**             |
| **Row 36** | Body corporate whose Board acts on director's directions                    | **manual check**      | **No**             |
| **Row 38** | Special resolution is passed in general meeting                             | **manual check**      | **NA**             |
| **Row 39** | Loans utilised for principal business activities                            | **manual check**      | **NA**             |

---

## 4. Section 185(3): Statutory Exemptions

|      Row #      | Exemption Category                                                      | What System Checks                                                                                    | Output Value                                                                                      |
| :--------------: | :---------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------ |
| **Row 42** | **Loan to Managing Director (MD) or Whole-Time Director (WTD)**   | Checks DIR-12 designations (`MD`, `WTD`, `Executive Director`) or executive remuneration.       | **check special resolution passed** (if MD/WTD)**No - Not MD/WTD** (if non-executive) |
| **Row 43** | **Conditions of service extended to all employees**               | Standard employee loan policy.                                                                        | **Manual check**                                                                            |
| **Row 44** | **Scheme approved by special resolution**                         | Approved employee loan scheme.                                                                        | **Manual check**                                                                            |
| **Row 45** | **Ordinary course of business (NBFC / Banking)**                  | Lending business charging rate$\ge$ Government Security yield.                                      | **Manual check**                                                                            |
| **Row 46** | **Loan/Guarantee by Holding Co to Wholly Owned Subsidiary (WOS)** | Checks if recipient is an entity (e.g.*"Vidit Pvt"*) or company is Holding Co.                      | **check if the entity is WOS**(or **NA** if no loans)                                 |
| **Row 47** | **Guarantee/Security by Holding Co for loan to Subsidiary**       | Scans for`"guarantee"` / `"security provided"`, while **ignoring `"security deposits"`**. | **check if guarantee is for subsidiary**(or **NA** if no loans)                       |

---

## 5. Section 186: Loans, Guarantees & Investments

### Activity Triggers & Thresholds

* **Row 48 (`Loan, guarantee given`)**: Detects loans/guarantees to any person or body corporate $\rightarrow$ **Yes** / **No**.
* **Row 49 (`Securities acquired / Investments`)**: Checks if `investments > 0` $\rightarrow$ **Yes** / **No**.
* **Row 51 (`60% Limit`)**: $60\% \times (\text{Paid-up Capital} + \text{Free Reserves} + \text{Securities Premium})$.
* **Row 52 (`100% Limit`)**: $100\% \times (\text{Free Reserves} + \text{Securities Premium})$.
* **Overall Limit**: $\text{Higher of Row 51 and Row 52}$.

### Limit Adherence (Rows 53 & 54)

|      Row #      | Particulars                                              | Within Limit ($\le \text{Limit}$) | Exceeding Limit ($> \text{Limit}$) | No Loans/Investments |              |
| :--------------: | :------------------------------------------------------- | :------------------------------------------------------------------------: | :------------------: | :----------: |
| **Row 53** | **If within limits, include in Board report**      |                               **Yes**                               |     **No**     | **NA** |
| **Row 54** | **If exceeding limit, mention in MGT 8 & AGM/EGM** |                                **No**                                |  **check SR**  | **NA** |
