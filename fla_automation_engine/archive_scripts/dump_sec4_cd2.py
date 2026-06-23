import pandas as pd

xl = pd.ExcelFile("/Users/apple/Desktop/FLA/fla_automation_engine/excel/FLA_Tool_v5_fixed.xlsx")
df = pd.read_excel(xl, sheet_name="2_FINANCIALS")

print("--- Section IV Rules (Cols B, C, D) ---")
for r_idx in range(140, 161):
    if r_idx < len(df):
        row = df.iloc[r_idx]
        col_b = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
        col_c = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else ""
        col_d = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else ""
        if col_b:
            print(f"Row {r_idx+2} | B: {col_b[:40]} | C: {col_c[:20]} | D: {col_d[:20]}")
