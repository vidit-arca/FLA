# FLA Extraction & Rule Engine Documentation

This document provides a comprehensive mapping of every rule, its underlying data requirements, the specific logic used to extract that data from the uploaded Excel files and PDF documents, and the calculations the engines use to evaluate the rule and populate the RBI FLA Return forms.

---

## Part 1: Data Extraction Layer

### 1. Excel Data Extraction (`ExcelExtractor`)
The `excel_extractor.py` processes uploaded `.xlsx` files to extract both Foreign Direct Investment (FDI) and Overseas Direct Investment (ODI) data depending on the role specified.

#### 1.1 Foreign Direct Investment (FDI) Extraction
**Targeted Sheets/Keywords:** Scans the first 20 rows of the uploaded shareholders list for headers containing keywords like `name`, `shareholder`, `nationality`, `country`, and `number of security`.

**Logic & Grouping:**
- Filters for Equity and Preference shares.
- Filters for Non-Resident (Foreign) Investors by excluding Indian entries.
- Aggregates shares by Country and Investor Name, classifying investors into **FDI (>= 10% holding)** and **DI (< 10% holding)**.

| Extracted Variable | Description / Source | Source of Data | Output Type |
| :--- | :--- | :--- | :--- |
| `fdi_investors_count` | Number of FDI investors (holding >= 10%) | Shareholders Excel | Integer |
| `fdi_investor_1_name` | Name of the largest FDI investor | Shareholders Excel | String |
| `fdi_investor_1_country`| Country of the largest FDI investor | Shareholders Excel | String |
| `fdi_investor_1_equity_percent_py/fy` | Equity % held by the largest FDI investor | Shareholders Excel | Float |
| `fdi_less_than_10_countries_count` | Number of countries where DI (<10%) is held | Shareholders Excel | Integer |
| `fdi_investor_2_name/country` | Comma-separated list of DI countries | Shareholders Excel | String |
| `fdi_investor_2_equity_percent_py/fy` | Aggregated equity % of all DI investors | Shareholders Excel | Float |
| `nr_shares_companies_py/fy` | Sum of shares held by non-resident companies/corporates | Shareholders Excel | Float |
| `nr_shares_individuals_py/fy` | Sum of shares held by non-resident individuals | Shareholders Excel | Float |

#### 1.2 Overseas Direct Investment (ODI) Extraction
**Targeted Sheets/Keywords:** Scans sheets named `FINANCIALS` or `FLA_RETURN`. Searches for specific prompt strings in column B to extract values from columns C (PY) and D (FY).

| Row Name / Requirement | Regex / Keywords Searched For | Extracted Variable | Source of Data |
| :--- | :--- | :--- | :--- |
| **DIE 1 Identification** | `name of the foreign company`, `country of incorporation` | `die_1_name`, `die_1_country` | FLA Return Excel |
| **DIE 1 Financials** | `total equity`, `reserves & surplus`, `p&l account balance`, `total sales` | `die_1_total_equity`, `die_1_reserves`, `die_1_sales` | FLA Return Excel |
| **DIE 1 Claims/Liabilities** | `liabilities to the die`, `claims on die`, `other liabilities to die` | `die_1_liabilities`, `die_1_claims` | FLA Return Excel |
| **Unrelated Assets (Block 4)** | `trade credit to foreign unrelated`, `loans given to foreign unrelated` | `unrelated_trade_credit_assets`, `unrelated_loans_assets` | FLA Return Excel |
| **ODI / Portfolio Countries** | `number of countries where you hold <10%`, `portfolio equity % held` | `odi_less_than_10_countries_count`, `portfolio_abroad_countries_count` | FLA Return Excel |

---

### 2. Document & OCR Text Extraction (`DocumentParser`)
The `parser.py` handles extraction from unstructured or semi-structured formats (PDFs, Markdown, JSON OCR outputs) such as the Board Report and Financial Statements.

**Extraction Logic:** 
- Uses Regex on text to find company identification details.
- Parses HTML/Markdown tables to extract specific financial rows using dynamic column mapping (Current Year vs Previous Year).
- Scans textual notes for employee counts, share face values, and nature of business.

