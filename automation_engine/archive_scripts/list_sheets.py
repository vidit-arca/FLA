import pandas as pd
try:
    xl = pd.ExcelFile("/Users/apple/Desktop/FLA/automation_engine/automation_engine/excel/FLA Return existing skeletal.xlsx")
    print("Sheets:", xl.sheet_names)
except Exception as e:
    print(f"Error: {e}")
