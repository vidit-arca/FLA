# Section 2 Data Logic Documentation

This document outlines the exact extraction and calculation logic used by the backend engine to populate the fields in **Section II (Financial Details)**. 

> [!NOTE]
> All monetary amounts (with the exception of raw share counts or percentages) are dynamically divided by `1,00,000` or `100` based on the document scale to ensure they are reported in **INR Lakhs** as required by the RBI.

| Row Label | Extraction / Calculation Logic |
| :--- | :--- |
| **1.0 (or c) Total Paid-up Capital** | **Calculated:** Sum of `1.1 Total Equity & Participating Preference Share Capital` + `1.2 Non-participating Preference Share Capital`. |
| **1.1 Total Equity & Participating Preference Share Capital** | **Calculated:** Sum of `(i) Ordinary/Equity Share Capital` + `(ii) Participating Preference Share Capital`. |
| (i) Ordinary/Equity Share Capital | **Extracted:** Reads the total Equity Share Amount directly from the **List of Shareholders** table on the Input Sheet, then divides by 1 Lakh. |
| (ii) Participating Preference Share Capital | **Extracted:** Reads the Participating Preference Share Amount directly from the **List of Shareholders** table on the Input Sheet, then divides by 1 Lakh. |
| **1.2 Non-participating Preference Share Capital** | **Extracted:** Reads the Non-participating Preference Share Amount directly from the **List of Shareholders** table on the Input Sheet, then divides by 1 Lakh. |
| **2.1 Equity and Participating Preference Share Capital (NR)** | **Calculated:** Mathematical sum of rows 1 through 11 (Individuals, Companies, FIIs, etc.) under the Non-Resident (NR) Shareholdings block. |
| 1 through 11 (NR Shareholder breakdown) | **Extracted:** Extracts the exact category-by-category amounts directly from the **List of Shareholders** table on the Input Sheet, then divides by 1 Lakh. |
| **3. Non Resident Equity & Participating Preference Share Capital %** | **Calculated:** `(2.1 Equity (NR) / 1.1 Total Equity) * 100`. (Calculates the exact foreign ownership percentage). |
| **3.1 Profit(+)/Loss(-) before tax** | **Extracted:** Scans the P&L document (or Input Sheet) for PBT keywords and extracts the exact number. Applies scale conversion to Lakhs. |
| **3.2 Profit(+)/Loss(-) after tax** | **Extracted:** Scans the P&L document (or Input Sheet) for PAT keywords and extracts the exact number. Applies scale conversion to Lakhs. |
| **3.3 Dividend** | **Extracted:** Scans the P&L document (or Input Sheet) for Dividend keywords and extracts the exact number. Applies scale conversion to Lakhs. |
| **3.4 Tax on Dividend** | **Extracted:** Scans the P&L document (or Input Sheet) for Dividend Tax keywords and extracts the exact number. Applies scale conversion to Lakhs. |
| **3.5 Retained Profit** | **Calculated:** `3.2 PAT` - `3.3 Dividend` - `3.4 Tax on Dividend`. |
| **4.1 Reserves & Surplus** | **Extracted:** Scans the Balance Sheet for Reserves & Surplus and extracts the exact number. Applies scale conversion to Lakhs. |
| **4.2 Of which, Profit (+) and Loss (-) balance** | **Extracted:** Scans the Balance Sheet for P&L Balance and extracts the exact number. Applies scale conversion to Lakhs. |
| **4.3 Net worth of Company** | **Calculated:** `1.1 Total Equity & Participating Preference Share Capital` + `4.1 Reserves & Surplus`. |
| **5.1 Domestic Sales** | **Extracted:** Scans the Input Sheet for Domestic Sales keywords and extracts the exact number. Applies scale conversion to Lakhs. |
| **5.2 Exports** | **Extracted:** Scans the Input Sheet for Exports keywords and extracts the exact number. Applies scale conversion to Lakhs. |
| **5.3 Total Sales** | **Extracted:** Scans the P&L (or Input Sheet) for Revenue from Operations and extracts the exact number. Applies scale conversion to Lakhs. |
| **5.4 Domestic Purchase** | **Extracted:** Scans the Input Sheet for Domestic Purchase keywords (scoped only to the Particulars column) and extracts the exact number. Applies scale conversion to Lakhs. |
| **5.5 Imports** | **Extracted:** Scans the Input Sheet for Imports keywords (scoped only to the Particulars column) and extracts the exact number. Applies scale conversion to Lakhs. |
| **5.6 Total Purchase** | **Calculated:** `5.4 Domestic Purchase` + `5.5 Imports`. |
| **6.1 No. of employees on payroll** | **Extracted:** Scans the Input Sheet for Employee Payroll count and extracts the exact whole number. (Does not convert to Lakhs). |
