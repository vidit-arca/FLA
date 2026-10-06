import openpyxl

wb2 = openpyxl.load_workbook("/Users/apple/Desktop/FLA/output/kiritlabs/FLA_Return_Populated.xlsx", data_only=True)
sheet2 = wb2["Section III"]
print(f"Populated C41 (DI %): {sheet2['C41'].value}")
print(f"Populated D44 (DI Equity): {sheet2['D44'].value}")
print(f"Populated D45 (DI Liab): {sheet2['D45'].value}")

