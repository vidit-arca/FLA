import os
from datetime import datetime
from typing import Dict, Any

from .state import WorkflowState
from ..ingestion import DocumentIngestion
from ..excel_writer import ExcelWriter
from ..ocr_pipeline import OcrPipeline
from automation_engine.core.factory import ModuleFactory

BASE_OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "output"))

def node_ingest(state: WorkflowState) -> WorkflowState:
    msg = "[*] Stage 1: Scanning input directory..."
    print(msg)
    state["logs"].append(msg)
    input_dir = state["input_dir"]
    
    # Use existing ingestion logic to correctly classify docs into a dict
    ingestor = DocumentIngestion(input_dir, module_type=state.get("module_type", "fla"))
    docs = ingestor.find_documents()
    
    previous_fla_file = ""
    
    # find_documents() returns a dict, but any file named previous_fla_* might end up as an 'unknown_excel' or similar.
    # Let's manually pluck the previous_fla file out of the directory
    for filename in os.listdir(input_dir):
        if filename.startswith("previous_fla_") or "FLA_ONLINE_FORM" in filename:
            previous_fla_file = os.path.join(input_dir, filename)
            found_msg = f"  -> Found Previous Year FLA file: {filename}"
            print(found_msg)
            state["logs"].append(found_msg)
            break
            
    # docs is a dict like {'board_report': 'path/to/board.pdf', 'financial_excel': 'path/to/fin.xlsx'}
    state["financial_docs"] = docs
    # Pass previous FLA path explicitly into docs so parser.parse_all() can prefill Section I fields
    if previous_fla_file:
        state["financial_docs"]["previous_fla"] = previous_fla_file
    state["previous_fla_file"] = previous_fla_file
    state["ocr_outputs"] = {} # Initialize
    
    return state

def node_ocr(state: WorkflowState) -> WorkflowState:
    msg = "[*] Stage 1.5: Running Deep Learning OCR on PDFs..."
    print(msg)
    state["logs"].append(msg)
    
    ocr_outputs = {}
    ocr_pipeline = OcrPipeline()
    
    docs = state.get("financial_docs", {})
    for doc_key, doc_path in docs.items():
        if isinstance(doc_path, str) and doc_path.lower().endswith(".pdf"):
            log_msg = f"  -> Triggering Marker OCR for {doc_key} ({os.path.basename(doc_path)})"
            print(log_msg)
            state["logs"].append(log_msg)
            
            res = ocr_pipeline.process_pdf(doc_path)
            if res and res.get("md"):
                ocr_outputs[doc_key] = res
                succ_msg = f"    [+] OCR Complete. Markdown saved to: {res['md']}"
                print(succ_msg)
                state["logs"].append(succ_msg)
            else:
                err_msg = f"    [!] OCR Failed or returned no markdown for {doc_key}"
                print(err_msg)
                state["logs"].append(err_msg)
                
    # Also explicitly OCR the previous FLA file if it is a PDF
    prev_file = state.get("previous_fla_file", "")
    if prev_file.lower().endswith(".pdf"):
        log_msg = f"  -> Triggering Marker OCR for Previous FLA ({os.path.basename(prev_file)})"
        print(log_msg)
        state["logs"].append(log_msg)
        res = ocr_pipeline.process_pdf(prev_file)
        if res and res.get("md"):
            # Swap out the PDF path for the newly generated Markdown path so the Comparison Node can parse it!
            state["previous_fla_file"] = res["md"]
            succ_msg = f"    [+] OCR Complete for Previous FLA. Markdown saved to: {res['md']}"
            print(succ_msg)
            state["logs"].append(succ_msg)
                
    state["ocr_outputs"] = ocr_outputs
    return state

