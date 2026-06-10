import sys
sys.path.append("/Users/apple/Desktop/FLA")
from fla_automation_engine.engine.extractors.excel_extractor import ExcelExtractor
import pandas as pd

extractor = ExcelExtractor()
res = extractor.extract_fdi_data("/Users/apple/Desktop/FLA/kiritlabs/List of Shareholders_Kritilabs.xlsx")
print(res)
