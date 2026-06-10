import pandas as pd
xl = pd.ExcelFile('/Users/apple/Desktop/FLA/data/Karomi/FLA details from company 1.xlsx')
for sheet in xl.sheet_names:
    print(f"--- {sheet} ---")
    df = pd.read_excel(xl, sheet_name=sheet)
    for i, row in df.iterrows():
        # print non-null values
        vals = [str(x) for x in row.values if pd.notna(x)]
        if vals:
            print(vals)
