import re
with open("/Users/apple/Desktop/FLA/fla_automation_engine/run_pipeline.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines[140:175]):
    print(f"{140+i}: {line.strip()}")
