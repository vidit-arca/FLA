import pandas as pd

xl = pd.ExcelFile("/Users/apple/Desktop/FLA/data/karomi/FLA details from company 1.xlsx")
print("Sheets:", xl.sheet_names)
