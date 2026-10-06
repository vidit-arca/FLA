with open("/Users/apple/Desktop/FLA/automation_engine/engine/parser.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_extract = False
for line in lines:
    if "particulars = row[particulars_col_idx].lower().strip()" in line:
        new_lines.append('                particulars = " | ".join([str(c).lower().strip() for c in row if isinstance(c, str)]).strip()\n')
    elif "if \"odi_details\" in docs_paths:" in line:
        new_lines.append('            if "extra_details" in docs_paths:\n')
        new_lines.append('                extra_path = docs_paths["extra_details"]\n')
        new_lines.append('                print(f"[*] Ingesting Extra Details: {os.path.basename(extra_path)}")\n')
        new_lines.append('                if extra_path.endswith(".xlsx") or extra_path.endswith(".xls"):\n')
        new_lines.append('                    import pandas as pd\n')
        new_lines.append('                    try:\n')
        new_lines.append('                        xl = pd.ExcelFile(extra_path)\n')
        new_lines.append('                        extra_tables = []\n')
        new_lines.append('                        for sheet in xl.sheet_names:\n')
        new_lines.append('                            df = pd.read_excel(xl, sheet_name=sheet)\n')
        new_lines.append('                            header = [str(c).lower() for c in df.columns]\n')
        new_lines.append('                            data = [[str(x) if pd.notna(x) else "" for x in r] for r in df.values]\n')
        new_lines.append('                            extra_tables.append([header] + data)\n')
        new_lines.append('                        extra_data = self.extract_financials_from_tables(extra_tables)\n')
        new_lines.append('                        all_extracted.update(extra_data)\n')
        new_lines.append('                        print(f"    [+] Extracted {len(extra_data)} dynamic fields from extra Excel.")\n')
        new_lines.append('                    except Exception as e:\n')
        new_lines.append('                        print(f"    [!] Error parsing extra details: {e}")\n\n')
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("/Users/apple/Desktop/FLA/automation_engine/engine/parser.py", "w") as f:
    f.writelines(new_lines)
