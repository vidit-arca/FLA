import json

with open("/Users/apple/Desktop/FLA/tool_structure.json", "r") as f:
    tool = json.load(f)

for sheet_name in ["2_FINANCIALS", "3_FLA_RETURN"]:
    print(f"\n--- Checking sheet {sheet_name} ---")
    for r_data in tool[sheet_name]:
        row_num = r_data["row"]
        cells = r_data["cells"]
        row_str = " | ".join([f"C{c['col']}: {c['val']} ({c['formula']})" if c['val'] is not None else "" for c in cells])
        if "Net Worth of DIE" in row_str or "3.5" in row_str or "DIE Name" in row_str:
            print(f"Row {row_num:03d}: {row_str}")
