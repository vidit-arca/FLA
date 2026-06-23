import os
import argparse
import sys

# Defensive mock for _lzma C library (bypasses torchvision datasets optical_flow import failure)
try:
    import _lzma
except ImportError:
    from types import ModuleType
    mock_lzma = ModuleType("_lzma")
    mock_lzma.LZMA_CONCATENATED = 1
    mock_lzma.FORMAT_AUTO = 0
    mock_lzma.FORMAT_XZ = 1
    mock_lzma.FORMAT_ALONE = 2
    mock_lzma.FORMAT_RAW = 3
    mock_lzma.CHECK_NONE = 0
    mock_lzma.CHECK_CRC32 = 1
    mock_lzma.CHECK_CRC64 = 4
    mock_lzma.CHECK_SHA256 = 12
    
    class MockLZMADecompressor:
        def __init__(self, *args, **kwargs):
            pass
    class MockLZMACompressor:
        def __init__(self, *args, **kwargs):
            pass
            
    mock_lzma.LZMADecompressor = MockLZMADecompressor
    mock_lzma.LZMACompressor = MockLZMACompressor
    mock_lzma.LZMAError = Exception
    sys.modules["_lzma"] = mock_lzma

# Ensure engine package is in sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))


from engine.ingestion import DocumentIngestion
from engine.ocr_pipeline import OcrPipeline
from engine.parser import DocumentParser
from engine.rule_engine import RuleEngine
from engine.excel_writer import ExcelWriter
from engine.validator import ReturnValidator

def main():
    # Resolve default paths relative to this script's parent folder
    engine_dir = os.path.abspath(os.path.dirname(__file__))
    base_dir = os.path.abspath(os.path.join(engine_dir, ".."))
    default_input = os.path.join(base_dir, "signed") if os.path.exists(os.path.join(base_dir, "signed")) else "signed"
    default_skeletal = os.path.join(engine_dir, "excel", "FLA Return existing skeletal.xlsx") if os.path.exists(os.path.join(engine_dir, "excel")) else "excel/FLA Return existing skeletal.xlsx"
    default_output = os.path.join(base_dir, "output", "FLA Return Populated.xlsx") if os.path.exists(os.path.join(base_dir, "output")) else "output/FLA Return Populated.xlsx"
    default_config = os.path.join(os.path.dirname(__file__), "rules_config.json")

    parser = argparse.ArgumentParser(description="RBI FLA Return Automation Engine")
    parser.add_argument(
        "--input-dir", 
        default=default_input, 
        help="Path to folder containing signed PDFs"
    )
    parser.add_argument(
        "--skeletal", 
        default=default_skeletal, 
        help="Path to target skeletal Excel file"
    )
    parser.add_argument(
        "--config", 
        default=default_config, 
        help="Path to rules configuration JSON"
    )
    parser.add_argument(
        "--output", 
        default=default_output, 
        help="Path to output populated Excel file"
    )
    parser.add_argument(
        "--force-ocr", 
        action="store_true", 
        help="Force execution of heavy VLM OCR even if cached outputs exist"
    )
    parser.add_argument(
        "--ocr-cmd", 
        default="marker_single", 
        help="Command or absolute path to the marker_single executable (e.g. /path/to/venv/bin/marker_single)"
    )
    parser.add_argument(
        "--ocr-dir", 
        default=os.path.join(os.path.dirname(__file__), "output", "marker"),
        help="Path to folder containing cached OCR outputs"
    )
    
    args = parser.parse_args()
    
    print("==========================================================")
    print("          STARTING FLA RETURN AUTOMATION ENGINE           ")
    print("==========================================================\n")
    
    # 1. Initialize modular stages
    ingestion = DocumentIngestion(args.input_dir)
    ocr = OcrPipeline(
        output_dir=args.ocr_dir,
        marker_cmd=args.ocr_cmd
    )
    parser_engine = DocumentParser(args.config)
    rule_engine = RuleEngine(args.config)
    writer = ExcelWriter(args.skeletal, args.output)
    validator = ReturnValidator()

    
    # 2. Ingest PDFs
    print("[*] Stage 1: Scanning input signed directory...")
    docs = ingestion.find_documents()
    print(f"    - Board Report: {docs.get('board_report')}")
    print(f"    - Financials/Auditors: {docs.get('financials')}")
    if "shareholders_fdi" in docs:
        print(f"    - Shareholders (FDI): {docs.get('shareholders_fdi')}")
    if "odi_details" in docs:
        print(f"    - ODI Details: {docs.get('odi_details')}")
    
    ocr_outputs = {}
    
    # 3. Coordinate OCR Layer on all PDF files in the input directory
    print("\n[*] Stage 2: Scanning directory and loading cached OCR results (local VLM OCR execution is bypassed)...")
    
    for key_name, doc_path in docs.items():
        if not doc_path:
            continue
            
        basename = os.path.basename(doc_path)
        
        # Only run OCR checks on PDFs
        if not doc_path.lower().endswith('.pdf'):
            print(f"  - Document: {basename} | Role: {key_name} | Type: Structured Data (No OCR required)")
            continue
            
        is_scanned = ingestion.is_scanned_pdf(doc_path)
        print(f"  - Document: {basename} | Role: {key_name} | Scanned: {is_scanned}")
        
        # Check if cache exists
        cached = ocr.get_cached_ocr_paths(doc_path)
        if cached["md"] or cached["json"]:
            print(f"    [+] Found cached OCR results for {basename}. Ingesting cached data...")
            ocr_outputs[key_name] = cached
        else:
            if is_scanned:
                print(f"    [!] Scanned document '{basename}' detected, but NO cached OCR results exist.")
                print(f"    [!] FATAL: Cannot extract data from this scanned PDF without OCR cache.")
                print(f"    [!] ACTION REQUIRED: Please run `python fla_automation_engine/run_ocr_batch.py` first to safely process this heavy ML task.")
            else:
                print(f"    [*] Native digital text layer detected. OCR not required.")
            
    # 4. Extract raw key-values
    print("\n[*] Stage 3: Extracting text segments and parsing financial tables...")
    extracted_data = parser_engine.parse_all(docs, ocr_outputs)
    
    # Print extracted elements count
    print(f"[+] Successfully extracted {len(extracted_data)} parameters from documents")
    print("    Parameters Preview:")
    for k, v in list(extracted_data.items())[:10]:
        print(f"      - {k}: {v}")
        
    # 5. Apply calculation rules
    print("\n[*] Stage 4: Applying business calculation formulas & unlisted rules...")
    cell_values = rule_engine.evaluate_all(extracted_data)
    
    # Count computed fields
    total_cells = sum(len(cells) for cells in cell_values.values())
    print(f"[+] Formatted and computed {total_cells} target Excel cells across 4 sheets")
    
    # 6. Write values into skeletal Excel
    print("\n[*] Stage 5: Writing values to target skeletal Excel coordinates...")
    try:
        populated_path = writer.write_values(cell_values)
        print(f"[+] Output Excel file created successfully!")
    except Exception as e:
        print(f"[!] Critical Error populating Excel: {e}")
        sys.exit(1)
        
    # 7. Audit & Validation consistency check
    print("\n[*] Stage 6: Running mathematical & portal validations...")
    validator.run_all_checks(cell_values)
    validator.save_report(output_dir=os.path.dirname(args.output))
    
    # 8. Generate detailed Extraction Audit / Missing Parameter Report
    print("\n[*] Stage 7: Generating extraction audit and missing parameter reports...")
    save_extractions_report(extracted_data, rule_engine, args.output)
    
    print("\n==========================================================")
    print("        FLA RETURN POPULATION COMPLETED SUCCESSFULLY      ")
    print("==========================================================")

