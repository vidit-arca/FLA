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
            # Check all sheets to find the one with the best header matches
            xl = pd.ExcelFile(excel_path)
            sheet_names = xl.sheet_names
            best_sheet = sheet_names[0]
            best_header_idx = 0
            best_max_matches = 0
            
            for sname in sheet_names:
                try:
                    raw_df = pd.read_excel(excel_path, sheet_name=sname, header=None)
                    for idx, row in raw_df.head(20).iterrows():
                        matches = 0
                        row_str = " ".join([str(x).lower() for x in row if pd.notna(x)])
                        if "name" in row_str and "shareholder" in row_str: matches += 1
                        if "nationality" in row_str or "country" in row_str: matches += 1
                        if "number of security" in row_str or "number of shares" in row_str or "no. of shares" in row_str or "number of securit" in row_str: matches += 1
                        
                        if matches > best_max_matches:
                            best_max_matches = matches
                            best_header_idx = idx
                            best_sheet = sname
                except Exception:
                    continue
            
            if best_max_matches > 0:
                df = pd.read_excel(excel_path, sheet_name=best_sheet, skiprows=best_header_idx)
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
            class_col = None
            for col in df.columns:
                lower_col = ' '.join(str(col).lower().strip().split())
                if "type of security" in lower_col:
                    security_type_col = col
                if "class of security" in lower_col:
                    class_col = col
            
            # Find the Amount column
            amount_col = None
            for col in df.columns:
                lower_col = ' '.join(str(col).lower().strip().split())
                if "total amount of securities held" in lower_col or "amount of securities held" in lower_col:
                    amount_col = col
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

            # Calculate total shares and amounts for Section 1 & 2 (Overall Paid-Up Capital)
            equity_count = 0.0
            equity_amount = 0.0
            part_pref_count = 0.0
            part_pref_amount = 0.0
            non_part_pref_count = 0.0
            non_part_pref_amount = 0.0
            
            # Track distinct security Type Numbers
            equity_types = set()
            part_pref_types = set()
            non_part_pref_types = set()
            
            excel_equity_fv = None
            excel_part_pref_fv = None
            excel_non_part_pref_fv = None

            # Find the nominal value per security column
            fv_col = None
            for col in df.columns:
                lower_col = ' '.join(str(col).lower().strip().split())
                if "nominal value" in lower_col or "face value" in lower_col:
                    fv_col = col
                    break

            def get_type_number(s_type, s_class):
                s_type = str(s_type).lower().strip()
                s_class = str(s_class).lower().replace('–', '-').replace('—', '-').strip()
                s_class = ' '.join(s_class.split())
                
                if "equity" in s_type:
                    if "class a" in s_class:
                        return "Type 2"
                    elif "class b" in s_class:
                        return "Type 3"
                    elif "equity" in s_class or s_class == "":
                        return "Type 1"
                    else:
                        return "Unknown/Other"
                elif "preference" in s_type or "ccps" in s_type or "ccps" in s_class or "preference" in s_class:
                    pref_mappings = {
                        "ccps series a": "Type 1",
                        "compulsorily convertible preference shares - series a": "Type 1",
                        "compulsorily convertible preference shares series a": "Type 1",
                        
                        "ccps series b": "Type 2",
                        "compulsorily convertible preference shares - series b": "Type 2",
                        "compulsorily convertible preference shares series b": "Type 2",
                        
                        "ccps series b1": "Type 3",
                        "compulsorily convertible preference shares - series b1": "Type 3",
                        "compulsorily convertible preference shares series b1": "Type 3",
                        
                        "ccps series b2": "Type 4",
                        "compulsorily convertible preference shares - series b2": "Type 4",
                        "compulsorily convertible preference shares series b2": "Type 4",
                        
                        "ccps series b3": "Type 5",
                        "compulsorily convertible preference shares - series b3": "Type 5",
                        "compulsorily convertible preference shares series b3": "Type 5",
                        
                        "ccps series d1": "Type 6",
                        "compulsorily convertible preference shares - series d1": "Type 6",
                        "compulsorily convertible preference shares series d1": "Type 6",
                        
                        "ccps series d2": "Type 7",
                        "compulsorily convertible preference shares - series d2": "Type 7",
                        "compulsorily convertible preference shares series d2": "Type 7",
                        
                        "ccps series d3": "Type 8",
                        "compulsorily convertible preference shares - series d3": "Type 8",
                        "compulsorily convertible preference shares series d3": "Type 8",
                        
                        "ccps series c1": "Type 9",
                        "compulsorily convertible preference shares - series c1": "Type 9",
                        "compulsorily convertible preference shares series c1": "Type 9",
                        
                        "ccps series c2": "Type 10",
                        "compulsorily convertible preference shares - series c2": "Type 10",
                        "compulsorily convertible preference shares series c2": "Type 10",
                        
                        "ccps series c3": "Type 11",
                        "compulsorily convertible preference shares - series c3": "Type 11",
                        "compulsorily convertible preference shares series c3": "Type 11",
                    }
                    for key, val in pref_mappings.items():
                        if key in s_class or s_class in key:
                            return val
                    return "Unknown/Other"
                return "Unknown/Other"
            
            if amount_col:
                df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce').fillna(0)
                for _, row in df.iterrows():
                    sec_type = str(row[security_type_col]).lower().strip() if security_type_col else ""
                    sec_class = str(row[class_col]).lower().strip() if class_col else ""
                    count = float(row[securities_col])
                    amt = float(row[amount_col])
                    
                    t_num = get_type_number(sec_type, sec_class)
                    fv = float(row[fv_col]) if fv_col and pd.notna(row[fv_col]) else 0.0
                    
                    if "equity" in sec_type or "equity" in sec_class:
                        equity_count += count
                        equity_amount += amt
                        if count > 0:
                            equity_types.add(t_num)
                            if fv > 0 and excel_equity_fv is None:
                                excel_equity_fv = fv
                    elif "preference" in sec_type or "preference" in sec_class:
                        if "non-participating" in sec_class or "non participating" in sec_class or "non-participating" in sec_type:
                            non_part_pref_count += count
                            non_part_pref_amount += amt
                            if count > 0:
                                non_part_pref_types.add(t_num)
                                if fv > 0 and excel_non_part_pref_fv is None:
                                    excel_non_part_pref_fv = fv
                        else:
                            part_pref_count += count
                            part_pref_amount += amt
                            if count > 0:
                                part_pref_types.add(t_num)
                                if fv > 0 and excel_part_pref_fv is None:
                                    excel_part_pref_fv = fv
                            
            extracted = {
                "excel_equity_shares_count": equity_count,
                "excel_equity_amount": equity_amount,
                "excel_part_pref_shares_count": part_pref_count,
                "excel_part_pref_amount": part_pref_amount,
                "excel_non_part_pref_shares_count": non_part_pref_count,
                "excel_non_part_pref_amount": non_part_pref_amount,
                "excel_equity_class_count": len(equity_types) if equity_types else 0,
                "excel_part_pref_class_count": len(part_pref_types) if part_pref_types else 0,
                "excel_non_part_pref_class_count": len(non_part_pref_types) if non_part_pref_types else 0,
                "excel_equity_face_value": excel_equity_fv,
                "excel_part_pref_face_value": excel_part_pref_fv,
                "excel_non_part_pref_face_value": excel_non_part_pref_fv
            }

            # Filter for Non-Resident (Foreign) Investors
            # Assume anything not 'India' or 'Indian' or 'IN' is foreign
            indian_terms = ['india', 'indian', 'in']
            foreign_df = df[~df[country_col].astype(str).str.lower().str.strip().isin(indian_terms)]
            
            sh_type_col = None
            category_col = None
            for col in df.columns:
                lower_col = ' '.join(str(col).lower().strip().split())
                if "type of shareholder" in lower_col or "type of sharehold" in lower_col:
                    sh_type_col = col
                elif "category of shareholder" in lower_col:
                    category_col = col
            
            # Buckets (Counts and Amounts)
            buckets = {
                "individuals": {"count": 0.0, "amount": 0.0},
                "companies": {"count": 0.0, "amount": 0.0},
                "fii": {"count": 0.0, "amount": 0.0},
                "fvci": {"count": 0.0, "amount": 0.0},
                "trusts": {"count": 0.0, "amount": 0.0},
                "pe_funds": {"count": 0.0, "amount": 0.0},
                "pension_funds": {"count": 0.0, "amount": 0.0},
                "swf": {"count": 0.0, "amount": 0.0},
                "partnerships": {"count": 0.0, "amount": 0.0},
                "fin_institutions": {"count": 0.0, "amount": 0.0},
                "nri_pio": {"count": 0.0, "amount": 0.0},
                "non_part_pref": {"count": 0.0, "amount": 0.0}
            }
            
            for _, row in foreign_df.iterrows():
                sec_type = str(row[security_type_col]).lower().strip() if security_type_col else ""
                sec_class = str(row[class_col]).lower().strip() if class_col else ""
                
                count = float(row[securities_col])
                amt = float(row[amount_col]) if amount_col else 0.0
                
                # Check for Non-Participating Preference Share (NR) first
                if "preference" in sec_type or "preference" in sec_class:
                    if "non-participating" in sec_class or "non participating" in sec_class or "non-participating" in sec_type:
                        buckets["non_part_pref"]["count"] += count
                        buckets["non_part_pref"]["amount"] += amt
                        continue # Skip bucket 1-11 assignment if it's Non-Part Preference
                
                # It's Equity or Participating Preference, so categorize into 1-11
                t_val = str(row[sh_type_col]).lower().strip() if sh_type_col else ""
                c_val = str(row[category_col]).lower().strip() if category_col else ""
                n_val = str(row[name_col]).lower().strip() if name_col else ""
                
                combined_desc = f"{t_val} {c_val} {n_val}"
                
                if "nri" in combined_desc or "pio" in combined_desc or "non resident indian" in combined_desc:
                    buckets["nri_pio"]["count"] += count
                    buckets["nri_pio"]["amount"] += amt
                elif "individual" in combined_desc or "person" in combined_desc:
                    buckets["individuals"]["count"] += count
                    buckets["individuals"]["amount"] += amt
                elif "fii" in combined_desc or "foreign institutional investor" in combined_desc:
                    buckets["fii"]["count"] += count
                    buckets["fii"]["amount"] += amt
                elif "fvci" in combined_desc or "venture capital" in combined_desc:
                    buckets["fvci"]["count"] += count
                    buckets["fvci"]["amount"] += amt
                elif "trust" in combined_desc:
                    buckets["trusts"]["count"] += count
                    buckets["trusts"]["amount"] += amt
                elif "private equity" in combined_desc or "pe fund" in combined_desc:
                    buckets["pe_funds"]["count"] += count
                    buckets["pe_funds"]["amount"] += amt
                elif "pension" in combined_desc or "provident" in combined_desc:
                    buckets["pension_funds"]["count"] += count
                    buckets["pension_funds"]["amount"] += amt
                elif "sovereign" in combined_desc or "swf" in combined_desc or "wealth fund" in combined_desc:
                    buckets["swf"]["count"] += count
                    buckets["swf"]["amount"] += amt
                elif "partnership" in combined_desc or "proprietorship" in combined_desc or "firm" in combined_desc:
                    buckets["partnerships"]["count"] += count
                    buckets["partnerships"]["amount"] += amt
                elif "financial institution" in combined_desc or "fi" in combined_desc.split():
                    buckets["fin_institutions"]["count"] += count
                    buckets["fin_institutions"]["amount"] += amt
                elif "company" in combined_desc or "corporate" in combined_desc or "body" in combined_desc or "ltd" in combined_desc or "limited" in combined_desc:
                    buckets["companies"]["count"] += count
                    buckets["companies"]["amount"] += amt
                else:
                    # Fallback default: Foreign Company
                    buckets["companies"]["count"] += count
                    buckets["companies"]["amount"] += amt
                    
            # Export all extracted NR buckets
            for key, data in buckets.items():
                extracted[f"excel_nr_{key}_shares_count"] = data["count"]
                extracted[f"excel_nr_{key}_amount"] = data["amount"]

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
