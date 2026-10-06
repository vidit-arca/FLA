import sys
import os
import glob
sys.path.append("/Users/apple/Desktop/FLA")
from automation_engine.modules.aoc4.rule_engine import AOC4RuleEngine
from automation_engine.core.excel_writer import ExcelWriter

def main():
    engine = AOC4RuleEngine("/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/rules_config.json")
    
    ocr_dir = "/Users/apple/Desktop/FLA/testing/Cameo global/2024-25/ocr_output"
    out_dir = "/Users/apple/Desktop/FLA/testing/Cameo global/2024-25"
    skeletal_path = "/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/excel/Annual Filing common error Output.xlsx"
    
    full_text = ""
    for filename in glob.glob(os.path.join(ocr_dir, "*.md")):
        with open(filename, 'r', encoding='utf-8') as f:
            full_text += f.read() + "\n"
            
    input_data = {
        "full_text": full_text
    }
    
    target_cells = engine.evaluate_all(input_data)
    
    output_path = os.path.join(out_dir, "Cameo_Global_24_25_AOC4_Populated.xlsx")
    writer = ExcelWriter(skeletal_path, output_path)
    writer.write_values(target_cells)
    print(f"Successfully generated: {output_path}")

if __name__ == '__main__':
    main()
