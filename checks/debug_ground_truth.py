import pandas as pd
wb = pd.ExcelFile("/Users/apple/Desktop/FLA/data/32065714-dd63-49f7-8c2d-7a5fb550a6cc/Uncia_Standalone FS_Mar 2026 Final v7.xlsx")
found = False
for sheet in wb.sheet_names:
    df = pd.read_excel(wb, sheet_name=sheet, header=None)
    for idx, row in df.iterrows():
        for cell in row.values:
            if isinstance(cell, str):
                cl = cell.lower()
                if any(x in cl for x in ["export", "sitting"]):
                    clean = [v for v in row.values if str(v).strip() not in ["", "nan"]][:6]
                    print(f"[{sheet}] Row {idx}: {clean}")
                    found = True
if not found:
    print("No mention of export or sitting fees found in Uncia FS.")
