import pandas as pd
import re
import os

# Context triggers: heading keywords that signal entry into a new financial section.
# The key is the context name, value is the regex to detect the heading row.
CONTEXT_TRIGGERS = {
    "long_term_borrowings":  r"long[\s\-]+term borrowings?",
    "short_term_borrowings": r"short[\s\-]+term borrowings?",
    "share_capital":         r"share capital",
    "reserves_surplus":      r"reserves\s*(and|&)\s*surplus|other equity",
    "trade_payables":        r"trade payables?",
    "fixed_assets":          r"property.*plant.*equipment|fixed assets|tangible assets",
    "trade_receivables":     r"trade receivables?",
    "revenue_operations":    r"revenue from operations?",
    "related_party":         r"related party|rpt",
}

# Metrics that should ONLY be extracted when a specific context is active.
# key = metric name, value = list of allowed context names
CONTEXT_METRICS = {
    "secured_loan": ["long_term_borrowings", "short_term_borrowings"],
}

# How many rows a context remains active after the heading row is detected
CONTEXT_TTL = 30

class AOC4ExcelExtractor:
    def __init__(self):
        # Maps metric names to regex keywords to match in the row headers
        self.numeric_keywords = {
            "total_revenue": [r"total revenue", r"total income", r"revenue and other income"],
            "prev_total_revenue": [r"previous year total revenue", r"total revenue.*previous year"],
            "turnover": [r"revenue from operations?", r"total turnover", r"sales turnover", r"gross turnover"],
            "prev_turnover": [r"previous year turnover", r"turnover.*previous year"],
            "authorised_capital": [r"authorised.*capital", r"authorized.*capital", r"authorised share capital", r"authorized share capital"],
            "paid_up_capital": [r"(?<!authorised\s)(?<!authorized\s)share capital", r"paid.?up capital", r"paid.?up share capital", r"subscribed and paid.?up", r"issued,?\s*subscribed", r"equity share capital", r"preference share capital"],
            "prev_paid_up_capital": [r"previous year share capital", r"share capital.*previous year"],
            "reserves_and_surplus": [r"reserves?\s*(?:and|&)\s*surplus", r"other equity"],
            "prev_reserves_and_surplus": [r"previous year reserve", r"reserves?.*previous year"],
            "borrowings": [r"total borrowing", r"total borrowings", r"^borrowing$", r"^borrowings$", r"long.?term borrowing", r"short.?term borrowing", r"loan from bank", r"secured loan", r"unsecured loan"],
            "long_term_borrowings": [r"long.?term borrowing", r"long.?term borrowings"],
            "short_term_borrowings": [r"short.?term borrowing", r"short.?term borrowings"],
            "operating_profit": [r"operating profit", r"profit before interest", r"ebitda"],
            "net_profit_before_tax": [r"profit before tax", r"profit before exceptional items", r"pbt", r"profit.*?before.*?tax", r"profit/\s*\(loss\)\s*before\s*tax"],
            "net_profit_after_tax": [r"profit after tax", r"profit for the period", r"\bpat\b", r"profit.*?after.*?tax", r"profit/\s*\(loss\)\s*for the year"],
            "loan_given_by_company": [r"loans given by company", r"loan given by company", r"loans to related parties", r"inter company loan", r"inter corporate deposit.*given", r"icd given"],
            "investments_made": [r"investments made by company", r"investment made by company", r"non.current investments", r"non current investments", r"current investments", r"investment in subsidiaries", r"investment in associates", r"investments"],
            "total_loans_investments_given": [r"total loans.*given", r"loans and advances given"],
            "corporate_guarantees": [r"corporate guarantees? given", r"guarantees? given by company", r"guarantees? given", r"guarantees"],
            "rpt_sale_goods": [r"sale of goods.*related party", r"sale of goods", r"sale of materials?", r"supply of goods", r"sales to related part(?:y|ies)", r"sale of products?"],
            "rpt_purchase_goods": [r"purchase of goods.*related party", r"purchase of goods", r"purchase of materials?", r"purchase or supply of goods", r"supply of materials?", r"purchases from related part(?:y|ies)", r"purchase of raw materials?"],
            "rpt_sale_property": [r"sale of property.*related party", r"sale of property", r"sale of fixed assets?", r"sale of immovable property", r"sale of assets?", r"sale of land", r"sale of building"],
            "rpt_purchase_property": [r"purchase of property.*related party", r"purchase of property", r"purchase of fixed assets?", r"purchase of immovable property", r"purchase of assets?", r"purchase of land", r"purchase of building"],
            "rpt_dispose_property": [r"dispos(?:al|e) of property", r"transfer of property", r"dispos(?:al|e) of assets?", r"dispos(?:al|e) of fixed assets?", r"transfer of assets?"],
            "rpt_availing_service": [r"availing of services?", r"services? availed", r"service charges paid", r"charges for availing services?", r"charges paid for services?", r"receiving of services?", r"receiving services?", r"availing.*service"],
            "rpt_rendering_service": [r"rendering of services?", r"services? rendered", r"service charges received", r"charges for rendering services?", r"charges received for services?", r"providing of services?", r"providing services?", r"rendering.*service"],
            "rpt_lease": [r"lease.*related party", r"^lease$", r"\brent\b", r"rental", r"lease rent", r"lease payments", r"premises rent", r"office rent"],
            "rpt_monthly_remun": [r"remuneration paid to directors", r"directors remuneration", r"director remuneration", r"remuneration to directors", r"managerial remuneration", r"remuneration.*director", r"monthly remuneration", r"annual remuneration", r"appointment to any office", r"salary"],
            "rpt_monthly_remun_2": [r"remuneration.*director.*2", r"second director.*remuneration", r"wtd.*remuneration", r"salary.*wtd"],
            "rpt_remuneration_underwriting": [r"remuneration for underwriting", r"underwriting commission", r"underwriting remuneration", r"underwriting.*subscription", r"underwriting of securities"],
            "loan_to_directors_assets": [r"loans given by company to directors", r"loan given by company to directors", r"loangiven by company to directors", r"loan given by company to director", r"loan to directors"],
            "secured_loan": [r"^secured$", r"\bsecured\b", r"\bsecured loan", r"\bsecured borrowings", r"term loan taken during the year", r"^term loans?$"],
            "loan_from_directors": [r"loan from directors", r"loan from shareholders", r"unsecured loan from director", r"unsecured loan taken"],
            "advance_from_customers": [r"advance from customers", r"security deposits"],
            "dues_to_msme": [r"dues to msme", r"micro and small enterprises", r"dues to micro"],
            "export_sales": [r"export sales", r"export turnover", r"revenue from export", r"fob value of exports"],
            "sitting_fees": [r"sitting fee", r"directors sitting fee", r"director sitting fee", r"sitting fees to directors"]
        }
        
        self.boolean_keywords = {
            "is_listed": [r"is listed", r"listed company"],
            "is_ind_as": [r"ind as applicable", r"ind as", r"indian accounting standard", r"accounting standard"],
            "has_loans_investments_guarantees": [r"has the company given loan.*guarantee", r"loans.*investments.*guarantees"],
            "has_loans_to_directors": [r"loan to directors", r"has the company given any loan to directors"],
            "body_corporate_investors": [r"body corporate has invested", r"invested in its share capital"],
            "borrowing_defaults": [r"default in repayment", r"borrowing default"],
            "has_bribe": [r"bribe", r"corrupt practices"],
            "has_internal_audit": [r"internal audit applicable", r"internal audit"],
            "has_corporate_shareholders": [r"body corporate|corporate shareholder|invested in share capital"]
        }
        
    def extract_from_docs(self, docs: dict) -> dict:
        """
        Takes the docs dictionary from the router and scans any Excel files
        to extract the financial metrics.
        """
        extracted = {}
        
        # Initialize defaults
        extracted["company_type"] = "private limited company"
        extracted["has_corporate_shareholders"] = None
        
        for k in self.numeric_keywords.keys():
            extracted[k] = None
        for k in self.boolean_keywords.keys():
            extracted[k] = None

        print("[*] AOC 4 Excel Extractor: Looking for financial excel files...")
        
        for key, path in docs.items():
            if path and os.path.exists(path) and (path.lower().endswith('.xlsx') or path.lower().endswith('.xls')):
                print(f"[*] AOC 4 Excel Extractor: Parsing {os.path.basename(path)}")
                try:
                    file_data = self._process_excel(path)
                    # Merge data (keep the first non-None found across multiple files/sheets)
                    for k, v in file_data.items():
                        if extracted.get(k) is None and v is not None:
                            extracted[k] = v
                except Exception as e:
                    print(f"[!] AOC 4 Excel Extractor Error parsing {path}: {e}")
                    
        return extracted
        
    def _clean_numeric(self, val):
        """Removes non-numeric characters and converts to float."""
        if pd.isna(val) or val is None or str(val).strip() == "":
            return None
            
        is_negative = False
        if isinstance(val, str):
            val = val.strip()
            if val == "-":
                return 0.0
            if val.startswith("(") and val.endswith(")"):
                is_negative = True
                
            # Guard against extracting numbers from descriptive sentences (e.g. "Within limits (Limit available upto 12.19 crores)")
            alpha_count = sum(c.isalpha() for c in val)
            if alpha_count > 15:
                return None
                
        clean_str = re.sub(r'[^\d.-]', '', str(val))
        try:
            parsed = float(clean_str) if clean_str else None
            if parsed is not None and is_negative:
                parsed = -parsed
            return parsed
        except ValueError:
            return None
            
    def _clean_boolean(self, val):
        """Looks for common affirmative or negative text."""
        if pd.isna(val) or val is None:
            return None
        val_str = str(val).strip().lower()
        if val_str in ['yes', 'y', 'true', '1']:
            return "yes"
        if val_str in ['no', 'n', 'false', '0']:
            return "no"
        if val_str in ['na', 'n/a', 'not applicable']:
            return "not applicable"
        return None
        
    def detect_financials_scale(self, full_text: str) -> float:
        """Detects if the financial numbers are in Thousands, Lakhs, etc., and returns a multiplier."""
        if not full_text:
            return 1.0
        text_lower = full_text.lower()

        # Check Balance Sheet / P&L header region first for exact unit
        bs_pl_match = re.search(r'(?:balance\s+sheet|statement\s+of\s+profit).*?(?:as\s+at|for\s+the\s+year|₹\s*in|\(in\s+).*?\n', text_lower, re.DOTALL)
        if bs_pl_match:
            header_snippet = bs_pl_match.group(0)
            if re.search(r'in\s+rupees?|amount\s*in\s*₹|in\s*₹\s*rupees?|amount\s*in\s*rs\.?|in\s*rs\.?|\(in\s*rs\.?\)|amount\s*in\s*inr', header_snippet):
                return 1.0
            if re.search(r'in\s+hundreds?', header_snippet):
                return 100.0
            if re.search(r'in\s+thousands?', header_snippet):
                return 1000.0
            if re.search(r'in\s+lakhs?', header_snippet):
                return 100000.0
            if re.search(r'in\s+crores?', header_snippet):
                return 10000000.0

        # General text checks:
        # 1. Crores
        if re.search(r'(?i)(in crores?|amount(s)? (are )?in crores?|in crores? (of )?indian rupees|\(in crores?\))', text_lower):
            return 10000000.0

        # 2. Lakhs
        if re.search(r'(?i)(in lakhs?|amount(s)? (are )?in lakhs?|in lakhs? (of )?indian rupees|\(in lakhs?\))', text_lower):
            return 100000.0

        # 3. Millions
        if re.search(r'(?i)(in millions?|amount(s)? (are )?in millions?|in millions? (of )?indian rupees|\(in millions?\))', text_lower):
            return 1000000.0

        # 4. Hundreds
        if re.search(r'(?i)(in hundreds?|amounts? (are )?in (?:indian )?rupees hundreds?|in (?:indian )?rupees hundreds?|amounts? (are )?in hundreds?|in hundreds? (of )?indian rupees|\(in hundreds?\))', text_lower):
            return 100.0

        # 5. Actuals — explicit "amount in Rs" or "amount in INR" signals raw rupees, return early
        if re.search(r'(?i)(amount\s*in\s*rs\.?|amount\s*in\s*inr|in\s*rs\.?\s*$|\(in\s*rs\.?\)|amount\s*in\s*rupees?)', text_lower):
            return 1.0

        # 6. Thousands (only if not explicit rupees elsewhere in BS/PL)
        if re.search(r'(?i)(amount(s)? (are )?in thousands?|in thousands? (of )?indian rupees|\(in thousands?\))', text_lower):
            if not re.search(r'(?i)(in rupees?|amount in ₹|₹ in rupees)', text_lower):
                return 1000.0

        return 1.0 # Default fallback (Actuals)

            
    def _process_excel(self, path: str) -> dict:
        """Processes a single Excel workbook and searches targeted sheets for keywords."""
        data = {k: None for k in list(self.numeric_keywords.keys()) + list(self.boolean_keywords.keys())}
        best_matches = {k: {"value": None, "priority": 999} for k in self.numeric_keywords.keys()}
        data["has_schedule_iii_format"] = "no"  # Default to no
        xls = pd.ExcelFile(path)
        
        schedule_iii_headers_found = set()
        required_headers = {
            "equity and liabilities", "shareholders' funds", "non-current liabilities",
            "current liabilities", "assets", "non-current assets", "current assets"
        }
        
        # Explicitly exclude non-financial checklist / questionnaire / administrative sheets
        excluded_sheet_keywords = [
            "validation", "caro", "mgt", "meeting", "bm control", "vpd", "index of charges", 
            "din", "view signatory", "signatory", "185", "188", "adt", "dir", "common error", 
            "format sheet", "for rbca", "list of forms", "control sheet", "checklist"
        ]
        
        # Scan ALL sheets in the workbook — skip only explicit admin/checklist sheets.
        # This ensures sheets with non-standard names (e.g. "Financial Statements",
        # "Sub Schedule BS") are never silently missed.
        sheets_to_scan = []
        for sheet_name in xls.sheet_names:
            sheet_lower = sheet_name.lower().strip()
            if any(ex in sheet_lower for ex in excluded_sheet_keywords):
                print(f"[~] Skipping admin/checklist sheet: '{sheet_name}'")
                continue
            sheets_to_scan.append(sheet_name)
        print(f"[*] Sheets to scan ({len(sheets_to_scan)}): {sheets_to_scan}")
        
        # Scan Master Sheet / Basic Details in company input workbook
        for sheet_name in xls.sheet_names:
            s_low = sheet_name.lower()
            if any(kw in s_low for kw in ["master", "basic details", "company info"]):
                try:
                    df_master = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                    for _, m_row in df_master.iterrows():
                        row_vals = [str(v).strip() for v in m_row.values if pd.notna(v)]
                        row_str = " ".join(row_vals).lower()
                        
                        if "cin" in row_str:
                            for cell in row_vals:
                                cin_m = re.search(r'\b([LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b', cell, re.I)
                                if cin_m:
                                    data["cin_number"] = cin_m.group(1).upper()
                                    data["is_listed"] = "yes" if data["cin_number"].startswith("L") else "no"
                                    print(f"[*] Excel Master Sheet: Found CIN = {data['cin_number']}")
                                    break
                                    
                        if "company name" in row_str and len(row_vals) >= 2:
                            data["company_name"] = row_vals[-1]
                            print(f"[*] Excel Master Sheet: Found Company Name = {data['company_name']}")
                            
                        if "incorporation" in row_str and len(row_vals) >= 2:
                            data["date_of_incorporation"] = row_vals[-1]
                            print(f"[*] Excel Master Sheet: Found Date of Inc = {data['date_of_incorporation']}")
                except Exception as e:
                    print(f"[!] Error parsing Master Sheet in Excel: {e}")

        full_text_blocks = []
        for sheet_name in sheets_to_scan:
            try:
                sheet_lower = sheet_name.lower()
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                full_text_blocks.append(" ".join(df.astype(str).values.flatten()))
                
                # Identify Note No column
                note_col_idx = None
                for index, row in df.head(20).iterrows():
                    for c_idx, cell in enumerate(row.values):
                        if isinstance(cell, str) and "note" in cell.lower():
                            note_col_idx = c_idx
                            break
                    if note_col_idx is not None:
                        break

                # Helper: detect "real" financial numbers vs note reference integers
                def _is_real_number(c):
                    if not isinstance(c, (int, float)):
                        return False
                    try:
                        if pd.isna(c):
                            return False
                    except (TypeError, ValueError):
                        pass
                    # Exclude small integers (1-50): likely note reference numbers
                    if 1 <= abs(c) <= 50 and float(c) == int(c):
                        return False
                    return True

                # --- Row Context Tracker state ---
                current_context = None
                context_ttl_remaining = 0

                for index, row in df.iterrows():
                    row_values = row.values

                    # --- Update context tracker ---
                    # A heading row has text cell(s) and NO "real" numeric values.
                    # Small integers 1-50 are likely Note reference numbers — exclude them.
                    row_numeric_vals = [c for c in row_values if _is_real_number(c)]
                    row_text_vals = [str(c).strip() for c in row_values if isinstance(c, str) and str(c).strip()]
                    is_heading_row = bool(row_text_vals) and not row_numeric_vals

                    if row_text_vals:
                        combined_row_text = " ".join(row_text_vals).lower()
                        context_matched = False
                        for ctx_name, ctx_pattern in CONTEXT_TRIGGERS.items():
                            if re.search(ctx_pattern, combined_row_text):
                                current_context = ctx_name
                                context_ttl_remaining = CONTEXT_TTL
                                context_matched = True
                                break
                        # Only reset TTL decay for rows that don't match any trigger
                        if not context_matched and current_context is not None:
                            context_ttl_remaining -= 1
                            if context_ttl_remaining <= 0:
                                current_context = None
                    elif current_context is not None:
                        # Blank row — counts towards expiry
                        context_ttl_remaining -= 1
                        if context_ttl_remaining <= 0:
                            current_context = None

                    for col_idx, cell in enumerate(row_values):
                        # Normalize: handle list cells (merged cells from openpyxl)
                        if isinstance(cell, list):
                            cell = " ".join(str(v) for v in cell if v is not None)
                        if isinstance(cell, str) and not pd.isna(cell):
                            # Strip leading dash/bullet markers (e.g. "- Total outstanding dues...")
                            cell_lower = re.sub(r'^[-\u2013\u2022\*\s]+', '', str(cell).lower().strip())
                            
                            # Check for Schedule III structural headers
                            if "balance sheet" in sheet_lower:
                                for req in required_headers:
                                    req_no_punct = req.replace("'", "")
                                    if req in cell_lower or req_no_punct in cell_lower:
                                        schedule_iii_headers_found.add(req)
                                        
                            # Check for corporate shareholders in share capital sheets
                            if "share capital" in sheet_lower or "shareholder" in sheet_lower or " sc" in sheet_lower or sheet_lower.endswith("sc"):
                                if data["has_corporate_shareholders"] is None:
                                    data["has_corporate_shareholders"] = "no"
                                if index > 1: # Skip header row
                                    if re.search(r'\b(ltd|private limited|limited|inc|pte|llp|body corporate|fund)\b', cell_lower):
                                        print(f"    -> Found corporate shareholder keyword in '{sheet_name}' row {index}")
                                        data["has_corporate_shareholders"] = "yes"
                            
                            # Check numeric metrics
                            for metric, patterns in self.numeric_keywords.items():
                                for p_idx, pattern in enumerate(patterns):
                                    if p_idx >= best_matches[metric]["priority"]:
                                        continue # We already have a better or equal priority match
                                        
                                    # If it's an RPT or Remuneration metric, ensure we are in a likely RPT/Notes sheet
                                    metric_lower = metric.lower()
                                    if metric_lower.startswith("rpt_") or "remun" in metric_lower or "director" in metric_lower or "wtd" in metric_lower or "related" in metric_lower:
                                        if not any(k in sheet_lower for k in ["rpt", "related party", "related party transcation", "related party transaction", "note", "nt ", "27"]):
                                            continue

                                    # Context-gated metrics: only extract if we are in an allowed context
                                    if metric in CONTEXT_METRICS:
                                        allowed_contexts = CONTEXT_METRICS[metric]
                                        if current_context not in allowed_contexts:
                                            continue

                                    if re.search(pattern, cell_lower):
                                        target_row_values = row_values
                                        
                                        # Advanced heuristic: if the keyword is generic like 'professional charges'
                                        # and we are looking for remuneration, look ahead up to 3 rows for an individual's name
                                        if metric == "rpt_monthly_remun" and "professional" in pattern:
                                            for lookahead in range(1, 4):
                                                if index + lookahead < len(df):
                                                    next_row = df.iloc[index + lookahead].values
                                                    next_row_str = " ".join([str(c).lower() for c in next_row if pd.notna(c)])
                                                    if re.search(r'\b(mr\.|ms\.|mrs\.|shri|dr\.)', next_row_str):
                                                        target_row_values = next_row
                                                        break
                                        
                                        row_nums = []
                                        for right_idx in range(col_idx + 1, len(target_row_values)):
                                            if right_idx == note_col_idx:
                                                continue # Skip the Note No column entirely
                                            val = self._clean_numeric(target_row_values[right_idx])
                                            if val is not None:
                                                # Allow 0 as valid (means nil). Only skip small positive
                                                # non-zero integers that are likely note references (e.g. 1, 2, 13)
                                                if val != 0 and 1 <= val < 50 and float(val).is_integer():
                                                    has_larger_next = False
                                                    for nxt in range(col_idx + 1, len(row_values)):
                                                        if nxt == right_idx:
                                                            continue
                                                        nxt_val = self._clean_numeric(row_values[nxt])
                                                        if nxt_val is not None and nxt_val > 50:
                                                            has_larger_next = True
                                                            break
                                                    if not has_larger_next:
                                                        continue
                                                row_nums.append(val)
                                                
                                        if row_nums:
                                            cy_val = row_nums[0]
                                            print(f"    -> Found '{metric}' = {cy_val} in sheet '{sheet_name}' (Priority {p_idx}: {pattern})")
                                            best_matches[metric]["value"] = cy_val
                                            best_matches[metric]["priority"] = p_idx
                                            data[metric] = cy_val # Keep data[metric] populated for fallback logic
                                            
                                            # If a second number exists in comparative column, record as previous year value
                                            if len(row_nums) > 1:
                                                prev_key = f"prev_{metric}"
                                                if prev_key in self.numeric_keywords and data.get(prev_key) is None:
                                                    py_val = row_nums[1]
                                                    data[prev_key] = py_val
                                                    if prev_key in best_matches:
                                                        best_matches[prev_key]["value"] = py_val
                                                        best_matches[prev_key]["priority"] = p_idx
                                                    print(f"    -> Found '{prev_key}' = {py_val} in sheet '{sheet_name}' (from comparative col)")
                                            break
                                        break
                                        
                            # Check boolean metrics
                            for metric, patterns in self.boolean_keywords.items():
                                if data[metric] is not None:
                                    continue
                                for pattern in patterns:
                                    if re.search(pattern, cell_lower):
                                        for right_idx in range(col_idx + 1, len(row_values)):
                                            val = self._clean_boolean(row_values[right_idx])
                                            if val is not None:
                                                print(f"    -> Found '{metric}' = {val} in sheet '{sheet_name}'")
                                                data[metric] = val
                                                break
                                        break
            except Exception as e:
                print(f"Error processing sheet {sheet_name}: {e}")
                
        # Determine Schedule III format
        if len(schedule_iii_headers_found) >= len(required_headers):
            data["has_schedule_iii_format"] = "yes"
            
        # Specific rule for Borrowings summation
        # If we didn't find "Total Borrowings" (Priorities 0-3), but we found both Long and Short Term, sum them
        if best_matches["borrowings"]["priority"] > 3:
            lt = data.get("long_term_borrowings")
            st = data.get("short_term_borrowings")
            if lt is not None and st is not None:
                print(f"    -> Summing Long Term ({lt}) and Short Term ({st}) for Total Borrowings")
                data["borrowings"] = lt + st
                
        full_text = " ".join(full_text_blocks)
        data["is_subsidiary_or_holding"] = self._evaluate_holding_status(full_text)
        data["is_holding_company"] = self._evaluate_is_holding_company(full_text)
        
        # Apply Unit Scale Multiplier
        scale = self.detect_financials_scale(full_text)
        if scale != 1.0:
            print(f"    -> Detected unit scale multiplier of {scale} (applying to all extracted numeric values)")
            for k in self.numeric_keywords.keys():
                if data[k] is not None and isinstance(data[k], (int, float)):
                    data[k] = data[k] * scale
            
        return data

    def _evaluate_holding_status(self, full_text: str) -> str:
        text = full_text.lower()
        text = re.sub(r'\s+', ' ', text)
        
        # Step 2: High Confidence Check
        holding_phrases = [
            "holding company", "holding company:", "parent company:", "ultimate holding company",
            "immediate holding company", "subsidiaries:", "list of subsidiaries"
        ]
        sub_phrases = [
            "subsidiary company", "is a subsidiary", "the company is a subsidiary of",
            "the company is a wholly owned subsidiary"
        ]
        
        # Check holding first
        for phrase in holding_phrases:
            if phrase in text:
                print(f"    -> Holding/Subsidiary check: High confidence match on '{phrase}' (Holding)")
                return "holding"
        
        # Then check subsidiary
        for phrase in sub_phrases:
            if phrase in text:
                print(f"    -> Holding/Subsidiary check: High confidence match on '{phrase}' (Subsidiary)")
                return "subsidiary"
                
        # Step 3: Ownership Validation Check (>50%)
        ownership_matches = re.findall(r'(?:ownership|holding|subsidiary|investment).{0,50}?(\d{2,3}(?:\.\d+)?)\s*%', text)
        for match in ownership_matches:
            try:
                if float(match) > 50.0 and float(match) <= 100.0:
                    print(f"    -> Holding/Subsidiary check: Ownership > 50% match ({match}%)")
                    return "holding"
            except ValueError:
                pass
                
        # Step 4: Medium Confidence Accumulation
        score = 0
        med_conf_phrases = [
            "investment in subsidiaries", "investment in associates",
            "consolidated financial statements comprise",
            "consolidated financial statements", "schedule of subsidiaries"
        ]
        for phrase in med_conf_phrases:
            if phrase in text:
                score += 20
                
        print(f"    -> Holding/Subsidiary check: Medium confidence score = {score}")
        if score >= 100:
            return "holding"
            
        return "no"

    def _evaluate_is_holding_company(self, full_text: str) -> str:
        text = full_text.lower()
        text = re.sub(r'\s+', ' ', text)
        
        # High Confidence Check for Holding
        high_conf_phrases = [
            "subsidiaries:", "list of subsidiaries", 
            "investment in subsidiaries", "schedule of subsidiaries",
            "consolidated financial statements comprise",
            "consolidated financial statements"
        ]
        for phrase in high_conf_phrases:
            if phrase in text:
                print(f"    -> Is Holding Company check: High confidence match on '{phrase}'")
                return "yes"
                
        return "no"

    def _detect_financials_scale(self, full_text: str) -> str:
        """Detects if the financial numbers are in Crores, Lakhs, Thousands, or Actuals."""
        if not full_text:
            return "Actuals"
        text_lower = full_text.lower()
        
        if re.search(r'(?i)(amount.*?in crores?|in crores? indian rupees|\(in crores?\))', text_lower):
            return "Crores"
        if re.search(r'(?i)(amount.*?in lakhs?|in lakhs? indian rupees|\(in lakhs?\))', text_lower):
            return "Lakhs"
        if re.search(r'(?i)(amount.*?in thousands?|in thousands? indian rupees|\(in thousands?\)|in [\'’]?000)', text_lower):
            return "Thousands"
        if re.search(r'(?i)(amount.*?in hundreds?|in hundreds? indian rupees|\(in hundreds?\))', text_lower):
            return "Hundreds"
        return "Actuals"
