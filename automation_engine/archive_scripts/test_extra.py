import pandas as pd
from automation_engine.modules.fla.parser import DocumentParser
import re

parser = DocumentParser("rules_config.json")
xl = pd.ExcelFile('/Users/apple/Desktop/FLA/data/Karomi/FLA details from company 1.xlsx')

extracted = {}
for sheet in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=sheet)
    for i, row in df.iterrows():
        # combine text columns to form a 'particulars' super-string
        row_str = " ".join(str(c).lower() for c in row if pd.notna(c) and isinstance(c, str))
        
        # Look for numbers
        numbers = []
        for c in row:
            if pd.notna(c):
                s = str(c).strip().replace(',', '')
                if re.match(r'^-?[\d\.]+$', s):
                    try:
                        numbers.append(float(s))
                    except:
                        pass
                        
        if not numbers:
            continue
            
        # Match against financial rules
        rules = parser.config.get("financial_extraction_rules", {})
        for field_name, rule_cfg in rules.items():
            keywords = rule_cfg.get("keywords", [])
            if any(k in row_str for k in keywords):
                # Assumes first number is FY, second is PY, or whatever based on columns
                # For this extra file, 'current year' is before 'previous year'
                if len(numbers) >= 2:
                    extracted[f"{field_name}_fy"] = numbers[0]
                    extracted[f"{field_name}_py"] = numbers[1]
                elif len(numbers) == 1:
                    extracted[f"{field_name}_fy"] = numbers[0]
                    extracted[f"{field_name}_py"] = numbers[0]

print("Dynamically Extracted:", extracted)