| Row Name / Requirement | Logic / Regex Keywords Searched For | Extracted Variable | Source of Data |
| :--- | :--- | :--- | :--- |
| **Company Identification** | `cin`, `pan`, `email`, regex for mobile/contact name | `cin_number`, `pan_number`, `company_name`, `email_id` | Board Report PDF/OCR |
| **Employee Count** | `Female X Male Y`, `Number of Employees ... TOTAL`, `payroll` | `employee_payroll_count_fy`, `employee_payroll_count_py` | Board Report PDF/OCR |
| **Unrelated Assets/Liabilities (Block 4)**| Regex for `1.1 Trade Credit`, `1.2 Loans`, `1.3 Currency & Deposits`, `1.4 Other receivable` | `unrelated_trade_credit_liab_fy`, `unrelated_loans_assets_py`, etc. | Extra Details PDF/Text |
| **Equity & CCPS Shares** | `Movement in the Equity Share capital`, `Convertible Preference` | `equity_shares_count_fy`, `part_pref_shares_count_fy` | Financials PDF/MD |
| **Share Face Value** | `par value of Rs. \d+ per share`, `face value of Rs.` | `equity_face_value_fy`, `part_pref_face_value_fy` | Financials PDF/MD |
| **Profit & Loss Balance** | `Surplus / (Deficit) in Statement of Profit and Loss` | `pl_balance_fy`, `pl_balance_py` | Financials PDF/MD |
| **Sales & Purchases** | `Domestic sales`, `Indigenous`, `Imported` | `domestic_sales_fy`, `import_purchases_fy` | Financials PDF/MD |
| **Related Party Txns** | `trade payable`, `outstanding`, `trade receivable`, `investment` matching Investor Name | `fdi_investor_1_other_liabilities_fy`, `_other_claims_fy` | Financials PDF/MD |
| **First FDI Date** | `FCGPR`, `first share allotment` followed by Month/Year | `fdi_first_received_date` | Financials PDF/MD |
| **Nature of Business / NIC**| `engaged in the business of`, `nature of operations is` | Maps to standard NIC Codes based on text matches | Board Report / Fin MD |

---

## Part 2: Rule Engine & State Compilation (`RuleEngine`)

The `rule_engine.py` aggregates extracted data, applies defaults from `rules_config.json`, and calculates derived financial metrics mapping to the FLA coordinate system (Sections I to IV).

### Section I & II: Company Financials & Paid-up Capital
Calculates fundamental metrics and normalizes share values to INR Lakhs.

| Metric / Calculation | Logic | Source of Data | Section Target Cells |
| :--- | :--- | :--- | :--- |
| **Shares to Lakhs** | `(Shares * Face Value) / 100000.0` | Fin MD & Config | Applied to Equity, Part Pref, Non-Part Pref |
| **Total Paid-up Capital** | Sum of Total Equity & Part Pref + Total Non-Part Pref | Section II Internal Calc | `F5/G5`, `F6/G6` |
| **NR Holdings Apportionment** | Proportional Rs. Lakhs Amount = `(Shares held / Total Shares) * Total Share Capital` | Shareholders Excel / Internal Calc | `F12-F22` / `G12-G22` |
| **Total NR Equity %** | `(Sum of NR Holdings / Total Paid-up) * 100` | Section II Internal Calc | `F24`, `G24` |
| **Retained Profit** | `Net Profit/Loss - Dividend on Equity - Dividend on Pref` | Section II Internal Calc | `F30`, `G30` |
| **Net Worth** | `Total Paid-up + Total Reserves & Surplus` | Section II Internal Calc | `F34`, `G34` |
| **Total Sales / Purchases** | Sum of Domestic + Exports/Imports | Section II Internal Calc | `F38/G38`, `F41/G41` |

### Section III: Foreign Direct Investment (FDI) & DI Calculations
Calculates proportional liabilities and other capital metrics based on the Net Worth.

| Metric / Calculation | Logic | Source of Data | Section Target Cells |
| :--- | :--- | :--- | :--- |
| **FDI 1 Equity Capital Holding** | `(FDI 1 Equity % / 100) * Net Worth` | Section II Net Worth / FDI % | `D20` / `E20` |
| **FDI 1 Liabilities to Investors** | Mirrors FDI 1 Equity Capital Holding | Section III Internal Calc | `D21` / `E21` |
| **FDI 1 Other Capital** | `Total Other Capital (Liabilities) - Claims on Direct Investor` | Section III Internal Calc | `D23` / `E23` |
| **FDI 2 / Block 2 DI 1** | Applies same proportional logic using FDI 2 % and DI 1 % | Section II Net Worth / FDI % | `Z33/Z34`, `D44/E44` |
| **Unrelated Total Liabilities** | Sum of Unrelated Trade Credit, Loans, Currency Deposits, Other | Section III Internal Calc | `D74`, `E74` |

