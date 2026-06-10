import json

with open("/Users/apple/Desktop/FLA/skel_structure.json", "r") as f:
    skel = json.load(f)

for sheet_name, rows in skel.items():
    print(f"\n=================== SHEET: {sheet_name} ===================")
    print(f"Total active rows: {len(rows)}")
    for r_idx, r_data in enumerate(rows[:50]): # show first 50 rows of each sheet
        row_num = r_data["row"]
        cells = r_data["cells"]
        # Filter cells to non-null or index them
        cell_strs = []
        for c in cells:
            val = c["val"]
            if val is not None:
                cell_strs.append(f"C{c['col']}: {repr(val)}")
        print(f"Row {row_num:03d}: " + " | ".join(cell_strs))
