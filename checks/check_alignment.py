import pandas as pd
comp_df = pd.read_excel('/Users/apple/Desktop/FLA/automation_engine/excel/FLA_comparsion.xlsx', sheet_name='Section I', header=None)
skel_df = pd.read_excel('/Users/apple/Desktop/FLA/automation_engine/automation_engine/excel/FLA Return existing skeletal.xlsx', sheet_name='Section I', header=None)

for i in range(1, 10):
    print(f"Row {i}:")
    print(f"  Comp: {comp_df.iloc[i, 0]} | {comp_df.iloc[i, 2]}")
    print(f"  Skel: {skel_df.iloc[i, 0]}")
