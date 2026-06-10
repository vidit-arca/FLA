import pandas as pd
import numpy as np

class ExcelExtractor:
    def __init__(self, config=None):
        self.config = config or {}

    def extract(self, excel_path, role):
        """Extract data based on the role."""
        if role == "shareholders_fdi":
            return self.extract_fdi_data(excel_path)
        elif role == "odi_details":
            return self.extract_odi_data(excel_path)
        return {}

    def extract_fdi_data(self, excel_path):
        """Extract Foreign Direct Investment (FDI) data from Shareholders list."""
        try:
            # Read without headers to find the actual header row
            raw_df = pd.read_excel(excel_path, header=None)
            
            header_idx = 0
            max_matches = 0
            
            # Search first 20 rows for header keywords
            for idx, row in raw_df.head(20).iterrows():
                matches = 0
                row_str = " ".join([str(x).lower() for x in row if pd.notna(x)])
                if "name" in row_str and "shareholder" in row_str: matches += 1
                if "nationality" in row_str or "country" in row_str: matches += 1
                if "number of security" in row_str or "number of shares" in row_str or "no. of shares" in row_str or "number of securit" in row_str: matches += 1
                
                if matches > max_matches:
                    max_matches = matches
                    header_idx = idx
            
            if max_matches > 0:
                df = pd.read_excel(excel_path, skiprows=header_idx)
            else:
                df = pd.read_excel(excel_path)
            
            # Expected columns check
            country_col = None
            name_col = None
            securities_col = None
            
            for col in df.columns:
                lower_col = str(col).lower().strip()
                # Normalize whitespace (replace newlines and multiple spaces with a single space)
                lower_col = ' '.join(lower_col.split())
                
                if "nationality" in lower_col or "country" in lower_col:
                    country_col = col
                if "name" in lower_col and "shareholder" in lower_col:
                    name_col = col
                # Prefer exact match or starting with 'number of' to avoid matching 'amount' column
                if "number of security" in lower_col or "number of shares" in lower_col or "no. of shares" in lower_col or "number of securit" in lower_col:
                    securities_col = col

            # Fallback if securities_col not found
            if not securities_col:
                for col in df.columns:
                    lower_col = ' '.join(str(col).lower().strip().split())
                    if "amount of securities" in lower_col or "amount" in lower_col:
                        securities_col = col

            if not (country_col and name_col and securities_col):
                print("[!] ExcelExtractor: Missing required columns in shareholders file.")
                return {}

            # Filter out Debentures if Type/Class of security column exists (keep only Equity and Preference)
            security_type_col = None
            for col in df.columns:
                lower_col = ' '.join(str(col).lower().strip().split())
                if "type of security" in lower_col or "class of security" in lower_col:
                    security_type_col = col
                    break
            
            if security_type_col:
                # Use string contains to catch things like "Equity shares" or "Equity\nshares"
                mask = df[security_type_col].astype(str).str.lower().str.replace('\n', ' ').str.contains("equity|preference", na=False, regex=True)
                df = df[mask]

            # Clean securities col
            df[securities_col] = pd.to_numeric(df[securities_col], errors='coerce').fillna(0)
            total_securities = df[securities_col].sum()
            
            if total_securities == 0:
                print("[!] ExcelExtractor: Total securities is 0.")
                return {}

            # Filter for Non-Resident (Foreign) Investors
            # Assume anything not 'India' or 'Indian' or 'IN' is foreign
            indian_terms = ['india', 'indian', 'in']
            foreign_df = df[~df[country_col].astype(str).str.lower().str.strip().isin(indian_terms)]
            
            # Sum foreign shares by Type of Shareholder (COMPANY vs INDIVIDUAL) - do this before grouping/sorting
            sh_type_col = None
            for col in df.columns:
                lower_col = ' '.join(str(col).lower().strip().split())
                if "type of shareholder" in lower_col or "category of shareholder" in lower_col or "type of sharehold" in lower_col:
                    sh_type_col = col
                    break
            
            nr_companies_shares = 0
            nr_individuals_shares = 0
            
            if sh_type_col:
                for _, row in foreign_df.iterrows():
                    val = str(row[sh_type_col]).lower().strip()
                    shares = float(row[securities_col])
                    if "company" in val or "corporate" in val or "body" in val or "firm" in val:
                        nr_companies_shares += shares
                    elif "individual" in val or "person" in val:
                        nr_individuals_shares += shares
                    else:
                        nr_companies_shares += shares
            else:
                for _, row in foreign_df.iterrows():
                    shares = float(row[securities_col])
                    nr_companies_shares += shares

            # Group foreign shareholders by name and country to aggregate different security types (like Equity + Preference)
            # for the same investor!
            foreign_df_copy = foreign_df.copy()
            foreign_df_copy["clean_name"] = foreign_df_copy[name_col].astype(str).str.lower().str.strip()
            foreign_df_copy["clean_country"] = foreign_df_copy[country_col].astype(str).str.lower().str.strip()
            
            grouped_foreign = foreign_df_copy.groupby(["clean_name", "clean_country"], as_index=False).agg({
                name_col: "first",
                country_col: "first",
                securities_col: "sum"
            })

            # Sort by largest holding
            foreign_df_sorted = grouped_foreign.sort_values(by=securities_col, ascending=False).reset_index(drop=True)

            # Classify grouped shareholders into FDI (>= 10% holding) and DI (< 10% holding)
            fdi_rows = []
            di_rows = []
            
            for i in range(len(foreign_df_sorted)):
                row = foreign_df_sorted.iloc[i]
                percent = (row[securities_col] / total_securities) * 100.0 if total_securities > 0 else 0.0
                if percent >= 10.0:
                    fdi_rows.append((row, percent))
                else:
                    di_rows.append((row, percent))
            
            extracted = {}
            fdi_count = len(foreign_df_sorted)
            extracted["fdi_investors_count"] = fdi_count
            
            # Populate FDI 1 (Block 1) using the largest FDI investor (>= 10%)
            if len(fdi_rows) > 0:
                fdi_rows_sorted = sorted(fdi_rows, key=lambda x: x[1], reverse=True)
                top_fdi_row, top_fdi_pct = fdi_rows_sorted[0]
                extracted["fdi_investor_1_name"] = str(top_fdi_row[name_col]).strip()
                extracted["fdi_investor_1_country"] = str(top_fdi_row[country_col]).strip()
                extracted["fdi_investor_1_equity_percent_py"] = top_fdi_pct
                extracted["fdi_investor_1_equity_percent_fy"] = top_fdi_pct
            else:
                extracted["fdi_investor_1_name"] = ""
                extracted["fdi_investor_1_country"] = ""
                extracted["fdi_investor_1_equity_percent_py"] = 0.0
                extracted["fdi_investor_1_equity_percent_fy"] = 0.0
                
            # Populate DI (Block 2) by consolidating all < 10% investors country-wise
            if len(di_rows) > 0:
                fdi_clean_keys = set()
                for f_row, _ in fdi_rows:
                    fdi_clean_keys.add((str(f_row["clean_name"]).strip(), str(f_row["clean_country"]).strip()))
                
                di_foreign_df = foreign_df_copy.copy()
                di_foreign_df["clean_key"] = list(zip(di_foreign_df["clean_name"].str.strip(), di_foreign_df["clean_country"].str.strip()))
                di_foreign_df = di_foreign_df[~di_foreign_df["clean_key"].isin(fdi_clean_keys)]
                
                if not di_foreign_df.empty:
                    # Group by clean_country
                    grouped_di = di_foreign_df.groupby("clean_country", as_index=False).agg({
                        country_col: "first",
                        securities_col: "sum"
                    })
                    
                    # Sort remaining countries alphabetically
                    grouped_di_sorted = grouped_di.sort_values(by="clean_country").reset_index(drop=True)
                    
                    # Set the count of countries in Block 2 (with <10%)
                    extracted["fdi_less_than_10_countries_count"] = len(grouped_di_sorted)
                    
                    # Consolidate all DI countries and sum their percentages
                    di_countries = []
                    di_countries_data = []
                    total_di_shares = 0
                    import json
                    for idx, row in grouped_di_sorted.iterrows():
                        c_name = str(row[country_col]).strip()
                        c_shares = float(row[securities_col])
                        c_pct = (c_shares / total_securities) * 100.0 if total_securities > 0 else 0.0
                        di_countries.append(c_name)
                        di_countries_data.append({
                            "country": c_name,
                            "percent_py": c_pct,
                            "percent_fy": c_pct
                        })
                        total_di_shares += c_shares
                        
                    di_country_str = ", ".join(di_countries)
                    di_percent = (total_di_shares / total_securities) * 100.0 if total_securities > 0 else 0.0
                    
                    extracted["fdi_investor_2_name"] = di_country_str
                    extracted["fdi_investor_2_country"] = di_country_str
                    extracted["fdi_investor_2_equity_percent_py"] = di_percent
                    extracted["fdi_investor_2_equity_percent_fy"] = di_percent
                    extracted["fdi_investor_2_countries_json"] = json.dumps(di_countries_data)
                else:
                    extracted["fdi_less_than_10_countries_count"] = 0
                    extracted["fdi_investor_2_name"] = ""
                    extracted["fdi_investor_2_country"] = ""
                    extracted["fdi_investor_2_equity_percent_py"] = 0.0
                    extracted["fdi_investor_2_equity_percent_fy"] = 0.0
                    extracted["fdi_investor_2_countries_json"] = "[]"
            else:
                extracted["fdi_less_than_10_countries_count"] = 0
                extracted["fdi_investor_2_name"] = ""
                extracted["fdi_investor_2_country"] = ""
                extracted["fdi_investor_2_equity_percent_py"] = 0.0
                extracted["fdi_investor_2_equity_percent_fy"] = 0.0

            extracted["nr_shares_companies_py"] = nr_companies_shares
            extracted["nr_shares_companies_fy"] = nr_companies_shares
            extracted["nr_shares_individuals_py"] = nr_individuals_shares
            extracted["nr_shares_individuals_fy"] = nr_individuals_shares

            return extracted
            
        except Exception as e:
            print(f"[!] Error in ExcelExtractor (FDI): {e}")
            return {}

    def extract_odi_data(self, excel_path):
        """Extract Overseas Direct Investment data from FLA mapping Excel."""
        extracted = {}
        try:
            import pandas as pd
            import re
            import json
            xl = pd.ExcelFile(excel_path)
            
            # Find the FINANCIALS sheet (or use the first one if name mismatch)
            sheet_name = None
            for name in xl.sheet_names:
                if "FINANCIALS" in name.upper() or "FLA_RETURN" in name.upper():
                    sheet_name = name
                    break
            if not sheet_name:
                sheet_name = xl.sheet_names[0]
                
            df = pd.read_excel(xl, sheet_name=sheet_name)
            
            def safe_float(val):
                if pd.isna(val) or val == "" or str(val).strip() == "": return 0.0
                try:
                    cleaned = re.sub(r'[^\d\.\-\,]', '', str(val))
                    if not cleaned: return 0.0
                    return float(cleaned.replace(',', ''))
                except: return 0.0
                
            def safe_str(val):
                if pd.isna(val): return ""
                return str(val).strip()

            month_first = ""
            year_first = ""
            die_count = 0
            
            block2_countries = []
            block3_countries = []
            in_block2 = False
            in_block3 = False
            current_country = {}
            
            for idx, row in df.iterrows():
                if len(row) < 2: continue
                col_b = safe_str(row.iloc[1]).lower()
                if not col_b: continue
                
                col_c = row.iloc[2] if len(row) > 2 else ""
                col_d = row.iloc[3] if len(row) > 3 else ""
                
                # Dynamic DIE Counting
                if "name of the foreign company" in col_b:
                    if safe_str(col_c):
                        die_count += 1
                        
                # DIE 1 Specifics
                if "die 1" in col_b:
                    if "name of the foreign company" in col_b: extracted["die_1_name"] = safe_str(col_c)
                    elif "country of incorporation" in col_b: extracted["die_1_country"] = safe_str(col_c)
                    elif "% equity holding" in col_b:
                        extracted["die_1_equity_percent_py"] = safe_float(col_c)
                        extracted["die_1_equity_percent_fy"] = safe_float(col_d)
                    elif "currency of die" in col_b: extracted["die_1_currency"] = safe_str(col_c)
                    elif "total equity" in col_b:
                        extracted["die_1_total_equity_py"] = safe_float(col_c)
                        extracted["die_1_total_equity_fy"] = safe_float(col_d)
                    elif "equity held by your company" in col_b:
                        extracted["die_1_equity_held_py"] = safe_float(col_c)
                        extracted["die_1_equity_held_fy"] = safe_float(col_d)
                    elif "reserves & surplus" in col_b:
                        extracted["die_1_reserves_py"] = safe_float(col_c)
                        extracted["die_1_reserves_fy"] = safe_float(col_d)
                    elif "p&l account balance" in col_b:
                        extracted["die_1_pl_balance_py"] = safe_float(col_c)
                        extracted["die_1_pl_balance_fy"] = safe_float(col_d)
                    elif "exchange rate py" in col_b: extracted["die_1_exchange_rate_py"] = safe_float(col_c)
                    elif "exchange rate fy" in col_b: 
                        val = col_c if pd.notna(col_c) and str(col_c).strip() else col_d
                        extracted["die_1_exchange_rate_fy"] = safe_float(val)
                    elif "total sales" in col_b:
                        extracted["die_1_sales_py"] = safe_float(col_c)
                        extracted["die_1_sales_fy"] = safe_float(col_d)
                    elif "of which – exports" in col_b:
                        extracted["die_1_exports_py"] = safe_float(col_c)
                        extracted["die_1_exports_fy"] = safe_float(col_d)
                    elif "total purchases" in col_b:
                        extracted["die_1_purchases_py"] = safe_float(col_c)
                        extracted["die_1_purchases_fy"] = safe_float(col_d)
                    elif "of which – imports" in col_b:
                        extracted["die_1_imports_py"] = safe_float(col_c)
                        extracted["die_1_imports_fy"] = safe_float(col_d)
                    elif "number of employees" in col_b:
                        extracted["die_1_employees_py"] = safe_float(col_c)
                        extracted["die_1_employees_fy"] = safe_float(col_d)
                    elif "liabilities to the die" in col_b:
                        extracted["die_1_liabilities_py"] = safe_float(col_c)
                        extracted["die_1_liabilities_fy"] = safe_float(col_d)
                    elif "claims on die" in col_b and "reverse" in col_b:
                        extracted["die_1_claims_py"] = safe_float(col_c)
                        extracted["die_1_claims_fy"] = safe_float(col_d)
                    elif "other liabilities to die" in col_b:
                        extracted["die_1_other_liabilities_py"] = safe_float(col_c)
                        extracted["die_1_other_liabilities_fy"] = safe_float(col_d)
                    elif "other claims on die" in col_b:
                        extracted["die_1_other_claims_py"] = safe_float(col_c)
                        extracted["die_1_other_claims_fy"] = safe_float(col_d)
                    elif "disinvestment" in col_b:
                        extracted["die_1_disinvestment_py"] = safe_float(col_c)
                        extracted["die_1_disinvestment_fy"] = safe_float(col_d)
                    elif "month of first odi" in col_b: month_first = safe_str(col_c)
                    elif "year of first odi" in col_b: year_first = safe_str(col_c)
                    
                # Block 4 fields
                elif "trade credit to foreign unrelated" in col_b:
                    extracted["unrelated_trade_credit_assets_py"] = safe_float(col_c)
                    extracted["unrelated_trade_credit_assets_fy"] = safe_float(col_d)
                elif "loans given to foreign unrelated" in col_b:
                    extracted["unrelated_loans_assets_py"] = safe_float(col_c)
                    extracted["unrelated_loans_assets_fy"] = safe_float(col_d)
                elif "foreign currency deposits held" in col_b:
                    extracted["unrelated_deposits_assets_py"] = safe_float(col_c)
                    extracted["unrelated_deposits_assets_fy"] = safe_float(col_d)
                elif "other receivables from unrelated" in col_b:
                    extracted["unrelated_other_receivables_assets_py"] = safe_float(col_c)
                    extracted["unrelated_other_receivables_assets_fy"] = safe_float(col_d)
                    
                # Block 2 & 3 State Machine
                if "number of countries where you hold <10%" in col_b:
                    in_block2 = True
                    in_block3 = False
                    # Extract count if given explicitly
                    if safe_str(col_c).isdigit(): extracted["odi_less_than_10_countries_count"] = int(safe_float(col_c))
                elif "portfolio equity % held" in col_b or "money market instruments" in col_b:
                    in_block3 = True
                    in_block2 = False
                elif "trade credit to foreign unrelated" in col_b:
                    in_block2 = False
                    in_block3 = False
                    
                if in_block2:
                    if col_b == "country name":
                        if current_country and "country" in current_country:
                            block2_countries.append(current_country)
                        current_country = {"country": safe_str(col_c)}
                    elif current_country and "equity % py / fy" in col_b:
                        current_country["percent_py"] = safe_float(col_c)
                        current_country["percent_fy"] = safe_float(col_d)
                        
                if in_block3:
                    if "country of foreign enterprise" in col_b:
                        if current_country and "country" in current_country:
                            block3_countries.append(current_country)
                        current_country = {"country": safe_str(col_c)}
                    elif current_country and "portfolio equity % held" in col_b:
                        current_country["percent_py"] = safe_float(col_c)
                        current_country["percent_fy"] = safe_float(col_d)
            
            # Flush last country
            if current_country and "country" in current_country:
                if in_block2: block2_countries.append(current_country)
                if in_block3: block3_countries.append(current_country)

            extracted["odi_die_count"] = die_count
            if month_first or year_first:
                extracted["odi_first_made_date"] = f"{month_first} {year_first}".strip()
            
            # If explicit count wasn't found, fallback to length of array
            if "odi_less_than_10_countries_count" not in extracted:
                extracted["odi_less_than_10_countries_count"] = len(block2_countries)
            
            extracted["portfolio_abroad_countries_count"] = len(block3_countries)
            
            extracted["odi_block2_countries_json"] = json.dumps(block2_countries)
            extracted["odi_block3_countries_json"] = json.dumps(block3_countries)
            
            return extracted
            
        except Exception as e:
            print(f"[!] Error in ExcelExtractor (ODI): {e}")
            return {}
