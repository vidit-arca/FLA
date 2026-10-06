"""
Comprehensive test of the generic extraction engine.
Compares extracted values vs user-provided ground truth tables for:
  1. Uncia (Excel source)
  2. Cameo (Markdown/PDF source)
"""
from automation_engine.modules.aoc4.excel_extractor import AOC4ExcelExtractor
from automation_engine.modules.aoc4.parser import AOC4Parser
from automation_engine.modules.aoc4.rule_engine import AOC4RuleEngine

CONFIG = "/Users/apple/Desktop/FLA/automation_engine/modules/aoc4/rules_config.json"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

# ─────────────────────────────────────────────────────────────────────────────
# UNCIA GROUND TRUTH  (amounts in Rupees / absolute)
# ─────────────────────────────────────────────────────────────────────────────
UNCIA_GROUND_TRUTH = {
    "paid_up_capital":         110398000,
    "reserves_and_surplus":    161044000,
    "borrowings":              123927000,   # total borrowings
    "net_worth":               271442000,
    "turnover":                359847000,
    "net_profit_before_tax":    12489000,
    "loan_from_directors":      28400000,
    "secured_loan":             22879000,
    "dues_to_msme":              4728000,
}

TOL = 0.01   # 1 % tolerance

def pct_diff(got, expected):
    if expected == 0:
        return 0.0 if got == 0 else float("inf")
    return abs(got - expected) / abs(expected) * 100

def check(label, got, expected, unit="Rs."):
    if got is None:
        status = f"{RED}✗ MISSING{RESET}"
        return status, False
    diff = pct_diff(float(got), float(expected))
    if diff <= TOL:
        status = f"{GREEN}✓ MATCH{RESET}  (Δ {diff:.4f}%)"
        return status, True
    else:
        status = f"{RED}✗ MISMATCH{RESET} (Δ {diff:.2f}%)"
        return status, False

print(f"\n{BOLD}{'='*70}{RESET}")
print(f"{BOLD}  TEST 1: UNCIA (Excel Workbook){RESET}")
print(f"{BOLD}{'='*70}{RESET}")

extractor = AOC4ExcelExtractor()
engine    = AOC4RuleEngine(CONFIG)

uncia_docs = {
    "fs_excel": "/Users/apple/Desktop/FLA/data/32065714-dd63-49f7-8c2d-7a5fb550a6cc/Uncia_Standalone FS_Mar 2026 Final v7.xlsx",
    "sh_excel": "/Users/apple/Desktop/FLA/data/32065714-dd63-49f7-8c2d-7a5fb550a6cc/List of shareholders- Uncia.xlsx"
}
fresh = extractor.extract_from_docs(uncia_docs)
fresh["full_text"] = "in thousand rupees"

# Run through rule engine so multiplier (1000x) is applied
cells = engine.evaluate_all(fresh)

# After evaluate_all, fresh is updated with scaled values
passed_u = 0
print(f"\n{'Particular':<45} {'Expected':>15} {'Extracted (Scaled)':>22} Status")
print("-"*95)
for key, expected in UNCIA_GROUND_TRUTH.items():
    got = fresh.get(key)
    status, ok = check(key, got, expected)
    print(f"{key:<45} {str(int(expected)):>15} {str(round(float(got), 0) if got is not None else 'None'):>22} {status}")
    if ok: passed_u += 1

print(f"\n{BOLD}Uncia Score: {passed_u}/{len(UNCIA_GROUND_TRUTH)} passed{RESET}")

# ─────────────────────────────────────────────────────────────────────────────
# CAMEO GROUND TRUTH (from MD file - values as they appear in the document)
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{BOLD}{'='*70}{RESET}")
print(f"{BOLD}  TEST 2: CAMEO (Markdown / PDF){RESET}")
print(f"{BOLD}{'='*70}{RESET}")

cameo_md_path = "/Users/apple/Desktop/FLA/data/aoc /CG/ocr_output/Cameo Financials FY 24-25.md"
try:
    cameo_text = open(cameo_md_path, encoding="utf-8").read()
    parser = AOC4Parser(CONFIG)
    all_keys = list(extractor.numeric_keywords.keys())
    cameo_extracted = parser.extract_financials_from_text(cameo_text, all_keys)

    print(f"\n{'Particular':<45} {'Extracted Value':>25} {'Source'}")
    print("-"*90)
    for key in all_keys:
        val = cameo_extracted.get(key)
        color = GREEN if val is not None else YELLOW
        print(f"{color}{key:<45} {str(val):>25}{RESET}")
    
    not_none = [k for k in all_keys if cameo_extracted.get(k) is not None]
    print(f"\n{BOLD}Cameo: Extracted {len(not_none)}/{len(all_keys)} metrics from Markdown{RESET}")
except FileNotFoundError:
    print(f"{RED}Cameo MD file not found at: {cameo_md_path}{RESET}")

print(f"\n{BOLD}{'='*70}{RESET}")
print("Done!")
