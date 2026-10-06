import openpyxl

wb = openpyxl.load_workbook("/Users/apple/Desktop/FLA/automation_engine/automation_engine/excel/FLA Return existing skeletal.xlsx", data_only=True)
sheet = wb["Section III"]

for r in [15, 16]:
    cell = sheet.cell(row=r, column=3)
    print(f"Cell {cell.coordinate}: Value='{cell.value}'")
    print(f"  Alignment: wrap_text={cell.alignment.wrap_text}, horizontal='{cell.alignment.horizontal}', vertical='{cell.alignment.vertical}'")
