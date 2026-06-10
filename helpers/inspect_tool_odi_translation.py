import json

with open("/Users/apple/Desktop/FLA/tool_structure.json", "r") as f:
    tool = json.load(f)

print("=== Analyzing DIE 1 rows in sheet 3_FLA_RETURN ===")
for r_data in tool["3_FLA_RETURN"]:
    row_num = r_data["row"]
    row_text = " | ".join([f"C{c['col']}: {c['val']} ({c['formula']})" if c['val'] is not None else "" for c in r_data["cells"]])
    row_text_clean = " ".join(row_text.split())
    if "DIE 1" in row_text_clean:
        print(f"Row {row_num:03d}: {row_text_clean}")
