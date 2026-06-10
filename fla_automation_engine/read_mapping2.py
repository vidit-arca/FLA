import pandas as pd

try:
    xl = pd.ExcelFile("/Users/apple/Desktop/FLA/excel/FLA_Tool_v5_fixed.xlsx")
    df = pd.read_excel(xl, sheet_name="3_FLA_RETURN")
    
    start_idx = max(0, 150 - 2)
    end_idx = min(len(df), 200 - 2)
    
    print(f"\n--- Snippet from 3_FLA_RETURN ---")
    for i in range(start_idx, end_idx):
        row = df.iloc[i]
        col_a = str(row.iloc[0]).strip()
        col_b = str(row.iloc[1]).strip()
        col_e = str(row.iloc[4]).strip()
        # Print if it's not nan
        if col_b != "nan" or col_e != "nan":
            print(f"Row {i+2} | Col A: {col_a[:30]} | Col B: {col_b[:80]} | Col E: {col_e[:300]}")

except Exception as e:
    print("Error:", e)
