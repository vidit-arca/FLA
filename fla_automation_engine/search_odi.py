import pandas as pd

xl = pd.ExcelFile("/Users/apple/Desktop/FLA/excel/FLA_Tool_v5_fixed.xlsx")
df = pd.read_excel(xl, sheet_name="2_FINANCIALS")

for r_idx, row in df.iterrows():
    val = str(row.iloc[1]).lower() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
    if "number of direct investment enterprises" in val or "number of die" in val or "no. of die" in val or "number of foreign" in val:
        print(f"Row {r_idx+2}: {val}")
