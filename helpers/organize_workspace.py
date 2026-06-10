import os
import shutil

def main():
    root_dir = "/Users/apple/Desktop/FLA"
    engine_dest = os.path.join(root_dir, "fla_automation_engine")
    engine_pkg_dest = os.path.join(engine_dest, "engine")
    helpers_dest = os.path.join(root_dir, "helpers")
    
    # Create directories
    os.makedirs(engine_dest, exist_ok=True)
    os.makedirs(engine_pkg_dest, exist_ok=True)
    os.makedirs(helpers_dest, exist_ok=True)
    
    print("[*] Created structured directories.")
    
    # Files to copy/move to engine folder
    core_files = {
        "rules_config.json": engine_dest,
        "requirements.txt": engine_dest,
        "README.md": engine_dest,
        "ocr_marker.py": engine_dest,
        "engine/__init__.py": engine_pkg_dest,
        "engine/ingestion.py": engine_pkg_dest,
        "engine/ocr_pipeline.py": engine_pkg_dest,
        "engine/parser.py": engine_pkg_dest,
        "engine/rule_engine.py": engine_pkg_dest,
        "engine/excel_writer.py": engine_pkg_dest,
        "engine/validator.py": engine_pkg_dest,
    }
    
    # Copy/move files
    for src_rel, dest_dir in core_files.items():
        src_path = os.path.join(root_dir, src_rel)
        if os.path.exists(src_path):
            shutil.copy2(src_path, dest_dir)
            print(f"    - Packaged {src_rel} -> {dest_dir}")
            
    # Move auxiliary helper/debug scripts to helpers/
    helpers = [
        "inspect_pdfs.py",
        "inspect_digital_text.py",
        "run_ocr_board.py",
        "extract_odi_formulas.py",
        "search_net_worth.py",
        "inspect_skel_formulas.py",
        "inspect_tool_odi_formula.py",
        "inspect_tool_odi_calculations.py",
        "inspect_skel_odi_capital.py",
        "inspect_tool_odi_translation.py",
        "inspect_excel.py",
        "print_skel.py",
        "print_tool_return.py",
        "dump_skeletal.py",
        "dump_financials.py",
        "dump_full_details.py",
        "analyze_sheets.py",
        "inspect_formulas.py"
    ]
    
    for helper in helpers:
        src_path = os.path.join(root_dir, helper)
        if os.path.exists(src_path):
            shutil.move(src_path, os.path.join(helpers_dest, helper))
            print(f"    - Organized helper {helper} -> helpers/")
            
    # Write the updated, robust run_pipeline.py into the fla_automation_engine directory
    updated_run_pipeline_code = """import os
import argparse
import sys

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
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    default_input = os.path.join(base_dir, "signed") if os.path.exists(os.path.join(base_dir, "signed")) else "signed"
    default_skeletal = os.path.join(base_dir, "excel", "FLA Return existing skeletal.xlsx") if os.path.exists(os.path.join(base_dir, "excel")) else "excel/FLA Return existing skeletal.xlsx"
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
    
    args = parser.parse_args()
    
    print("==========================================================")
    print("          STARTING FLA RETURN AUTOMATION ENGINE           ")
    print("==========================================================\\n")
    
    # 1. Initialize modular stages
    ingestion = DocumentIngestion(args.input_dir)
    ocr = OcrPipeline(output_dir=os.path.join(os.path.dirname(__file__), "output", "marker"))
    parser_engine = DocumentParser(args.config)
    rule_engine = RuleEngine(args.config)
    writer = ExcelWriter(args.skeletal, args.output)
    validator = ReturnValidator()
    
    # 2. Ingest PDFs
    print("[*] Stage 1: Scanning input signed directory...")
    docs = ingestion.find_documents()
    print(f"    - Board Report: {docs.get('board_report')}")
    print(f"    - Financials/Auditors: {docs.get('financials')}")
    
    ocr_outputs = {}
    
    # 3. Coordinate OCR Layer
    if docs.get("financials"):
        is_scanned = ingestion.is_scanned_pdf(docs["financials"])
        print(f"[*] Stage 2: Classifying financials PDF. Scanned: {is_scanned}")
        
        if is_scanned:
            # Check cached results or run OCR
            print("[*] Financials is a scanned document. Accessing OCR pipeline...")
            ocr_res = ocr.process_pdf(docs["financials"], force=args.force_ocr)
            ocr_outputs["financials"] = ocr_res
        else:
            print("[*] Financials contains native digital text layer. OCR not required.")
            
    # 4. Extract raw key-values
    print("\\n[*] Stage 3: Extracting text segments and parsing financial tables...")
    extracted_data = parser_engine.parse_all(docs, ocr_outputs)
    
    # Print extracted elements count
    print(f"[+] Successfully extracted {len(extracted_data)} parameters from documents")
    print("    Parameters Preview:")
    for k, v in list(extracted_data.items())[:10]:
        print(f"      - {k}: {v}")
        
    # 5. Apply calculation rules
    print("\\n[*] Stage 4: Applying business calculation formulas & unlisted rules...")
    cell_values = rule_engine.evaluate_all(extracted_data)
    
    # Count computed fields
    total_cells = sum(len(cells) for cells in cell_values.values())
    print(f"[+] Formatted and computed {total_cells} target Excel cells across 4 sheets")
    
    # 6. Write values into skeletal Excel
    print("\\n[*] Stage 5: Writing values to target skeletal Excel coordinates...")
    try:
        populated_path = writer.write_values(cell_values)
        print(f"[+] Output Excel file created successfully!")
    except Exception as e:
        print(f"[!] Critical Error populating Excel: {e}")
        sys.exit(1)
        
    # 7. Audit & Validation consistency check
    print("\\n[*] Stage 6: Running mathematical & portal validations...")
    validator.run_all_checks(cell_values)
    validator.save_report(output_dir=os.path.dirname(args.output))
    
    print("\\n==========================================================")
    print("        FLA RETURN POPULATION COMPLETED SUCCESSFULLY      ")
    print("==========================================================")

if __name__ == "__main__":
    main()
"""
    
    with open(os.path.join(engine_dest, "run_pipeline.py"), "w") as f:
        f.write(updated_run_pipeline_code)
    print("    - Written updated run_pipeline.py to engine folder.")
    
    # Delete the old loose engine folders and files from root to ensure clean structure
    loose_files = [
        "run_pipeline.py",
        "rules_config.json",
        "requirements.txt",
        "README.md",
    ]
    for lf in loose_files:
        path = os.path.join(root_dir, lf)
        if os.path.exists(path):
            os.remove(path)
            
    if os.path.exists(os.path.join(root_dir, "engine")):
        shutil.rmtree(os.path.join(root_dir, "engine"))
        print("[*] Deleted old loose directories from root.")
        
    print("\n[+] Workspace successfully structured!")

if __name__ == "__main__":
    main()
