"""
Run AOC4 for Phusaram Mundhra Private Limited using the existing module pipeline.
Points to /testing/Phusaram/ocr_output
"""
import os
import sys

sys.path.insert(0, "/Users/apple/Desktop/FLA")

from automation_engine.modules.aoc4.rule_engine import AOC4RuleEngine
from automation_engine.core.excel_writer import ExcelWriter

def main():
    config_path = "/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/rules_config.json"
    engine = AOC4RuleEngine(config_path)

    ocr_dir = "/Users/apple/Desktop/FLA/testing/Phusaram/ocr_output"
    out_dir = "/Users/apple/Desktop/FLA/testing/Phusaram/output"
    os.makedirs(out_dir, exist_ok=True)

    skeletal_path = "/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/excel/Annual Filing common error Output.xlsx"
    if not os.path.exists(skeletal_path):
        skeletal_path = "/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/excel/ANNFIL COMMONERROR .xlsx"

    # Read ALL .md files from the ocr_output folder and merge into one full_text
    full_text = ""
    md_files = [f for f in sorted(os.listdir(ocr_dir)) if f.endswith(".md")]
    print(f"[*] Found {len(md_files)} markdown file(s): {md_files}")
    for fname in md_files:
        fpath = os.path.join(ocr_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            full_text += f.read() + "\n\n"

    # Also collect any Excel reference file as a doc
    docs = {}
    for fname in sorted(os.listdir(ocr_dir)):
        if fname.lower().endswith(".xlsx") or fname.lower().endswith(".xls"):
            docs["financials_excel"] = os.path.join(ocr_dir, fname)
            print(f"[*] Found reference Excel: {fname}")

    company_name = "Phusaram Mundhra Private Limited"
    safe_name    = "Phusaram_Mundhra_Private_Limited"
    output_path  = os.path.join(out_dir, f"{safe_name}_AOC4_Populated.xlsx")

    input_data = {
        "full_text": full_text,
        "docs": docs,
    }

    print(f"\n[*] Running AOC4 rule engine for: {company_name}")
    target_cells = engine.evaluate_all(input_data)

    writer = ExcelWriter(skeletal_path, output_path)
    writer.write_values(target_cells)
    print(f"\n[✓] AOC4 Excel written → {output_path}")
    print(f"[*] Flags generated: {len(target_cells.get('_flags', []))}")

    # ── Comparison / PY Variance Report ──────────────────────────────────────
    print("\n[*] Generating Previous Year Variance / Comparison Report...")
    try:
        from automation_engine.modules.aoc4.py_variance_checker import AOC4PreviousYearReconciler

        reconciler = AOC4PreviousYearReconciler()

        # Target primary Financial Statements markdown (contains Balance Sheet, P&L, Notes)
        primary_fs = [f for f in md_files if "financial" in f.lower() or "fs" in f.lower()]
        if primary_fs:
            with open(os.path.join(ocr_dir, primary_fs[0]), "r", encoding="utf-8") as f:
                cy_source = f.read()
        else:
            cy_source = full_text

        # Discover Prior Year (PY) filed document
        py_source = None
        base_dir = os.path.dirname(ocr_dir)
        py_dir = os.path.join(base_dir, "py_filed")
        
        if os.path.exists(py_dir):
            py_files = [f for f in os.listdir(py_dir) if f.endswith(".md") or f.endswith(".xlsx")]
            if py_files:
                py_source = os.path.join(py_dir, py_files[0])
                if py_source.endswith(".md"):
                    with open(py_source, "r", encoding="utf-8") as f:
                        py_source = f.read()
                        
        if not py_source:
            # Check for inline PY naming convention
            py_inline = [f for f in os.listdir(ocr_dir) if ("py_" in f.lower() or "_filed" in f.lower()) and (f.endswith(".md") or f.endswith(".xlsx"))]
            if py_inline:
                py_source = os.path.join(ocr_dir, py_inline[0])
                if py_source.endswith(".md"):
                    with open(py_source, "r", encoding="utf-8") as f:
                        py_source = f.read()
                        
        if py_source:
            print("\n[*] Found 'Last Year Filed' document. Performing true Previous Year reconciliation.")
        else:
            print("\n[!] WARNING: No 'Last Year Filed' document found.")
            print("    Performing 'Same Document Verification' (comparing CY vs PY column of the same report).")
            print("    For true reconciliation, place the prior year document in a 'py_filed' folder or name it 'PY_...'.")
            py_source = cy_source

        report = reconciler.reconcile(cy_source, py_source)

        compare_path = os.path.join(out_dir, f"{safe_name}_Comparison_Report.xlsx")
        reconciler.export_to_excel(report, compare_path)

        summary = report.get("summary", {})
        print(f"[✓] Comparison Report written → {compare_path}")
        print(f"    Total compared : {summary.get('total_compared', 0)}")
        print(f"    Matched        : {summary.get('matched', 0)}")
        print(f"    Mismatches     : {summary.get('mismatches', 0)}")
        print(f"    Overall Status : {summary.get('status', 'N/A')}")

    except Exception as e:
        print(f"[!] Comparison report error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
