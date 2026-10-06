import json

with open("/Users/apple/Desktop/FLA/tool_structure.json", "r") as f:
    tool = json.load(f)

print("=== Analyzing 3_FLA_RETURN sheet for Section IV / ODI formulas ===")
for r_data in tool["3_FLA_RETURN"]:
    row_num = r_data["row"]
    cells = r_data["cells"]
    
    row_text = " | ".join([f"C{c['col']}: {c['val']} ({c['formula']})" if c['val'] is not None else "" for c in cells])
    row_text_clean = " ".join(row_text.split())
    if "DIE 1" in row_text_clean or "ODI" in row_text_clean or "Exchange Rate" in row_text_clean or "Net Worth of DIE" in row_text_clean:
        print(f"Row {row_num:03d}: {row_text_clean[:200]}")
