import re
with open("/Users/apple/Desktop/FLA/fla_automation_engine/engine/extractors/text_extractor.py", "r") as f:
    print(re.findall(r"def \w+", f.read()))
