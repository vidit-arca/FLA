import pandas as pd, re

df = pd.read_excel("/Users/apple/Desktop/FLA/data/32065714-dd63-49f7-8c2d-7a5fb550a6cc/Uncia_Standalone FS_Mar 2026 Final v7.xlsx", sheet_name="BS", header=None)

# Find the investments row
for idx, row in df.iterrows():
    for col_idx, cell in enumerate(row.values):
        if isinstance(cell, str) and "invest" in str(cell).lower():
            row_vals = [v for v in row.values if str(v).strip() not in ["", "nan", "None"]]
            print(f"Row {idx} col {col_idx}: [{cell[:80]}]")
            print(f"  First 8 values: {row_vals[:8]}")
            print()
