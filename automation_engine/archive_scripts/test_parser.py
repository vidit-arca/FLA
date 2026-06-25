with open("/Users/apple/Desktop/FLA/automation_engine/engine/parser.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "odi_details" in line or "excel_extractor" in line:
        print(f"{i}: {line.strip()}")
