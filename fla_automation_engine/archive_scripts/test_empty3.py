import openpyxl

wb2 = openpyxl.load_workbook("/Users/apple/Desktop/FLA/output/kiritlabs/FLA_Return_Populated.xlsx", data_only=True)
sheet2 = wb2["Section II"]
print(f"Populated Net Worth F34: {sheet2['F34'].value}")
print(f"Populated Net Worth G34: {sheet2['G34'].value}")

sheet3 = wb2["Section III"]
print(f"Populated D17 (NRI %): {sheet3['D17'].value}")
print(f"Populated E17 (NRI %): {sheet3['E17'].value}")
