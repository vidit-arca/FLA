import json

with open("/Users/apple/Desktop/FLA/automation_engine/rules_config.json", "r") as f:
    config = json.load(f)

found = []
for section, cells in config.get("cell_mappings", {}).items():
    for cell_key, cell_data in cells.items():
        if cell_data.get("field") == "fdi_investor_2_countries_json" or cell_key == "fdi_investor_2_countries_json":
            found.append((section, cell_key, cell_data))

print(found)
