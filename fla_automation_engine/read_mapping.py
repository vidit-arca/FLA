import pandas as pd

try:
    xl = pd.ExcelFile("/Users/apple/Desktop/FLA/excel/FLA_Tool_v5_fixed.xlsx")
    print("Sheets:", xl.sheet_names)
    
    # Try reading the first sheet
    df = pd.read_excel(xl, sheet_name=xl.sheet_names[0])
    
    # The user mentioned row 154 (1-indexed). Let's print rows 150 to 200.
    # In pandas, if it has a header, row 154 might be index 152.
    print(f"\n--- Snippet from {xl.sheet_names[0]} ---")
    start_idx = max(0, 150 - 2)
    end_idx = min(len(df), 200 - 2)
    
    for i in range(start_idx, end_idx):
        row = df.iloc[i]
        # Print Column B and Column E (index 1 and 4 assuming A=0, B=1, C=2, D=3, E=4)
        col_b = str(row.iloc[1])[:100] if len(row) > 1 else ""
        col_e = str(row.iloc[4])[:300] if len(row) > 4 else ""
        print(f"Row {i+2} | Col B: {col_b} | Col E: {col_e}")

except Exception as e:
    print("Error:", e)
