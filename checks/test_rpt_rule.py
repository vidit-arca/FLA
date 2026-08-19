import sys
import os

# Add automation_engine to path
sys.path.append('/Users/apple/Desktop/FLA')

from automation_engine.modules.aoc4.aoc4_error_checker import AOC4CommonErrorEngine

checker = AOC4CommonErrorEngine('/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/excel/ANNFIL COMMONERROR .xlsx')

# Test Data with Mismatching Export Sales vs RPT Sales
test_data = {
    "full_text": "notes to accounts: related party",
    "export_sales": 5000.0,
    "rpt_sale_goods": 4500.0
}

cells = checker.execute(test_data)
for cell in cells:
    if "whether rpt transaction given" in str(cell['particulars']).lower():
        print(f"Mismatch Test -> Value: {cell['user_value']} | Reason: {cell['reason']}")

# Test Data with Matching Export Sales vs RPT Sales
test_data_match = {
    "full_text": "notes to accounts: related party",
    "export_sales": 5000.0,
    "rpt_sale_goods": 5000.0
}

cells_match = checker.execute(test_data_match)
for cell in cells_match:
    if "whether rpt transaction given" in str(cell['particulars']).lower():
        print(f"Match Test -> Value: {cell['user_value']} | Reason: {cell['reason']}")

