import pandas as pd

xl = pd.ExcelFile("/Users/apple/Desktop/FLA/fla_automation_engine/excel/FLA_Tool_v5_fixed.xlsx")
df = pd.read_excel(xl, sheet_name="2_FINANCIALS")

for r_idx in range(150, 250):
    if r_idx < len(df):
        row = df.iloc[r_idx]
        val = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
        if val:
            print(f"Row {r_idx+2}: {val[:80]}")
