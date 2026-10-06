import json

with open("/Users/apple/Desktop/FLA/tool_structure.json", "r") as f:
    tool = json.load(f)

# Let's search sheet 3_FLA_RETURN for formulas containing "169" or "170" (which are exchange rates in 2_FINANCIALS)
print("=== Searching for exchange rate conversion formulas ===")
for sheet_name in ["3_FLA_RETURN", "2_FINANCIALS"]:
    for r_data in tool.get(sheet_name, []):
        row_num = r_data["row"]
        for c in r_data["cells"]:
            formula = c.get("formula")
            if formula and ("169" in formula or "170" in formula or "165" in formula or "166" in formula or "167" in formula):
                print(f"{sheet_name} Row {row_num:03d} Col {c['col']}: {c['val']} ({formula})")
