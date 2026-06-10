import json

with open("fla_automation_engine/rules_config.json", "r") as f:
    config = json.load(f)

sec3 = config["cell_mappings"]["Section III"]

# Find all FDI1 rules
fdi1_rules = {}
for k, v in list(sec3.items()):
    if k.startswith("FDI1_"):
        fdi1_rules[k] = v

def create_fdi_rules(index, base_row_offsets):
    rules = {}
    for k, v in fdi1_rules.items():
        new_k = k.replace("FDI1_", f"FDI{index}_")
        new_v = dict(v)
        
        # update row label
        new_v["row_label"] = v["row_label"].replace("FDI 1:", f"FDI {index}:").replace("1.1 ", f"1.1 ").replace("1.2 ", f"1.2 ").replace("2 ", f"2 ").replace("2.1 ", f"2.1 ").replace("2.2 ", f"2.2 ").replace("3 ", f"3 ") # label doesn't usually matter for the engine itself, but for reporting it does. Let's just do a basic replace.
        new_v["row_label"] = new_v["row_label"].replace("FDI 1", f"FDI {index}")
        
        # update field names
        if "field" in new_v:
            new_v["field"] = v["field"].replace("fdi_investor_1_", f"fdi_investor_{index}_")
            
        # update formulas
        if "formula" in new_v:
            new_v["formula"] = v["formula"].replace("fdi_investor_1_", f"fdi_investor_{index}_")
            
        # update cell coordinates based on pattern
        if "cell" in new_v:
            old_cell = v["cell"]
            # e.g. D17 -> D + (17 + offset)
            col = old_cell[0]
            row = int(old_cell[1:])
            new_row = row + base_row_offsets[index]
            new_v["cell"] = f"{col}{new_row}"
            
        # Update subtract_cells formula cell refs if it is one
        if "subtract_cells" in new_v.get("formula", ""):
            # e.g., "subtract_cells('Section III', 'D24', 'D25')" -> new cells
            f_col = new_v["cell"][0]
            row24 = 24 + base_row_offsets[index]
            row25 = 25 + base_row_offsets[index]
            new_v["formula"] = f"subtract_cells('Section III', '{f_col}{row24}', '{f_col}{row25}')"
            
        rules[new_k] = new_v
    return rules

# FDI1 starts around row 17 (Name is B17, Liabilities is D21, Disinvestment is D26)
# According to tool_structure.json:
# FDI 1 Name is row 18 (which has cell B18?). Wait, tool_structure row 18? No, tool_structure.json has "val" entries.
# Actually, the user has "FLA Tool v5 fixed.xlsx" where the cells might be different. Let's look at what we know.
# Investor 1: Other Liabilities is row 88.
# Investor 2: Other Liabilities is row 100. (+12 rows)
# Investor 3: Other Liabilities is row 112. (+24 rows)
# Therefore, FDI2 is exactly +12 rows from FDI1. FDI3 is +24 rows from FDI1.

fdi2_rules = create_fdi_rules(2, {2: 12})
fdi3_rules = create_fdi_rules(3, {3: 24})

# Insert into Section III
for k, v in fdi2_rules.items():
    sec3[k] = v
for k, v in fdi3_rules.items():
    sec3[k] = v

with open("fla_automation_engine/rules_config.json", "w") as f:
    json.dump(config, f, indent=2)

print("Updated rules_config.json successfully!")
