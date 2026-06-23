import openpyxl

wb = openpyxl.load_workbook("/Users/apple/Desktop/FLA/fla_automation_engine/fla_automation_engine/excel/FLA Return existing skeletal.xlsx")
sheet = wb["Section II"]

print("=== INSPECTING ROW 7 ===")
for col in ["C", "D", "E", "F", "G"]:
    cell = f"{col}7"
    print(f"Cell {cell}: Value={sheet[cell].value}, Merged={any(cell in rng for rng in sheet.merged_cells.ranges)}")

print("\n=== INSPECTING ROW 43 ===")
for col in ["C", "D", "E", "F", "G"]:
    cell = f"{col}43"
    print(f"Cell {cell}: Value={sheet[cell].value}, Merged={any(cell in rng for rng in sheet.merged_cells.ranges)}")
