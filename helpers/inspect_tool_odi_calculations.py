import json

with open("/Users/apple/Desktop/FLA/tool_structure.json", "r") as f:
    tool = json.load(f)

print("=== Analyzing ODI calculations in tool file ===")
for sheet_name in ["3_FLA_RETURN", "2_FINANCIALS"]:
    for r_data in tool.get(sheet_name, []):
        row_num = r_data["row"]
        row_text = " | ".join([f"C{c['col']}: {c['val']} ({c['formula']})" if c['val'] is not None else "" for c in r_data["cells"]])
        row_text_clean = " ".join(row_text.split())
        if "DIE 1" in row_text_clean and ("Equity" in row_text_clean or "Capital" in row_text_clean or "Claims" in row_text_clean):
            print(f"{sheet_name} Row {row_num:03d}: {row_text_clean[:200]}")
