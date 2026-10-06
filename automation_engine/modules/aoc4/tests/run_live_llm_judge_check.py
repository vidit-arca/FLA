"""Live end-to-end check of the AOC-4 LLM judge on a REAL OCR output folder.

It reproduces the production pipeline for the 5 narrative "LLM judged" common
error rules:

    OCR markdown files  ->  full_text ("\\n\\n".join, as AOC4Parser does)
                        ->  AOC4CommonErrorEngine.execute()   (deterministic)
                        ->  AOC4LLMJudgeEngine.judge()        (Ollama model)
                        ->  hybrid verdict (LLM overrides deterministic)

Usage
-----
    python automation_engine/modules/aoc4/tests/run_live_llm_judge_check.py \
        ["testing/Kripya solution/Input for Common error/ocr_output_2025_2026"]

Options
-------
    --url URL      Ollama base URL (default: AOC4_OLLAMA_URL or the engine's
                   DEFAULT_URL = http://192.168.112.2:11434)
    --model NAME   Model name (default: AOC4_LLM_MODEL or the engine's
                   DEFAULT_MODEL = qwen3.5:4b; use llama3.2 for a local Ollama)
    --timeout SEC  Per-request timeout (default: 300 - CPU inference is slow)
    --only TEXT    Only judge rules whose particulars contain TEXT
    --dump-prompts DIR   Also write the exact prompt sent per rule (audit trail)
    --report FILE  Where to write the JSON report (default: llm_judge_live_report.json)

Exit code is 0 when the run completed; the report always records which rules
were decided by the LLM and which fell back to the deterministic engine.
"""

import argparse
import json
import os
import sys
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
AOC4_DIR = os.path.dirname(TESTS_DIR)                                     # .../modules/aoc4
# aoc4 -> modules -> automation_engine -> repository root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(AOC4_DIR)))

for _path in (PROJECT_ROOT, AOC4_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from automation_engine.modules.aoc4.common_error.aoc4_error_checker import AOC4CommonErrorEngine
from automation_engine.modules.aoc4.llm.llm_judge import AOC4LLMJudgeEngine

DEFAULT_FOLDER = os.path.join(
    PROJECT_ROOT, "testing", "Kripya solution", "Input for Common error",
    "ocr_output_2025_2026")

RULES_EXCEL_CANDIDATES = [
    os.path.join(AOC4_DIR, "excel", "Annual Filing common error Output.xlsx"),
    os.path.join(AOC4_DIR, "excel", "ANNFIL COMMONERROR .xlsx"),
]


def load_full_text(folder):
    """Join every OCR .md file the way AOC4Parser does (\\n\\n separated)."""
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith(".md"))
    if not names:
        raise SystemExit("No .md OCR files found in %s" % folder)

    parts = []
    for name in names:
        with open(os.path.join(folder, name), "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        print("  + %-58s %9s chars" % (name, format(len(text), ",")))
        parts.append(text)
    return "\n\n".join(parts), names


class TimedJudge:
    """Drop-in stand-in for AOC4LLMJudgeEngine that records timing/verdicts.

    The checker only ever calls ``is_judged_rule()`` and ``judge()``, so wrapping
    keeps the hybrid behaviour byte-for-byte identical while giving us
    per-rule latency and audit detail.
    """

    def __init__(self, inner, prompt_dump_dir=None, only=None, dry_run=False):
        self.inner = inner
        self.prompt_dump_dir = prompt_dump_dir
        self.only = only
        self.dry_run = dry_run
        self.calls = []

    def is_judged_rule(self, particulars):
        if self.only and self.only.lower() not in str(particulars).lower():
            return False  # let the deterministic engine answer for this row
        return self.inner.is_judged_rule(particulars)

    def judge(self, rule, input_data):
        particulars = rule.get("particulars", "")
        full_text = input_data.get("full_text") or ""
        # Rebuild the exact window/prompt the real judge will use (rule-aware).
        rule_name = self.inner.name_for_rule(particulars)
        try:
            window = self.inner._relevant_window(full_text, rule_name=rule_name)
            prompt = self.inner._build_prompt(
                strat=particulars,
                intent=self.inner._INTENTS.get(rule_name, ""),
                window=window)
        except Exception:  # pragma: no cover - defensive
            window, prompt = "", ""

        if self.prompt_dump_dir:
            os.makedirs(self.prompt_dump_dir, exist_ok=True)
            safe = "".join(c if c.isalnum() else "_" for c in particulars)[:60]
            with open(os.path.join(self.prompt_dump_dir, "%s.prompt.txt" % safe),
                      "w", encoding="utf-8") as fh:
                fh.write(prompt)

        started = time.time()
        if self.dry_run:
            result, error = None, None
        else:
            try:
                result = self.inner.judge(rule, input_data)
                error = None
            except Exception as exc:
                result, error = None, "%s: %s" % (type(exc).__name__, exc)
        elapsed = time.time() - started

        self.calls.append({
            "particulars": particulars,
            "rule_id": rule.get("id"),
            "llm_value": (result or {}).get("user_value"),
            "llm_reason": (result or {}).get("reason"),
            "seconds": round(elapsed, 2),
            "window_chars": len(window),
            "document_chars": len(full_text),
            "error": error,
        })
        return result


def health_check(url, timeout=5):
    """Is the Ollama server reachable, and which models does it report?"""
    import requests
    try:
        resp = requests.get("%s/api/tags" % url, timeout=timeout)
        resp.raise_for_status()
        models = [m.get("name") for m in resp.json().get("models", [])]
        return True, models
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)


