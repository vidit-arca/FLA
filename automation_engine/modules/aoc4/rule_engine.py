import json
import os
import re
import openpyxl
from automation_engine.modules.aoc4.aoc4_error_checker import AOC4CommonErrorEngine
from automation_engine.modules.aoc4.compliance_engine import PrivateComplianceEngine
from automation_engine.modules.aoc4.rpt_loans_engine import RPTLoansEngine
from automation_engine.modules.aoc4.excel_extractor import AOC4ExcelExtractor

class AOC4RuleEngine:
    def __init__(self, config_path: str):
        self.config_path = config_path
        with open(config_path, "r") as f:
            self.config = json.load(f)
            
        base_dir = os.path.dirname(config_path)
        # Default to the clean Annual Filing common error Output.xlsx template
        self.excel_path = os.path.join(base_dir, "excel", "Annual Filing common error Output.xlsx")
        if not os.path.exists(self.excel_path):
            self.excel_path = os.path.join(base_dir, "excel", "ANNFIL COMMONERROR .xlsx")
            
        self.output_skeletal_path = self.excel_path
        self.checker = AOC4CommonErrorEngine(self.excel_path)
        self.compliance_engine = PrivateComplianceEngine()
        self.rpt_loans_engine = RPTLoansEngine()
        self.excel_extractor = AOC4ExcelExtractor()

    def _normalize_string(self, text):
        if not text:
            return ""
        return re.sub(r'[^a-z0-9]', '', str(text).lower())

    def evaluate_all(self, extracted_data: dict) -> dict:
        print("[*] AOC 4 Rule Engine: Evaluating common errors...")
        print("[*] AOC 4 Rule Engine: Evaluating private compliance...")

        # ── FIX 1: Always pass full_text into financial_data so all engines have it ──
        full_text = extracted_data.get("full_text", "")

        # 1. Run Excel Extractor on the original docs to pull structured financial metrics
        docs = extracted_data.get("docs", {})
        financial_data = self.excel_extractor.extract_from_docs(docs)

        # ── PURE COMPUTATION OF NET WORTH (CY & PY) ──
        # Net Worth must be computed purely as Paid-up Capital + Reserves & Surplus.
        # It must NEVER use text fallback or regex keyword hunting.
        puc = financial_data.get("paid_up_capital") if financial_data.get("paid_up_capital") is not None else extracted_data.get("paid_up_capital")
        reserves = financial_data.get("reserves_and_surplus") if financial_data.get("reserves_and_surplus") is not None else extracted_data.get("reserves_and_surplus")
        if puc is not None or reserves is not None:
            financial_data["net_worth"] = (float(puc) if puc is not None else 0.0) + (float(reserves) if reserves is not None else 0.0)
            extracted_data["net_worth"] = financial_data["net_worth"]
            print(f"[*] AOC 4 Rule Engine: Computed Pure Net Worth (CY) = {financial_data['net_worth']}")

        prev_puc = financial_data.get("prev_paid_up_capital") if financial_data.get("prev_paid_up_capital") is not None else extracted_data.get("prev_paid_up_capital")
        prev_reserves = financial_data.get("prev_reserves_and_surplus") if financial_data.get("prev_reserves_and_surplus") is not None else extracted_data.get("prev_reserves_and_surplus")
        if prev_puc is not None or prev_reserves is not None:
            financial_data["prev_net_worth"] = (float(prev_puc) if prev_puc is not None else 0.0) + (float(prev_reserves) if prev_reserves is not None else 0.0)
            extracted_data["prev_net_worth"] = financial_data["prev_net_worth"]
            print(f"[*] AOC 4 Rule Engine: Computed Pure Net Worth (PY) = {financial_data['prev_net_worth']}")

        # ── FIX 2: Always run text fallback, not just when excel partially succeeds ──
        # Identify missing numeric keys (Net Worth is purely computed above, exclude it from fallback)
        expected_keys = [k for k in self.excel_extractor.numeric_keywords.keys() if k not in ["net_worth", "prev_net_worth"]]
        missing_keys = [k for k in expected_keys if financial_data.get(k) is None]
        print(f"[*] AOC 4 Rule Engine: {len(missing_keys)}/{len(expected_keys)} numeric fields missing after Excel extraction.")

        if full_text:
            from automation_engine.modules.aoc4.parser import AOC4Parser
            temp_parser = AOC4Parser(self.config_path)

            # ── Extract MCA Masterdata fields (Authorised/Paid-up Capital) ──
            mca_fields = temp_parser._extract_mca_masterdata(full_text)
            for k, v in mca_fields.items():
                if v is not None:
                    extracted_data[k] = v

            # Always run text fallback for missing fields
            if missing_keys:
                fallback_data = temp_parser.extract_financials_from_text(full_text, missing_keys)

                scale = self.excel_extractor.detect_financials_scale(full_text)
                # If Excel or extracted numbers are already in raw Rupees (>= 1,00,000), do NOT apply scale multiplier
                if any(isinstance(v, (int, float)) and v >= 100000 for v in financial_data.values()):
                    scale = 1.0

                if scale != 1.0:
                    print(f"[*] AOC 4 Parser: Applying unit scale multiplier {scale} to text fallback data")
                    for k in fallback_data.keys():
                        if isinstance(fallback_data[k], (int, float)):
                            fallback_data[k] = fallback_data[k] * scale

                filled = {k: v for k, v in fallback_data.items() if v is not None}
                print(f"[*] AOC 4 Rule Engine: Text fallback filled {len(filled)} fields: {list(filled.keys())}")
                for k, v in fallback_data.items():
                    if financial_data.get(k) is None:
                        financial_data[k] = v
        else:
            print("[!] AOC 4 Rule Engine: No full_text available — text fallback skipped. Check if documents were parsed correctly.")

        # Re-verify pure Net Worth calculation after any fallback on Paid-up Capital or Reserves
        puc = financial_data.get("paid_up_capital") if financial_data.get("paid_up_capital") is not None else extracted_data.get("paid_up_capital")
        reserves = financial_data.get("reserves_and_surplus") if financial_data.get("reserves_and_surplus") is not None else extracted_data.get("reserves_and_surplus")
        if puc is not None or reserves is not None:
            financial_data["net_worth"] = (float(puc) if puc is not None else 0.0) + (float(reserves) if reserves is not None else 0.0)

        prev_puc = financial_data.get("prev_paid_up_capital") if financial_data.get("prev_paid_up_capital") is not None else extracted_data.get("prev_paid_up_capital")
        prev_reserves = financial_data.get("prev_reserves_and_surplus") if financial_data.get("prev_reserves_and_surplus") is not None else extracted_data.get("prev_reserves_and_surplus")
        if prev_puc is not None or prev_reserves is not None:
            financial_data["prev_net_worth"] = (float(prev_puc) if prev_puc is not None else 0.0) + (float(prev_reserves) if prev_reserves is not None else 0.0)


        # Fallback for Schedule III format detection from Markdown text
        if financial_data.get("has_schedule_iii_format") is None and full_text:
            text_lower = full_text.lower()
            required_headers = {
                "equity and liabilities", "shareholders' funds", "non-current liabilities",
                "current liabilities", "assets", "non-current assets", "current assets"
            }
            found_count = sum(1 for req in required_headers if req in text_lower or req.replace("'", "") in text_lower)
            if found_count >= 5:
                financial_data["has_schedule_iii_format"] = "yes"
            else:
                financial_data["has_schedule_iii_format"] = "no"

        # Always carry full_text forward so compliance/RPT engines can scan it
        financial_data["full_text"] = full_text

        # ── FIX: Force overwrite LLM hallucinations with Rule Engine deterministic extraction ──
        for k, v in financial_data.items():
            extracted_data[k] = v

        # Diagnostic log — helps debug 0-checks in production
        populated = [k for k in expected_keys if extracted_data.get(k) not in (None, 0, 0.0)]
        print(f"[*] AOC 4 Rule Engine: {len(populated)}/{len(expected_keys)} numeric fields populated before compliance run.")
                
        # 1. Run private compliance engine
        compliance_flags = self.compliance_engine.execute(extracted_data)
        extracted_data["compliance_flags"] = compliance_flags
        
        # 2. Run common error checker so it has access to the updated extracted_data (e.g. is_small_company)
        common_flags = self.checker.execute(extracted_data)
        
        # 3. Run the RPT & Loans Engine
        print("[*] AOC 4 Rule Engine: Evaluating RPT and Loans...")
        rpt_flags = self.rpt_loans_engine.execute(extracted_data)
        
        flags = common_flags + compliance_flags + rpt_flags
        
        target_cells = {
            "Common Error": {},
            "RPT and loans to Director": {}
        }
        
        # ── FIX 3: Ensure flags are always stored even if template is missing ──
        extracted_data["flags"] = flags
        print(f"[*] AOC 4 Rule Engine: Total flags generated = {len(flags)} (common={len(common_flags)}, compliance={len(compliance_flags)}, rpt={len(rpt_flags)})")

        # Open the target skeletal template to find dynamic rows
        if not os.path.exists(self.output_skeletal_path):
            print(f"[!] Warning: Output skeletal path not found at {self.output_skeletal_path}")
            return target_cells
            
        wb = openpyxl.load_workbook(self.output_skeletal_path, data_only=True)
        
        # Detect Private Compliance Sheet Name
        priv_sheet_name = None
        for sname in wb.sheetnames:
            if "private" in sname.lower() and "compliance" in sname.lower():
                priv_sheet_name = sname
                break
                
        if priv_sheet_name:
            target_cells[priv_sheet_name] = {}
        
        # Map Common Error sheet
        if "Common Error" in wb.sheetnames:
            sheet = wb["Common Error"]
            # Build a map of Particulars -> Row Number
            row_map = {}
            for row in range(2, sheet.max_row + 1):
                particulars = sheet.cell(row=row, column=2).value
                if particulars:
                    norm = self._normalize_string(particulars)
                    row_map[norm] = row
                    
            for flag in common_flags:
                norm_flag = self._normalize_string(flag["particulars"])
                matched_row = row_map.get(norm_flag)
                if matched_row:
                    yes_no = flag.get("user_value") if flag.get("user_value") else ("No" if flag.get("status") == "Failed" else "Yes")
                    comment = flag.get("reason", "")
                    
                    target_cells["Common Error"][f"C{matched_row}"] = yes_no
                    target_cells["Common Error"][f"D{matched_row}"] = comment
                else:
                    print(f"[!] Could not find dynamic mapping for rule in Excel: {flag['particulars'][:50]}...")
                    
        # Map Private Compliance sheet
        if priv_sheet_name and priv_sheet_name in wb.sheetnames:
            sheet_comp = wb[priv_sheet_name]
            
            # Check if particulars are in Col 1 (A) or Col 3 (C)
            part_col_idx = 1
            for r in range(4, 15):
                val_c = sheet_comp.cell(row=r, column=3).value
                if val_c and any(k in str(val_c).lower() for k in ["paidup", "reserves", "borrowings"]):
                    part_col_idx = 3
                    break
                    
            row_map_comp = {}
            for row in range(2, sheet_comp.max_row + 1):
                particulars = sheet_comp.cell(row=row, column=part_col_idx).value
                if particulars:
                    norm = self._normalize_string(particulars)
                    row_map_comp[norm] = row
            
            cy_col = "B" if part_col_idx == 1 else "D"
            py_col = "D" if part_col_idx == 1 else "F"
            app_col = "B" if part_col_idx == 1 else "D"
            rat_col = "C" if part_col_idx == 1 else "E"
            
            raw_data_map = {
                "Paidup capital": ("paid_up_capital", "prev_paid_up_capital"),
                "Reserves and Surplus": ("reserves_and_surplus", None),
                "Total Borrowings": ("borrowings", None),
                "Loangiven by Company to Directors or Director related entities (assets)": ("loan_to_directors_assets", None),
                "Loans given by Company (assets)": ("loan_given_by_company", None),
                "Investments made by Company (assets)": ("investments_made", None),
                "Corporate Guarantees given by Company": ("corporate_guarantees", None),
                "Loan from Directors or their relatives (Liabilities)": ("loan_from_directors", None),
                "Secured Loan": ("secured_loan", None),
                "Advance from Customers, Shareholders, Security Deposits (Liabilitys)": ("advance_from_customers", None),
                "Dues to MSME": ("dues_to_msme", None),
                "Networth": ("net_worth", "prev_net_worth"),
                "Turnover": ("turnover", "prev_turnover"),
                "Total Revenue": ("total_revenue", None),
                "Profit Before Tax": ("net_profit_before_tax", None),
                "ED / WTD - 1 Monthly Remuneration": ("rpt_monthly_remun", None),
                "ED / WTD - 2 Monthly Remuneration": ("rpt_monthly_remun_2", None),
                "Number of Bodies Corporate Shareholder holding more than 10%": ("has_corporate_shareholders", None),
                "Is the Company a Holding or a Subsidiary Company ": ("is_subsidiary_or_holding", None),
                "Is the Company a Holding, Subsidiary or Associate of IND AS applicable Companies": ("is_ind_as", None),
                "Exprt": ("export_sales", "prev_export_sales"),
                "Sitting Fees to Directors": ("sitting_fees", "prev_sitting_fees")
            }
            
            if extracted_data.get("paid_up_capital") is not None and extracted_data.get("reserves_and_surplus") is not None:
                try:
                    extracted_data["net_worth"] = float(extracted_data["paid_up_capital"]) + float(extracted_data["reserves_and_surplus"])
                except (ValueError, TypeError):
                    pass
            if extracted_data.get("prev_paid_up_capital") is not None and extracted_data.get("prev_reserves_and_surplus") is not None:
                try:
                    extracted_data["prev_net_worth"] = float(extracted_data["prev_paid_up_capital"]) + float(extracted_data["prev_reserves_and_surplus"])
                except (ValueError, TypeError):
                    pass

            for particular_name, (cy_key, py_key) in raw_data_map.items():
                norm = self._normalize_string(particular_name)
                matched_row = row_map_comp.get(norm)
                if matched_row:
                    if cy_key:
                        val = extracted_data.get(cy_key)
                        if val is None:
                            if cy_key in ["is_subsidiary_or_holding", "is_ind_as"]:
                                val = "No"
                            else:
                                val = 0

                        if cy_key == "has_corporate_shareholders":
                            val = 1 if str(val).lower() == "yes" else (val if isinstance(val, (int, float)) else 0)
                        elif isinstance(val, bool):
                            if not val and cy_key == "is_subsidiary_or_holding":
                                val = "Not a Subsidiary company"
                            else:
                                val = "Yes" if val else "No"
                        elif str(val).lower() in ["yes", "holding", "subsidiary"]: val = "Yes"
                        elif str(val).lower() == "no":
                            if cy_key == "is_subsidiary_or_holding":
                                val = "Not a Subsidiary company"
                            else:
                                val = "No"
                        if isinstance(val, (int, float)) and cy_key in ["loan_from_directors", "secured_loan", "borrowings", "dues_to_msme", "advance_from_customers"]:
                            val = abs(val)
                        target_cells[priv_sheet_name][f"{cy_col}{matched_row}"] = val
                    
                    if py_key and extracted_data.get(py_key) is not None:
                        val_py = extracted_data[py_key]
                        if isinstance(val_py, (int, float)) and py_key in ["prev_loan_from_directors", "prev_secured_loan", "prev_borrowings"]:
                            val_py = abs(val_py)
                        target_cells[priv_sheet_name][f"{py_col}{matched_row}"] = val_py
                        
            # Map compliance flags by normalized particular string, or explicit rule ID fallback
            id_to_row_clean = {
                "COMP_SMALL_CO": 37,
                "COMP_CARO": 38,
                "COMP_ROTATION": 39,
                "COMP_IND_AS": 40,
                "COMP_XBRL": 41,
                "COMP_VIGIL": 42,
                "COMP_IFC": 43,
                "COMP_INT_AUDIT": 44,
                "COMP_SEC_AUDIT": 45,
                "COMP_KMP": 46,
                "COMP_LOAN_186": 47,
                "COMP_LOAN_DIRECTOR": 48,
                "COMP_COST_AUDIT": 49,
                "COMP_CHARGE_FORM": 50,
                "COMP_AOC_1": 51,
                "COMP_AOC_2": 52,
                "COMP_RPT_OMNIBUS": 53,
                "COMP_CSR": 54,
                "COMP_CSR_COMMITTEE": 55,
                "COMP_DEPOSIT_DEC": 56,
                "COMP_DPT_3": 57,
                "COMP_MSME": 58,
                "COMP_BEN_2": 59,
                "COMP_MGT_8": 60,
                "COMP_MGT_7_CERT": 61
            }
            id_to_row_legacy = {
                "COMP_SMALL_CO": 35,
                "COMP_CARO": 36,
                "COMP_ROTATION": 37,
                "COMP_IND_AS": 38,
                "COMP_XBRL": 39,
                "COMP_VIGIL": 40,
                "COMP_IFC": 41,
                "COMP_INT_AUDIT": 42,
                "COMP_SEC_AUDIT": 43,
                "COMP_KMP": 44,
                "COMP_LOAN_186": 45,
                "COMP_LOAN_DIRECTOR": 46,
                "COMP_COST_AUDIT": 47,
                "COMP_CHARGE_FORM": 48,
                "COMP_AOC_1": 49,
                "COMP_AOC_2": 50,
                "COMP_RPT_OMNIBUS": 51,
                "COMP_CSR": 52,
                "COMP_CSR_COMMITTEE": 53,
                "COMP_DEPOSIT_DEC": 54,
                "COMP_DPT_3": 55,
                "COMP_MSME": 56,
                "COMP_BEN_2": 57,
                "COMP_MGT_8": 58,
                "COMP_MGT_7_CERT": 59
            }
            active_id_map = id_to_row_clean if part_col_idx == 1 else id_to_row_legacy

            for flag in compliance_flags:
                norm_p = self._normalize_string(flag["particulars"])
                matched_row = row_map_comp.get(norm_p)
                if not matched_row:
                    matched_row = active_id_map.get(flag.get("id"))
                
                if matched_row:
                    if part_col_idx == 3:
                        target_cells[priv_sheet_name][f"C{matched_row}"] = flag["particulars"]
                    target_cells[priv_sheet_name][f"{app_col}{matched_row}"] = flag.get("user_value", "")
                    target_cells[priv_sheet_name][f"{rat_col}{matched_row}"] = flag.get("rationale", "")
                    if part_col_idx == 3:
                        target_cells[priv_sheet_name][f"F{matched_row}"] = ""
                        target_cells[priv_sheet_name][f"G{matched_row}"] = ""

        # Map RPT sheet
        if "RPT and loans to Director" in wb.sheetnames:
            sheet_rpt = wb["RPT and loans to Director"]
            
            # Auto-populate previous year 10% benchmark cells (C6 and C7)
            prev_to = extracted_data.get("prev_turnover")
            prev_nw = extracted_data.get("prev_net_worth")
            if prev_to is not None:
                try:
                    target_cells["RPT and loans to Director"]["C6"] = float(prev_to) * 0.10
                except (ValueError, TypeError):
                    pass
            if prev_nw is not None:
                try:
                    target_cells["RPT and loans to Director"]["C7"] = float(prev_nw) * 0.10
                except (ValueError, TypeError):
                    pass

            row_map_rpt = {}
            for row in range(2, sheet_rpt.max_row + 1):
                for col_idx in [1, 2, 3]:
                    val = sheet_rpt.cell(row=row, column=col_idx).value
                    if val:
                        norm = self._normalize_string(val)
                        row_map_rpt[norm] = row
            
            id_to_row_rpt = {
                "COMP_SEC_185_BASE": 26,
                "COMP_SEC_185_FIRM": 27,
                "COMP_SEC_185_EXC1": 29,
                "COMP_SEC_185_EXC2": 30,
                "COMP_SEC_185_EXC3": 31,
                "COMP_SEC_185_NON_COMPLIANCE": 32,
                "COMP_SEC_185_INTERESTED_BASE": 33,
                "COMP_SEC_185_INTERESTED_PVT": 34,
                "COMP_SEC_185_INTERESTED_BODY_CORP": 35,
                "COMP_SEC_185_INTERESTED_BOARD": 36,
                "COMP_SEC_185_INTERESTED_SR": 38,
                "COMP_SEC_185_INTERESTED_UTIL": 39
            }

            for flag in rpt_flags:
                flag_id = flag.get("id", "")
                norm_flag = self._normalize_string(flag["particulars"])
                matched_row = row_map_rpt.get(norm_flag)
                if not matched_row:
                    matched_row = id_to_row_rpt.get(flag_id)
                
                if matched_row:
                    # For RPT Section 188 transactions (Rows 11-20):
                    # Write 'actual_value' to Col F and 'user_value' (Materiality Yes/No) to Col G
                    if flag_id.startswith("COMP_SEC_188_"):
                        if flag.get("actual_value") is not None and str(flag.get("actual_value")) != "0.0":
                            target_cells["RPT and loans to Director"][f"F{matched_row}"] = flag.get("actual_value")
                        target_cells["RPT and loans to Director"][f"G{matched_row}"] = flag.get("user_value")
                    elif flag_id == "COMP_SEC_185_APPLICABILITY":
                        # Row 25 is a standard section header ("PROHIBITION | Loans to directors... | APPLICABILITY | Section 185")
                        # Keep standard header intact without overwriting
                        pass
                    else:
                        # For Section 185 and Section 186 (Rows 26-54), verdicts and limits go to Col D
                        target_cells["RPT and loans to Director"][f"D{matched_row}"] = flag.get("user_value")

        extracted_data["flags"] = flags
        target_cells["_flags"] = flags
        
        return target_cells
