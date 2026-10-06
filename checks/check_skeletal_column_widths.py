import openpyxl

wb = openpyxl.load_workbook("/Users/apple/Desktop/FLA/automation_engine/automation_engine/excel/FLA Return existing skeletal.xlsx", data_only=True)
sheet = wb["Section III"]

print("=== SKELETAL SPREADSHEET COLUMN WIDTHS ===")
for col in range(1, 9):
    col_letter = openpyxl.utils.get_column_letter(col)
    width = sheet.column_dimensions[col_letter].width
    print(f"Column {col_letter}: Width={width}")
