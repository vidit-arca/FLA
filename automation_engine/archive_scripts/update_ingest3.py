with open("/Users/apple/Desktop/FLA/automation_engine/engine/ingestion.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "files = [f for f in os.listdir(self.signed_dir)]" in line:
        new_lines.append("        files_to_check = []\n")
        new_lines.append("        for root, _, files in os.walk(self.signed_dir):\n")
        new_lines.append("            for f in files:\n")
        new_lines.append("                if not f.startswith('.') and not 'venv' in root:\n")
        new_lines.append("                    files_to_check.append((root, f))\n")
    elif "for f in files:" in line and "lower_name = f.lower()" in lines[i+1]:
        new_lines.append("        for root, f in files_to_check:\n")
    elif "full_path = os.path.join(self.signed_dir, f)" in line:
        new_lines.append("            full_path = os.path.join(root, f)\n")
    elif "for f in os.listdir(parent_dir):" in line:
        new_lines.append("                for root, _, pfiles in os.walk(parent_dir):\n")
        new_lines.append("                    for f in pfiles:\n")
    elif "full_path = os.path.join(parent_dir, f)" in line:
        new_lines.append("                        full_path = os.path.join(root, f)\n")
    else:
        new_lines.append(line)

with open("/Users/apple/Desktop/FLA/automation_engine/engine/ingestion.py", "w") as f:
    f.writelines(new_lines)
