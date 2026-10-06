import openpyxl
import os

wb2 = openpyxl.load_workbook("/Users/apple/Desktop/FLA/output/kiritlabs/FLA_Return_Populated.xlsx", data_only=True)
sheet2 = wb2["Section III"]
print(f"Populated D20 (Equity Capital): {sheet2['D20'].value}")
print(f"Populated D21 (1.1 Liab): {sheet2['D21'].value}")
print(f"Populated E21 (1.1 Liab): {sheet2['E21'].value}")

