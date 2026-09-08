import json
import os
import docx
import pdfplumber
import re

class AOC4Parser:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "rules_config.json")
        self.config_path = config_path
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def extract_docx_text(self, path: str) -> str:
        """Extracts text from a native .docx file."""
        try:
            doc = docx.Document(path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            
            # Also extract from tables
            for table in doc.tables:
                for row in table.rows:
                    row_data = [cell.text for cell in row.cells]
                    text += " | ".join(row_data) + "\n"
            return text
        except Exception as e:
            print(f"[!] Error reading docx {path}: {e}")
            return ""

    def extract_excel_text(self, path: str) -> str:
        """Extracts text from relevant financial and master sheets of a native .xlsx/.xls file."""
        import pandas as pd
        try:
            excel_file = pd.ExcelFile(path)
            text_blocks = []
            
            target_keywords = [
                "balance sheet", "p&l", "pandl", "pl", "profit and loss", "statement of profit", 
                "profit", "loss", "notes", "note", "nt ", "related party", "rpt", "revenue", 
                "share capital", "financials", "bs", "cfs", "master data", "master", "company info", 
                "basic details", "schedule", "trading", "expenses", "income"
            ]
            
            excluded_keywords = [
                "validation", "caro", "mgt", "meeting", "bm control", "vpd", "index of charges", 
                "din", "view signatory", "signatory", "185", "188", "adt", "dir", "common error", 
                "format sheet", "for rbca", "list of forms", "control sheet", "checklist"
            ]
            
            for sheet_name in excel_file.sheet_names:
                sheet_lower = sheet_name.lower().strip()
                # Skip non-financial administrative/checklist sheets
                if any(ex in sheet_lower for ex in excluded_keywords):
                    continue
                # If target keywords match, include sheet
                if any(kw in sheet_lower for kw in target_keywords):
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    text_blocks.append(f"--- Sheet: {sheet_name} ---\n" + df.to_string(index=False, na_rep=''))
                    
            return "\n\n".join(text_blocks)
        except Exception as e:
            print(f"[!] Error reading excel {path}: {e}")
            return ""

    def parse_all(self, docs: dict, ocr_outputs: dict) -> dict:
        print("[*] AOC 4 Parser initialized: Extracting full text...")
        doc_texts = {}
        
        # 1. First, extract text per document
        for doc_key, doc_path in docs.items():
            if not doc_path or not os.path.exists(doc_path):
                continue
                
            basename = os.path.basename(doc_path).lower()
            text_content = ""
            
            # Native DOCX
            if basename.endswith(".docx") or basename.endswith(".doc"):
                print(f"[*] AOC 4 Parser: Extracting text natively from {basename}")
                text_content = self.extract_docx_text(doc_path)
                
            # Native Excel (AOC4 only)
            elif basename.endswith(".xlsx") or basename.endswith(".xls"):
                print(f"[*] AOC 4 Parser: Extracting text natively from {basename}")
                text_content = self.extract_excel_text(doc_path)
                
            # Native PDF (pdfplumber) or OCR Markdown
            elif basename.endswith(".pdf"):
                original_basename = os.path.basename(doc_path)
                if ocr_outputs and original_basename in ocr_outputs:
                    md_path = ocr_outputs[original_basename].get("md")
                    if md_path and os.path.exists(md_path):
                        print(f"[*] AOC 4 Parser: Extracting from Marker OCR Markdown for {basename}")
                        with open(md_path, "r", encoding="utf-8") as f:
                            text_content = f.read()
                if not text_content:
                    print(f"[*] AOC 4 Parser: Extracting natively from PDF {basename}")
                    try:
                        with pdfplumber.open(doc_path) as pdf:
                            for page in pdf.pages:
                                t = page.extract_text()
                                if t: text_content += t + "\n"
                    except Exception as e:
                        print(f"[!] Error parsing PDF {basename}: {e}")
            
            # Markdown directly
            elif basename.endswith(".md"):
                print(f"[*] AOC 4 Parser: Reading Markdown file {basename}")
                try:
                    with open(doc_path, "r", encoding="utf-8") as f:
                        text_content = f.read()
                except Exception as e:
                    print(f"[!] Error reading MD {basename}: {e}")
            
            if text_content:
                doc_texts[doc_key] = (basename, text_content)

        # 2. Detect Financial Statements Target Year
        fs_target_year = None
        if "financials" in doc_texts:
            fn, fc = doc_texts["financials"]
            fs_target_year = self._detect_financials_target_year(fc, fn)
            if fs_target_year:
                print(f"[*] AOC 4 Parser: Identified Primary Financial Statements Target Year = FY {fs_target_year-1}-{str(fs_target_year)[-2:]} (31st March, {fs_target_year})")

        # 3. Detect and Validate Audit Reports
        # An audit report is considered valid if:
        # - Any non-prior-year uploaded doc containing an audit report matches fs_target_year
        # - Or if no audit report is detected at all (audit_report_valid remains True, other rules check presence)
        # It is ONLY flagged as Invalid Input (mismatched) if:
        # - An audit report was uploaded, but NO uploaded audit report matches fs_target_year,
        #   and at least one audit report was detected for a different year.
        audit_reports = []
        valid_texts = []

        for doc_key, (basename, text_content) in doc_texts.items():
            is_prev_year_doc = any(k in doc_key.lower() for k in ["prev", "previous", "prior", "last_year", "py_"]) or any(k in basename.lower() for k in ["prev", "previous", "prior", "last_year", "last year", "old", "py_"])
            
            has_audit_keywords = any(k in text_content.lower() for k in ["independent auditor", "auditor's report", "auditors report", "report on the standalone financial"])
            
            if not is_prev_year_doc and has_audit_keywords:
                doc_audit_year = self._detect_audit_report_year(text_content, basename)
                audit_reports.append((doc_key, basename, text_content, doc_audit_year))
            else:
                valid_texts.append(text_content)

        audit_report_valid = True
        audit_report_error = None

        if audit_reports:
            matching_reports = [r for r in audit_reports if r[3] and fs_target_year and r[3] == fs_target_year]
            if matching_reports:
                audit_report_valid = True
                audit_report_error = None
                for r in matching_reports:
                    valid_texts.append(r[2])
                for r in audit_reports:
                    if not r[3]:
                        valid_texts.append(r[2])
            else:
                mismatched_years = [r[3] for r in audit_reports if r[3] and fs_target_year and r[3] != fs_target_year]
                if mismatched_years:
                    doc_audit_year = mismatched_years[0]
                    audit_report_valid = False
                    audit_report_error = f"Uploaded Audit Report is for FY {doc_audit_year-1}-{str(doc_audit_year)[-2:]} (ended 31st March, {doc_audit_year}), which does not match Current Year Financial Statements (FY {fs_target_year-1}-{str(fs_target_year)[-2:]} ended 31st March, {fs_target_year})."
                    print(f"  [!] AOC 4 Parser: Disqualifying mismatched Audit Report: {audit_report_error}")
                else:
                    for r in audit_reports:
                        valid_texts.append(r[2])

        full_text = "\n\n".join(valid_texts)

        # Extract CIN and determine if listed
        cin_match = re.search(r'\b([LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b', full_text, re.IGNORECASE)
        extracted_data = {
            "full_text": full_text,
            "docs": docs,
            "financials_target_year": fs_target_year,
            "audit_report_valid": audit_report_valid,
            "audit_report_error": audit_report_error
        }
        
        if cin_match:
            cin_number = cin_match.group(1).upper()
            extracted_data["cin_number"] = cin_number
            if cin_number.startswith("L"):
                extracted_data["is_listed"] = "yes"
            elif cin_number.startswith("U"):
                extracted_data["is_listed"] = "no"

        # ── MCA Masterdata extraction ─────────────────────────────────────────
        # Parse Authorised Capital and Paid up Capital from any MCA masterdata
        # markdown table (e.g. "Masterdata as on ...md") so the error checker
        # can perform a numerical MCA vs FS cross-verification instead of
        # returning "Missing Data".
        mca_fields = self._extract_mca_masterdata(full_text)
        for k, v in mca_fields.items():
            if v is not None:
                extracted_data[k] = v

        return extracted_data

    def _detect_financials_target_year(self, text: str, filename: str = "") -> int | None:
        """Detects reporting year from Financial Statements content or filename."""
        cleaned = re.sub(r'<[^>]+>', '', text)
        patterns = [
            r'(?:balance\s+sheet\s+as\s+at|statement\s+of\s+profit\s+and\s+loss.*?for\s+the\s+year\s+ended|for\s+the\s+year\s+ended|ended\s+on)\s+(?:31st?\s+march,?\s+|march,?\s+)?(20\d{2})',
            r'(?:as\s+at\s+31st?\s+march,?\s+|march,?\s+)(20\d{2})',
            r'(?:31st?\s+march,?\s+)(20\d{2})'
        ]
        for pat in patterns:
            m = re.search(pat, cleaned, re.IGNORECASE)
            if m:
                return int(m.group(1))
        if filename:
            fn_lower = filename.lower()
            m_fn = re.search(r'(?:20|fy[-_]?)(\d{2})[-_ ]+(\d{2})', fn_lower)
            if m_fn:
                return 2000 + int(m_fn.group(2))
            m_fn4 = re.search(r'(20\d{2})', fn_lower)
            if m_fn4:
                return int(m_fn4.group(1))
        return None

    def _detect_audit_report_year(self, text: str, filename: str = "") -> int | None:
        """Detects the audited (primary) year from an Independent Auditor's Report.
        
        Strategy: strip HTML tags (handles <sup>st</sup> etc.), then take the MAXIMUM
        year found in '31st March YYYY' or 'March 31, YYYY' mentions within the auditor's
        opinion/intro block. This ensures prior-year references (in 'Other Matter',
        comparative clauses, CARO notes, etc.) don't override the primary year.
        Falls back to max year across the full doc, then the filename.
        """
        # Strip HTML tags first — handles <sup>st</sup>, <b>, <i>, etc.
        cleaned = re.sub(r'<[^>]+>', '', text)
        
        # Regex that captures BOTH date formats:
        #   "31st March, 2026" / "31st March 2026"  (Indian format)
        #   "March 31, 2026"                         (US/alternate format)
        date_pattern = r'(?:31st?\s+march[,\s]+|march\s+31[,\s]+)(20\d{2})'
        
        # Priority 1: Scan the Opinion/Intro block (~2000 chars after the report heading)
        opinion_block = re.search(
            r'(?:independent\s+auditors?\'?s?\s+report|report\s+of\s+(?:the\s+)?independent\s+auditors?)'
            r'.{0,2000}',
            cleaned, re.I | re.DOTALL
        )
        if opinion_block:
            years_in_opinion = [int(y) for y in re.findall(date_pattern, opinion_block.group(0), re.I)]
            if years_in_opinion:
                return max(years_in_opinion)

        # Priority 2: Canonical phrases that anchor the primary audit year
        anchor_patterns = [
            r'financial\s+position\s+of\s+the\s+company\s+as\s+at\s+' + date_pattern,
            r'which\s+comprises?\s+the\s+balance\s+sheet\s+as\s+at\s+' + date_pattern,
            r'balance\s+sheet\s+as\s+at\s+' + date_pattern,
        ]
        for pat in anchor_patterns:
            m = re.search(pat, cleaned, re.I)
            if m:
                return int(m.group(1))

        # Priority 3: Max year from ALL date mentions in the full doc
        all_years = [int(y) for y in re.findall(date_pattern, cleaned, re.I)]
        if all_years:
            return max(all_years)

        # Fallback: filename
        return self._detect_financials_target_year(text, filename)


    def _extract_mca_masterdata(self, full_text: str) -> dict:
        """
        Scans the full merged OCR text for MCA Master Data table rows and
        extracts Authorised Capital, Paid up Capital, and Face Value.
        Returns a dict with keys:
            mca_authorised_capital  – float (rupees)
            mca_paid_up_capital     – float (rupees)
            mca_face_value          – float (rupees per share, optional)
        """
        result = {
            "mca_authorised_capital": None,
            "mca_paid_up_capital": None,
            "mca_face_value": None,
            "mca_small_company": None,
            "has_corporate_shareholders": None,
        }

        def _parse_inr(raw: str):
            """Strip commas, parentheses, Rs / ₹ symbols and return float."""
            if not raw:
                return None
            cleaned = re.sub(r'[₹RsINR,\s]', '', raw.strip())
            cleaned = re.sub(r'\((\d[\d.]*)\)', r'-\1', cleaned)   # (1000) → -1000
            try:
                return float(cleaned)
            except ValueError:
                return None

        lines = full_text.split("\n")
        for line in lines:
            line_lower = line.lower()

            # Skip financial-statement lines (share capital notes, balance sheet rows)
            # to avoid picking up figures from the annual report tables.
            if re.search(r'notes?\s+to\s+(the\s+)?financial|balance sheet|profit.*loss|cash flow|statement of', line_lower):
                continue

            # ── Authorised Capital ──
            if result["mca_authorised_capital"] is None:
                if re.search(r'authori[sz]ed\s*(share\s*)?capital', line_lower):
                    numbers = re.findall(r'[\d,]+(?:\.\d+)?', line)
                    for num_str in reversed(numbers):
                        val = _parse_inr(num_str)
                        if val and val >= 10_000:
                            result["mca_authorised_capital"] = val
                            print(f"[*] MCA Masterdata: Authorised Capital = {val}")
                            break

            # ── Paid up Capital ──
            if result["mca_paid_up_capital"] is None:
                if re.search(r'paid[\s\-]*up\s*(share\s*)?capital', line_lower):
                    numbers = re.findall(r'[\d,]+(?:\.\d+)?', line)
                    for num_str in reversed(numbers):
                        val = _parse_inr(num_str)
                        if val and val >= 10_000:
                            result["mca_paid_up_capital"] = val
                            print(f"[*] MCA Masterdata: Paid up Capital = {val}")
                            break

            # ── Face Value ──
            if result["mca_face_value"] is None:
                if re.search(r'face\s*value', line_lower):
                    numbers = re.findall(r'[\d,]+(?:\.\d+)?', line)
                    for num_str in numbers:
                        val = _parse_inr(num_str)
                        if val and 1 <= val <= 1000:
                            result["mca_face_value"] = val
                            print(f"[*] MCA Masterdata: Face Value = {val}")
                            break

            # ── Small Company Indicator ──
            if result["mca_small_company"] is None:
                if re.search(r'small\s*company', line_lower) and ("|" in line or ":" in line):
                    if re.search(r'\b(no|n)\b', line_lower):
                        result["mca_small_company"] = "no"
                        print("[*] MCA Masterdata: Small Company = No")
                    elif re.search(r'\b(yes|y)\b', line_lower):
                        result["mca_small_company"] = "yes"
                        print("[*] MCA Masterdata: Small Company = Yes")

        # ── Detect Corporate Shareholders in text ──
        if any(corp in full_text.lower() for corp in ["gmbh", "pte ltd", "private limited", "limited", "corp", "inc", "llc", "holding company"]):
            result["has_corporate_shareholders"] = "yes"
        else:
            result["has_corporate_shareholders"] = "no"

        return result


    def _clean_table_cell_numeric(self, val_str: str):
        if not val_str or str(val_str).strip() in ['-', '--', '—', 'Nil', 'NIL', 'None', '', 'NA', 'N/A']:
            return 0.0
        val_str = str(val_str).strip()
        is_neg = False
        if val_str.startswith('(') and val_str.endswith(')'):
            is_neg = True
            val_str = val_str[1:-1]
        elif val_str.startswith('-'):
            is_neg = True
            val_str = val_str[1:]
        
        # Strip currency symbols and formatting commas
        val_str = re.sub(r'[^\d.]', '', val_str)
        try:
            val = float(val_str)
            return -val if is_neg else val
        except ValueError:
            return None

    def extract_from_ocr_markdown_tables(self, md_text: str) -> dict:
        """Extracts structured financial metrics directly from Markdown tables produced by Marker OCR."""
        extracted = {}
        lines = md_text.split('\n')
        current_table = []
        
        for l in lines:
            if l.strip().startswith('|') and l.strip().endswith('|'):
                if re.match(r'^\s*\|(?:\s*:?-+:?\s*\|)+\s*$', l):
                    continue
                current_table.append(l)
            else:
                if len(current_table) >= 2:
                    self._process_ocr_table(current_table, extracted)
                current_table = []
        if len(current_table) >= 2:
            self._process_ocr_table(current_table, extracted)
        return extracted

    def _process_ocr_table(self, table_rows: list, extracted: dict):
        grid = []
        for r in table_rows:
            cells = [c.strip() for c in r.split('|')[1:-1]]
            grid.append(cells)
        
        if not grid:
            return
            
        full_table_text = ' '.join([' '.join(row) for row in grid]).lower()
        
        is_bs = any(k in full_table_text for k in ['equity and liabilities', "shareholders' funds", 'non-current assets', 'current assets'])
        is_pl = any(k in full_table_text for k in ['revenue from operation', 'total revenue', 'total income', 'profit before tax', 'expenses'])
        is_share_cap = any(k in full_table_text for k in ['authorised', 'issued, subscribed', 'equity share capital', 'share capital']) and not is_bs
        is_rpt = any(k in full_table_text for k in ['related party', 'key management', 'kmp', 'remuneration paid', 'managerial remuneration'])
        
        for row in grid:
            if len(row) < 2:
                continue
            particulars = row[0].lower().strip()
            
            # Numeric cells in this row
            num_cells = []
            for c in row[1:]:
                val = self._clean_table_cell_numeric(c)
                if val is not None:
                    num_cells.append(val)
                    
            if not num_cells:
                continue
                
            cy_val = None
            py_val = None
            
            # If 3+ numbers: Note No, CY, PY
            if len(num_cells) >= 3 and 1 <= num_cells[0] <= 50 and float(num_cells[0]).is_integer():
                cy_val = num_cells[1]
                py_val = num_cells[2]
            elif len(num_cells) == 2:
                cy_val = num_cells[0]
                py_val = num_cells[1]
            elif len(num_cells) == 1:
                cy_val = num_cells[0]
                
            if cy_val is None:
                continue
                
            if is_bs:
                if re.search(r'\bshare capital\b', particulars) and 'shareholders' not in particulars and 'paid_up_capital' not in extracted:
                    extracted['paid_up_capital'] = cy_val
                    if py_val is not None: extracted['prev_paid_up_capital'] = py_val
                elif re.search(r'\breserves?\s*(?:&|and)\s*surplus\b', particulars) and 'reserves_and_surplus' not in extracted:
                    extracted['reserves_and_surplus'] = cy_val
                    if py_val is not None: extracted['prev_reserves_and_surplus'] = py_val
                elif re.search(r'\blong[\s-]term borrowings?\b', particulars) and 'long_term_borrowings' not in extracted:
                    extracted['long_term_borrowings'] = cy_val
                    if py_val is not None: extracted['prev_long_term_borrowings'] = py_val
                elif re.search(r'\bshort[\s-]term borrowings?\b', particulars) and 'short_term_borrowings' not in extracted:
                    extracted['short_term_borrowings'] = cy_val
                    if py_val is not None: extracted['prev_short_term_borrowings'] = py_val
                elif re.search(r'\bnon[\s-]current investments\b', particulars) and 'investments_made' not in extracted:
                    extracted['investments_made'] = cy_val
                    if py_val is not None: extracted['prev_investments_made'] = py_val
                elif re.search(r'\bcurrent investments\b', particulars) and ('investments_made' not in extracted or extracted.get('investments_made') == 0):
                    extracted['investments_made'] = cy_val
                    if py_val is not None: extracted['prev_investments_made'] = py_val
                elif re.search(r'\b(?:loans? given to directors?|loans? to directors?)\b', particulars) and 'loan_to_directors_assets' not in extracted:
                    extracted['loan_to_directors_assets'] = cy_val
                elif re.search(r'\btotal (?:outstanding dues of )?micro and small enterprises\b', particulars) and 'dues_to_msme' not in extracted:
                    extracted['dues_to_msme'] = cy_val
                elif re.search(r'\badvance from customers\b', particulars) and 'advance_from_customers' not in extracted:
                    extracted['advance_from_customers'] = cy_val
            elif is_pl:
                if re.search(r'\brevenue from operations?\b', particulars) and 'turnover' not in extracted:
                    extracted['turnover'] = cy_val
                    if py_val is not None: extracted['prev_turnover'] = py_val
                elif re.search(r'\btotal (?:revenue|income)\b', particulars) and 'total_revenue' not in extracted:
                    extracted['total_revenue'] = cy_val
                    if py_val is not None: extracted['prev_total_revenue'] = py_val
                elif re.search(r'\bprofit before (?:exceptional.*tax|tax)\b', particulars) and 'net_profit_before_tax' not in extracted:
                    extracted['net_profit_before_tax'] = cy_val
                    if py_val is not None: extracted['prev_net_profit_before_tax'] = py_val
                elif re.search(r'\bprofit.*?(?:for the (?:period|year)|after tax)\b', particulars) and 'net_profit_after_tax' not in extracted:
                    extracted['net_profit_after_tax'] = cy_val
                    if py_val is not None: extracted['prev_net_profit_after_tax'] = py_val
            elif is_share_cap:
                if re.search(r'\bissued, subscribed\b', particulars) and 'paid_up_capital' not in extracted:
                    extracted['paid_up_capital'] = cy_val
                    if py_val is not None: extracted['prev_paid_up_capital'] = py_val
                elif re.search(r'\bauthorised\b', particulars) and 'authorised_capital' not in extracted:
                    extracted['authorised_capital'] = cy_val
            elif is_rpt:
                if re.search(r'\b(?:sale of goods|sale of materials?|supply of goods)\b', particulars) and 'rpt_sale_goods' not in extracted:
                    extracted['rpt_sale_goods'] = cy_val
                elif re.search(r'\b(?:purchase of goods|purchase of materials?|purchase or supply of goods)\b', particulars) and 'rpt_purchase_goods' not in extracted:
                    extracted['rpt_purchase_goods'] = cy_val
                elif re.search(r'\b(?:sale of property|sale of (?:fixed )?assets?)\b', particulars) and 'rpt_sale_property' not in extracted:
                    extracted['rpt_sale_property'] = cy_val
                elif re.search(r'\b(?:purchase of property|purchase of (?:fixed )?assets?)\b', particulars) and 'rpt_purchase_property' not in extracted:
                    extracted['rpt_purchase_property'] = cy_val
                elif re.search(r'\b(?:dispos(?:al|e) of property|transfer of property|dispos(?:al|e) of assets?)\b', particulars) and 'rpt_dispose_property' not in extracted:
                    extracted['rpt_dispose_property'] = cy_val
                elif re.search(r'\b(?:availing of services?|services? availed|charges for availing services?|receiving of services?)\b', particulars) and 'rpt_availing_service' not in extracted:
                    extracted['rpt_availing_service'] = cy_val
                elif re.search(r'\b(?:rendering of services?|services? rendered|charges for rendering services?|providing of services?)\b', particulars) and 'rpt_rendering_service' not in extracted:
                    extracted['rpt_rendering_service'] = cy_val
                elif re.search(r'\b(?:rent\b|lease\b|rental\b|lease rent)\b', particulars) and 'rpt_lease' not in extracted:
                    extracted['rpt_lease'] = cy_val
                elif re.search(r'\b(?:remuneration|salary|sitting fee|managerial remuneration|director remuneration)\b', particulars) and 'rpt_monthly_remun' not in extracted:
                    extracted['rpt_monthly_remun'] = cy_val
                elif re.search(r'\b(?:underwriting|remuneration for underwriting|underwriting commission)\b', particulars) and 'rpt_remuneration_underwriting' not in extracted:
                    extracted['rpt_remuneration_underwriting'] = cy_val
                elif re.search(r'\b(?:loan from directors?|unsecured loan)\b', particulars) and 'loan_from_directors' not in extracted:
                    extracted['loan_from_directors'] = cy_val

    def extract_financials_from_text(self, text: str, missing_keys: list) -> dict:
        """Extracts financial data strictly using structured OCR Markdown tables first, with secondary fallback."""
        print(f"[*] AOC 4 Parser: Attempting text fallback extraction for: {missing_keys}")
        
        # ── TIER 1: Structured OCR Markdown Table Extractor ──
        table_data = self.extract_from_ocr_markdown_tables(text)
        found_data = {}
        for k, v in table_data.items():
            if v is not None:
                found_data[k] = v
                print(f"    [+] Table Extracted '{k}' = {v}")
                
        # Update missing keys list
        remaining_missing = [k for k in missing_keys if k not in found_data]
        if not remaining_missing:
            return found_data
            
        numeric_keywords = {
            "total_revenue": [r"total revenue", r"total income", r"revenue and other income"],
            "turnover": [r"revenue from operation", r"total turnover", r"sales turnover", r"gross turnover", r"turnover"],
            "prev_turnover": [r"previous year turnover", r"turnover.*previous year"],
            "authorised_capital": [r"authorised.*capital", r"authorized.*capital", r"authorised share capital", r"authorized share capital", r"\bauthorised\b", r"\bauthorized\b"],
            "paid_up_capital": [r"(?<!authorised\s)(?<!authorized\s)share capital", r"paid.?up.*capital", r"paid up share capital", r"subscribed and paid up", r"equity share capital", r"preference share capital"],
            "reserves_and_surplus": [r"reserves?\s*(?:and|&)\s*surplus", r"other equity", r"retained earnings"],
            "borrowings": [r"total borrowing", r"total borrowings", r"borrowing", r"borrowings", r"long term borrowing", r"short term borrowing", r"long term borrowings", r"short term borrowings", r"secured loans", r"unsecured loans", r"loan from bank", r"loan from director", r"secured loan", r"unsecured loan"],
            "loan_to_directors_assets": [r"loans given by company to directors", r"loan given by company to directors", r"loangiven by company to directors", r"loan given by company to director", r"loan to directors"],
            "secured_loan": [r"\bsecured loan", r"\bsecured loans", r"\bsecured borrowings", r"^secured$", r"^secured\b", r"term loan taken during the year", r"^term loans?$"],
            "loan_from_directors": [r"loan from directors", r"loan from director", r"loan from shareholders", r"unsecured loan from director", r"unsecured loan taken", r"due to directors", r"loans from relatives of directors"],
            "unsecured_loan": [r"unsecured loan", r"unsecured borrowings"],
            "advance_from_customers": [r"advance from customers", r"advance from shareholders", r"security deposits"],
            "operating_profit": [r"operating profit", r"profit before interest", r"ebitda"],
            "net_profit_before_tax": [r"profit before tax", r"profit before exceptional items", r"pbt", r"profit.*?before.*?tax", r"profit/\s*\(loss\)\s*before\s*tax"],
            "net_profit_after_tax": [r"total profit.*?for the period", r"profit.*?\(loss\)\s*for the period", r"profit for the period", r"profit.*?for the year from continuing operations", r"profit.*?\(loss\).*?for the year from continuing", r"profit for the year", r"profit after tax", r"profit/.*?\(loss\).*?for the year", r"profit.*?after.*?tax"],
            "rpt_monthly_remun": [r"remuneration paid to directors", r"directors remuneration", r"remuneration to directors", r"managerial remuneration", r"remuneration.*director", r"monthly remuneration", r"annual remuneration", r"appointment to any office", r"salary", r"director remuneration"],
            "rpt_monthly_remun_2": [r"remuneration.*director.*2", r"second director.*remuneration", r"wtd.*remuneration", r"salary.*wtd"],
            "rpt_lease": [r"lease\b", r"\brent\b", r"rental", r"lease rent", r"lease payments", r"premises rent", r"office rent"],
            "rpt_sale_goods": [r"sale of goods", r"sale of materials?", r"supply of goods", r"sales to related part(?:y|ies)", r"sale of products?"],
            "rpt_purchase_goods": [r"purchase of goods", r"purchase of materials?", r"purchase or supply of goods", r"supply of materials?", r"purchases from related part(?:y|ies)", r"purchase of raw materials?"],
            "rpt_sale_property": [r"sale of property", r"sale of fixed assets?", r"sale of immovable property", r"sale of assets?", r"sale of land", r"sale of building"],
            "rpt_purchase_property": [r"purchase of property", r"purchase of fixed assets?", r"purchase of immovable property", r"purchase of assets?", r"purchase of land", r"purchase of building"],
            "rpt_dispose_property": [r"dispos(?:al|e) of property", r"transfer of property", r"dispos(?:al|e) of assets?", r"dispos(?:al|e) of fixed assets?", r"transfer of assets?"],
            "rpt_availing_service": [r"availing of services?", r"services? availed", r"service charges paid", r"charges for availing services?", r"charges paid for services?", r"receiving of services?", r"receiving services?"],
            "rpt_rendering_service": [r"rendering of services?", r"services? rendered", r"service charges received", r"charges for rendering services?", r"charges received for services?", r"providing of services?", r"providing services?"],
            "rpt_remuneration_underwriting": [r"remuneration for underwriting", r"underwriting commission", r"underwriting remuneration", r"underwriting.*subscription", r"underwriting of securities"],
            "loan_given_by_company": [r"loans given by company", r"loan given by company", r"loans to related parties", r"inter company loan", r"inter corporate deposit.*given", r"icd given"],
            "investments_made": [r"investments made by company", r"investment made by company", r"non.current investments", r"non current investments", r"(?<!non-)(?<!non )current investments", r"investment in subsidiaries", r"investment in associates"],
            "total_loans_investments_given": [r"total loans.*given", r"loans and advances given"],
            "corporate_guarantees": [r"corporate guarantees? given", r"guarantees? given by company", r"guarantees? given", r"guarantees"],
            "borrowing_defaults": [r"default in repayment", r"borrowing default"],
            "has_corporate_shareholders": [r"corporate shareholder", r"holding more than 10%", r"shareholding pattern"],
            "export_sales": [r"export turnover", r"revenue from export", r"fob value of exports", r"export of services", r"export services", r"export of service", r"exports", r"earnings in foreign exchange", r"earnings in foreign currency", r"foreign currency", r"foreign exchange", r"forex"],
            "sitting_fees": [r"sitting fee", r"directors sitting fee", r"director sitting fee", r"sitting fees to directors"]
        }
        
        lines = text.lower().split("\n")
        
        # Pre-compute board report sections so we can quickly check if a line is inside one
        in_board_report_lines = [False] * len(lines)
        in_br = False
        for i, line in enumerate(lines):
            if re.search(r'^(#+\s*)?(board(\'s)? report|directors?\'? report)', line):
                in_br = True
            elif re.search(r'^(#+\s*)?(independent auditor\'s report|notes to the financial statements|balance sheet|statement of profit)', line):
                in_br = False
            in_board_report_lines[i] = in_br
        
        for key in missing_keys:
            if key not in numeric_keywords:
                continue
                
            patterns = numeric_keywords[key]
            valid_number = None
            
            # Search entire document for highest priority pattern first
            for pattern in patterns:
                for idx, line in enumerate(lines):
                    # Strictly enforce Financial Statements as the only input source for all compliance fields
                    if in_board_report_lines[idx]:
                        continue
                        
                    if re.search(pattern, line):
                        # Skip income-tax computation lines that contain 'total income' 
                        # but are not the P&L total income (e.g., 'Gross Total Income', 'Net Total Income')
                        if key == "total_revenue" and re.search(r'gross total income|net total income|brought forward loss|deduction under chapter', line):
                            continue
                            
                        # Skip Auditor boilerplate lines that cause false positives (e.g. 'less than Rs.50 Crores')
                        if re.search(r'crores|lakhs|is exempted|notification dated|last audited financial statements|section 197', line):
                            continue
                            
                        # Skip cash flow lines for borrowings to prevent extracting 'Proceeds from borrowings'
                        if key in ["borrowings", "long_term_borrowings", "short_term_borrowings"] and re.search(r'proceeds from|repayment of|cash flow|borrowing cost', line):
                            continue

                        # Skip financial ratio table rows for PAT — they contain ':1' or '0.0x:1' values
                        # e.g. "Return on equity ratio | Profit for the year | 31.55:1" must not be picked as PAT
                        if key == "net_profit_after_tax" and re.search(r'\bratios?\b|:\s*\d+|return on|average total|per share|eps|\bbasic\b|\bdiluted\b', line):
                            continue

                        # Restrict all Related Party Transaction metrics to Related Party Transaction sections only
                        if key.startswith("rpt_"):
                            # Block actuarial/employee benefit assumptions
                            if re.search(r'growth|actuarial|discount rate|mortality|employee benefit|gratuity|leave encashment', line):
                                continue
                            
                            is_rpt_section = False
                            start_check = max(0, idx - 60)
                            for check_idx in range(idx, start_check, -1):
                                l_text = lines[check_idx]
                                if re.search(r'cash flow|balance sheet|statement of profit', l_text):
                                    break
                                if re.search(r'related part(y|ies)|as\s*18|ind\s*as\s*24', l_text):
                                    is_rpt_section = True
                                    break
                            if not is_rpt_section:
                                continue

                        # Found a keyword match. Extract all numbers on this line AFTER the keyword.
                        match_obj = re.search(pattern, line)
                        search_text = line[match_obj.start():]
                        
                        # In single-line OCR layouts, a line may contain multiple labels and values (e.g., "(a) Label 1 (b) Label 2 100 200").
                        # If we matched Label 1, we must NOT pick up Label 2's values. Truncate search_text if we hit a new label marker.
                        after_kw = search_text[len(match_obj.group()):]
                        next_label_match = re.search(r'\s\([a-z]\)\s|\s\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)\s|\s\d+\.\s', after_kw)
                        if next_label_match:
                            search_text = search_text[:len(match_obj.group()) + next_label_match.start()]
                        
                        # Strip out quantities of shares to prevent extracting them as currency values
                        search_text = re.sub(r'\d+(?:,\d+)*\s*(?:equity\s*shares?|preference\s*shares?|shares?)', '', search_text)
                        
                        # Strip out percentages (e.g. 7.00%, 15%) to prevent extracting them as currency amounts
                        search_text = re.sub(r'\(?\d+(?:,\d+)*(?:\.\d+)?\)?\s*%', '', search_text)
                        
                        # Look ahead up to 2 lines ONLY for multi-line wrapped cells (e.g. P&L items).
                        # For balance sheet row items (where the label appears on a standalone line with
                        # no value, meaning the item is NIL/zero), do NOT look ahead - it would
                        # incorrectly pick up the next row's value!
                        has_numbers = bool(re.findall(r'(-?\s*(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?|\((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?\))', line))
                        
                        # Detect balance-sheet style rows: line contains a letter like (a), (b), (c)
                        # followed by label but no number — this means value is blank/nil in the table.
                        is_bs_row_no_value = bool(re.match(r'^\s*\(?[a-z]\)?[.)\s]', line)) and not has_numbers
                        
                        if not has_numbers and not is_bs_row_no_value and not line.strip().startswith("|"):
                            for i in range(1, 3):
                                if idx + i < len(lines):
                                    next_line = lines[idx + i]
                                    if next_line.strip().startswith("|"):
                                        break
                                    search_text += " " + next_line
                        
                        # If it's a blank balance sheet row, record 0 and move on
                        if is_bs_row_no_value:
                            valid_number = 0.0
                            print(f"    -> Found fallback '{key}' = 0.0 (Blank/Nil row: '{pattern}')")
                            break
                            
                        # CRITICAL: Never extract Authorized capital as Paid Up Capital
                        if key == "paid_up_capital" and re.search(r'authori[sz]ed', search_text.lower()):
                            continue

                        # CRITICAL: Ignore statutory narrative / checklist questions (e.g. CARO questions, Board approvals, MGT-7 questions)
                        # when searching for Balance Sheet / Financial Asset & Liability items
                        if key in ["loan_to_directors_assets", "loan_given_by_company", "corporate_guarantees", "investments_made", "secured_loan", "dues_to_msme"]:
                            if re.search(r'\b(?:approval|shareholders?|whether|pursuant to|in accordance with|provisions of|falling under|compliance with|referred in|terms of section)\b', search_text, flags=re.I):
                                continue
                                     
                        # Convert standalone dashes that are table cell values (between | pipes) to '0'
                        # Only replace dashes surrounded by pipes: | - | → | 0 |
                        # This avoids replacing mathematical dashes like in 'Profit before tax (VII - VIII)'
                        search_text = re.sub(r'(?<=\|)\s*-\s*(?=\|)', ' 0 ', search_text)
                        
                        # Strip out statutory sections and legal references (e.g. Under S 185, Section 185, Sec 186, Section 135, u/s 185, Clause 4, Rule 11)
                        search_text = re.sub(r'\b(?:under\s+s(?:ec)?\.?|u/s\.?|u/sec\.?|u/section\.?|s(?:ec)?\.?|sections?|clauses?|rules?|schedules?|sch\.?)\s*\d+[a-z0-9\(\)]*\b', '', search_text, flags=re.I)
                        # Strip out section references like '185 of the Act'
                        search_text = re.sub(r'\b\d+[a-z0-9\(\)]*\s+(?:of\s+the\s+(?:companies\s+)?act)\b', '', search_text, flags=re.I)
                        # Strip out Act/Order/Circular/Notification reference numbers
                        search_text = re.sub(r'\b(?:acts?|regulations?|orders?|notifications?|cir(?:cular)?\.?)\s*(?:no\.?|of)?\s*\d+[a-z0-9\(\)]*\b', '', search_text, flags=re.I)
                        # Strip out FY / AY references (e.g. FY 2024-25, AY 2025)
                        search_text = re.sub(r'\b(?:fy|ay)\s*\d{2,4}(?:-\d{2,4})?\b', '', search_text, flags=re.I)

                        # Convert 'Nil' / 'NIL' / 'None' to 0 (after stripping section numbers)
                        search_text = re.sub(r'\b(?:nil|none)\b', ' 0 ', search_text, flags=re.I)
                        
                        # Strip out dates (e.g. 31.03.2025, 31/03/2024, 2024-03-31) to prevent extracting them as numbers
                        search_text = re.sub(r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b', '', search_text)
                        
                        # Fix OCR artifact: Indian numbers with dots instead of commas
                        # e.g. '3.27.991' should be '3,27,991' — pattern: digit.2digits.3digits
                        search_text = re.sub(r'(\d+)\.(\d{2})\.(\d{3})\b', r'\1,\2,\3', search_text)
                        
                        numbers = re.findall(r'(-?\s*(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?|\((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?\))', search_text)
                        if not numbers:
                            continue
                            
                        for num_idx, num_str in enumerate(numbers):
                            clean_num = num_str.replace(",", "").replace(" ", "")
                            try:
                                if clean_num.startswith("(") and clean_num.endswith(")"):
                                    val = -float(clean_num[1:-1])
                                else:
                                    val = float(clean_num)
                            except ValueError:
                                continue
                                
                            # Filter out likely note numbers (e.g. 1, 14, 2, 6.1)
                            if val != 0 and 1 <= val < 100:
                                if "." not in clean_num and val < 50:
                                    continue
                                # If it has a decimal (e.g. 6.1) and is the very first number, check if the next number is 10x larger
                                if "." in clean_num and num_idx == 0 and len(numbers) > 1:
                                    next_num_str = numbers[1].replace(",", "").replace(" ", "")
                                    try:
                                        next_val = abs(float(next_num_str.strip("()")))
                                        if next_val > val * 10:
                                            continue
                                    except:
                                        pass
                                
                            # Filter out calendar years (1990 to 2035) for financial values (abs handles negative dashes like -2025)
                            if 1990 <= abs(val) <= 2035 and "." not in clean_num:
                                continue

                            # Skip zero if non-zero numbers appear later in the list
                            # (handles note-column '| - |' converted to 0 appearing before the actual value)
                            if val == 0:
                                remaining = numbers[num_idx + 1:]
                                # Only skip if there are at least TWO numbers ahead (Current + Previous)
                                # This ensures we don't accidentally skip a valid '0' Current Year when Previous Year is non-zero
                                if len(remaining) >= 2:
                                    has_nonzero_ahead = any(
                                        float(n.replace(",", "").replace(" ", "").strip("()")) != 0
                                        for n in remaining
                                        if n.replace(",", "").replace(" ", "").strip("()")
                                    )
                                    if has_nonzero_ahead:
                                        continue
                                
                            valid_number = val
                            
                            # Also look for previous year comparative figure on the same table row
                            if not key.startswith("prev_"):
                                prev_valid_number = None
                                for next_num_str in numbers[num_idx + 1:]:
                                    next_clean = next_num_str.replace(",", "").replace(" ", "")
                                    try:
                                        if next_clean.startswith("(") and next_clean.endswith(")"):
                                            n_val = -float(next_clean[1:-1])
                                        else:
                                            n_val = float(next_clean)
                                    except ValueError:
                                        continue
                                    if 1990 <= abs(n_val) <= 2035 and "." not in next_clean:
                                        continue
                                    prev_valid_number = n_val
                                    break
                                
                                if prev_valid_number is not None:
                                    prev_key = f"prev_{key}"
                                    found_data[prev_key] = prev_valid_number
                                    
                            break # Take the first valid number (usually current year)
                            
                    if valid_number is not None:
                        break # Found a valid number for this pattern, stop line search
                        
                if valid_number is not None:
                    if valid_number == 0.0:
                        # Store zero as a candidate, but keep searching subsequent patterns 
                        # in hopes of finding a non-zero value (e.g. if non-current is 0 but current is non-zero)
                        if key not in found_data:
                            found_data[key] = 0.0
                    else:
                        found_data[key] = valid_number
                        print(f"    -> Found fallback '{key}' = {valid_number} (Matched: {pattern})")
                        break # Found a non-zero value, stop searching patterns
                    
        # Filter out Board Report sections so holding and IND-AS checks are solely based on Financial Statements
        fs_lines = [line for idx, line in enumerate(lines) if not in_board_report_lines[idx]]
        fs_text = "\n".join(fs_lines)

        found_data["is_subsidiary_or_holding"] = self._evaluate_holding_status(fs_text)
        found_data["is_ind_as"] = self._evaluate_ind_as_status(fs_text)
        return found_data

    def _evaluate_holding_status(self, full_text: str) -> str:
        """Analyzes financial statements text to determine holding/subsidiary status."""
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
                print(f"[*] Holding/Subsidiary check: High confidence match on '{phrase}' (Holding)")
                return "holding"
        
        # Then check subsidiary
        for phrase in sub_phrases:
            if phrase in text:
                print(f"[*] Holding/Subsidiary check: High confidence match on '{phrase}' (Subsidiary)")
                return "subsidiary"
                
        # Step 3: Ownership Validation Check (>50%)
        ownership_matches = re.findall(r'(?:ownership|holding|subsidiary|investment).{0,50}?(\d{2,3}(?:\.\d+)?)\s*%', text)
        for match in ownership_matches:
            try:
                if float(match) > 50.0 and float(match) <= 100.0:
                    print(f"[*] Holding/Subsidiary check: Ownership > 50% match ({match}%)")
                    return "holding" # Usually means it holds an investment > 50%
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
                
        print(f"[*] Holding/Subsidiary check: Medium confidence score = {score}")
        if score >= 100:
            return "holding"
            
        return "no"

    def _evaluate_ind_as_status(self, full_text: str) -> str:
        """Analyzes full text to determine if IND AS applies based on Balance Sheet structure."""
        text = full_text.lower()
        
        # Step 1: Structural Check (Division II vs Division I format)
        # Strip out common markdown/HTML formatting that might disrupt regex
        clean_text = re.sub(r'[*_]|<b>|</b>|<br>', '', text)
        
        # Search for the first standalone row headers in the Balance Sheet table
        assets_match = re.search(r'\|\s*(?:[ivx\d\.\-\(\)]*\s*)?assets\s*\|', clean_text)
        liab_match = re.search(r'\|\s*(?:[ivx\d\.\-\(\)]*\s*)?(?:equity and liabilities|liabilities and equity|equity & liabilities)\s*\|', clean_text)
        
        if assets_match and liab_match:
            if assets_match.start() < liab_match.start():
                print(f"[*] IND AS check: Structural Match (Assets presented before Liabilities) -> Yes")
                return "yes"
            else:
                print(f"[*] IND AS check: Structural Match (Liabilities presented before Assets) -> No")
                return "no"
                
        # Step 2: Fallback Keyword Check
        text = re.sub(r'\s+', ' ', text)
        ind_as_phrases = [
            "indian accounting standard",
            "ind as",
            "companies (indian accounting standards) rules",
            "ind-as"
        ]
        
        for phrase in ind_as_phrases:
            # Add word boundaries to avoid matching "kind as" or similar
            if re.search(r'\b' + re.escape(phrase) + r'\b', text):
                print(f"[*] IND AS check: Fallback Keyword Match on '{phrase}' -> Yes")
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
        if re.search(r'(?i)(in hundreds?|amounts? (are )?in (?:indian )?rupees hundreds?|in (?:indian )?rupees hundreds?|amounts? (are )?in hundreds?|in hundreds? (of )?indian rupees|\(in hundreds?\))', text_lower):
            return "Hundreds"
            
        return "Actuals"
