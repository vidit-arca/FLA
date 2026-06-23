import pandas as pd

xl = pd.ExcelFile("/Users/apple/Desktop/FLA/data/karomi/FLA details from company 1.xlsx")
df = pd.read_excel(xl, sheet_name="Details")
print("Details sheet:")
print(df.head(15))

if "OFBV" in xl.sheet_names:
    df_ofbv = pd.read_excel(xl, sheet_name="OFBV")
    print("\nOFBV sheet:")
    print(df_ofbv.head(15))
