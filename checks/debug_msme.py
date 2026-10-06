import re, pandas as pd

df = pd.read_excel("/Users/apple/Desktop/FLA/data/32065714-dd63-49f7-8c2d-7a5fb550a6cc/Uncia_Standalone FS_Mar 2026 Final v7.xlsx", sheet_name="BS", header=None)
patterns = [r"dues to msme", r"micro and small enterprises", r"dues to micro"]

print("=== Searching BS sheet for MSME keywords ===")
for idx, row in df.iterrows():
    for col_idx, cell in enumerate(row.values):
        if isinstance(cell, str):
            cell_lower = str(cell).lower().strip()
            for pat in patterns:
                if re.search(pat, cell_lower):
                    print(f"Row {idx} col {col_idx}: [{cell[:80]}]  matched [{pat}]")
                    print(f"  All row values: {list(row.values[:8])}")
                    print()
