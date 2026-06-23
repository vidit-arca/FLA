import pandas as pd
xls = pd.ExcelFile('/Users/apple/Desktop/FLA/fla_automation_engine/excel/FLA_comparsion.xlsx')
for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet, header=None)
    if df.shape[1] >= 4:
        rules = df[df.iloc[:, 3].notna() & (df.iloc[:, 3] != 'Source of Information')]
        if not rules.empty:
            print(f'\n--- {sheet} ---')
            for _, row in rules.head(5).iterrows():
                print(f'Field: {row.iloc[0]} | Rule: {row.iloc[3]}')
