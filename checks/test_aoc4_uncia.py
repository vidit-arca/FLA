#!/usr/bin/env python3
"""
Run AOC4 test with Uncia data
"""

import os
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from automation_engine.modules.aoc4.parser import AOC4Parser
from automation_engine.modules.aoc4.compliance_engine import AOC4ComplianceEngine
from automation_engine.modules.aoc4.excel import extract_aoc4_cells

# Paths
DATA_DIR = Path("/Users/apple/Desktop/FLA/uncai")
OUTPUT_DIR = Path("/Users/apple/Desktop/FLA/output")

# Create output directories
OUTPUT_DIR.mkdir(exist_ok=True)
AOC4_OUTPUT = OUTPUT_DIR / "aoc4"
AOC4_OUTPUT.mkdir(exist_ok=True)

def main():
    print("=" * 60)
    print("Running AOC4 Compliance Test for Uncia")
    print("=" * 60)
    print()

    # Check for required files
    print("Checking for required AOC4 files...")

    financials_file = DATA_DIR / "Uncia_Standalone Financials_Mar 2026 Final v7.xlsx"
    previous_year_file = DATA_DIR / "Previous year financials.xlsx"

    if not financials_file.exists():
        print(f"Warning: Financials file not found: {financials_file}")
        print("Using Previous year financials.md for testing...")
        previous_year_file = DATA_DIR / "Previous year financials.md"

    if not previous_year_file.exists():
        print(f"Error: Previous year file not found: {previous_year_file}")
        return

    print(f"✓ Financials: {financials_file}")
    print(f"✓ Previous Year: {previous_year_file}")
    print()

    # Initialize AOC4 parser
    print("Initializing AOC4 parser...")
    parser = AOC4Parser(
        financials_file=financials_file,
        previous_year_file=previous_year_file
    )

    # Parse the financials
    print("Parsing financial documents...")
    parser.parse_documents()
    print()

    # Extract AOC4 cells
    print("Extracting AOC4 compliance cells...")
    cells = extract_aoc4_cells(parser)

    print(f"Extracted {len(cells)} AOC4 cells")
    for cell_id, cell in sorted(cells.items()):
        print(f"  - {cell_id}: {cell.get('value', 'N/A')}")
    print()

    # Initialize compliance engine
    print("Initializing AOC4 compliance engine...")
    engine = AOC4ComplianceEngine(parser, cells)

    # Evaluate compliance
    print("Evaluating AOC4 compliance...")
    results = engine.evaluate()

    print()
    print("=" * 60)
    print("COMPLIANCE RESULTS")
    print("=" * 60)
    print()

    print(f"Total Requirements: {results['total_requirements']}")
    print(f"Compliant: {results['compliant_count']}")
    print(f"Non-Compliant: {results['non_compliant_count']}")
    print()

    if results['compliance_score'] is not None:
        print(f"Compliance Score: {results['compliance_score']:.1%}")
    print()

    # Print non-compliant items
    non_compliant = results.get('non_compliant', [])
    if non_compliant:
        print("Non-Compliant Items:")
        print("-" * 40)
        for item in non_compliant:
            print(f"  - {item['section_id']}: {item['description']}")
            print(f"    Required: {item.get('required_value', 'N/A')}")
            print(f"    Found: {item.get('actual_value', 'N/A')}")
            print()
    else:
        print("✓ All requirements are compliant!")
    print()

    # Save results to Excel
    print("Saving results to Excel...")
    output_file = AOC4_OUTPUT / "Uncia_AOC4_Compliance.xlsx"
    engine.save_to_excel(output_file)
    print(f"Results saved to: {output_file}")
    print()

    # Save detailed report
    report_file = AOC4_OUTPUT / "Uncia_AOC4_Report.md"
    with open(report_file, "w") as f:
        f.write("# Uncia AOC4 Compliance Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"**Compliance Score**: {results['compliance_score']:.1%} (if applicable)\n")
        f.write(f"**Total Requirements**: {results['total_requirements']}\n")
        f.write(f"**Compliant**: {results['compliant_count']}\n")
        f.write(f"**Non-Compliant**: {results['non_compliant_count']}\n")
        f.write("\n## Non-Compliant Items\n")
        f.write("-" * 40 + "\n")
        if non_compliant:
            for item in non_compliant:
                f.write(f"\n### {item['section_id']}\n")
                f.write(f"- **Description**: {item['description']}\n")
                f.write(f"- **Required**: {item.get('required_value', 'N/A')}\n")
                f.write(f"- **Found**: {item.get('actual_value', 'N/A')}\n")
        else:
            f.write("✓ All requirements are compliant!\n")
    print(f"Report saved to: {report_file}")
    print()

    print("=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
