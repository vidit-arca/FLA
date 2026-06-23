import openpyxl

wb = openpyxl.load_workbook("/Users/apple/Desktop/FLA/fla_automation_engine/fla_automation_engine/excel/FLA Return existing skeletal.xlsx", data_only=True)
sheet = wb["Section III"]
print(f"Skeletal C17: {sheet['C17'].value}")
print(f"Skeletal D17: {sheet['D17'].value}")
print(f"Skeletal C18: {sheet['C18'].value}")
print(f"Skeletal D18: {sheet['D18'].value}")

