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
                
            if source == 'nan':
                if "share capital notes" in particulars.lower():
                    source = "financials - Balance sheet - Liabilities"
                else:
                    source = ""
                
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
            extracted_reason = None
            
            # Row 1: Check for all required headings
            if "whether audit report has the following fields" in particulars.lower() and "opinion" in particulars.lower():
                missing = []
                
                # a) Opinion
                if "opinion" not in full_text_lower: missing.append("Opinion")
                # b) Basis of Opinion
                if "basis of opinion" not in full_text_lower and "basis for opinion" not in full_text_lower: missing.append("Basis for Opinion")
                # c) Emphasis of matter
                if "emphasis of matter" not in full_text_lower: missing.append("Emphasis of matter")
                # d) Key Audit Matters
                if "key audit matters" not in full_text_lower and "key audit matter" not in full_text_lower: missing.append("Key Audit Matters")
                # e) Other Information
                if "other information" not in full_text_lower: missing.append("Other Information")
                # f) Responsibility of Management
                if "responsibilities of management" not in full_text_lower and "management's responsibility" not in full_text_lower: missing.append("Responsibility of Management")
                # g) Auditor's responsibility
                if "auditor's responsibilities" not in full_text_lower and "auditor's responsibility" not in full_text_lower: missing.append("Auditor's responsibility")
                # h) Other matters
                if "other matters" not in full_text_lower and "other matter" not in full_text_lower: missing.append("Other matters")
                # i) report on other legal and regulatory requirements
                if "report on other legal and regulatory requirements" not in full_text_lower and "other legal and regulatory requirements" not in full_text_lower: missing.append("Report on other legal and regulatory requirements")
                # j) reporting on Internal finanical Controls
                if "internal financial control" not in full_text_lower and "internal financial controls" not in full_text_lower: missing.append("Internal Financial Controls")
                
                if not missing:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = f"Missing fields: {', '.join(missing)}"
                
            # Row 2: Check for CARO
            elif "caro" in particulars.lower() or "companies auditor's report order" in particulars.lower():
                # Remove punctuation from text to check for CARO 
                import re
                clean_text = re.sub(r'[^a-z0-9 ]', ' ', full_text_lower)
                clean_text = re.sub(r'\s+', ' ', clean_text)
                
                if "companies auditor s report order" in clean_text or "caro " in clean_text or " caro" in clean_text:
                    import re
                    # Look for "not applicable" within ~100 characters of CARO keywords
                    is_na = False
                    for kw in ["companies auditor s report order", "caro"]:
                        for m in re.finditer(r'\b' + kw + r'\b', clean_text):
                            window = clean_text[max(0, m.start() - 150):min(len(clean_text), m.end() + 150)]
                            if "not applicable" in window:
                                is_na = True
                                break
                        if is_na:
                            break
                            
                    if is_na:
                        extracted_value = "Not Applicable"
                        extracted_reason = "Auditor's report explicitly states CARO is not applicable."
                    else:
                        extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing keywords: 'CARO' or 'Companies Auditor's Report Order'"
                    
            # Row 3: Schedule III
            elif "schedule iii" in particulars.lower():
                has_format = str(input_data.get("has_schedule_iii_format", "no")).lower()
                if has_format == "yes":
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Failed to detect Schedule III format based on table structure"
                    
            # Row 4: CIN, DIN, CEO, CFO
            elif "cin number" in particulars.lower() or "din of the director" in particulars.lower():
                found_cin = "cin" in full_text_lower or "corporate identity number" in full_text_lower
                found_din = "din" in full_text_lower
                # Check for address keyword
                found_address = "address" in full_text_lower or "registered office" in full_text_lower
                
                if found_cin and found_din and found_address:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    missing = []
                    if not found_cin: missing.append("CIN")
                    if not found_din: missing.append("DIN")
                    if not found_address: missing.append("Address")
                    extracted_reason = f"Missing fields: {', '.join(missing)}"
                    
            # Row 5: Previous year figures
            elif "previous year figures" in particulars.lower():
                import re
                has_prev_column = "previous year" in full_text_lower or "prior year" in full_text_lower or bool(re.search(r"31st march 20\d\d", full_text_lower)) or bool(re.search(r"31\.03\.20\d\d", full_text_lower))
                
                prev_file = input_data.get("previous_fla_file") or input_data.get("prev_year_financials")
                
                # Financial metrics to tally for BS & PL
                metrics_to_check = [
                    ("Turnover/Revenue", input_data.get("prev_turnover"), input_data.get("last_year_turnover")),
                    ("Paid Up Capital", input_data.get("prev_paid_up_capital"), input_data.get("last_year_paid_up_capital")),
                    ("Net Worth", input_data.get("prev_net_worth"), input_data.get("last_year_net_worth")),
                    ("Net Profit", input_data.get("prev_net_profit_after_tax"), input_data.get("last_year_net_profit"))
                ]
                
                mismatches = []
                compared_count = 0
                
                if prev_file:
                    for label, fy_prev_val, py_val in metrics_to_check:
                        if fy_prev_val is not None and py_val is not None:
                            try:
                                v1 = float(fy_prev_val)
                                v2 = float(py_val)
                                compared_count += 1
                                # Rounding tolerance (e.g. within 1 unit or 0.1%)
                                if abs(v1 - v2) > max(1.0, abs(v2) * 0.01):
                                    mismatches.append(f"{label} (FY PY Col: {v1} vs PY Doc: {v2})")
                            except (ValueError, TypeError):
                                pass
                                
                if prev_file and compared_count > 0:
                    if not mismatches:
                        extracted_value = "Yes"
                    else:
                        extracted_value = "No"
                        extracted_reason = f"Previous year figures in BS/PL do not tally with last year's filed financials: {', '.join(mismatches)}"
                elif has_prev_column:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing previous year comparative figures or prior year date column in Balance Sheet / P&L"
                    
            # Row 6: Share capital notes
            elif "shareholding more than 5%" in particulars.lower():
                if ("5%" in full_text_lower or "5 percent" in full_text_lower) and ("shareholder" in full_text_lower or "holding" in full_text_lower or "promoter" in full_text_lower):
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing keywords: '5%' or '5 percent' combined with 'shareholder', 'holding' or 'promoter'"
            
            elif "statutory register" in particulars.lower():
                extracted_value = "No"
                extracted_reason = "Manual Check Required: Please verify Shareholding with Statutory Register."
                    
            elif "authorised capital is mentioned correctly" in particulars.lower():
                import re
                has_keywords = any(kw in full_text_lower for kw in ["authorised capital", "authorized capital", "authorised share capital", "authorized share capital"])
                
                mca_auth = input_data.get("mca_authorised_capital") or input_data.get("authorised_capital_mca")
                doc_auth = input_data.get("authorised_capital")
                
                if mca_auth is not None and doc_auth is not None:
                    try:
                        v1 = float(mca_auth)
                        v2 = float(doc_auth)
                        if abs(v1 - v2) <= max(1000.0, v1 * 0.01):
                            extracted_value = "Yes"
                            extracted_reason = f"Numerical Match: FS ({v2}) closely matches MCA ({v1})"
                        else:
                            extracted_value = "No"
                            extracted_reason = f"Authorised Capital in FS ({v2}) does not match MCA Master Data ({v1})"
                    except (ValueError, TypeError):
                        extracted_value = "Yes" if has_keywords else "No"
                else:
                    extracted_value = "Missing Data"
                    extracted_reason = "Missing MCA Master Data to cross-verify against."
                    
            elif "paid up capital" in particulars.lower() and "mentioned correctly" in particulars.lower():
                import re
                has_keywords = any(kw in full_text_lower for kw in ["paid up capital", "paid-up capital", "paid up share capital", "subscribed and paid up"])
                
                mca_puc = input_data.get("mca_paid_up_capital") or input_data.get("paid_up_capital_mca")
                doc_puc = input_data.get("paid_up_capital")
                
                if mca_puc is not None and doc_puc is not None:
                    try:
                        v1 = float(mca_puc)
                        v2 = float(doc_puc)
                        if abs(v1 - v2) <= max(1000.0, v1 * 0.01):
                            extracted_value = "Yes"
                            extracted_reason = f"Numerical Match: FS ({v2}) closely matches MCA ({v1})"
                        else:
                            extracted_value = "No"
                            extracted_reason = f"Paid Up Capital in FS ({v2}) does not match MCA Master Data ({v1})"
                    except (ValueError, TypeError):
                        extracted_value = "Yes" if has_keywords else "No"
                else:
                    extracted_value = "Missing Data"
                    extracted_reason = "Missing MCA Master Data to cross-verify against."
                    
            elif "reconciliation  of shares" in particulars.lower() or "reconciliation of shares" in particulars.lower():
                keywords = [
                    "reconciliation",
                    "shares at beginning of year",
                    "shares at end of year",
                    "number of equity shares outstanding at the end of the year",
                    "number of equity shares outstanding at the beginning of the year"
                ]
                
                matched = [kw for kw in keywords if kw in full_text_lower]
                if matched:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing keywords for share reconciliation"
                    
            elif "promoter holding is disclosed" in particulars.lower():
                keywords = [
                    "promoter",
                    "promoter holding",
                    "promoter's holding",
                    "shares held by promoter",
                    "shares held by promoters",
                    "name of promoters",
                    "shareholding of promoters"
                ]
                matched = [kw for kw in keywords if kw in full_text_lower]
                if matched:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing keywords for promoter holding disclosure"
                    
            # Row 7: Cash flow statement
            elif "cash flow statement is given" in particulars.lower():
                is_small_company = input_data.get("is_small_company_calculated", False)
                if is_small_company:
                    extracted_value = "Not Applicable"
                    extracted_reason = "Exempt because it is a Small Company."
                else:
                    if "cash flow statement" in full_text_lower or "statement of cash flows" in full_text_lower:
                        extracted_value = "Yes"
                    else:
                        extracted_value = "No"
                        extracted_reason = "Missing keywords: 'cash flow statement'"

                    
            # Row 8: Significant Accounting Policies
            elif "significant accounting policies" in particulars.lower():
                if "significant accounting policies" in full_text_lower or "summary of significant accounting policies" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing keywords: 'significant accounting policies'"
                    
            # Row 9: EPS
            elif "eps & diluted eps" in particulars.lower():
                import re
                eps_pattern = r'\b(eps|earnings per share|diluted eps|diluted earning(s)? per share)\b'
                matches = list(re.finditer(eps_pattern, full_text_lower))
                
                if matches:
                    has_numbers = False
                    for match in matches:
                        start = max(0, match.start() - 100)
                        end = min(len(full_text_lower), match.end() + 100)
                        context = full_text_lower[start:end]
                        if re.search(r'\d', context):
                            has_numbers = True
                            break
                            
                    if has_numbers:
                        extracted_value = "Yes"
                    else:
                        extracted_value = "No"
                        extracted_reason = "EPS keywords found, but no numbers present near them"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing keywords: 'eps', 'earnings per share', 'diluted eps'"
                    
            # Row 10: Signed by directors and auditors
            elif "signed by both the directors and the auditors" in particulars.lower():
                import re
                has_text_signatures = "director" in full_text_lower and ("auditor" in full_text_lower or "partner" in full_text_lower or "chartered accountant" in full_text_lower)
                has_image_seal = bool(re.search(r'!\[.*?\]\(.*?\)', full_text_lower))
                
                if has_text_signatures and has_image_seal:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing either text signatures (Director + Auditor) OR visual seal/image"
            
            # Row 11: Check for UDIN
            elif "udin" in particulars.lower():
                import re
                # We use word boundaries \b to avoid matching "udin" inside words like "including"
                has_udin_word = bool(re.search(r'\budin\b', full_text_lower))
                has_18_digit = bool(re.search(r'\b\d{18}\b', full_text_lower))
                
                if has_udin_word or has_18_digit:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing keywords: exact word 'udin' or an 18-digit number"
                    
            # Row 12: Seal of the auditor
            elif "seal of the auditor" in particulars.lower():
                import re
                has_auditor_text = "seal" in full_text_lower or "stamp" in full_text_lower
                has_image_seal = bool(re.search(r'!\[.*?\]\(.*?\)', full_text_lower))
                
                if has_auditor_text or has_image_seal:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    extracted_reason = "Missing auditor seal/stamp keywords AND no visual image found"
                    
            # Row 13 & 14: RPT and Forex
            elif "rpt transaction" in particulars.lower() or "forex and rpt" in particulars.lower():
                import re
                
                forex_keywords = [
                    "value of imports",
                    "c.i.f basis",
                    "c.l.f basis",
                    "expenditure in foreign currency",
                    "earnings in foreign exchange",
                    "foreign exchange",
                    "foreign currency",
                    "forex",
                    "related party",
                    "rpt"
                ]
                
                if "forex" in particulars.lower():
                    # Find all keyword matches
                    matched_spans = []
                    for kw in forex_keywords:
                        for m in re.finditer(re.escape(kw), full_text_lower):
                            matched_spans.append((m.start(), m.end()))
                    
                    if matched_spans:
                        has_numbers = False
                        for start_idx, end_idx in matched_spans:
                            ctx_start = max(0, start_idx - 150)
                            ctx_end = min(len(full_text_lower), end_idx + 150)
                            context = full_text_lower[ctx_start:ctx_end]
                            if re.search(r'\d', context):
                                has_numbers = True
                                break
                        
                        if has_numbers:
                            extracted_value = "Yes"
                        else:
                            extracted_value = "No"
                            extracted_reason = "Forex/RPT keywords found, but no figures/numbers present near them"
                    else:
                        extracted_value = "No"
                        extracted_reason = "Missing Forex/RPT keywords in Notes to Accounts"
                else:
                    export_sales = input_data.get("export_sales")
                    rpt_sales = input_data.get("rpt_sale_goods")
                    
                    if export_sales is not None and rpt_sales is not None and (float(export_sales) > 0 or float(rpt_sales) > 0):
                        if float(export_sales) == float(rpt_sales):
                            extracted_value = "Yes"
                            extracted_reason = f"Numerical Match: Export Services ({export_sales}) == RPT Sales ({rpt_sales})"
                        else:
                            extracted_value = "No"
                            extracted_reason = f"Mismatch: Export Services/Exports ({export_sales}) does not match RPT Sales ({rpt_sales})"
                    else:
                        rpt_keywords = [
                            "related party",
                            "rpt",
                            "loan to directors",
                            "loan from directors",
                            "remuneration to kmp"
                        ]
                        matched_rpt = [kw for kw in rpt_keywords if kw in full_text_lower]
                        if matched_rpt:
                            extracted_value = "Yes"
                        else:
                            extracted_value = "No"
                            extracted_reason = "Missing RPT keywords (e.g. 'loan to directors', 'related party')"
            # Audit Trail Rules — Main Header
            elif "audit trail features" in particulars.lower() or "accounting software" in particulars.lower():
                audit_keywords = [
                    "audit trail",
                    "edit log",
                    "accounting software",
                    "recording of audit trail",
                    "feature of recording audit trail"
                ]
                matched = [kw for kw in audit_keywords if kw in full_text_lower]
                if matched:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    extracted_reason = "Missing audit trail keywords in auditor report"

            # Audit Trail — (a) Edit Log / Recording Audit Trail
            elif "edit log" in particulars.lower():
                if "edit log" in full_text_lower or "recording audit trail" in full_text_lower or "feature of recording audit trail" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    extracted_reason = "Missing keywords: 'edit log' or 'recording audit trail'"

            # Audit Trail — (b) Operated Throughout the Year
            elif "operated throughout the year" in particulars.lower():
                if "operated throughout the year" in full_text_lower or ("operated" in full_text_lower and "throughout" in full_text_lower):
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    extracted_reason = "Missing keyword: 'operated throughout the year'"

            # Audit Trail — (c) Not Tampered With
            elif "tampered with" in particulars.lower():
                if "tampered with" in full_text_lower or "not tampered" in full_text_lower or "audit trail feature has not been tampered" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    extracted_reason = "Missing keyword: 'tampered with'"

            # Audit Trail — (d) Preserved / Statutory Requirements
            elif "preserved by the company" in particulars.lower() or "statutory requirements for record retention" in particulars.lower():
                if ("preserv" in full_text_lower or "retention" in full_text_lower) and "audit trail" in full_text_lower:
                    extracted_value = "Yes"
                else:
                    extracted_value = "No"
                    audit_trail_failed = True
                    extracted_reason = "Missing keywords: 'preserved' or 'statutory requirements for record retention'"

            # Audit Trail — Final Decision: Send Back if Any NO
            elif "if any of the above points is no" in particulars.lower():
                if audit_trail_failed:
                    extracted_value = "No"
                    extracted_reason = "One or more audit trail sub-checks failed — send financials back"
                else:
                    extracted_value = "Yes"

            # CSR Rules (Rows 30-37)
            elif any(csr_phrase in particulars.lower() for csr_phrase in [
                "amount required to be spent",
                "expenditure incurred",
                "shortfall at the end",
                "previous years shortfall",
                "reason for shortfall",
                "nature of csr activities",
                "contribution to a trust",
                "contractual obligation"
            ]):
                is_csr_applicable = input_data.get("is_csr_applicable_calculated", False)
                
                if not is_csr_applicable:
                    extracted_value = "Not Applicable"
                    extracted_reason = "CSR is Not Applicable based on compliance criteria (Net Worth < 500Cr, Turnover < 1000Cr, PBT < 5Cr)"
                else:
                    p_lower = particulars.lower()
                    if "amount required to be spent" in p_lower:
                        kws = ["amount required to be spent", "required to be spent"]
                    elif "expenditure incurred" in p_lower:
                        kws = ["expenditure incurred", "amount of expenditure"]
                    elif "shortfall at the end" in p_lower:
                        kws = ["shortfall at the end", "shortfall"]
                    elif "previous years shortfall" in p_lower:
                        kws = ["previous years shortfall", "previous year shortfall"]
                    elif "reason for shortfall" in p_lower:
                        kws = ["reason for shortfall"]
                    elif "nature of csr activities" in p_lower:
                        kws = ["nature of csr", "csr activities", "contribution towards"]
                    elif "contribution to a trust" in p_lower or "related party transactions" in p_lower:
                        kws = ["related party transactions", "contribution to a trust", "trust"]
                    elif "contractual obligation" in p_lower or "liability incurred" in p_lower:
                        kws = ["contractual obligation", "provision is made", "liability incurred"]
                    else:
                        kws = ["csr", "corporate social responsibility"]
                        
                    found_kw = None
                    for kw in kws:
                        if kw in full_text_lower:
                            found_kw = kw
                            break
                            
                    if found_kw:
                        import re
                        has_numbers = False
                        
                        start_idx = 0
                        while True:
                            idx = full_text_lower.find(found_kw, start_idx)
                            if idx == -1:
                                break
                                
                            window_start = max(0, idx - 150)
                            window_end = min(len(full_text_lower), idx + len(found_kw) + 150)
                            window_text = full_text_lower[window_start:window_end]
                            
                            if re.search(r'\d', window_text):
                                has_numbers = True
                                break
                                
                            start_idx = idx + 1
                            
                        if has_numbers:
                            extracted_value = "Yes"
                        else:
                            extracted_value = "No"
                            extracted_reason = f"Keyword '{found_kw}' found, but no figures/numbers present near it"
                    else:
                        extracted_value = "No"
                        extracted_reason = f"Missing keywords for CSR disclosure item: '{kws[0]}'"
                    
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
                    extracted_reason = f"Keyword not found in documents: '{search_key}'"
            
            if not extracted_value or extracted_value == 'No':
                reason = "Value is missing in extraction." if not extracted_value else "Rule not found in document (No)."
                
                if extracted_reason:
                    reason = f"Why it is No: {extracted_reason}"
                
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
                    "status": "Passed" if extracted_value == "Yes" else "Failed",
                    "user_value": extracted_value,
                    "reason": extracted_reason if extracted_reason else "Rule text matched in document"
                })
                
        return flags