def save_extractions_report(extracted_data, rule_engine, output_path):
    import json
    import os
    
    output_dir = os.path.dirname(output_path)
    txt_report_path = os.path.join(output_dir, "missing_extractions_report.txt")
    json_report_path = os.path.join(output_dir, "missing_extractions_report.json")
    
    # Extract all unique fields mapped in the config
    all_extracted_fields = {}
    for section, fields in rule_engine.config.get("cell_mappings", {}).items():
        for key, field_cfg in fields.items():
            if field_cfg.get("type") == "extracted" and field_cfg.get("field"):
                f_name = field_cfg["field"]
                if f_name not in all_extracted_fields:
                    all_extracted_fields[f_name] = {
                        "row_label": field_cfg.get("row_label"),
                        "cell": field_cfg.get("cell"),
                        "default": field_cfg.get("default"),
                        "section": section
                    }
                    
    found_list = []
    missing_list = []
    
    for f_name, info in all_extracted_fields.items():
        if f_name in extracted_data:
            found_list.append({
                "field": f_name,
                "value": extracted_data[f_name],
                "row_label": info["row_label"],
                "cell": info["cell"],
                "section": info["section"]
            })
        else:
            missing_list.append({
                "field": f_name,
                "default": info["default"],
                "row_label": info["row_label"],
                "cell": info["cell"],
                "section": info["section"]
            })
            
    # Sort lists by section and cell
    found_list = sorted(found_list, key=lambda x: (x["section"], x["cell"]))
    missing_list = sorted(missing_list, key=lambda x: (x["section"], x["cell"]))
    
    # Write TXT report
    with open(txt_report_path, "w") as f:
        f.write("================================================================================\n")
        f.write("                    FLA RETURN EXTRACTION AUDIT REPORT\n")
        f.write("================================================================================\n\n")
        f.write("This report shows which metadata and financial parameters were successfully found\n")
        f.write("and extracted from the input PDF documents (Board Report & Financials), and which\n")
        f.write("parameters were NOT found and therefore fell back to their regulatory defaults.\n\n")
        
        f.write("--------------------------------------------------------------------------------\n")
        f.write(f"1. FOUND PARAMETERS (Successfully Extracted from PDFs) [Total: {len(found_list)}]\n")
        f.write("--------------------------------------------------------------------------------\n")
        
        curr_section = None
        for item in found_list:
            if item["section"] != curr_section:
                curr_section = item["section"]
                f.write(f"\n[{curr_section}]\n")
            f.write(f"  - {item['field']}: {item['value']}  (Target Cell: {item['cell']} | {item['row_label']})\n")
            
        f.write("\n--------------------------------------------------------------------------------\n")
        f.write(f"2. MISSING PARAMETERS (Not Found - Fell Back to regulatory/skeletal defaults) [Total: {len(missing_list)}]\n")
        f.write("--------------------------------------------------------------------------------\n")
        
        curr_section = None
        for item in missing_list:
            if item["section"] != curr_section:
                curr_section = item["section"]
                f.write(f"\n[{curr_section}]\n")
            f.write(f"  - {item['field']}: Target Cell: {item['cell']} -> Defaulted to: {item['default']}  ({item['row_label']})\n")
            
    # Write JSON report
    report_json = {
        "found_parameters": found_list,
        "missing_parameters": missing_list
    }
    with open(json_report_path, "w") as f:
        json.dump(report_json, f, indent=4)
        
    print(f"[+] Saved extraction audit reports to:")
    print(f"    - Text Report: {txt_report_path}")
    print(f"    - JSON Data:   {json_report_path}")

if __name__ == "__main__":
    main()
