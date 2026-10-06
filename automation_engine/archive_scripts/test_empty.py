import openpyxl

wb = openpyxl.load_workbook("/Users/apple/Desktop/FLA/automation_engine/automation_engine/excel/FLA Return existing skeletal.xlsx", data_only=True)
sheet = wb["Section III"]
print(f"Skeletal C21: {sheet['C21'].value}")
print(f"Skeletal D21: {sheet['D21'].value}")
print(f"Skeletal E21: {sheet['E21'].value}")
print(f"Is C21:E21 merged? {'C21:E21' in [r.coord for r in sheet.merged_cells.ranges]}")
print(f"Are there any merges for row 21? {[r.coord for r in sheet.merged_cells.ranges if r.min_row <= 21 <= r.max_row]}")