def resolve_excel():
    for path in RULES_EXCEL_CANDIDATES:
        if os.path.exists(path):
            return path
    raise SystemExit("Rules workbook not found in %s" % os.path.dirname(
        RULES_EXCEL_CANDIDATES[0]))


def run_deterministic(excel_path, full_text):
    checker = AOC4CommonErrorEngine(excel_path, enable_llm_judge=False)
    started = time.time()
    flags = checker.execute({"full_text": full_text})
    return {f["particulars"]: f for f in flags}, time.time() - started


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", nargs="?", default=DEFAULT_FOLDER)
    parser.add_argument("--url", default=os.environ.get("AOC4_OLLAMA_URL",
                                                       AOC4LLMJudgeEngine.DEFAULT_URL))
    parser.add_argument("--model", default=os.environ.get("AOC4_LLM_MODEL",
                                                         AOC4LLMJudgeEngine.DEFAULT_MODEL))
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--only", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="build/dump the exact prompts without calling the model")
    parser.add_argument("--dump-prompts", default=None)
    parser.add_argument("--report", default="llm_judge_live_report.json")
    args = parser.parse_args(argv)

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        raise SystemExit("Input folder not found: %s" % folder)

    print("=" * 100)
    print("AOC-4 LLM judge live check")
    print("  input folder : %s" % folder)
    print("   ollama url   : %s" % args.url)
    print("   model        : %s" % args.model)
    print("=" * 100)

    print("\n[1/3] Rebuilding full_text from OCR markdown (AOC4Parser style):")
    full_text, sources = load_full_text(folder)
    print("  => full_text = %s chars from %d document(s)" % (format(len(full_text), ","),
                                                              len(sources)))

    excel_path = resolve_excel()
    print("\n[2/3] Deterministic (LLM disabled) baseline from %s" % os.path.basename(excel_path))
    deterministic, det_seconds = run_deterministic(excel_path, full_text)
    print("  => %d rules evaluated in %.2fs" % (len(deterministic), det_seconds))

    reachable, detail = health_check(args.url)
    if reachable:
        print("\n[3/3] Ollama REACHABLE - installed models: %s" % (detail,))
    else:
        print("\n[3/3] Ollama UNREACHABLE (%s)" % detail)
        print("      The run will exercise the deterministic fallback path.")

    judge = AOC4LLMJudgeEngine(ollama_url=args.url, model=args.model, timeout=args.timeout)
    counter = TimedJudge(judge, prompt_dump_dir=args.dump_prompts, only=args.only,
                         dry_run=args.dry_run)
    checker = AOC4CommonErrorEngine(excel_path, llm_judge=counter)

    rules = [r for r in checker.rules if judge.is_judged_rule(r["particulars"])]
    if args.only:
        rules = [r for r in rules if args.only.lower() in r["particulars"].lower()]

    print("\nJudged rules to evaluate: %d" % len(rules))
    started = time.time()
    flags = checker.execute({"full_text": full_text})
    total_seconds = time.time() - started
    by_particulars = {f["particulars"]: f for f in flags}

    print("\n" + "-" * 100)
    print("%-8s %-14s %-14s %8s %9s  %s" % ("RULE", "DETERMINISTIC", "LLM VERDICT", "SECONDS",
                                            "WINDOW", "PARTICULARS"))
    print("-" * 100)
    for call in counter.calls:
        det = deterministic.get(call["particulars"], {}).get("user_value", "-")
        print("%-8s %-14s %-14s %8.2f %9s  %s" % (
            call["rule_id"], det, call["llm_value"] if call["llm_value"] else "fallback",
            call["seconds"], format(call["window_chars"], ","),
            call["particulars"][:44].replace("\n", " ")))
    print("-" * 100)
    print("execute() total: %.2fs (deterministic baseline %.2fs + %d LLM call(s))"
          % (total_seconds, det_seconds, len(counter.calls)))

    print("\nVerdict reasons:")
    for call in counter.calls:
        print("\n  %s  [%s]" % (call["rule_id"], call["particulars"][:78].replace("\n", " ")))
        print("    deterministic : %s" % deterministic.get(call["particulars"], {}).get(
            "user_value", "-"))
        print("    llm           : %s%s" % (
            call["llm_value"] if call["llm_value"] else "None (fell back)",
            "" if not call["error"] else "  ERROR=%s" % call["error"]))
        print("    final hybrid  : %s" % by_particulars.get(call["particulars"], {}).get(
            "user_value", "-"))
        print("    reason        : %s" % (call["llm_reason"] or "-")[:400])

    report = {
        "input_folder": folder,
        "documents": sources,
        "full_text_chars": len(full_text),
        "rules_workbook": excel_path,
        "ollama_url": args.url,
        "model": args.model,
        "ollama_reachable": reachable,
        "ollama_detail": str(detail),
        "deterministic_seconds": round(det_seconds, 2),
        "execute_seconds": round(total_seconds, 2),
        "judged_rules": len(rules),
        "llm_decided": sum(1 for c in counter.calls if c["llm_value"]),
        "llm_fallback": sum(1 for c in counter.calls if not c["llm_value"]),
        "calls": counter.calls,
    }
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("\nReport written to %s" % os.path.abspath(args.report))
    return 0


if __name__ == "__main__":
    sys.exit(main())