### Section IV: Overseas Direct Investment (ODI) Calculations
Calculates proportional claims and equity capital for Direct Investment Enterprises (DIE).

| Metric / Calculation | Logic | Source of Data | Section Target Cells |
| :--- | :--- | :--- | :--- |
| **DIE 1 Net Worth** | `Total Equity + Reserves & Surplus` | ODI Extraction | `D30` / `E30` |
| **DIE 1 Equity Capital (INR Lakhs)** | `(Equity held in FC * Exchange Rate) / 100000.0` | ODI Extraction | `D39` / `E39` |
| **DIE 1 Other Capital** | `Total Other Capital (Claims) - Liabilities to DIE` | ODI Extraction | `D42` / `E42` |
| **Unrelated Total Claims** | Sum of Unrelated Trade Credit, Loans, Deposits, Other Receivables | ODI Extraction | `D100`, `E100` |

---


## Appendix: Complete Cell Mapping Details (All Rows)

This section details every single cell coordinate mapped across all sections in the FLA return.

### Section I
| Cell | Field / Formula | Type | Default |
| :--- | :--- | :--- | :--- |
| Year | `filing_year` | extracted | 2025 |
| Company_Name | `company_name` | extracted |  |
| PAN_Number | `pan_number` | extracted |  |
| CIN_Number | `cin_number` | extracted |  |
| Contact_Person | `contact_name` | extracted |  |
| Telephone | `telephone` | extracted |  |
| Mobile | `mobile_number` | extracted |  |
| Email_Head | `email_id` | extracted |  |
| Email_Contact | `email_id` | extracted |  |
| Designation | `designation` | extracted |  |
| Website | `website` | extracted |  |
| Closing_Date | `get_closing_date()` | calculated |  |
| Nature_of_Business | `nic_code` | extracted |  |
| Merged_Status | `merged_status` | extracted | No |
| Listed_Status | `listed_status` | extracted | No |
| Equity_Share_Count_PY | `equity_shares_count_py` | extracted |  |
| Equity_Share_Count_FY | `equity_shares_count_fy` | extracted |  |
| Part_Pref_Share_Count_PY | `part_pref_shares_count_py` | extracted |  |
| Part_Pref_Share_Count_FY | `part_pref_shares_count_fy` | extracted |  |
| Non_Part_Pref_Share_Count_PY | `non_part_pref_shares_count_py` | extracted | 0 |
| Non_Part_Pref_Share_Count_FY | `non_part_pref_shares_count_fy` | extracted | 0 |
| Equity_FV_PY | `equity_face_value_py` | extracted | 1 |
| Equity_FV_FY | `equity_face_value_fy` | extracted | 1 |
| Part_Pref_FV_PY | `part_pref_face_value_py` | extracted |  |
| Part_Pref_FV_FY | `part_pref_face_value_fy` | extracted |  |
| Non_Part_Pref_FV_PY | `non_part_pref_face_value_py` | extracted |  |
| Non_Part_Pref_FV_FY | `non_part_pref_face_value_fy` | extracted |  |
| Listed_Market_Price_PY | `get_listed_market_price('py')` | calculated |  |
| Listed_Market_Price_FY | `get_listed_market_price('fy')` | calculated |  |
| Identification_Inward_FDI | `inward_fdi_status` | extracted | Yes |
| Type_of_Company | `company_type` | extracted | Private Limited |
| AMC_Status | `amc_status` | extracted | No |
| Tech_Collab_Status | `tech_collab_status` | extracted | No |
| Business_Activity_Status | `business_activity_status` | extracted | Yes |

