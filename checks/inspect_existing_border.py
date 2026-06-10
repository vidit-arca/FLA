import openpyxl

wb = openpyxl.load_workbook("/Users/apple/Desktop/FLA/output/FLA Return Populated.xlsx")
sheet = wb["Section III"]

cell = sheet["B17"]
b = cell.border
print("=== B17 BORDER STYLE & COLOR ===")
print(f"Top: style={b.top.style}, color={b.top.color}")
print(f"Bottom: style={b.bottom.style}, color={b.bottom.color}")
print(f"Left: style={b.left.style}, color={b.left.color}")
print(f"Right: style={b.right.style}, color={b.right.color}")