def node_extract(state: WorkflowState) -> WorkflowState:
    msg = "[*] Stage 2 & 3: Parsing documents and applying rules..."
    print(msg)
    state["logs"].append(msg)
    
    mod = ModuleFactory.get_module(state.get("module_type", "fla"))
    DocumentParser = mod["parser"]
    RuleEngine = mod["rule_engine"]
    
    parser = DocumentParser(mod["config_path"])
    extracted_data = parser.parse_all(state["financial_docs"], state.get("ocr_outputs", {}))
    
    rule_engine = RuleEngine(mod["config_path"])
    
    # --- Auto-fill from Previous Year FLA ---
    if state.get("previous_fla_file") and os.path.exists(state["previous_fla_file"]):
        try:
            from automation_engine.modules.fla.comparison_platform.modules.legacy_parser import LegacyFLAParser
            import re
            with open(state["previous_fla_file"], "r", encoding="utf-8", errors="ignore") as f:
                prev_data = LegacyFLAParser().parse_md(f.read())

            # Mapping of previous FLA field names (from parsed markdown) to internal extracted_data keys
            PREFILL_FIELD_MAP = {
                # Contact / metadata fields
                "Name of the Contact Person":               "contact_name",
                "Name of the Contact Person*":              "contact_name",
                "Telephone No. (with extension)":           "telephone",
                "Telephone No. (with extension)*":          "telephone",
                "Mobile Number":                            "mobile_number",
                "Mobile Number*":                           "mobile_number",
                "E-Mail ID (Head of the institution)":      "email_id",
                "E-Mail ID (Head of the institution)*":     "email_id",
                "E-Mail of Contact person":                 "email_contact",
                "E-Mail of Contact person*":                "email_contact",
                "Designation":                              "designation",
                "Designation*":                             "designation",
                "Website (if any)":                         "website",
                # Company identity
                "2. PAN number":                            "pan_number",
                "2. PAN number*":                           "pan_number",
                "Nature of Business":                       "nic_code",
                "Nature of Business*":                      "nic_code",
                # Status fields
                "Whether your company is merged/amalgamated during year":               "merged_status",
                "Whether your company is merged / amalgamated during the year*":        "merged_status",
                "Whether the company is listed?":                                       "listed_status",
                "Whether the company is listed?*":                                      "listed_status",
                "Identification of reporting company":                                  "inward_fdi_status",
                "Type of company":                                                      "company_type",
                "Type of company*":                                                     "company_type",
                "Whether the Company is Asset Management Company?":                     "amc_status",
                "Whether the Company is Asset Management Company?*":                    "amc_status",
                "Whether the Company has Technical Foreign collaboration?":             "tech_collab_status",
                "Whether the Company has Technical Foreign collaboration?*":            "tech_collab_status",
                "Whether the company has any business activity?":                       "business_activity_status",
                "Whether the company has any business activity?*":                      "business_activity_status",
            }

            # Fields that must ALWAYS be prefilled from previous FLA (even if value is empty string).
            # These fields have NO extraction logic in parser.py — the previous FLA is the only source.
            ALWAYS_PREFILL = {
                "contact_name",    # Name of the Contact Person
                "telephone",       # Telephone No. (with extension)
                "email_id",        # E-Mail ID (Head of institution)
                "email_contact",   # E-Mail of Contact Person
                "company_type",    # Type of company
                "website",         # Website (if any)
            }

            for prev_key, internal_key in PREFILL_FIELD_MAP.items():
                if prev_key in prev_data:
                    prev_val = prev_data[prev_key]
                    # For ALWAYS_PREFILL fields: copy even if value is empty
                    # For other fields: only copy if value is non-empty
                    has_value = bool(prev_val) or (internal_key in ALWAYS_PREFILL)
                    if has_value and (internal_key not in extracted_data or not extracted_data[internal_key]):
                        extracted_data[internal_key] = prev_val
                        msg = f"  [+] Auto-filled '{internal_key}' from Previous FLA: '{prev_val}'"
                        print(msg)
                        state["logs"].append(msg)


            # Special handling: Account Closing Date -> increment year
            for k, v in prev_data.items():
                ck = re.sub(r"[^a-z0-9]", "", str(k).lower())
                if "accountclosingdate" in ck:
                    date_str = str(v).strip()
                    if date_str:
                        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_str)
                        if match:
                            prev_day, prev_month, prev_year = match.groups()
                            next_year = int(prev_year) + 1

                            if "filing_year" not in extracted_data or not extracted_data.get("filing_year"):
                                extracted_data["filing_year"] = next_year
                                msg = f"  [+] Auto-filled filing_year from Previous FLA: {next_year}"
                                print(msg)
                                state["logs"].append(msg)

                            if "closing_date" not in extracted_data or not extracted_data.get("closing_date"):
                                next_closing_date = f"{prev_day}/{prev_month}/{next_year}"
                                extracted_data["closing_date"] = next_closing_date
                                msg = f"  [+] Auto-filled closing_date from Previous FLA: {next_closing_date}"
                                print(msg)
                                state["logs"].append(msg)
                    break

        except Exception as e:
            err_msg = f"  [!] Failed to extract from previous FLA: {e}"
            print(err_msg)
            state["logs"].append(err_msg)

            
    target_cells = rule_engine.evaluate_all(extracted_data)
    
    state["extracted_data"] = extracted_data
    state["target_cells"] = target_cells
    
    # Content-based year detection for multi-document AOC-4 runs
    if state.get("module_type", "fla") == "aoc4":
        import re
        all_mds = []
        for k, v in state.get("ocr_outputs", {}).items():
            if isinstance(v, dict) and "md" in v and os.path.exists(v["md"]):
                with open(v["md"], "r", encoding="utf-8", errors="ignore") as mf:
                    all_mds.append((os.path.abspath(v["md"]), mf.read()))
        
        # Also check raw input files (e.g. directly uploaded .md or .xlsx)
        docs = state.get("financial_docs", {})
        for k, p in docs.items():
            if isinstance(p, str) and os.path.exists(p):
                abs_p = os.path.abspath(p)
                if p.endswith(".md"):
                    with open(abs_p, "r", encoding="utf-8", errors="ignore") as mf:
                        all_mds.append((abs_p, mf.read()))
                elif p.endswith(".xlsx") or p.endswith(".xls"):
                    all_mds.append((abs_p, abs_p)) # Absolute Excel path directly
        
        # Also check if any other files in input_dir were uploaded
        input_dir = state.get("input_dir", "")
        if os.path.exists(input_dir):
            for f in os.listdir(input_dir):
                full_f = os.path.abspath(os.path.join(input_dir, f))
                if full_f.endswith(('.xlsx', '.xls')) and not any(m[0] == full_f for m in all_mds):
                    all_mds.append((full_f, full_f))
                elif full_f.endswith('.md') and not any(m[0] == full_f for m in all_mds):
                    with open(full_f, "r", encoding="utf-8", errors="ignore") as mf:
                        all_mds.append((full_f, mf.read()))

        excel_sources = [m[1] for m in all_mds if m[1].endswith(('.xlsx', '.xls'))]
        text_sources = [m[1] for m in all_mds if not m[1].endswith(('.xlsx', '.xls'))]

        # Filter only Excel files that actually contain Financial Statement sheets
        fin_excels = []
        for p in excel_sources:
            try:
                import openpyxl
                wb_test = openpyxl.load_workbook(p, read_only=True)
                names_l = [s.lower() for s in wb_test.sheetnames]
                wb_test.close()
                if any(kw in s for s in names_l for kw in ["balance sheet", "profit and loss", "p&l", "statement of profit", "financials"]):
                    fin_excels.append(p)
            except Exception:
                pass

        # Identify text documents that contain actual Balance Sheet & P&L tables
        primary_fs_candidates = []
        for t in text_sources:
            t_low = t.lower()
            has_bs = "|" in t and any(kw in t_low for kw in ["share capital", "total equity", "total liabilities", "balance sheet as at", "balance sheet"])
            has_pl = "|" in t and any(kw in t_low for kw in ["revenue from operations", "total income", "total expenses", "profit before tax", "profit and loss"])
            if has_bs and has_pl:
                # Target actual financial year ending dates (e.g. 31st March 2026, March 31, 2025)
                fy_matches = re.findall(r'(?:31(?:st)?\s*(?:march|mar)|march\s*31(?:st)?)[,\s]*(202\d)', t, re.IGNORECASE)
                if fy_matches:
                    max_yr = max(int(y) for y in fy_matches)
                else:
                    hdr_matches = re.findall(r'(?:as at|ended|for the year).*?(202\d)', t, re.IGNORECASE)
                    max_yr = max(int(y) for y in hdr_matches) if hdr_matches else 2025
                tbl_count = t.count('\n|')
                primary_fs_candidates.append((max_yr, tbl_count, t))

        # For each distinct reporting year, pick the most comprehensive document (highest table count)
        year_best = {}
        for yr, tbl_count, t in primary_fs_candidates:
            if yr not in year_best or tbl_count > year_best[yr][0]:
                year_best[yr] = (tbl_count, t)
        sorted_years = sorted(year_best.keys(), reverse=True)

        if len(fin_excels) >= 2:
            cy_cand = [f for f in fin_excels if any(k in f.lower() for k in ['25-26', '2026', 'cy', 'current'])]
            py_cand = [f for f in fin_excels if any(k in f.lower() for k in ['24-25', '2025', 'py', 'previous'])]
            state["cy_source"] = cy_cand[0] if cy_cand else fin_excels[0]
            state["py_source"] = py_cand[0] if py_cand else fin_excels[1]
            msg_py = f"  [+] Multi-Excel detected: CY ({os.path.basename(state['cy_source'])}) vs PY ({os.path.basename(state['py_source'])})."
            print(msg_py)
            state["logs"].append(msg_py)
        elif fin_excels and (primary_fs_candidates or text_sources):
            state["cy_source"] = fin_excels[0]
            state["py_source"] = year_best[sorted_years[0]][1] if sorted_years else (primary_fs_candidates[0][2] if primary_fs_candidates else "\n\n".join(text_sources))
            msg_py = f"  [+] Multi-doc detected: Cross-reconciling Financial Excel against OCR Financial Statements."
            print(msg_py)
            state["logs"].append(msg_py)
        elif len(sorted_years) >= 2:
            # True multi-year cross reconciliation (CY FY vs PY FY)
            state["cy_source"] = year_best[sorted_years[0]][1]
            state["py_source"] = year_best[sorted_years[1]][1]
            msg_py = f"  [+] Multi-year detected: CY (FY {sorted_years[0]}) vs PY (FY {sorted_years[1]}) assigned based on content."
            print(msg_py)
            state["logs"].append(msg_py)
        elif len(primary_fs_candidates) >= 1:
            chosen_fs = year_best[sorted_years[0]][1] if sorted_years else primary_fs_candidates[0][2]
            state["cy_source"] = chosen_fs
            state["py_source"] = chosen_fs
        elif len(text_sources) > 1:
            merged_text = "\n\n".join(text_sources)
            state["cy_source"] = merged_text
            state["py_source"] = merged_text
        elif text_sources:
            state["cy_source"] = text_sources[0]
            state["py_source"] = text_sources[0]
        elif fin_excels:
            state["cy_source"] = fin_excels[0]
            state["py_source"] = fin_excels[0]
    
    return state