### Section II
| Cell | Field / Formula | Type | Default |
| :--- | :--- | :--- | :--- |
| Paid_Up_Capital_PY | `sum_cells('Section II', ['F6', 'F9'])` | calculated |  |
| Paid_Up_Capital_FY | `sum_cells('Section II', ['G6', 'G9'])` | calculated |  |
| Equity_Pref_Capital_PY | `sum_cells('Section II', ['F7', 'F8'])` | calculated |  |
| Equity_Pref_Capital_FY | `sum_cells('Section II', ['G7', 'G8'])` | calculated |  |
| Ordinary_Equity_Shares_PY | `equity_shares_count_py` | extracted |  |
| Ordinary_Equity_Shares_FY | `equity_shares_count_fy` | extracted |  |
| Ordinary_Equity_Amount_PY | `shares_to_lakhs('equity_shares_count_py', 'equity_face_value_py')` | calculated |  |
| Ordinary_Equity_Amount_FY | `shares_to_lakhs('equity_shares_count_fy', 'equity_face_value_fy')` | calculated |  |
| Part_Pref_Shares_PY | `part_pref_shares_count_py` | extracted |  |
| Part_Pref_Shares_FY | `part_pref_shares_count_fy` | extracted |  |
| Part_Pref_Amount_PY | `shares_to_lakhs('part_pref_shares_count_py', 'part_pref_face_value_py')` | calculated |  |
| Part_Pref_Amount_FY | `shares_to_lakhs('part_pref_shares_count_fy', 'part_pref_face_value_fy')` | calculated |  |
| Non_Part_Pref_Shares_PY | `non_part_pref_shares_count_py` | extracted |  |
| Non_Part_Pref_Shares_FY | `non_part_pref_shares_count_fy` | extracted |  |
| Non_Part_Pref_Amount_PY | `shares_to_lakhs('non_part_pref_shares_count_py', 'non_part_pref_face_value_py')` | calculated |  |
| Non_Part_Pref_Amount_FY | `shares_to_lakhs('non_part_pref_shares_count_fy', 'non_part_pref_face_value_fy')` | calculated |  |
| NR_Equity_Pref_Capital_PY | `sum_cells('Section II', ['F12', 'F13', 'F14', 'F15', 'F16', 'F17', 'F18', 'F19', 'F20', 'F21', 'F22'])` | calculated |  |
| NR_Equity_Pref_Capital_FY | `sum_cells('Section II', ['G12', 'G13', 'G14', 'G15', 'G16', 'G17', 'G18', 'G19', 'G20', 'G21', 'G22'])` | calculated |  |
| NR_Individuals_PY | `nr_shares_individuals_py` | extracted | 0 |
| NR_Individuals_FY | `nr_shares_individuals_fy` | extracted | 0 |
| NR_Companies_PY | `nr_shares_companies_py` | extracted | 0 |
| NR_Companies_FY | `nr_shares_companies_fy` | extracted | 0 |
| NR_FIIs_PY | `nr_shares_fiis_py` | extracted | 0 |
| NR_FIIs_FY | `nr_shares_fiis_fy` | extracted | 0 |
| NR_FVCIs_PY | `nr_shares_fvcis_py` | extracted | 0 |
| NR_FVCIs_FY | `nr_shares_fvcis_fy` | extracted | 0 |
| NR_Trusts_PY | `nr_shares_trusts_py` | extracted | 0 |
| NR_Trusts_FY | `nr_shares_trusts_fy` | extracted | 0 |
| NR_PE_Funds_PY | `nr_shares_pe_funds_py` | extracted | 0 |
| NR_PE_Funds_FY | `nr_shares_pe_funds_fy` | extracted | 0 |
| NR_Pension_Funds_PY | `nr_shares_pension_funds_py` | extracted | 0 |
| NR_Pension_Funds_FY | `nr_shares_pension_funds_fy` | extracted | 0 |
| NR_Sovereign_Funds_PY | `nr_shares_sovereign_funds_py` | extracted | 0 |
| NR_Sovereign_Funds_FY | `nr_shares_sovereign_funds_fy` | extracted | 0 |
| NR_Partnerships_PY | `nr_shares_partnerships_py` | extracted | 0 |
| NR_Partnerships_FY | `nr_shares_partnerships_fy` | extracted | 0 |
| NR_Fin_Institutions_PY | `nr_shares_fin_inst_py` | extracted | 0 |
| NR_Fin_Institutions_FY | `nr_shares_fin_inst_fy` | extracted | 0 |
| NR_NRIs_PIO_PY | `nr_shares_nris_py` | extracted | 0 |
| NR_NRIs_PIO_FY | `nr_shares_nris_fy` | extracted | 0 |
| NR_Non_Part_Pref_Shares_PY | `nr_shares_non_part_pref_py` | extracted | 0 |
| NR_Non_Part_Pref_Shares_FY | `nr_shares_non_part_pref_fy` | extracted | 0 |
| NR_Equity_Pref_Percent_PY | `percentage_of('Section II', 'F11', 'F6')` | calculated |  |
| NR_Equity_Pref_Percent_FY | `percentage_of('Section II', 'G11', 'G6')` | calculated |  |
| PBT_PY | `profit_before_tax_py` | extracted | 0.0 |
| PBT_FY | `profit_before_tax_fy` | extracted | 0.0 |
| PAT_PY | `profit_after_tax_py` | extracted | 0.0 |
| PAT_FY | `profit_after_tax_fy` | extracted | 0.0 |
| Dividend_PY | `dividend_paid_py` | extracted | 0.0 |
| Dividend_FY | `dividend_paid_fy` | extracted | 0.0 |
| Tax_on_Dividend_PY | `tax_on_dividend_py` | extracted | 0.0 |
| Tax_on_Dividend_FY | `tax_on_dividend_fy` | extracted | 0.0 |
| Retained_Profit_PY | `subtract_cells('Section II', 'F27', 'F28', 'F29')` | calculated |  |
| Retained_Profit_FY | `subtract_cells('Section II', 'G27', 'G28', 'G29')` | calculated |  |
| Reserves_Surplus_PY | `reserves_and_surplus_py` | extracted | 0.0 |
| Reserves_Surplus_FY | `reserves_and_surplus_fy` | extracted | 0.0 |
| PL_Balance_PY | `pl_balance_py` | extracted | 0.0 |
| PL_Balance_FY | `pl_balance_fy` | extracted | 0.0 |
| Net_Worth_PY | `sum_cells('Section II', ['F6', 'F32'])` | calculated |  |
| Net_Worth_FY | `sum_cells('Section II', ['G6', 'G32'])` | calculated |  |
| Domestic_Sales_PY | `domestic_sales_py` | extracted | 0.0 |
| Domestic_Sales_FY | `domestic_sales_fy` | extracted | 0.0 |
| Export_Sales_PY | `export_sales_py` | extracted | 0.0 |
| Export_Sales_FY | `export_sales_fy` | extracted | 0.0 |
| Total_Sales_PY | `sum_cells('Section II', ['F36', 'F37'])` | calculated |  |
| Total_Sales_FY | `sum_cells('Section II', ['G36', 'G37'])` | calculated |  |
| Domestic_Purchases_PY | `domestic_purchases_py` | extracted | 0.0 |
| Domestic_Purchases_FY | `domestic_purchases_fy` | extracted | 0.0 |
| Import_Purchases_PY | `import_purchases_py` | extracted | 0.0 |
| Import_Purchases_FY | `import_purchases_fy` | extracted | 0.0 |
| Total_Purchases_PY | `sum_cells('Section II', ['F39', 'F40'])` | calculated |  |
| Total_Purchases_FY | `sum_cells('Section II', ['G39', 'G40'])` | calculated |  |
| Employees_Payroll_PY | `employee_payroll_count_py` | extracted | 0 |
| Employees_Payroll_FY | `employee_payroll_count_fy` | extracted | 0 |

