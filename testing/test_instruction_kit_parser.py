"""
Unit test for MCA Instruction Kit Parser and Conditional DAG Engine.
"""

import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from automation_engine.modules.idp_studio.forms import InstructionKitParser


def test_instruction_kit_parsing():
    pdf_path = os.path.join(REPO_ROOT, "Instruction Kit_ADT-1.pdf")
    assert os.path.exists(pdf_path), f"Instruction Kit PDF not found at {pdf_path}"

    parser = InstructionKitParser()
    schema = parser.parse(pdf_path)

    print("\n[+] Testing Template Name and Governing Law...")
    assert "ADT-1" in schema["template_name"], f"Expected ADT-1 in template name, got {schema['template_name']}"
    assert "Companies Act" in schema["governing_law"], f"Expected Companies Act in law, got {schema['governing_law']}"

    fields = schema.get("fields", [])
    print(f"[+] Total fields extracted: {len(fields)}")
    assert len(fields) >= 15, f"Expected at least 15 fields, got {len(fields)}"

    # Check key canonical fields
    field_ids = {f["id"]: f for f in fields}
    print("[+] Validating key canonical fields presence...")
    
    # Check CIN
    has_cin = any("corporate" in fid or "cin" in fid for fid in field_ids)
    assert has_cin, "Missing CIN field in parsed schema"

    # Check Category of Auditor (Radio with Individual & Firm)
    has_category = any("category" in fid for fid in field_ids)
    assert has_category, "Missing Category of Auditor field"

    # Check Firm Registration Number (FRN)
    has_frn = any("firm" in fid and "registration" in fid for fid in field_ids)
    assert has_frn, "Missing Firm Registration Number (FRN)"

    # Check conditional dependencies
    print("[+] Validating conditional DAG dependencies...")
    dependent_fields = [f for f in fields if f.get("depends_on")]
    print(f"[+] Found {len(dependent_fields)} conditional dependent fields:")
    for df in dependent_fields:
        dep = df["depends_on"]
        print(f"    - {df['id']} ({df.get('label')}) -> depends on {dep.get('field')} {dep.get('operator')} '{dep.get('value')}'")

    assert len(dependent_fields) >= 1, "Expected at least 1 conditional dependent field"

    print("\n[✓] ALL INSTRUCTION KIT PARSER TESTS PASSED!")


if __name__ == "__main__":
    test_instruction_kit_parsing()
