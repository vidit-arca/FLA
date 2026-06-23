import pandas as pd
xls = pd.ExcelFile('/Users/apple/Desktop/FLA/fla_automation_engine/excel/FLA_comparsion.xlsx')
for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet, header=None)
    print(f"\n=== {sheet} ===")
    for idx, row in df.iterrows():
        for col_idx, val in row.items():
            s = str(val).upper()
            if 'PREVIOUS FLA' in s:
                print(f"Row {idx+1}, Col {col_idx}: {val}")
                # Print the first few columns of this row to give context
                context = [str(row.iloc[i]) for i in range(min(4, len(row)))]
                print(f"  Context: {context}")
