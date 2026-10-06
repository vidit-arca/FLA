"""Live test harness for the AOC-4 **compliance sheet** LLM judge.

Runs the REAL production pipeline (``AOC4RuleEngine.evaluate_all``) twice on an
OCR folder - once with the LLM judges disabled (deterministic baseline) and once
with the shipped defaults (deterministic + LLM hybrid) - then, when a
ground-truth compliance workbook is supplied, scores BOTH against it.

Flow::

    ocr/*.md -> full_text -> AOC4RuleEngine.evaluate_all()
                                  ├─ excel extractor / text fallback -> facts
                                  └─ PrivateComplianceEngine
                                        ├─ deterministic thresholds   (baseline)
                                        └─ AOC4ComplianceLLMJudgeEngine (hybrid)
    compare baseline vs hybrid vs the reviewer-filled compliance sheet

Usage::

    python automation_engine/modules/aoc4/tests/run_live_compliance_check.py \\
        "Y:/Main-OCR-main/Main-OCR-main/data/Insap" \\
        --ground-truth "Y:/Main-OCR-main/Main-OCR-main/data/Insap/2. Compliance sheet.xlsx"

Options
-------
    --ground-truth XLSX  reviewer-filled sheet -> adds accuracy scoring
    --include-previous   keep previous-year .md files in full_text
                         (default: excluded, matching AOC4Parser behaviour)
    --url/--model/--timeout  LLM endpoint overrides (shipped defaults if omitted)
    --report FILE        JSON report path (default: compliance_live_report.json)
    --dry-run            skip LLM calls entirely (baseline == hybrid)
"""

import argparse
import json
import os
import re
import sys
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
AOC4_DIR = os.path.dirname(TESTS_DIR)                                     # .../modules/aoc4
# aoc4 -> modules -> automation_engine -> repository root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(AOC4_DIR)))

for _path in (PROJECT_ROOT, AOC4_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import requests

from automation_engine.modules.aoc4.rule_engine import AOC4RuleEngine
from automation_engine.modules.aoc4.compliance.compliance_llm_judge import (
    AOC4ComplianceLLMJudgeEngine,
)

CONFIG_PATH = os.path.join(AOC4_DIR, "rules_config.json")

# Verdict vocabulary used for scoring.
APPLICABLE = "Applicable"
NOT_APPLICABLE = "Not Applicable"
AMBIGUOUS = "ambiguous"        # reviewer did not state A/NA -> not scored
UNKNOWN = "unknown"            # engine returned something unexpected

# File-name tokens marking a previous-year document (AOC4Parser uses the same
# idea: prev/prior/last_year/py_ in the doc key or basename).
PREV_TOKENS = ("prev", "prior", "last_year", "py_")


def load_full_text(folder, include_previous=False):
    """Join the OCR ``.md`` files into full_text, the way AOC4Parser does."""
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith(".md"))
    used = [n for n in names
            if include_previous or not any(t in n.lower() for t in PREV_TOKENS)]
    skipped = [n for n in names if n not in used]
    text = "\n\n".join(
        open(os.path.join(folder, n), encoding="utf-8", errors="replace").read()
        for n in used)
    return text, used, skipped


def normalize_expected(raw):
    """Map a reviewer's free-text answer to Applicable / Not Applicable / ambiguous."""
    if raw is None:
        return UNKNOWN
    t = re.sub(r"\s+", " ", str(raw)).strip().lower()
    if not t:
        return UNKNOWN
    if "not applicable" in t:
        return NOT_APPLICABLE
    if t in ("na", "n/a", "no") or t.startswith("na ") or t.startswith("n/a "):
        return NOT_APPLICABLE
    if "need not appoint" in t or "need not be" in t:
        return NOT_APPLICABLE
    # Ambiguous reviewer notes -> not scored
    if any(k in t for k in ("check for", "to be checked", "check sec",
                            "compliance to be")):
        return AMBIGUOUS
    # Applicable ... / "Yes, it is ..." / a filed-date answer -> Applicable
    if t.startswith("applicable") or "yes" in t:
        return APPLICABLE
    if t.startswith("date "):       # "Date 19/11/2024, SRN_..." => a filing exists
        return APPLICABLE
    return UNKNOWN


def normalize_ours(raw):
    """Map our engine's user_value onto the same vocabulary."""
    if raw is None:
        return UNKNOWN
    t = re.sub(r"\s+", " ", str(raw)).strip().lower()
    if t == "applicable":
        return APPLICABLE
    if t in ("not applicable", "na", "n/a"):
        return NOT_APPLICABLE
    if t in ("yes", "y", "true"):        # e.g. COMP_SMALL_CO answers Yes/No
        return APPLICABLE
    if t in ("no", "n", "false"):
        return NOT_APPLICABLE
    if t in ("missing data", ""):
        return UNKNOWN
    if "not applicable" in t:
        return NOT_APPLICABLE
    if "applicable" in t:
        return APPLICABLE
    return UNKNOWN


