import os
import sys

sys.path.append("/Users/apple/Desktop/FLA")
from automation_engine.modules.aoc4.rule_engine import AOC4RuleEngine
from automation_engine.core.excel_writer import ExcelWriter

def main():
    engine = AOC4RuleEngine("/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/rules_config.json")
    
    ocr_dir = "/Users/apple/Desktop/FLA/ocr_output"
    out_dir = "/Users/apple/Desktop/FLA/updated_aoc4_v3"
    os.makedirs(out_dir, exist_ok=True)
    
    # The actual skeletal file according to the aoc4 module
    skeletal_path = "/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/excel/Annual Filing common error Output.xlsx"
    
    for filename in os.listdir(ocr_dir):
        if not filename.endswith(".md"):
            continue
            
        print(f"Processing {filename}...")
        
        base = filename.replace("FS_", "")
        comp_name = base.split("_FY")[0].strip()
        safe_company_name = "".join(c if c.isalnum() or c in " .-_" else "_" for c in comp_name)
        
        output_path = os.path.join(out_dir, f"{safe_company_name}_AOC4_Populated.xlsx")
        
        path = os.path.join(ocr_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            full_text = f.read()
            
        input_data = {
            "full_text": full_text
        }
        
        target_cells = engine.evaluate_all(input_data)
        
        writer = ExcelWriter(skeletal_path, output_path)
        writer.write_values(target_cells)
        print(f"Wrote {output_path}")

        # ── Comparison / PY Variance Report ──────────────────────────────────────
        print(f"Generating Comparison Report for {safe_company_name}...")
        try:
            from automation_engine.modules.aoc4.py_variance_checker import AOC4PreviousYearReconciler
            reconciler = AOC4PreviousYearReconciler()

            cy_source = full_text
            py_source = None
            
            # 1. Check for PY in py_filed folder
            base_dir = os.path.dirname(ocr_dir)
            py_dir = os.path.join(base_dir, "py_filed")
            if os.path.exists(py_dir):
                py_cands = [f for f in os.listdir(py_dir) if comp_name.lower() in f.lower() and (f.endswith(".md") or f.endswith(".xlsx"))]
                if py_cands:
                    py_path = os.path.join(py_dir, py_cands[0])
                    if py_path.endswith(".md"):
                        with open(py_path, "r", encoding="utf-8") as f2:
                            py_source = f2.read()
                    else:
                        py_source = py_path

            # 2. Check for PY inline naming (e.g., PY_ or _Filed)
            if not py_source:
                py_inline = [f for f in os.listdir(ocr_dir) if comp_name.lower() in f.lower() and ("py_" in f.lower() or "_filed" in f.lower()) and (f.endswith(".md") or f.endswith(".xlsx"))]
                if py_inline:
                    py_path = os.path.join(ocr_dir, py_inline[0])
                    if py_path.endswith(".md"):
                        with open(py_path, "r", encoding="utf-8") as f2:
                            py_source = f2.read()
                    else:
                        py_source = py_path

            if py_source:
                print("  -> Found 'Last Year Filed' document. Performing true Previous Year reconciliation.")
            else:
                print("  -> [!] WARNING: No 'Last Year Filed' document found.")
                print("     Performing 'Same Document Verification' (comparing CY vs PY column of the same report).")
                py_source = cy_source

            report = reconciler.reconcile(cy_source, py_source)
            compare_path = os.path.join(out_dir, f"{safe_company_name}_Comparison_Report.xlsx")
            reconciler.export_to_excel(report, compare_path)
            
            summary = report.get("summary", {})
            print(f"  -> Comparison Report written → {compare_path}")
            print(f"     Status: {summary.get('status', 'N/A')} (Matched: {summary.get('matched', 0)} / {summary.get('total_compared', 0)})\n")
            
        except Exception as e:
            print(f"  -> [!] Comparison report error: {e}")

if __name__ == '__main__':
    main()