def node_output(state: WorkflowState) -> WorkflowState:
    msg = "[*] Stage 4: Exporting to Excel and Validating..."
    print(msg)
    state["logs"].append(msg)
    
    safe_company_name = "".join(c if c.isalnum() or c in " .-_" else "_" for c in state["company_name"])
    output_dir = os.path.join(BASE_OUTPUT_DIR, safe_company_name)
    os.makedirs(output_dir, exist_ok=True)
    
    module_type = state.get("module_type", "fla").upper()
    output_path = os.path.join(output_dir, f"{safe_company_name}_{module_type}_Populated.xlsx")

    # Path logic: __file__ is inside core/workflow/nodes.py
    mod = ModuleFactory.get_module(state.get("module_type", "fla"))
    skeletal_filename = mod.get("skeletal_file", "FLA Return existing skeletal.xlsx")
    skeletal_path = os.path.join(mod["excel_dir"], skeletal_filename)
    
    writer = ExcelWriter(skeletal_path, output_path)
    writer.write_values(state["target_cells"])
    
    ReturnValidator = mod["validator"]
    validator = ReturnValidator()
    validator.run_all_checks(state["target_cells"])
    validator.save_report(output_dir)
    
    state["output_excel"] = output_path
    return state

def check_comparison(state: WorkflowState) -> str:
    # Always run comparison for AOC4 (since it can perform both cross-doc and same-doc verification)
    if state.get("module_type", "fla") == "aoc4":
        return "compare"
    if state.get("previous_fla_file"):
        return "compare"
    return "end"

