import openpyxl

wb = openpyxl.load_workbook("/Users/apple/Desktop/FLA/fla_automation_engine/fla_automation_engine/excel/FLA Return existing skeletal.xlsx", data_only=False)
sheet = wb["Section IV"]

# Let's inspect some rows: 26, 27, 28, 29, 30 (Net Worth), 31, 39 (Equity Capital), 42 (Other Capital)
rows_to_check = [9, 10, 17, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 39, 40, 41, 42, 43, 44, 45]
print("=== Inspecting formulas in Section IV ===")
for r in rows_to_check:
    row_vals = [sheet.cell(row=r, column=c).value for c in range(1, 10)]
    print(f"Row {r:02d}: {row_vals}")
