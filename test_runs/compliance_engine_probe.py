"""Live probe for the AOC-4 **compliance engine** + its LLM judge.

The shipped production wiring has ``ENABLE_COMPLIANCE_LLM_JUDGE = False``
(rule_engine.py), so the official live harness never calls the compliance judge.
This probe drives ``PrivateComplianceEngine`` directly, three ways, on a real OCR
folder:

  1. deterministic  - ``enable_llm_judge=False``   (baseline)
  2. hybrid         - ``enable_llm_judge=True``    (real Ollama server)
  3. dead server    - judge pointed at a closed port (fallback + circuit breaker)

Run:
    python test_runs/compliance_engine_probe.py "testing/Kripya solution/Input for Common error/ocr_output_2025_2026"
"""

import json
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import requests

from automation_engine.modules.aoc4.compliance_engine import PrivateComplianceEngine
from automation_engine.modules.aoc4.compliance_llm_judge import (
    JUDGED_REQUIREMENT_KEYS,
    AOC4ComplianceLLMJudgeEngine,
)
from automation_engine.modules.aoc4.rule_engine import AOC4RuleEngine

CONFIG_PATH = os.path.join(PROJECT_ROOT, "automation_engine", "modules", "aoc4",
                           "rules_config.json")
PREV_TOKENS = ("prev", "prior", "last_year", "py_")


class CallMeter:
    """Records every HTTP POST the judges make, without changing behaviour."""

    def __init__(self):
        self.calls = []

    def __enter__(self):
        self._original = requests.post
        original = self._original

        def metered(url, **kwargs):
            started = time.time()
            try:
                response = original(url, **kwargs)
                status = response.status_code
            except Exception:
                self.calls.append({"url": url, "seconds": round(time.time() - started, 2),
                                   "status": "ERROR"})
                raise
            self.calls.append({"url": url, "seconds": round(time.time() - started, 2),
                               "status": status})
            return response

        requests.post = metered
        return self

    def __exit__(self, *exc):
        requests.post = self._original
        return False

    def summary(self):
        ok = [c for c in self.calls if c["status"] == 200]
        return {"calls": len(self.calls), "http_ok": len(ok),
                "seconds": round(sum(c["seconds"] for c in self.calls), 2),
                "max": max([c["seconds"] for c in self.calls], default=0)}


def load_full_text(folder):
    if not any(f.lower().endswith(".md") for f in os.listdir(folder)):
        inner = os.path.join(folder, "ocr_output")
        if os.path.isdir(inner):
            folder = inner
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith(".md"))
    used = [n for n in names if not any(t in n.lower() for t in PREV_TOKENS)]
    text = "\n\n".join(open(os.path.join(folder, n), encoding="utf-8",
                            errors="replace").read() for n in used)
    return text, used, folder


def pipeline_facts(full_text):
    """Facts exactly as the production pipeline computes them (judges off)."""
    engine = AOC4RuleEngine(CONFIG_PATH)
    engine.checker.llm_judge = None
    engine.compliance_engine.llm_judge = None
    data = {"full_text": full_text, "docs": {}}
    engine.evaluate_all(data)
    return data


def flags_by_id(flags):
    return {f["id"]: f for f in flags}