def node_compare(state: WorkflowState) -> WorkflowState:
    msg = "[*] Stage 5: Running Automated Comparison against Previous Year..."
    print(msg)
    state["logs"].append(msg)
    
    mod_type = state.get("module_type", "fla")
    
    if mod_type == "aoc4":
        try:
            from automation_engine.modules.aoc4.py_variance_checker import AOC4PreviousYearReconciler
            reconciler = AOC4PreviousYearReconciler()
            
            docs = state.get("financial_docs", {})
            cy_src = state.get("cy_source")
            py_src = state.get("py_source")
            
            if not cy_src or not py_src:
                fin_files = [v for k, v in docs.items() if (k.startswith("financials") or k == "financial_excel" or k.startswith("fallback_md")) and isinstance(v, str) and os.path.exists(v)]
                cy_candidates = [f for f in fin_files if any(k in f.lower() for k in ['25-26', '2026', 'cy', 'current'])]
                py_candidates = [f for f in fin_files if any(k in f.lower() for k in ['24-25', '2025', 'py', 'previous'])]
                
                if cy_candidates and not cy_src:
                    cy_src = cy_candidates[0]
                if py_candidates and not py_src:
                    py_src = py_candidates[0]
                    
                if not cy_src:
                    cy_src = docs.get("financials") or (fin_files[0] if fin_files else "")
                if not py_src:
                    py_src = cy_src
            
            print(f"  -> Reconciling CY ({os.path.basename(str(cy_src))}) vs PY ({os.path.basename(str(py_src))})")
            report = reconciler.reconcile(cy_src, py_src)
            state["comparison_results"] = report.get("reconciliation_items", [])
            state["comparison_summary"] = report.get("summary", {})
            
            # Save standalone Comparison Report
            safe_company_name = "".join(c if c.isalnum() or c in " .-_" else "_" for c in state["company_name"])
            output_dir = os.path.join(BASE_OUTPUT_DIR, safe_company_name)
            compare_path = os.path.join(output_dir, f"{safe_company_name}_Comparison_Report.xlsx")
            reconciler.export_to_excel(report, compare_path)
            
            # Also append the Previous Year Comparison sheet directly into the main Populated Excel!
            if state.get("output_excel") and os.path.exists(state["output_excel"]):
                reconciler.append_to_existing_workbook(report, state["output_excel"])
                
            summary = report.get("summary", {})
            reconcile_msg = f"  [+] AOC4 Comparison Complete: {summary.get('total_compared', 0)} line items compared ({summary.get('matched', 0)} Matched, {summary.get('mismatches', 0)} Mismatches). Appended to output Excel."
            print(reconcile_msg)
            state["logs"].append(reconcile_msg)
            
        except Exception as e:
            error_msg = f"[!] AOC4 Comparison Failed: {str(e)}"
            print(error_msg)
            state["logs"].append(error_msg)
            state["comparison_results"] = []
    else:
        try:
            from automation_engine.modules.fla.comparison_platform.manager import ComparisonPlatformManager
            manager = ComparisonPlatformManager()
            # The Comparison platform takes source (previous year) and target (newly generated)
            results = manager.run_comparison(state.get("module_type", "fla"), state["previous_fla_file"], state["output_excel"])
            state["comparison_results"] = results
            
            mismatches = sum(1 for r in results if "Mismatch" in r.get("reason", ""))
            missing = sum(1 for r in results if "Missing" in r.get("reason", ""))
            
            if mismatches > 0 or missing > 0:
                warn_msg = f"  [!] COMPARISON FLAGGED: {mismatches} Mismatches and {missing} Missing items found! Manual review required."
                print(warn_msg)
                state["logs"].append(warn_msg)
            else:
                success_msg = f"  [+] Comparison completed successfully. All {len(results)} rules validated perfectly."
                print(success_msg)
                state["logs"].append(success_msg)
        except Exception as e:
            error_msg = f"[!] Comparison Failed: {str(e)}"
            print(error_msg)
            state["logs"].append(error_msg)
            state["comparison_results"] = []
        
    return state
