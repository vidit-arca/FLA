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
    ingestor = DocumentIngestion(input_dir)
    docs = ingestor.find_documents()
    
    previous_fla_file = ""
    
    # find_documents() returns a dict, but any file named previous_fla_* might end up as an 'unknown_excel' or similar.
    # Let's manually pluck the previous_fla file out of the directory
    for filename in os.listdir(input_dir):
        if filename.startswith("previous_fla_"):
            previous_fla_file = os.path.join(input_dir, filename)
            found_msg = f"  -> Found Previous Year FLA file: {filename}"
            print(found_msg)
            state["logs"].append(found_msg)
            break
            
    # docs is a dict like {'board_report': 'path/to/board.pdf', 'financial_excel': 'path/to/fin.xlsx'}
    state["financial_docs"] = docs
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
    target_cells = rule_engine.evaluate_all(extracted_data)
    
    state["extracted_data"] = extracted_data
    state["target_cells"] = target_cells
    
    return state

def node_output(state: WorkflowState) -> WorkflowState:
    msg = "[*] Stage 4: Exporting to Excel and Validating..."
    print(msg)
    state["logs"].append(msg)
    
    safe_company_name = "".join(c if c.isalnum() or c in " .-_" else "_" for c in state["company_name"])
    output_dir = os.path.join(BASE_OUTPUT_DIR, safe_company_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "FLA_Return_Populated.xlsx")

    # Path logic: __file__ is inside core/workflow/nodes.py
    mod = ModuleFactory.get_module(state.get("module_type", "fla"))
    skeletal_path = os.path.join(mod["excel_dir"], "FLA Return existing skeletal.xlsx")
    
    writer = ExcelWriter(skeletal_path, output_path)
    writer.write_values(state["target_cells"])
    
    ReturnValidator = mod["validator"]
    validator = ReturnValidator()
    validator.run_all_checks(state["target_cells"])
    validator.save_report(output_dir)
    
    state["output_excel"] = output_path
    return state

def check_comparison(state: WorkflowState) -> str:
    if state.get("previous_fla_file"):
        return "compare"
    return "end"

def node_compare(state: WorkflowState) -> WorkflowState:
    msg = "[*] Stage 5: Running Automated Comparison against Previous Year..."
    print(msg)
    state["logs"].append(msg)
    
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
