import json

with open("/Users/apple/Desktop/FLA/skel_structure.json", "r") as f:
    skel = json.load(f)

print("=== Analyzing Section IV in skeletal sheet ===")
for cell_data in skel.get("Section IV", []):
    row_num = cell_data["row"]
    cells = cell_data["cells"]
    
    row_text = " | ".join([f"C{c['col']}: {c['val']}" if c['val'] is not None else "" for c in cells])
    row_text_clean = " ".join(row_text.split())
    if "DIE" in row_text_clean or "3." in row_text_clean or "Equity" in row_text_clean:
        print(f"Row {row_num:03d}: {row_text_clean[:200]}")