### Section III
| Cell | Field / Formula | Type | Default |
| :--- | :--- | :--- | :--- |
| FDI_Investors_Count | `fdi_investors_count` | extracted | 1 |
| FDI_First_Time_Date | `fdi_first_received_date` | extracted | N/A |
| FDI1_Name | `fdi_investor_1_name` | extracted |  |
| FDI1_Country | `fdi_investor_1_country` | extracted |  |
| FDI1_Equity_Percent_PY | `fdi_investor_1_equity_percent_py` | extracted | 0 |
| FDI1_Equity_Percent_FY | `fdi_investor_1_equity_percent_fy` | extracted | 0 |
| FDI1_Equity_Capital_PY | `calculate_fdi_equity('fdi_investor_1_equity_percent_py', 'Net_Worth_PY')` | calculated |  |
| FDI1_Equity_Capital_FY | `calculate_fdi_equity('fdi_investor_1_equity_percent_fy', 'Net_Worth_FY')` | calculated |  |
| FDI1_Liabilities_PY | `calculate_fdi_equity('fdi_investor_1_equity_percent_py', 'Net_Worth_PY')` | calculated |  |
| FDI1_Liabilities_FY | `calculate_fdi_equity('fdi_investor_1_equity_percent_fy', 'Net_Worth_FY')` | calculated |  |
| FDI1_Claims_PY | `fdi_investor_1_claims_py` | extracted | 0.0 |
| FDI1_Claims_FY | `fdi_investor_1_claims_fy` | extracted | 0.0 |
| FDI1_Other_Capital_PY | `subtract_cells('Section III', 'D24', 'D25')` | calculated |  |
| FDI1_Other_Capital_FY | `subtract_cells('Section III', 'E24', 'E25')` | calculated |  |
| FDI1_Other_Liabilities_PY | `fdi_investor_1_other_liabilities_py` | extracted | 0.0 |
| FDI1_Other_Liabilities_FY | `fdi_investor_1_other_liabilities_fy` | extracted | 0.0 |
| FDI1_Other_Claims_PY | `fdi_investor_1_other_claims_py` | extracted | 0.0 |
| FDI1_Other_Claims_FY | `fdi_investor_1_other_claims_fy` | extracted | 0.0 |
| FDI1_Disinvestment_PY | `fdi_investor_1_disinvestment_py` | extracted | 0.0 |
| FDI1_Disinvestment_FY | `fdi_investor_1_disinvestment_fy` | extracted | 0.0 |
| Block2_No_Countries | `fdi_less_than_10_countries_count` | extracted | 0 |
| Portfolio_Equity_Percent_PY | `portfolio_equity_percent_py` | extracted | 0.0 |
| Portfolio_Equity_Percent_FY | `portfolio_equity_percent_fy` | extracted | 0.0 |
| Portfolio_Equity_Market_Value_PY | `portfolio_equity_mv_py` | extracted | 0.0 |
| Portfolio_Equity_Market_Value_FY | `portfolio_equity_mv_fy` | extracted | 0.0 |
| Portfolio_Money_Market_PY | `portfolio_money_market_py` | extracted | 0.0 |
| Portfolio_Money_Market_FY | `portfolio_money_market_fy` | extracted | 0.0 |
| Portfolio_Bonds_PY | `portfolio_bonds_py` | extracted | 0.0 |
| Portfolio_Bonds_FY | `portfolio_bonds_fy` | extracted | 0.0 |
| Portfolio_Disinvestment_PY | `portfolio_disinvestment_py` | extracted | 0.0 |
| Portfolio_Disinvestment_FY | `portfolio_disinvestment_fy` | extracted | 0.0 |
| Unrelated_Trade_Credit_PY | `unrelated_trade_credit_liab_py` | extracted | 0.0 |
| Unrelated_Trade_Credit_FY | `unrelated_trade_credit_liab_fy` | extracted | 0.0 |
| Unrelated_Loans_PY | `unrelated_loans_liab_py` | extracted | 0.0 |
| Unrelated_Loans_FY | `unrelated_loans_liab_fy` | extracted | 0.0 |
| Unrelated_Deposits_PY | `unrelated_deposits_liab_py` | extracted | 0.0 |
| Unrelated_Deposits_FY | `unrelated_deposits_liab_fy` | extracted | 0.0 |
| Unrelated_Other_Payables_PY | `unrelated_other_payables_liab_py` | extracted | 0.0 |
| Unrelated_Other_Payables_FY | `unrelated_other_payables_liab_fy` | extracted | 0.0 |
| Unrelated_Total_PY | `sum_cells('Section III', ['D70', 'D71', 'D72', 'D73'])` | calculated |  |
| Unrelated_Total_FY | `sum_cells('Section III', ['E70', 'E71', 'E72', 'E73'])` | calculated |  |
| FDI2_Name | `fdi_investor_2_name` | extracted |  |
| FDI2_Country | `fdi_investor_2_country` | extracted |  |
| FDI2_Equity_Percent_PY | `fdi_investor_2_equity_percent_py` | extracted | 0 |
| FDI2_Equity_Percent_FY | `fdi_investor_2_equity_percent_fy` | extracted | 0 |
| FDI2_Equity_Capital_PY | `calculate_fdi_equity('fdi_investor_2_equity_percent_py', 'Net_Worth_PY')` | calculated |  |
| FDI2_Equity_Capital_FY | `calculate_fdi_equity('fdi_investor_2_equity_percent_fy', 'Net_Worth_FY')` | calculated |  |
| FDI2_Liabilities_PY | `calculate_fdi_equity('fdi_investor_2_equity_percent_py', 'Net_Worth_PY')` | calculated |  |
| FDI2_Liabilities_FY | `calculate_fdi_equity('fdi_investor_2_equity_percent_fy', 'Net_Worth_FY')` | calculated |  |
| FDI2_Claims_PY | `fdi_investor_2_claims_py` | extracted | 0.0 |
| FDI2_Claims_FY | `fdi_investor_2_claims_fy` | extracted | 0.0 |
| FDI2_Other_Capital_PY | `subtract_cells('Section III', 'D36', 'D37')` | calculated |  |
| FDI2_Other_Capital_FY | `subtract_cells('Section III', 'E36', 'E37')` | calculated |  |
| FDI2_Other_Liabilities_PY | `fdi_investor_2_other_liabilities_py` | extracted | 0.0 |
| FDI2_Other_Liabilities_FY | `fdi_investor_2_other_liabilities_fy` | extracted | 0.0 |
| FDI2_Other_Claims_PY | `fdi_investor_2_other_claims_py` | extracted | 0.0 |
| FDI2_Other_Claims_FY | `fdi_investor_2_other_claims_fy` | extracted | 0.0 |
| FDI2_Disinvestment_PY | `fdi_investor_2_disinvestment_py` | extracted | 0.0 |
| FDI2_Disinvestment_FY | `fdi_investor_2_disinvestment_fy` | extracted | 0.0 |
| FDI3_Name | `fdi_investor_2_country` | extracted |  |
| FDI3_Country | `fdi_investor_2_equity_percent_py` | extracted | 0 |
| FDI3_Equity_Percent_PY | `fdi_investor_2_equity_percent_fy` | extracted | 0 |
| FDI3_Equity_Percent_FY | `fdi_investor_2_unused` | extracted | 0 |
| FDI3_Equity_Capital_PY | `` | calculated |  |
| FDI3_Equity_Capital_FY | `` | calculated |  |
| FDI3_Liabilities_PY | `` | calculated |  |
| FDI3_Liabilities_FY | `` | calculated |  |
| FDI3_Claims_PY | `fdi_investor_2_claims_py` | extracted | 0.0 |
| FDI3_Claims_FY | `fdi_investor_2_claims_fy` | extracted | 0.0 |
| FDI3_Other_Capital_PY | `` | calculated |  |
| FDI3_Other_Capital_FY | `` | calculated |  |
| FDI3_Other_Liabilities_PY | `fdi_investor_2_other_liabilities_py` | extracted | 0.0 |
| FDI3_Other_Liabilities_FY | `fdi_investor_2_other_liabilities_fy` | extracted | 0.0 |
| FDI3_Other_Claims_PY | `fdi_investor_2_other_claims_py` | extracted | 0.0 |
| FDI3_Other_Claims_FY | `fdi_investor_2_other_claims_fy` | extracted | 0.0 |
| FDI3_Disinvestment_PY | `fdi_investor_2_disinvestment_py` | extracted | 0.0 |
| FDI3_Disinvestment_FY | `fdi_investor_2_disinvestment_fy` | extracted | 0.0 |

