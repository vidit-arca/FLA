import openpyxl

wb = openpyxl.load_workbook("/Users/apple/Desktop/FLA/automation_engine/automation_engine/excel/FLA Return existing skeletal.xlsx")

for sheet_name in ["Section I", "Section II", "Section III", "Section IV"]:
    sheet = wb[sheet_name]
    print(f"\n--- Merged cells in {sheet_name} (Sample) ---")
    ranges = list(sheet.merged_cells.ranges)
    print(f"Total merged ranges: {len(ranges)}")
    # Print first 5 merged ranges
    for r in ranges[:10]:
        print(f"  - Range: {r.coord} (Top-left: {r.start_cell.coordinate})")
