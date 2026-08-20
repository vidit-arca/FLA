import sys
sys.path.append('/Users/apple/Desktop/FLA/automation_engine/modules/aoc4')
from parser import AOC4Parser
import glob

p = AOC4Parser(config_path='/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/rules_config.json')
files = glob.glob('/Users/apple/Desktop/FLA/testing/Cameo global/2024-25/ocr_output/*.md')
full_text = ''
for f in files:
    with open(f, 'r') as fp:
        full_text += fp.read() + '\n'

res = p.extract_financials_from_text(full_text, ["borrowings"])
print("Extraction:", res)
