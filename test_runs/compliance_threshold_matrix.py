"""Boundary/threshold verification of the AOC-4 compliance engine.

Drives the REAL ``PrivateComplianceEngine`` (LLM off, fully deterministic) through
scenarios pinned to the Companies Act 2013 limits the engine implements, so the
thresholds can be checked at, below and above every boundary.

Run:  python test_runs/compliance_threshold_matrix.py
Exit code 0 = every expectation met.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from automation_engine.modules.aoc4.compliance_engine import PrivateComplianceEngine

CR = 10000000.0          # 1 crore, in the absolute rupees the engine expects
LAKH = 100000.0
BASE = {
    "company_type": "private limited company",
    "is_listed": "no",
    "is_ind_as": "no",
    "is_subsidiary_or_holding": "no",
}


def case(name, overrides, expected):
    return {"name": name, "input": dict(BASE, **overrides), "expected": expected}


# One entry per scenario: (flag_id -> expected user_value).
SCENARIOS = [
    # ---- 1. Small company: turnover <= 100 Cr AND PUC <= 10 Cr AND not holding/sub
    case("small co: turnover 99 Cr / PUC 9 Cr",
         {"turnover": 99 * CR, "paid_up_capital": 9 * CR},
         {"COMP_SMALL_CO": "Yes"}),
    case("small co: turnover 101 Cr (over the 100 Cr limit)",
         {"turnover": 101 * CR, "paid_up_capital": 9 * CR},
         {"COMP_SMALL_CO": "No"}),
    case("small co: PUC 11 Cr (over the 10 Cr limit)",
         {"turnover": 99 * CR, "paid_up_capital": 11 * CR},
         {"COMP_SMALL_CO": "No"}),
    case("small co: holding/subsidiary (disqualified)",
         {"turnover": 1 * CR, "paid_up_capital": 1 * CR,
          "is_subsidiary_or_holding": "subsidiary"},
         {"COMP_SMALL_CO": "No"}),
    case("small co: MCA master data says Yes (override beats the math)",
         {"turnover": 500 * CR, "paid_up_capital": 50 * CR, "mca_small_company": "Yes"},
         {"COMP_SMALL_CO": "Yes"}),

    # ---- 2. CARO: private + non-small -> exempt only inside (PUC+Res<=1 Cr, Bor<=1 Cr, TO<=10 Cr)
    #      NOTE: the 3 thresholds are only reachable when the company is NOT small, which
    #      for a private company requires the MCA master data to say so (mca_small_company=No);
    #      any private company inside these limits would otherwise be small and auto-exempt.
    case("CARO: non-small private inside all 3 limits",
         {"mca_small_company": "No", "turnover": 9 * CR, "paid_up_capital": 0.5 * CR,
          "reserves_and_surplus": 0.4 * CR, "borrowings": 0.9 * CR},
         {"COMP_CARO": "Not Applicable"}),
    case("CARO: borrowings 1.5 Cr (over the 1 Cr limit)",
         {"mca_small_company": "No", "turnover": 9 * CR, "paid_up_capital": 0.5 * CR,
          "reserves_and_surplus": 0.4 * CR, "borrowings": 1.5 * CR},
         {"COMP_CARO": "Applicable"}),
    case("CARO: turnover 11 Cr (over the 10 Cr limit)",
         {"mca_small_company": "No", "turnover": 11 * CR, "paid_up_capital": 0.5 * CR,
          "reserves_and_surplus": 0.4 * CR, "borrowings": 0.9 * CR},
         {"COMP_CARO": "Applicable"}),
    case("CARO: small company is exempt",
         {"turnover": 99 * CR, "paid_up_capital": 9 * CR},
         {"COMP_CARO": "Not Applicable"}),

    # ---- 3. CSR: NW >= 500 Cr OR TO >= 1000 Cr OR PBT >= 5 Cr
    case("CSR: PBT 5 Cr (at the limit)",
         {"net_profit_before_tax": 5 * CR}, {"COMP_CSR": "Applicable"}),
    case("CSR: PBT 4.9 Cr with modest NW/TO",
         {"net_profit_before_tax": 4.9 * CR, "net_worth": 100 * CR, "turnover": 500 * CR},
         {"COMP_CSR": "Not Applicable"}),
    case("CSR: net worth 500 Cr (at the limit)",
         {"net_worth": 500 * CR, "net_profit_before_tax": 1 * CR},
         {"COMP_CSR": "Applicable"}),

    # ---- 4. Rotation of auditors: listed/public, or private with PUC >= 50 Cr
    case("Rotation: private PUC 50 Cr (at the limit)",
         {"paid_up_capital": 50 * CR}, {"COMP_ROTATION": "Applicable"}),
    case("Rotation: private PUC 49.9 Cr",
         {"paid_up_capital": 49.9 * CR}, {"COMP_ROTATION": "Not Applicable"}),

    # ---- 5. XBRL: listed OR Ind AS OR PUC >= 5 Cr OR turnover >= 100 Cr
    case("XBRL: PUC 5 Cr (at the limit)",
         {"paid_up_capital": 5 * CR, "turnover": 1 * CR}, {"COMP_XBRL": "Applicable"}),
    case("XBRL: turnover 100 Cr (at the limit)",
         {"paid_up_capital": 1 * CR, "turnover": 100 * CR}, {"COMP_XBRL": "Applicable"}),
    case("XBRL: below both limits, unlisted, non-Ind AS",
         {"paid_up_capital": 4.9 * CR, "turnover": 99 * CR},
         {"COMP_XBRL": "Not Applicable"}),

    # ---- 6. Vigil mechanism: borrowings > 50 Cr
    case("Vigil: borrowings 51 Cr", {"borrowings": 51 * CR}, {"COMP_VIGIL": "Applicable"}),
    case("Vigil: borrowings 50 Cr (at the limit, not over)",
         {"borrowings": 50 * CR}, {"COMP_VIGIL": "Not Applicable"}),

    # ---- 7. Internal financial controls (private): TO < 50 Cr AND borrowings < 25 Cr
    case("IFC: private TO 49 Cr / borrowings 24 Cr",
         {"turnover": 49 * CR, "borrowings": 24 * CR}, {"COMP_IFC": "Not Applicable"}),
    case("IFC: private TO 50 Cr (at the limit)",
         {"turnover": 50 * CR, "borrowings": 24 * CR}, {"COMP_IFC": "Applicable"}),

    # ---- 8. Internal audit: TO >= 200 Cr OR borrowings >= 100 Cr
    case("Internal audit: TO 200 Cr (at the limit)",
         {"turnover": 200 * CR}, {"COMP_INT_AUDIT": "Applicable"}),
    case("Internal audit: TO 199 Cr / borrowings 99 Cr",
         {"turnover": 199 * CR, "borrowings": 99 * CR},
         {"COMP_INT_AUDIT": "Not Applicable"}),

    # ---- 9. Ind AS: listed, or Ind AS applied, or NW >= 250 Cr
    case("Ind AS: net worth 250 Cr (at the limit)",
         {"net_worth": 250 * CR}, {"COMP_IND_AS": "Applicable"}),
    case("Ind AS: net worth 249 Cr, unlisted, non-Ind AS",
         {"net_worth": 249 * CR}, {"COMP_IND_AS": "Not Applicable"}),

    # ---- 10. MGT-8: listed OR PUC >= 10 Cr OR turnover >= 50 Cr
    case("MGT-8: PUC 10 Cr (at the limit)",
         {"paid_up_capital": 10 * CR, "turnover": 1 * CR}, {"COMP_MGT_8": "Applicable"}),
    case("MGT-8: PUC 9 Cr / turnover 49 Cr",
         {"paid_up_capital": 9 * CR, "turnover": 49 * CR},
         {"COMP_MGT_8": "Not Applicable"}),

    # ---- 11/12/13. MGT-7 certification, secretarial audit, KMP
    case("MGT-7 cert: non-small company loses the exemption",
         {"turnover": 101 * CR, "paid_up_capital": 9 * CR},
         {"COMP_MGT_7_CERT": "Applicable"}),
    case("MGT-7 cert: small company exempt",
         {"turnover": 99 * CR, "paid_up_capital": 9 * CR},
         {"COMP_MGT_7_CERT": "Not Applicable"}),
    case("Secretarial audit: borrowings 100 Cr (at the limit)",
         {"borrowings": 100 * CR}, {"COMP_SEC_AUDIT": "Applicable"}),
    case("KMP: PUC 10 Cr (at the limit)",
         {"paid_up_capital": 10 * CR}, {"COMP_KMP": "Applicable"}),

    # ---- 14/15/16/17. Loans, cost audit, charge form
    case("Sec 186: investments present", {"investments_made": 1.0},
         {"COMP_LOAN_186": "Applicable"}),
    case("Sec 186: nothing detected", {},
         {"COMP_LOAN_186": "Not Applicable"}),
    case("Loan to director: asset-side loan present",
         {"loan_to_directors_assets": 1.0}, {"COMP_LOAN_DIRECTOR": "Applicable"}),
    case("Cost audit: always flagged for manual verification", {},
         {"COMP_COST_AUDIT": "Not Applicable"}),
    case("Charge form: secured loan present", {"secured_loan": 1.0},
         {"COMP_CHARGE_FORM": "Applicable"}),

    # ---- 18/19. AOC-1 / AOC-2 + RPT omnibus
    case("AOC-1: holding company", {"is_holding_company": "yes"},
         {"COMP_AOC_1": "Applicable"}),
    case("AOC-2: RPT sales present", {"rpt_sale_goods": 1.0},
         {"COMP_AOC_2": "Applicable", "COMP_RPT_OMNIBUS": "Applicable"}),

    # ---- 20/21/22/23/24. CSR committee, deposits, DPT-3, MSME, BEN-2
    case("CSR committee: 2% of 3-yr PBT (10 Cr) exceeds 50 lakh",
         {"net_profit_before_tax": 10 * CR}, {"COMP_CSR_COMMITTEE": "Applicable"}),
    case("CSR committee: 2% of 3-yr PBT (5 lakh) below 50 lakh",
         {"net_profit_before_tax": 5 * LAKH}, {"COMP_CSR_COMMITTEE": "Not Applicable"}),
    case("Deposit declaration: loan from director present",
         {"loan_from_directors": 1.0}, {"COMP_DEPOSIT_DEC": "Applicable"}),
    case("DPT-3: borrowings present", {"borrowings": 1.0}, {"COMP_DPT_3": "Applicable"}),
    case("MSME: dues to MSME present", {"dues_to_msme": 1.0}, {"COMP_MSME": "Applicable"}),
    case("BEN-2: corporate shareholder present",
         {"has_corporate_shareholders": "yes"}, {"COMP_BEN_2": "Applicable"}),
    case("BEN-2: no corporate shareholder",
         {"has_corporate_shareholders": "no"}, {"COMP_BEN_2": "Not Applicable"}),
    case("BEN-2: shareholder data absent -> must ask for manual review",
         {}, {"COMP_BEN_2": "Missing Data"}),
]


def run(inputs):
    engine = PrivateComplianceEngine(enable_llm_judge=False)
    return {f["id"]: f for f in engine.execute(dict(inputs))}


# Behaviour that contradicts the statute / the engine's own intent. Reported, not scored.
KNOWN_GAPS = [
    {"name": "public company judged a 'Small Company' (Sec 2(85) requires a PRIVATE company)",
     "input": {"company_type": "public limited company", "turnover": 1 * CR,
               "paid_up_capital": 1 * CR},
     "flag": "COMP_SMALL_CO", "engine": "Yes", "statute": "No / out of scope"},
    {"name": "public company then inherits the small-company CARO exemption",
     "input": {"company_type": "public limited company", "turnover": 1 * CR,
               "paid_up_capital": 1 * CR},
     "flag": "COMP_CARO", "engine": "Not Applicable", "statute": "Applicable"},
    {"name": "missing turnover/PUC data is coerced to 0 -> 'Small Company: Yes' "
             "(the 'Missing Data' branch is unreachable)",
     "input": {}, "flag": "COMP_SMALL_CO", "engine": "Yes", "statute": "Manual / Missing Data"},
    {"name": "missing turnover/borrowings data is coerced to 0 -> 'Internal Audit: Not Applicable'",
     "input": {}, "flag": "COMP_INT_AUDIT", "engine": "Not Applicable",
     "statute": "Manual / Missing Data"},
]


RICH = {
    "turnover": 60 * CR, "paid_up_capital": 6 * CR, "reserves_and_surplus": 30 * CR,
    "borrowings": 30 * CR, "net_profit_before_tax": 6 * CR, "secured_loan": 1 * CR,
    "rpt_sale_goods": 5 * CR, "loan_from_directors": 1 * CR, "dues_to_msme": 1 * CR,
    "investments_made": 1 * CR,
}


def main():
    failures = []
    print("=" * 118)
    print("AOC-4 COMPLIANCE ENGINE - THRESHOLD MATRIX (deterministic, LLM off)")
    print("=" * 118)
    print("%-58s %-18s %-16s %-16s %s" % ("SCENARIO", "FLAG", "EXPECTED", "ACTUAL", ""))
    print("-" * 118)
    for scenario in SCENARIOS:
        flags = run(scenario["input"])
        for flag_id, expected in scenario["expected"].items():
            actual = flags.get(flag_id, {}).get("user_value")
            ok = actual == expected
            if not ok:
                failures.append((scenario["name"], flag_id, expected, actual))
            print("%-58s %-18s %-16s %-16s %s" % (
                scenario["name"][:58], flag_id, expected, actual,
                "OK" if ok else "** FAIL **"))

    empty_flags = run({})
    print("-" * 118)
    print("full flag set, EMPTY input  : %d flags" % len(empty_flags))
    print("full flag set, RICH input   : %d flags" % len(run(RICH)))
    print("distinct ids emitted overall: %d" % len(set(empty_flags) | set(run(RICH))))

    print("\n" + "=" * 118)
    print("DOCUMENTED GAPS (behaviour contradicts the statute / the engine's own intent)")
    print("=" * 118)
    gap_confirmed = 0
    for gap in KNOWN_GAPS:
        actual = run(gap["input"]).get(gap["flag"], {}).get("user_value")
        status = "CONFIRMED" if actual == gap["engine"] else "not reproduced (%s)" % actual
        if actual == gap["engine"]:
            gap_confirmed += 1
        print("  [%s] %-18s engine=%-16s statute=%-18s %s" % (
            status, gap["flag"], actual, gap["statute"], gap["name"]))

    print("\n" + "=" * 118)
    if failures:
        print("RESULT: %d FAILED threshold expectation(s)" % len(failures))
        for name, flag_id, expected, actual in failures:
            print("  - %s | %s: expected %s, got %s" % (name, flag_id, expected, actual))
    else:
        print("RESULT: all %d threshold expectations met" %
              sum(len(s["expected"]) for s in SCENARIOS))
    print("documented gaps reproduced: %d/%d" % (gap_confirmed, len(KNOWN_GAPS)))
    print("=" * 118)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
