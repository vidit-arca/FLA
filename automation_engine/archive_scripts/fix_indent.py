import re

file_path = "/Users/apple/Desktop/FLA/automation_engine/engine/parser.py"
with open(file_path, "r") as f:
    lines = f.readlines()

for i in range(480, 514):
    line = lines[i]
    if line.startswith("                "):
        # outdent by 4 spaces
        lines[i] = line[4:]

with open(file_path, "w") as f:
    f.writelines(lines)
