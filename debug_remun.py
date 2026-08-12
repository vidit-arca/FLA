import pandas as pd

wb_path = "/Users/apple/Desktop/FLA/data/32065714-dd63-49f7-8c2d-7a5fb550a6cc/Uncia_Standalone FS_Mar 2026 Final v7.xlsx"
xls = pd.ExcelFile(wb_path)

print("Searching for 8660 (annual remuneration=866 Cr/100 in thousands)...")
for sheet in xls.sheet_names:
    try:
        df = pd.read_excel(xls, sheet_name=sheet, header=None)
        for idx, row in df.iterrows():
            vals = list(row.values)
            for v in vals:
                try:
                    fval = float(str(v).replace(",", "").strip())
                    if abs(fval - 8660) < 1 or abs(fval - 866) < 0.5:
                        clean_vals = [x for x in vals if str(x).strip() not in ["", "nan"]][:6]
                        print(f"[{sheet}] Row {idx}: value={fval} -> row={clean_vals}")
                        break
                except:
                    pass
    except Exception as e:
        print(f"Error reading {sheet}: {e}")
