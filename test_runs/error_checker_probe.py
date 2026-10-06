"""Runner for the AOC-4 common-error checker.

``automation_engine/modules/aoc4/tests/test_error_checker.py`` is a legacy script
that cannot run as-is:

  * ``from aoc4_error_checker import ...`` needs the aoc4 package dir on sys.path
  * it looks for an ``excel/`` folder **next to itself** (``tests/excel/``), but the
    workbooks live in ``modules/aoc4/excel/``, and the file name it hardcodes
    (``ANNFIL COMMONERROR.xlsx``) does not match the shipped one
    (``ANNFIL COMMONERROR .xlsx`` - note the space).

This runner reproduces exactly what that script asserts (same engine, same mock
input) against the workbook that actually exists.

Run:  python test_runs/error_checker_probe.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from automation_engine.modules.aoc4.common_error.aoc4_error_checker import AOC4CommonErrorEngine

EXCEL = os.path.join(PROJECT_ROOT, "automation_engine", "modules", "aoc4", "excel",
                     "Annual Filing common error Output.xlsx")

# Mock input copied from tests/test_error_checker.py (the 'No' should raise a flag).
MOCK_INPUT = {
    "Whether audit report has the following fields \na) Opinion of the Auditor\n"
    "b) Basis of Opinion\nc) Emphasis of matter\nd) Key Audit Matters\n"
    "e) Other Information (if any)\nf) Responsibility of Management for the financial "
    "statement (FS)\ng) Auditor's responsibility for the Audit of FS\nh) Other matters\n"
    "i) report on other legal and regulatory requirements \nj) reporting on Internal "
    "finanical Controls  (if applicable)\n": "Yes",
    "whether CARO/Companies (Auditor's Report) Order is as per  format given in "
    "Jamku>Services>ANNUAL FILING >SAMPLE CARO": "No",
    "Whether EPS & Diluted EPS is mentioned in PL": "Yes",
}


def main():
    print("workbook : %s" % EXCEL)
    print("exists   : %s" % os.path.exists(EXCEL))
    engine = AOC4CommonErrorEngine(EXCEL, enable_llm_judge=False)
    print("rules loaded from excel: %d" % len(engine.rules))

    flags = engine.execute(dict(MOCK_INPUT))
    print("flags produced        : %d" % len(flags))
    print("\nfirst 5 flags")
    for flag in flags[:5]:
        print("  [%s] %s -> %s" % (flag.get("rule_id"), str(flag.get("particulars"))[:60],
                                   flag.get("user_value")))

    ids = {f.get("rule_id") for f in flags}
    print("\ndistinct rule_ids : %d" % len(ids))
    negative = [f for f in flags if str(f.get("user_value")).strip().lower() in
                ("no", "failed", "missing data")]
    print("non-conforming flags raised: %d (the mock 'No' answer must be among them)"
          % len(negative))
    for flag in negative[:5]:
        print("  - %s: %s" % (flag.get("rule_id"), str(flag.get("particulars"))[:70]))
    return 0 if flags else 1


if __name__ == "__main__":
    sys.exit(main())
