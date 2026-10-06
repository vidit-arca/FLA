import pandas as pd
df = pd.read_excel("/Users/apple/Desktop/FLA/data/32065714-dd63-49f7-8c2d-7a5fb550a6cc/Uncia_Standalone FS_Mar 2026 Final v7.xlsx", sheet_name="RPT-Nt 27A&B", header=None)
print("Headers near row 39:")
for r in range(37, 43):
    clean = [v for v in df.iloc[r].values if str(v).strip() not in ["", "nan"]]
    print(f"Row {r}: {clean[:7]}")
