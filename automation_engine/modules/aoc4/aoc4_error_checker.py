import pandas as pd
import os

class AOC4CommonErrorEngine:
    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.rules = []
        self._load_rules()
        
    def _load_rules(self):
        """Load the rules from the ANNFIL COMMONERROR.xlsx file."""
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(f"Rules file not found at: {self.excel_path}")
            
        df = pd.read_excel(self.excel_path, sheet_name='Common Error')
        
        for idx, row in df.iterrows():
            particulars = str(row.get('Particulars', '')).strip()
            source = str(row.get('SOURCE', '')).strip()
            
            # Skip empty or structural rows (like headers or NaNs)
            if not particulars or particulars == 'nan':
                continue
                
            self.rules.append({
                "id": f"RULE_{idx}",
                "particulars": particulars,
                "source": source
            })

    def execute(self, input_data: dict) -> list:
        """
        Evaluate the parsed input_data against the loaded rules.
        Returns a list of flags for any checks that failed or are missing.
        """
        flags = []
        audit_trail_failed = False
        for rule in self.rules:
            particulars = rule["particulars"]
            
            # Get the full text from the parser and normalize it
            full_text = input_data.get("full_text", "")
            if not isinstance(full_text, str):
                full_text = ""
                
            full_text_lower = full_text.lower()
            
            # Custom rule implementations
            extracted_value = None
            
            # Row 1: Check for all required headings
            if "whether audit report has the following fields" in particulars.lower() and "opinion" in particulars.lower():
                # Allow either 'basis of opinion' or 'basis for opinion'
                found_opinion = "opinion" in full_text_lower
                found_basis = "basis of opinion" in full_text_lower or "basis for opinion" in full_text_lower
                found_mgmt = "responsibilities of management" in full_text_lower or "management's responsibility" in full_text_lower
                found_auditor = "auditor's responsibilities" in full_text_lower or "auditor's responsibility" in full_text_lower
                
                if found_opinion and found_basis and found_mgmt and found_auditor:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                
            # Row 2: Check for CARO
            elif "caro" in particulars.lower() or "companies auditor's report order" in particulars.lower():
                # Remove punctuation from text to check for CARO 
                import re
                clean_text = re.sub(r'[^a-z0-9 ]', ' ', full_text_lower)
                clean_text = re.sub(r'\s+', ' ', clean_text)
                
                if "companies auditor s report order" in clean_text or "caro" in clean_text:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 3: Schedule III
            elif "schedule iii" in particulars.lower():
                has_format = str(input_data.get("has_schedule_iii_format", "no")).lower()
                if has_format == "yes":
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 4: CIN, DIN, CEO, CFO
            elif "cin number" in particulars.lower() or "din of the director" in particulars.lower():
                if ("cin" in full_text_lower or "corporate identity number" in full_text_lower) and "din" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 5: Previous year figures
            elif "previous year figures" in particulars.lower():
                import re
                if "previous year" in full_text_lower or "prior year" in full_text_lower or re.search(r"31st march 20\d\d", full_text_lower):
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 6: Share capital notes
            elif "shareholding more than 5%" in particulars.lower():
                if "5%" in full_text_lower and ("shareholder" in full_text_lower or "holding" in full_text_lower or "promoter" in full_text_lower):
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
            
            elif "statutory register" in particulars.lower():
                # Usually manual, default to No unless statutory register is explicitly mentioned
                if "statutory register" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            elif "authorised capital is mentioned correctly" in particulars.lower():
                if "authorised capital" in full_text_lower or "authorized capital" in full_text_lower or "authorised share capital" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            elif "paid up capital  is mentioned correctly" in particulars.lower():
                if "paid up capital" in full_text_lower or "paid-up capital" in full_text_lower or "paid up share capital" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            elif "reconciliation  of shares" in particulars.lower():
                if "reconciliation" in full_text_lower and ("shares outstanding" in full_text_lower or "number of shares" in full_text_lower or "beginning of the year" in full_text_lower):
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            elif "promoter holding is disclosed" in particulars.lower():
                if "promoter holding" in full_text_lower or "promoter's holding" in full_text_lower or "shares held by promoters" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 7: Cash flow statement
            elif "cash flow statement is given" in particulars.lower():
                if "cash flow statement" in full_text_lower or "statement of cash flows" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 8: Significant Accounting Policies
            elif "significant accounting policies" in particulars.lower():
                if "significant accounting policies" in full_text_lower or "summary of significant accounting policies" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 9: EPS
            elif "eps & diluted eps" in particulars.lower():
                if "eps" in full_text_lower or "earnings per share" in full_text_lower or ("basic" in full_text_lower and "diluted" in full_text_lower):
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 10: Signed by directors and auditors
            elif "signed by both the directors and the auditors" in particulars.lower():
                if "director" in full_text_lower and ("auditor" in full_text_lower or "partner" in full_text_lower or "chartered accountant" in full_text_lower):
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
            
            # Row 11: Check for UDIN
            elif "udin" in particulars.lower():
                import re
                if "udin" in full_text_lower or re.search(r'\b\d{18}\b', full_text_lower):
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 12: Seal of the auditor
            elif "seal of the auditor" in particulars.lower():
                if "firm registration number" in full_text_lower or "frn" in full_text_lower or "seal" in full_text_lower or "membership no" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 13 & 14: RPT and Forex
            elif "rpt transaction" in particulars.lower() or "forex and rpt" in particulars.lower():
                found_rpt = "related party" in full_text_lower or "rpt" in full_text_lower
                found_forex = "foreign exchange" in full_text_lower or "forex" in full_text_lower or "foreign currency" in full_text_lower
                
                if "forex" in particulars.lower():
                    extracted_value = "Yes" if (found_rpt and found_forex) else "No"
                else:
                    extracted_value = "Yes" if found_rpt else "No"
                    
            # Audit Trail Rules
            elif "audit trail features" in particulars.lower() or "accounting software" in particulars.lower():
                if "accounting software" in full_text_lower and "audit trail" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    
            elif "edit log" in particulars.lower():
                if "edit log" in full_text_lower or "recording audit trail" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    
            elif "operated throughout the year" in particulars.lower():
                if "operated throughout the year" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    
            elif "tampered with" in particulars.lower():
                if "tampered with" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    
            elif "preserved by the company" in particulars.lower() or "statutory requirements for record retention" in particulars.lower():
                if "preserv" in full_text_lower and "audit trail" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    
            elif "if any of the above points is no" in particulars.lower():
                if audit_trail_failed:
                    extracted_value = "No"
                else:
                    extracted_value = "Yes"
                    
            # CSR Rules (Rows 30-37)
            elif any(csr_phrase in particulars.lower() for csr_phrase in [
                "amount required to be spent by the company during the year",
                "amount of expenditure incurred",
                "shortfall at the end of the year",
                "total of previous years shortfall",
                "reason for shortfall",
                "nature of csr activities",
                "details of related party transactions, e.g., contribution to a trust",
                "where a provision is made with respect to a liability incurred by entering into a contractual obligation"
            ]):
                import re
                if "corporate social responsibility" in full_text_lower or "csr expense" in full_text_lower or re.search(r'\bcsr\b', full_text_lower):
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    
            # Row 17 & 18: Manual Team Checks
            elif "board resolutions was issued" in particulars.lower() or "directors were abroad" in particulars.lower():
                # These are explicitly marked as "Team to check with client", so we default to No to ensure they are flagged.
                extracted_value = "No"
            
            # Standard fuzzy fallback
            else:
                # Create a simplified search keyword from the particulars
                search_key = particulars.lower().replace("whether audit report has the following fields -", "").strip()
                search_key = search_key.replace("details of", "").strip()
                search_key = search_key.replace("?", "").strip()
                
                if not full_text_lower:
                    extracted_value = None
                elif search_key and search_key in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
            
            if not extracted_value or extracted_value == 'No':
                reason = "Value is missing in extraction." if not extracted_value else "Rule not found in document (No)."
                
                # Special message for Audit Trail rules
                if "audit trail" in particulars.lower() or "edit log" in particulars.lower() or "accounting software" in particulars.lower() or "tampered with" in particulars.lower() or "operated throughout the year" in particulars.lower() or "if any of the above points is no" in particulars.lower():
                    reason = "Send financials back to the company highlighting the 'NO' (Audit trail issue)."
                    
                # Special message for manual team checks
                if "board resolutions was issued" in particulars.lower() or "directors were abroad" in particulars.lower():
                    reason = "Manual Check Required: Team must verify this directly with the client."
                
                flags.append({
                    "rule_id": rule["id"],
                    "particulars": particulars,
                    "source": rule["source"],
                    "status": "Failed",
                    "user_value": extracted_value,
                    "reason": reason
                })
            else:
                flags.append({
                    "rule_id": rule["id"],
                    "particulars": particulars,
                    "source": rule["source"],
                    "status": "Passed",
                    "user_value": extracted_value,
                    "reason": "Rule text matched in document"
                })
                
        return flags
