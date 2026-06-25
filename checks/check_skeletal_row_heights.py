import openpyxl

wb = openpyxl.load_workbook("/Users/apple/Desktop/FLA/automation_engine/automation_engine/excel/FLA Return existing skeletal.xlsx", data_only=True)
sheet = wb["Section III"]

print("=== SKELETAL SPREADSHEET ROW HEIGHTS ===")
for r in range(14, 21):
    print(f"Row {r}: Height={sheet.row_dimensions[r].height}")
