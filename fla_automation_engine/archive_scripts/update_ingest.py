with open("/Users/apple/Desktop/FLA/fla_automation_engine/engine/ingestion.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_excel_heuristics = False
for line in lines:
    if "# Excel Heuristics" in line:
        in_excel_heuristics = True
        new_lines.append(line)
        continue
    
    if in_excel_heuristics:
        if "elif f.endswith('.xlsx') or f.endswith('.xls'):" in line:
            new_lines.append("            elif f.endswith('.xlsx') or f.endswith('.xls') or f.endswith('.md') or f.endswith('.pdf'):\n")
        elif "if \"shareholder\" in lower_name:" in line:
            new_lines.append("                if \"shareholder\" in lower_name:\n")
        elif "docs[\"shareholders_fdi\"] = full_path" in line:
            new_lines.append(line)
        elif "elif \"odi\" in lower_name:" in line:
            new_lines.append("                elif \"odi\" in lower_name:\n")
        elif "docs[\"odi_details\"] = full_path" in line:
            new_lines.append(line)
            in_excel_heuristics = False
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open("/Users/apple/Desktop/FLA/fla_automation_engine/engine/ingestion.py", "w") as f:
    f.writelines(new_lines)
