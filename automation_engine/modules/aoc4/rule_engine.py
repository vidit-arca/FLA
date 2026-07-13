import json
import os
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
        self.excel_path = os.path.join(base_dir, "excel", "ANNFIL COMMONERROR.xlsx")
        self.output_skeletal_path = os.path.join(base_dir, "excel", "Annual Filing common error Output.xlsx")
        self.checker = AOC4CommonErrorEngine(self.excel_path)
        self.compliance_engine = PrivateComplianceEngine()
        self.rpt_loans_engine = RPTLoansEngine()
        self.excel_extractor = AOC4ExcelExtractor()

    def _normalize_string(self, text):
        if not text:
            return ""
        return str(text).strip().lower().replace(" ", "").replace("\n", "")

    def evaluate_all(self, extracted_data: dict) -> dict:
        print("[*] AOC 4 Rule Engine: Evaluating common errors...")
        

        print("[*] AOC 4 Rule Engine: Evaluating private compliance...")
        # 1. Run Excel Extractor on the original docs to pull structured financial metrics
        docs = extracted_data.get("docs", {})
        financial_data = self.excel_extractor.extract_from_docs(docs)
        
        # Identify missing numeric keys
        expected_keys = [
            "turnover", "prev_turnover", "paid_up_capital", "net_worth", "prev_net_worth",
            "reserves_and_surplus", "borrowings", "secured_loan", "unsecured_loan",
            "operating_profit", "net_profit_before_tax", "net_profit_after_tax",
            "rpt_monthly_remun", "rpt_lease", "rpt_sale_goods", "rpt_purchase_goods",
            "total_loans_investments_given", "borrowing_defaults"
        ]
        missing_keys = [k for k in expected_keys if financial_data.get(k) is None]
        
        # If any numeric fields are missing, try extracting from raw Markdown (PDFs)
        if missing_keys and "full_text" in extracted_data:
            from automation_engine.modules.aoc4.parser import AOC4Parser
            # The parser logic is now in AOC4Parser. We need an instance.
            # But wait, self doesn't have an instance of AOC4Parser readily available here, 
            # so we instantiate one temporarily or call it statically.
            temp_parser = AOC4Parser(self.config_path)
            fallback_data = temp_parser.extract_financials_from_text(extracted_data["full_text"], missing_keys)
            
            # Merge the fallback data
            for k, v in fallback_data.items():
                financial_data[k] = v
                
        # Fallback for Schedule III format detection from Markdown text
        if financial_data.get("has_schedule_iii_format", "no") == "no" and "full_text" in extracted_data:
            text_lower = extracted_data["full_text"].lower()
            required_headers = {
                "equity and liabilities", "shareholders' funds", "non-current liabilities",
                "current liabilities", "assets", "non-current assets", "current assets"
            }
            found_count = sum(1 for req in required_headers if req in text_lower or req.replace("'", "") in text_lower)
            # If we find almost all headers (>= 5 out of 7) in the raw text, it's a Schedule III structure
            if found_count >= 5:
                financial_data["has_schedule_iii_format"] = "yes"
        
        # Merge the financial metrics into extracted_data so compliance engine can read them
        extracted_data.update(financial_data)
        
        # Now run common error checker so it has access to all extracted financial data
        common_flags = self.checker.execute(extracted_data)
        
        # 2. Run the Compliance Engine with the populated numerical data
        compliance_flags = self.compliance_engine.execute(extracted_data)
        
        # 3. Run the RPT & Loans Engine
        print("[*] AOC 4 Rule Engine: Evaluating RPT and Loans...")
        rpt_flags = self.rpt_loans_engine.execute(extracted_data)
        
        flags = common_flags + compliance_flags + rpt_flags
        
        target_cells = {
            "Common Error": {},
            "Compliance sheet for private": {},
            "RPT and loans to Director": {}
        }
        
        # Open the target skeletal template to find dynamic rows
        if not os.path.exists(self.output_skeletal_path):
            print(f"[!] Warning: Output skeletal path not found at {self.output_skeletal_path}")
            extracted_data["flags"] = flags
            return target_cells
            
        wb = openpyxl.load_workbook(self.output_skeletal_path, data_only=True)
        if "Common Error" in wb.sheetnames:
            sheet = wb["Common Error"]
            # Build a map of Particulars -> Row Number
            row_map = {}
            for row in range(2, sheet.max_row + 1):
                particulars = sheet.cell(row=row, column=2).value
                if particulars:
                    norm = self._normalize_string(particulars)
                    row_map[norm] = row
                    
            # Map the flags to their Excel cells
            for flag in common_flags:
                norm_flag = self._normalize_string(flag["particulars"])
                matched_row = row_map.get(norm_flag)
                if matched_row:
                    yes_no = "No" if flag["status"] == "Failed" else "Yes"
                    comment = flag["reason"] if flag["status"] == "Failed" else ""
                    
                    target_cells["Common Error"][f"C{matched_row}"] = yes_no
                    target_cells["Common Error"][f"D{matched_row}"] = comment
                else:
                    print(f"[!] Could not find dynamic mapping for rule in Excel: {flag['particulars'][:50]}...")
                    
        # We can also map compliance flags to 'Compliance sheet for private' if needed
        if "Compliance sheet for private" in wb.sheetnames:
            sheet_comp = wb["Compliance sheet for private"]
            row_map_comp = {}
            for row in range(2, sheet_comp.max_row + 1):
                # Requirement is in Column A (1)
                particulars = sheet_comp.cell(row=row, column=1).value
                if particulars:
                    norm = self._normalize_string(particulars)
                    row_map_comp[norm] = row
            
            for flag in compliance_flags:
                norm_flag = self._normalize_string(flag["particulars"])
                matched_row = row_map_comp.get(norm_flag)
                if matched_row:
                    # Current year "Complied or not" is mapped to Column B
                    target_cells["Compliance sheet for private"][f"B{matched_row}"] = flag["user_value"]
                    
        if "RPT and loans to Director" in wb.sheetnames:
            sheet_rpt = wb["RPT and loans to Director"]
            row_map_rpt = {}
            for row in range(2, sheet_rpt.max_row + 1):
                # Search cols 1, 2, and 3 for particulars (some are in C like "Has the Company give loan...")
                particulars = sheet_rpt.cell(row=row, column=1).value or sheet_rpt.cell(row=row, column=2).value or sheet_rpt.cell(row=row, column=3).value
                if particulars:
                    norm = self._normalize_string(particulars)
                    row_map_rpt[norm] = row
            
            for flag in rpt_flags:
                norm_flag = self._normalize_string(flag["particulars"])
                matched_row = row_map_rpt.get(norm_flag)
                if matched_row:
                    # For RPT, write 'actual_value' to Col F
                    if flag.get("actual_value") is not None and str(flag.get("actual_value")) != "0.0":
                        target_cells["RPT and loans to Director"][f"F{matched_row}"] = flag.get("actual_value")
                    
                    # For Section 185 and 186, Applicability goes to Col D. Otherwise Col G.
                    flag_id = flag.get("id", "")
                    if flag_id.startswith("COMP_SEC_185_") or flag_id.startswith("COMP_SEC_186_"):
                        target_cells["RPT and loans to Director"][f"D{matched_row}"] = flag.get("user_value")
                    else:
                        target_cells["RPT and loans to Director"][f"G{matched_row}"] = flag.get("user_value")

        extracted_data["flags"] = flags
        target_cells["_flags"] = flags
        
        return target_cells
