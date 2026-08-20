import sys
sys.path.append('/Users/apple/Desktop/FLA/automation_engine/modules/aoc4')
from parser import AOC4Parser
import re

p = AOC4Parser(config_path='/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/rules_config.json')

import glob
files = glob.glob('/Users/apple/Desktop/FLA/testing/Cameo global/2024-25/ocr_output/*.md')
full_text = ''
for f in files:
    with open(f, 'r') as fp:
        full_text += fp.read() + '\n'

lines = full_text.lower().split("\n")
for idx, line in enumerate(lines):
    if re.search(r"borrowing", line):
        # same skip rules
        if re.search(r'proceeds from|repayment of|cash flow', line):
            continue
        print(f"Line {idx}: {line.strip()}")
        match_obj = re.search(r"borrowing", line)
        search_text = line[match_obj.start():]
        print(f"  search_text init: {search_text}")
        has_numbers = bool(re.findall(r'(-?\s*(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?|\((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?\))', line))
        is_bs_row_no_value = bool(re.match(r'^\s*\(?[a-z]\)?[.)\s]', line)) and not has_numbers
        if not has_numbers and not is_bs_row_no_value and not line.strip().startswith("|"):
            for i in range(1, 3):
                if idx + i < len(lines):
                    next_line = lines[idx + i]
                    if next_line.strip().startswith("|"):
                        break
                    search_text += " " + next_line
        print(f"  search_text after lookahead: {search_text}")

