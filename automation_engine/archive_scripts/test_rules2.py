with open("/Users/apple/Desktop/FLA/automation_engine/engine/rule_engine.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines[:100]):
    if "cells[cell_data.get(\"cell\")]" in line or "cells[cell_key]" in line or "fdi_investor_2_countries_json" in line or "extracted_data" in line:
        print(f"{i}: {line.strip()}")