### Section IV
| Cell | Field / Formula | Type | Default |
| :--- | :--- | :--- | :--- |
| ODI_DIE_Count | `odi_die_count` | extracted | 0 |
| ODI_First_Time_Date | `odi_first_made_date` | extracted | N/A |
| DIE1_Name | `die_1_name` | extracted |  |
| DIE1_Country | `die_1_country` | extracted |  |
| DIE1_Equity_Percent_PY | `die_1_equity_percent_py` | extracted | 0.0 |
| DIE1_Equity_Percent_FY | `die_1_equity_percent_fy` | extracted | 0.0 |
| DIE1_Currency | `die_1_currency` | extracted |  |
| DIE1_Total_Equity_PY | `die_1_total_equity_py` | extracted | 0.0 |
| DIE1_Total_Equity_FY | `die_1_total_equity_fy` | extracted | 0.0 |
| DIE1_Equity_Held_PY | `die_1_equity_held_py` | extracted | 0.0 |
| DIE1_Equity_Held_FY | `die_1_equity_held_fy` | extracted | 0.0 |
| DIE1_Reserves_PY | `die_1_reserves_py` | extracted | 0.0 |
| DIE1_Reserves_FY | `die_1_reserves_fy` | extracted | 0.0 |
| DIE1_PL_Balance_PY | `die_1_pl_balance_py` | extracted | 0.0 |
| DIE1_PL_Balance_FY | `die_1_pl_balance_fy` | extracted | 0.0 |
| DIE1_Net_Worth_PY | `sum_cells('Section IV', ['D26', 'D28'])` | calculated |  |
| DIE1_Net_Worth_FY | `sum_cells('Section IV', ['E26', 'E28'])` | calculated |  |
| DIE1_Exchange_Rate_PY | `die_1_exchange_rate_py` | extracted | 0 |
| DIE1_Exchange_Rate_FY | `die_1_exchange_rate_fy` | extracted | 0 |
| DIE1_Sales_PY | `die_1_sales_py` | extracted | 0.0 |
| DIE1_Sales_FY | `die_1_sales_fy` | extracted | 0.0 |
| DIE1_Exports_PY | `die_1_exports_py` | extracted | 0.0 |
| DIE1_Exports_FY | `die_1_exports_fy` | extracted | 0.0 |
| DIE1_Purchases_PY | `die_1_purchases_py` | extracted | 0.0 |
| DIE1_Purchases_FY | `die_1_purchases_fy` | extracted | 0.0 |
| DIE1_Imports_PY | `die_1_imports_py` | extracted | 0.0 |
| DIE1_Imports_FY | `die_1_imports_fy` | extracted | 0.0 |
| DIE1_Employees_PY | `die_1_employees_py` | extracted | 0 |
| DIE1_Employees_FY | `die_1_employees_fy` | extracted | 0 |
| DIE1_Equity_Capital_INR_PY | `translate_die_equity('py')` | calculated |  |
| DIE1_Equity_Capital_INR_FY | `translate_die_equity('fy')` | calculated |  |
| DIE1_Liabilities_PY | `die_1_liabilities_py` | extracted | 0.0 |
| DIE1_Liabilities_FY | `die_1_liabilities_fy` | extracted | 0.0 |
| DIE1_Claims_PY | `die_1_claims_py` | extracted | 0.0 |
| DIE1_Claims_FY | `die_1_claims_fy` | extracted | 0.0 |
| DIE1_Other_Capital_PY | `subtract_cells('Section IV', 'D43', 'D44')` | calculated |  |
| DIE1_Other_Capital_FY | `subtract_cells('Section IV', 'E43', 'E44')` | calculated |  |
| DIE1_Other_Liabilities_PY | `die_1_other_liabilities_py` | extracted | 0.0 |
| DIE1_Other_Liabilities_FY | `die_1_other_liabilities_fy` | extracted | 0.0 |
| DIE1_Other_Claims_PY | `die_1_other_claims_py` | extracted | 0.0 |
| DIE1_Other_Claims_FY | `die_1_other_claims_fy` | extracted | 0.0 |
| DIE1_Disinvestment_PY | `die_1_disinvestment_py` | extracted | 0.0 |
| DIE1_Disinvestment_FY | `die_1_disinvestment_fy` | extracted | 0.0 |
| Block2_No_Countries_Abroad | `odi_less_than_10_countries_count` | extracted | 0 |
| Portfolio_Abroad_No_Countries | `portfolio_abroad_countries_count` | extracted | 0 |
| Unrelated_Trade_Credit_Assets_PY | `unrelated_trade_credit_assets_py` | extracted | 0.0 |
| Unrelated_Trade_Credit_Assets_FY | `unrelated_trade_credit_assets_fy` | extracted | 0.0 |
| Unrelated_Loans_Assets_PY | `unrelated_loans_assets_py` | extracted | 0.0 |
| Unrelated_Loans_Assets_FY | `unrelated_loans_assets_fy` | extracted | 0.0 |
| Unrelated_Deposits_Assets_PY | `unrelated_deposits_assets_py` | extracted | 0.0 |
| Unrelated_Deposits_Assets_FY | `unrelated_deposits_assets_fy` | extracted | 0.0 |
| Unrelated_Other_Receivables_PY | `unrelated_other_receivables_assets_py` | extracted | 0.0 |
| Unrelated_Other_Receivables_FY | `unrelated_other_receivables_assets_fy` | extracted | 0.0 |
| Unrelated_Total_Assets_PY | `sum_cells('Section IV', ['D96', 'D97', 'D98', 'D99'])` | calculated |  |
| Unrelated_Total_Assets_FY | `sum_cells('Section IV', ['E96', 'E97', 'E98', 'E99'])` | calculated |  |

