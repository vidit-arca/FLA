import json

with open("/Users/apple/Desktop/FLA/automation_engine/rules_config.json", "r") as f:
    config = json.load(f)

odi_fields = []
for cell_key, cell_data in config["cell_mappings"].get("Section IV", {}).items():
    if cell_data.get("type") == "extracted":
        odi_fields.append((cell_data.get("field"), cell_data.get("row_label")))

for f in odi_fields:
    print(f)
