import json

with open("/Users/apple/Desktop/FLA/tool_structure.json", "r") as f:
    tool = json.load(f)

print("=== Analyzing 3_FLA_RETURN sheet around rows 135 to 160 ===")
for r_data in tool["3_FLA_RETURN"]:
    row_num = r_data["row"]
    if 130 <= row_num <= 165:
        cells = r_data["cells"]
        row_text = " | ".join([f"C{c['col']}: {c['val']} ({c['formula']})" if c['val'] is not None else "" for c in cells])
        row_text_clean = " ".join(row_text.split())
        print(f"Row {row_num:03d}: {row_text_clean}")
