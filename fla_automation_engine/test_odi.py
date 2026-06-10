import sys
import os
import json

sys.path.append(os.path.abspath('.'))
from engine.extractors.excel_extractor import ExcelExtractor

extractor = ExcelExtractor()
result = extractor.extract_odi_data("/Users/apple/Desktop/FLA/excel/FLA_Tool_v5_fixed.xlsx")

for key, val in result.items():
    if "json" in key:
        print(f"{key}: {val[:50]}...")
    else:
        print(f"{key}: {val}")
