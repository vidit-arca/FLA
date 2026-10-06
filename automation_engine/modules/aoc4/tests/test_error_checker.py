import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
AOC4_DIR = os.path.dirname(TESTS_DIR)                                     # .../modules/aoc4
# aoc4 -> modules -> automation_engine -> repository root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(AOC4_DIR)))

for _path in (PROJECT_ROOT, AOC4_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from automation_engine.modules.aoc4.common_error.aoc4_error_checker import AOC4CommonErrorEngine

def test_engine():
    excel_path = os.path.join(AOC4_DIR, 'excel', 'ANNFIL COMMONERROR .xlsx')
    engine = AOC4CommonErrorEngine(excel_path)
    
    # Create a mock input json that mimics the parser output
    mock_input = {
        "Whether audit report has the following fields \na) Opinion of the Auditor\nb) Basis of Opinion\nc) Emphasis of matter\nd) Key Audit Matters\ne) Other Information (if any)\nf) Responsibility of Management for the financial statement (FS)\ng) Auditor's responsibility for the Audit of FS\nh) Other matters\ni) report on other legal and regulatory requirements \nj) reporting on Internal finanical Controls  (if applicable)\n": "Yes",
        "whether CARO/Companies (Auditor's Report) Order is as per  format given in Jamku>Services>ANNUAL FILING >SAMPLE CARO": "No", # This should trigger a flag
        "Whether EPS & Diluted EPS is mentioned in PL": "Yes"
        # We are intentionally leaving out other fields to see if the engine flags them as missing.
    }
    
    print(f"Loaded {len(engine.rules)} rules from excel.")
    
    flags = engine.execute(mock_input)
    
    print(f"\n--- VALIDATION FLAGS ({len(flags)} found) ---")
    for flag in flags[:5]: # Print first 5
        print(f"[{flag['rule_id']}] Source: {flag['source']}")
        print(f"  Particulars: {flag['particulars'][:60]}...")
        print(f"  User Value: {flag['user_value']}")
        print(f"  Reason: {flag['reason']}\n")
        
    print(f"... and {len(flags) - 5} more flags.")

if __name__ == "__main__":
    test_engine()
