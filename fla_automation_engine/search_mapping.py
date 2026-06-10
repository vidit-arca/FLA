import pandas as pd

xl = pd.ExcelFile("/Users/apple/Desktop/FLA/excel/FLA_Tool_v5_fixed.xlsx")
for sheet in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=sheet)
    # Search for "Sec IV" or "Section IV" anywhere in the dataframe
    for r_idx, row in df.iterrows():
        for c_idx, cell in enumerate(row):
            val = str(cell)
            if "Sec IV" in val or "Section 4" in val or "Section IV" in val:
                print(f"Found in sheet '{sheet}', Row {r_idx+2}:")
                # Print the whole row
                print([str(x)[:100] for x in row if pd.notna(x)])
                break
