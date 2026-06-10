import pandas as pd

xl = pd.ExcelFile("/Users/apple/Desktop/FLA/data/karomi/FLA details from company 1.xlsx")
if "OFBV" in xl.sheet_names:
    df_ofbv = pd.read_excel(xl, sheet_name="OFBV")
    print("\nOFBV sheet:")
    # Print first few rows without truncation
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_colwidth', None)
    print(df_ofbv.head(25))
