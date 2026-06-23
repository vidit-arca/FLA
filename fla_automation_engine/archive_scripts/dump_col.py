import pandas as pd
df = pd.read_excel("/Users/apple/Desktop/FLA/fla_automation_engine/fla_automation_engine/excel/FLA Return existing skeletal.xlsx", sheet_name="Section III", header=None)
for row_idx, row in df.iterrows():
    val = row[0]
    if pd.notna(val):
        print(f"Row {row_idx+1}: {str(val).strip()[:100]}")
