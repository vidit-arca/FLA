import pandas as pd
import re
import os

class AOC4ExcelExtractor:
    def __init__(self):
        # Maps metric names to regex keywords to match in the row headers
        self.numeric_keywords = {
            "turnover": [r"revenue from operations?", r"total turnover", r"sales turnover", r"gross turnover"],
            "prev_turnover": [r"previous year turnover", r"turnover.*previous year"],
            "paid_up_capital": [r"paid.?up capital", r"paid.?up share capital", r"subscribed and paid.?up", r"equity share capital"],
            "net_worth": [r"net worth", r"total equity", r"capital.*reserve.*surplus"],
            "prev_net_worth": [r"previous year net worth", r"net worth.*previous year"],
            "reserves_and_surplus": [r"reserves\s*&\s*surplus", r"reserves and surplus", r"other equity"],
            "borrowings": [r"total borrowing", r"borrowing", r"loan from bank", r"loan from director", r"secured loan", r"unsecured loan"],
            "operating_profit": [r"operating profit", r"profit before interest", r"ebitda"],
            "net_profit_before_tax": [r"profit before tax", r"profit before exceptional items", r"pbt", r"profit.*?before.*?tax"],
            "net_profit_after_tax": [r"profit after tax", r"profit for the period", r"pat", r"profit.*?after.*?tax", r"profit/.*?\(loss\).*?for the year"],
            "total_loans_investments_given": [r"loans and advances given", r"investments made", r"total loans.*given", r"current investment", r"non current investment"],
            "rpt_sale_goods": [r"sale of goods.*related party", r"sale of goods"],
            "rpt_purchase_goods": [r"purchase of goods.*related party", r"purchase or supply of goods"],
            "rpt_sale_property": [r"sale of property.*related party", r"sale of property"],
            "rpt_purchase_property": [r"purchase of property.*related party", r"purchase of property"],
            "rpt_dispose_property": [r"dispose of property", r"disposal of property"],
            "rpt_availing_service": [r"availing of service", r"availing.*service"],
            "rpt_rendering_service": [r"rendering of service", r"rendering.*service"],
            "rpt_lease": [r"lease.*related party", r"^lease$", r"rent"],
            "rpt_monthly_remun": [r"monthly remuneration", r"appointment to any office", r"salary"],
            "rpt_remuneration_underwriting": [r"remuneration for underwriting", r"underwriting.*subscription"],
            "loan_to_directors_assets": [r"loangiven by company to directors", r"loan given by company to director", r"loan to directors"],
            "secured_loan": [r"secured loan", r"secured borrowings"],
            "loan_from_directors": [r"loan from directors", r"loan from shareholders"],
            "advance_from_customers": [r"advance from customers", r"security deposits"],
            "dues_to_msme": [r"dues to msme", r"micro and small enterprises"]
        }
        
        self.boolean_keywords = {
            "is_subsidiary_or_holding": [r"subsidiary or holding", r"is subsidiary"],
            "is_listed": [r"is listed", r"listed company"],
            "is_ind_as": [r"ind as applicable", r"ind as", r"indian accounting standard", r"accounting standard"],
            "has_loans_investments_guarantees": [r"has the company given loan.*guarantee", r"loans.*investments.*guarantees"],
            "has_loans_to_directors": [r"loan to directors", r"has the company given any loan to directors"],
            "body_corporate_investors": [r"body corporate has invested", r"invested in its share capital"],
            "borrowing_defaults": [r"default in repayment", r"borrowing default"],
            "has_bribe": [r"bribe", r"corrupt practices"],
            "has_internal_audit": [r"internal audit applicable", r"internal audit"]
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
            
        if isinstance(val, str):
            val = val.strip()
            if val == "-":
                return 0.0
                
        clean_str = re.sub(r'[^\d.-]', '', str(val))
        try:
            return float(clean_str) if clean_str else None
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
            
    def _process_excel(self, path: str) -> dict:
        """Processes a single Excel workbook and searches targeted sheets for keywords."""
        data = {k: None for k in list(self.numeric_keywords.keys()) + list(self.boolean_keywords.keys())}
        data["has_schedule_iii_format"] = "no"  # Default to no
        xls = pd.ExcelFile(path)
        
        schedule_iii_headers_found = set()
        required_headers = {
            "equity and liabilities", "shareholders' funds", "non-current liabilities",
            "current liabilities", "assets", "non-current assets", "current assets"
        }
        
        target_sheet_keywords = [
            "balance sheet", "p&l","PandL", "profit and loss", "statement of profit",
            "notes", "related party", "rpt", "revenue", "share capital", "financials", "bs"
        ]
        
        # Filter sheets to avoid false positives on summary or irrelevant sheets
        sheets_to_scan = []
        for sheet_name in xls.sheet_names:
            sheet_lower = sheet_name.lower()
            if any(keyword in sheet_lower for keyword in target_sheet_keywords):
                sheets_to_scan.append(sheet_name)
                
        # Fallback: If no sheets matched our target names, scan them all
        if not sheets_to_scan:
            sheets_to_scan = xls.sheet_names
        
        for sheet_name in sheets_to_scan:
            try:
                sheet_lower = sheet_name.lower()
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                
                # Identify Note No column
                note_col_idx = None
                for index, row in df.head(20).iterrows():
                    for c_idx, cell in enumerate(row.values):
                        if isinstance(cell, str) and "note" in cell.lower():
                            note_col_idx = c_idx
                            break
                    if note_col_idx is not None:
                        break

                for index, row in df.iterrows():
                    row_values = row.values
                    
                    for col_idx, cell in enumerate(row_values):
                        if isinstance(cell, str) and not pd.isna(cell):
                            cell_lower = str(cell).lower().strip()
                            
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
                                if index > 5: # Skip header rows to avoid company name
                                    if re.search(r'\b(ltd|private limited|limited|inc)\b', cell_lower):
                                        print(f"    -> Found corporate shareholder keyword in '{sheet_name}' row {index}")
                                        data["has_corporate_shareholders"] = "yes"
                            
                            # Check numeric metrics
                            for metric, patterns in self.numeric_keywords.items():
                                if data[metric] is not None:
                                    continue
                                for pattern in patterns:
                                    if re.search(pattern, cell_lower):
                                        for right_idx in range(col_idx + 1, len(row_values)):
                                            if right_idx == note_col_idx:
                                                continue # Skip the Note No column entirely
                                            val = self._clean_numeric(row_values[right_idx])
                                            if val is not None:
                                                print(f"    -> Found '{metric}' = {val} in sheet '{sheet_name}'")
                                                data[metric] = val
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
            
        return data
