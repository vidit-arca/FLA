import pandas as pd

xl = pd.ExcelFile("/Users/apple/Desktop/FLA/excel/FLA_Tool_v5_fixed.xlsx")
df = pd.read_excel(xl, sheet_name="2_FINANCIALS")

print("--- Section IV Rules ---")
for r_idx in range(150, 250):
    if r_idx < len(df):
        row = df.iloc[r_idx]
        col_b = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        col_e = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
        if col_b or col_e:
            # col_a is index 0
            col_a = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            print(f"Row {r_idx+2} | A: {col_a[:60]} | B: {col_b[:60]} | E: {col_e[:60]}")
