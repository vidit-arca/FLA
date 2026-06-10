import pandas as pd

xl = pd.ExcelFile("/Users/apple/Desktop/FLA/excel/FLA_Tool_v5_fixed.xlsx")
for sheet in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=sheet)
    for r_idx, row in df.iterrows():
        for cell in row:
            if "B1.1: Equity Cap" in str(cell) or "B1: Equity Cap" in str(cell):
                print(f"Found in sheet '{sheet}', Row {r_idx+2}:")
                print([str(x)[:100] for x in row if pd.notna(x)])
                break
