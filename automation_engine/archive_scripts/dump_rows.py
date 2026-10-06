import pandas as pd
df = pd.read_excel("/Users/apple/Desktop/FLA/automation_engine/automation_engine/excel/FLA Return existing skeletal.xlsx", sheet_name="Section III", header=None)
for row_idx, row in df.iloc[17:23].iterrows():
    print(f"Row {row_idx+1}: {[str(x)[:30] for x in row if pd.notna(x)]}")