def read_ground_truth(path):
    """Return ([(requirement, applicability_text)], sheet, header_row, app_col).

    Auto-detects the header row containing a cell equal to ``Requirement`` and
    uses the next cell containing ``Applicability`` as the answer column, which
    covers both layouts seen so far
    (``CA 2013 - Compliance Sheet`` B15/C15 and ``Sheet1`` A2/B2).
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        for row in range(1, ws.max_row + 1):
            for col in range(1, ws.max_column + 1):
                if str(ws.cell(row=row, column=col).value or "").strip().lower() != "requirement":
                    continue
                app_col = None
                for c2 in range(col + 1, ws.max_column + 1):
                    if "applicability" in str(ws.cell(row=row, column=c2).value or "").lower():
                        app_col = c2
                        break
                if app_col is None:
                    continue
                rows = []
                for r in range(row + 1, ws.max_row + 1):
                    req = ws.cell(row=r, column=col).value
                    if req is None or not str(req).strip():
                        continue
                    rows.append((str(req).strip(), ws.cell(row=r, column=app_col).value))
                if rows:
                    return rows, sheet, row, app_col
    raise SystemExit("No 'Requirement'/'Applicability' header found in %s" % path)


class LLMCallMeter:
    """Records every LLM HTTP call (both judges share the `requests` module)."""

    def __init__(self):
        self.calls = []
        self._original = None

    def __enter__(self):
        self._original = requests.post
        original = self._original

        def metered(url, **kwargs):
            started = time.time()
            response = original(url, **kwargs)
            self.calls.append({
                "url": url,
                "model": (kwargs.get("json") or {}).get("model"),
                "seconds": round(time.time() - started, 2),
                "status": response.status_code,
            })
            return response

        requests.post = metered
        return self

    def __exit__(self, *exc):
        requests.post = self._original
        return False

    @property
    def total_seconds(self):
        return round(sum(c["seconds"] for c in self.calls), 2)

    def summary(self):
        if not self.calls:
            return {"calls": 0}
        return {
            "calls": len(self.calls),
            "seconds": self.total_seconds,
            "min": min(c["seconds"] for c in self.calls),
            "max": max(c["seconds"] for c in self.calls),
            "models": sorted({c["model"] for c in self.calls if c["model"]}),
            "http_errors": sum(1 for c in self.calls if c["status"] >= 400),
        }


def _name_judge():
    """An offline judge instance used only for requirement-name -> key mapping."""
    return AOC4ComplianceLLMJudgeEngine(ollama_url="")


# The 3 rows OUTSIDE the LLM scope (rows 37-39 / "Small Company", "CARO",
# "Rotation") are not in the judge's catalogue - map them so they still show up
# in the report (scored, but clearly marked as deterministic-only).
EXTRA_ALIASES = {
    "isitasmallcompany": "COMP_SMALL_CO",
    "caro": "COMP_CARO",
    "rotationofauditors": "COMP_ROTATION",
}


def requirement_key(req, judge):
    key = judge.name_for_requirement(req)
    if key:
        return key
    return EXTRA_ALIASES.get(judge._normalize(req))


def run_pipeline(full_text, dry_run=False):
    """Run the real evaluate_all() once. Returns (extracted_data, seconds)."""
    engine = AOC4RuleEngine(CONFIG_PATH)
    if dry_run:
        engine.checker.llm_judge = None
        engine.compliance_engine.llm_judge = None
    data = {"full_text": full_text, "docs": {}}
    started = time.time()
    engine.evaluate_all(data)
    return data, round(time.time() - started, 2)


def flags_by_id(data):
    return {f.get("id"): f for f in data.get("compliance_flags", [])}


def score(gt_rows, flags, judge):
    """Score one engine's flags against the reviewer's sheet."""
    results = []
    for req, raw in gt_rows:
        key = requirement_key(req, judge)
        flag = flags.get(key)
        expected = normalize_expected(raw)
        ours = normalize_ours(flag.get("user_value")) if flag else UNKNOWN
        scored = expected in (APPLICABLE, NOT_APPLICABLE)
        in_llm_scope = key in AOC4ComplianceLLMJudgeEngine._REQUIREMENTS
        results.append({
            "requirement": req,
            "key": key,
            "expected_text": None if raw is None else str(raw).strip(),
            "expected": expected,
            "actual": ours,
            "user_value": flag.get("user_value") if flag else None,
            "correct": (ours == expected) if scored else None,
            "in_llm_scope": in_llm_scope,
            "judge": flag.get("judged_by") if flag else None,
        })
    return results


def print_table(title, results):
    print("\n" + "=" * 130)
    print(title)
    print("=" * 130)
    print("  %-46s %-14s %-14s %-14s %s" %
          ("Requirement", "Expected", "Baseline", "Hybrid", ""))
    for i, r in enumerate(results, 1):
        correct = r.get("hybrid_correct", r.get("correct"))
        mark = "  " if correct is None else ("OK  " if correct else "FAIL")
        scope = "" if r.get("in_llm_scope", True) else " [no-LLM scope]"
        print("  %-46s %-14s %-14s %-14s %s%s" % (
            r["requirement"][:46], r["expected"],
            r.get("baseline", r.get("actual")), r.get("hybrid", r.get("actual")),
            mark, scope))


def accuracy(results, field="actual"):
    """Accuracy over scored rows; ``field`` picks the run to score
    (``actual`` on single-run results, ``baseline``/``hybrid`` on merged ones)."""
    scored = [r for r in results if r["expected"] in (APPLICABLE, NOT_APPLICABLE)]
    if not scored:
        return {"scored": 0, "correct": 0, "accuracy": None}
    correct = sum(1 for r in scored if r.get(field) == r["expected"])
    return {"scored": len(scored), "correct": correct,
            "accuracy": round(100.0 * correct / len(scored), 1)}


def main():
    parser = argparse.ArgumentParser(description="AOC-4 compliance LLM judge live test")
    parser.add_argument("folder",
                        help="company folder (with ocr_output/) or the ocr_output folder itself")
    parser.add_argument("--ground-truth", default=None,
                        help="reviewer-filled compliance .xlsx for scoring")
    parser.add_argument("--include-previous", action="store_true",
                        help="keep previous-year .md files in full_text")
    parser.add_argument("--url", default=None, help="override AOC4_LLM_URL")
    parser.add_argument("--model", default=None, help="override AOC4_LLM_MODEL")
    parser.add_argument("--timeout", type=int, default=None, help="override AOC4_LLM_TIMEOUT")
    parser.add_argument("--report", default=None, help="JSON report path")
    parser.add_argument("--dry-run", action="store_true", help="LLM calls disabled")
    args = parser.parse_args()

    folder = args.folder
    if not any(f.lower().endswith(".md") for f in os.listdir(folder)):
        inner = os.path.join(folder, "ocr_output")
        if os.path.isdir(inner):
            folder = inner

    # Endpoint overrides are read by both judges at construction time.
    if args.url:
        os.environ["AOC4_LLM_URL"] = args.url
    if args.model:
        os.environ["AOC4_LLM_MODEL"] = args.model
    if args.timeout:
        os.environ["AOC4_LLM_TIMEOUT"] = str(args.timeout)

    full_text, used, skipped = load_full_text(folder, args.include_previous)
    judge = _name_judge()

    print("#" * 130)
    print("# AOC-4 COMPLIANCE LLM JUDGE - LIVE TEST")
    print("# folder          : %s" % folder)
    print("# files used      : %s" % ", ".join(used))
    print("# files skipped   : %s" % (", ".join(skipped) or "-"))
    print("# full_text chars : %d" % len(full_text))
    print("# model / timeout : %s / %ss" % (os.environ.get("AOC4_LLM_MODEL", "(default)"),
                                            os.environ.get("AOC4_LLM_TIMEOUT", "(default)")))
    print("# dry_run         : %s" % args.dry_run)
    print("#" * 130)

    # ---- 1) deterministic baseline (LLM judges off) ----
    base_data, base_s = run_pipeline(full_text, dry_run=True)
    print("\n[baseline] evaluate_all: %.2fs (LLM off)" % base_s)

    # ---- 2) hybrid run (shipped defaults) ----
    if args.dry_run:
        hyb_data, hyb_s, llm_stats = base_data, 0.0, {"calls": 0}
    else:
        with LLMCallMeter() as meter:
            hyb_data, hyb_s = run_pipeline(full_text, dry_run=False)
        llm_stats = meter.summary()
    print("[hybrid]   evaluate_all: %.2fs  LLM: %s" % (hyb_s, llm_stats))

    base_flags, hyb_flags = flags_by_id(base_data), flags_by_id(hyb_data)
    company = os.path.basename(os.path.dirname(folder)) or os.path.basename(folder)
    report = {
        "company": company,
        "folder": folder,
        "files_used": used,
        "files_skipped": skipped,
        "full_text_chars": len(full_text),
        "dry_run": args.dry_run,
        "model": os.environ.get("AOC4_LLM_MODEL", "qwen3.5:4b (shipped default)"),
        "baseline_seconds": base_s,
        "hybrid_seconds": hyb_s,
        "llm": llm_stats,
        "facts": {k: base_data.get(k) for k in
                  ("company_type", "is_listed", "is_ind_as", "is_subsidiary_or_holding",
                   "mca_small_company", "paid_up_capital", "net_worth", "turnover",
                   "total_revenue", "net_profit_before_tax", "borrowings",
                   "long_term_borrowings", "short_term_borrowings", "loan_from_directors",
                   "dues_to_msme", "investments_made", "loan_given_by_company",
                   "loan_to_directors_assets", "corporate_guarantees")},
    }

    if args.ground_truth:
        gt_rows, sheet, hrow, acol = read_ground_truth(args.ground_truth)
        print("\n[ground truth] %s  sheet=%r header row=%d answer col=%d  rows=%d"
              % (args.ground_truth, sheet, hrow, acol, len(gt_rows)))
        base_res = {r["key"]: r for r in score(gt_rows, base_flags, judge)}
        hyb_res = {r["key"]: r for r in score(gt_rows, hyb_flags, judge)}

        merged = []
        for req, raw in gt_rows:
            key = requirement_key(req, judge)
            b, h = base_res[key], hyb_res[key]
            merged.append({
                "requirement": req, "key": key,
                "expected_text": b["expected_text"], "expected": b["expected"],
                "baseline": b["actual"], "hybrid": h["actual"],
                "in_llm_scope": b["in_llm_scope"],
                "baseline_correct": b["correct"], "hybrid_correct": h["correct"],
                "hybrid_judge": h["judge"],
                "hybrid_rationale": ((hyb_flags.get(key) or {}).get("rationale") or "")[:400],
                "baseline_rationale": ((base_flags.get(key) or {}).get("rationale") or "")[:300],
            })

        print_table("SCORED: %s" % os.path.basename(args.ground_truth), merged)
        acc_b, acc_h = accuracy(merged, "baseline"), accuracy(merged, "hybrid")
        amb = sum(1 for r in merged if r["expected"] == AMBIGUOUS)
        unmapped = [r["requirement"] for r in merged if r["key"] is None]
        improvements = [r["requirement"] for r in merged
                        if r["baseline_correct"] is False and r["hybrid_correct"] is True]
        regressions = [r["requirement"] for r in merged
                       if r["baseline_correct"] is True and r["hybrid_correct"] is False]

        print("\n" + "-" * 130)
        print("SUMMARY")
        print("-" * 130)
        print("  rows in sheet            : %d  (ambiguous/not-scored: %d)" % (len(merged), amb))
        print("  baseline (LLM off)       : %d/%d = %.1f%%" %
              (acc_b["correct"], acc_b["scored"], acc_b["accuracy"] or 0))
        print("  hybrid (LLM on)          : %d/%d = %.1f%%" %
              (acc_h["correct"], acc_h["scored"], acc_h["accuracy"] or 0))
        print("  improved by LLM          : %d %s" % (len(improvements), improvements))
        print("  regressed by LLM         : %d %s" % (len(regressions), regressions))
        print("  unmapped GT rows         : %s" % (unmapped or "none"))
        report.update({
            "ground_truth": args.ground_truth,
            "rows": merged,
            "baseline_accuracy": acc_b,
            "hybrid_accuracy": acc_h,
            "ambiguous_rows": amb,
            "improvements": improvements,
            "regressions": regressions,
            "unmapped_rows": unmapped,
        })
    else:
        # No ground truth: dump every flag from both runs for manual review.
        rows = []
        print("\n" + "=" * 130)
        print("ALL COMPLIANCE FLAGS (baseline vs hybrid) - no ground truth supplied")
        print("=" * 130)
        for key in sorted(set(base_flags) | set(hyb_flags)):
            b, h = base_flags.get(key), hyb_flags.get(key)
            bv = b.get("user_value") if b else None
            hv = h.get("user_value") if h else None
            part = (h or b or {}).get("particulars")
            print("  %-22s %-44s %-14s -> %-14s %-9s %s" %
                  (key, str(part)[:44], bv, hv,
                   "CHANGED" if bv != hv else "", (h or {}).get("judged_by") or ""))
            rows.append({"id": key, "particulars": part, "baseline": bv,
                         "hybrid": hv, "hybrid_judge": (h or {}).get("judged_by"),
                         "hybrid_rationale": (h or {}).get("rationale")})
        report["rows"] = rows

    if args.report:
        report_path = args.report
    else:
        art_dir = os.path.join(TESTS_DIR, "live_check_artifacts")
        os.makedirs(art_dir, exist_ok=True)
        report_path = os.path.join(art_dir, "compliance_live_report_%s.json" % company)
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
    print("\n[report] %s" % report_path)


if __name__ == "__main__":
    main()