def run_engine(data, enable_llm, url=None, model=None):
    engine = PrivateComplianceEngine(enable_llm_judge=enable_llm)
    if url is not None and engine.llm_judge is not None:
        engine.llm_judge.ollama_url = url
        engine.llm_judge.timeout = 5
    if model is not None and engine.llm_judge is not None:
        engine.llm_judge.model = model
    started = time.time()
    flags = engine.execute(data)
    return flags, round(time.time() - started, 2), engine


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        PROJECT_ROOT, "testing", "Kripya solution", "Input for Common error",
        "ocr_output_2025_2026")
    full_text, used, folder = load_full_text(folder)

    print("=" * 110)
    print("AOC-4 COMPLIANCE ENGINE + LLM JUDGE - LIVE PROBE")
    print("  folder         : %s" % folder)
    print("  documents      : %s" % ", ".join(used))
    print("  full_text      : %d chars" % len(full_text))
    print("  judged scope   : %d requirement rows" % len(JUDGED_REQUIREMENT_KEYS))
    print("=" * 110)

    print("\n[1/4] Running the production pipeline for the facts (judges disabled)...")
    data = pipeline_facts(full_text)
    print("  facts: %s" % {k: data.get(k) for k in
                           ("turnover", "paid_up_capital", "net_worth",
                            "reserves_and_surplus", "borrowings", "net_profit_before_tax",
                            "company_type", "is_listed", "is_ind_as",
                            "is_subsidiary_or_holding", "mca_small_company")})

    print("\n[2/4] Deterministic compliance engine (enable_llm_judge=False)...")
    base, base_s, base_engine = run_engine(data, enable_llm=False)
    print("  %d flags in %.2fs | llm_judge=%r" % (len(base), base_s, base_engine.llm_judge))
    in_scope = [f for f in base if AOC4ComplianceLLMJudgeEngine().is_judged_requirement(f)]
    print("  flags inside the LLM scope: %d/%d" % (len(in_scope), len(base)))

    print("\n[3/4] Hybrid compliance engine (enable_llm_judge=True, live server)...")
    with CallMeter() as meter:
        hyb, hyb_s, hyb_engine = run_engine(data, enable_llm=True)
    print("  %d flags in %.2fs | judge=%s @ %s / %s" % (
        len(hyb), hyb_s, type(hyb_engine.llm_judge).__name__,
        hyb_engine.llm_judge.ollama_url, hyb_engine.llm_judge.model))
    print("  LLM HTTP: %s" % meter.summary())

    print("\n[4/4] Robustness: judge pointed at a dead port (deterministic fallback)...")
    dead, dead_s, _ = run_engine(data, enable_llm=True, url="http://127.0.0.1:9")
    dead_by_id = flags_by_id(dead)
    base_by_id = flags_by_id(base)
    same = all(dead_by_id[k]["user_value"] == base_by_id[k]["user_value"] for k in base_by_id)
    print("  %d flags in %.2fs | identical verdicts to baseline: %s" % (len(dead), dead_s, same))

    print("\n" + "-" * 110)
    print("%-20s %-14s %-14s %-14s %-9s %s" %
          ("ID", "DETERMINISTIC", "HYBRID", "DEAD-SERVER", "JUDGED_BY", "PARTICULARS"))
    print("-" * 110)
    hyb_by_id = flags_by_id(hyb)
    changed = 0
    for key in sorted(base_by_id):
        b, h, d = base_by_id[key], hyb_by_id.get(key, {}), dead_by_id.get(key, {})
        mark = "  ** CHANGED **" if b["user_value"] != h.get("user_value") else ""
        if mark:
            changed += 1
        print("%-20s %-14s %-14s %-14s %-9s %s%s" % (
            key, b["user_value"], h.get("user_value"), d.get("user_value"),
            h.get("judged_by") or "-", str(b["particulars"])[:46], mark))

    llm_judged = sum(1 for f in hyb if f.get("judged_by") == "llm")
    print("-" * 110)
    print("flags              : %d (deterministic) / %d (hybrid)" % (len(base), len(hyb)))
    print("LLM-decided flags  : %d  |  verdicts changed by the LLM: %d" % (llm_judged, changed))
    print("hybrid wall clock  : %.2fs  (deterministic %.2fs)" % (hyb_s, base_s))

    report = {"folder": folder, "documents": used, "full_text_chars": len(full_text),
              "deterministic_seconds": base_s, "hybrid_seconds": hyb_s,
              "dead_server_seconds": dead_s, "llm_http": meter.summary(),
              "flags_total": len(base), "llm_decided": llm_judged,
              "changed": changed, "dead_server_matches_baseline": same,
              "flags": [{"id": k, "particulars": base_by_id[k]["particulars"],
                         "deterministic": base_by_id[k]["user_value"],
                         "hybrid": hyb_by_id.get(k, {}).get("user_value"),
                         "judged_by": hyb_by_id.get(k, {}).get("judged_by"),
                         "hybrid_rationale": (hyb_by_id.get(k, {}).get("rationale") or "")[:400],
                         "deterministic_rationale": base_by_id[k].get("rationale")}
                        for k in sorted(base_by_id)]}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "compliance_engine_probe.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
    print("\n[report] %s" % out)


if __name__ == "__main__":
    main()
