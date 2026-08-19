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
    skeletal_path = "/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/excel/ANNFIL COMMONERROR .xlsx"
    
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

if __name__ == '__main__':
    main()
