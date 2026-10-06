# AOC-4 Automation Engine — Test Results (2026-09-28)

Scope: the `automation_engine/` package, with focus on **the compliance engine** and
**the LLM judges**. Executed on Windows / Python 3.12.4 (`.venv`), while the repo
`automation_engine/` copy is read-only except for the new `test_runs/` folder.

## 1. Environment

| Item | Value |
|---|---|
| Shipped LLM endpoint | `http://192.168.112.2:11434` — **reachable**, model `qwen3.5:4b` installed |
| Models on that server | `qwen3.5:4b`, `qwen2.5:14b`, `qwen2.5-coder:7b`, `medgemma:27b`, `ministral-3:3b-instruct-2512-q4_K_M`, `qwen3.5:2b`, `mistral:latest` |
| Local Ollama | `http://localhost:11434` — `llama3.2:latest` (used for comparison) |
| Test data | `testing/Kripya solution/Input for Common error/ocr_output_2025_2026` (3 OCR `.md`, 184 KB text) |

## 2. Test matrix

| # | Test | Command | Result |
|---|---|---|---|
| 1 | Compliance LLM-judge unit suite | `python automation_engine/modules/aoc4/tests/test_compliance_llm_judge.py` | **48 tests OK** |
| 2 | Common-error LLM-judge unit suite | `python .../tests/test_llm_judge.py` | **68 tests OK** (1 skipped) |
| 3 | Figure LLM-judge unit suite | `python .../tests/test_figure_llm_judge.py` | **56 tests OK** |
| 4 | LLM connectivity smoke test | `python test_runs/llm_smoke_test.py` | both servers **200** |
| 5 | Common-error judge, live | `python .../tests/run_live_llm_judge_check.py` | **5/5 rules decided by LLM, 0 fallbacks** |
| 6 | Compliance engine, live (deterministic + LLM + dead server) | `python test_runs/compliance_engine_probe.py` | **25 flags; 22/22 LLM calls HTTP 200** |
| 7 | Compliance threshold matrix | `python test_runs/compliance_threshold_matrix.py` | **47/47 expectations met**, 4 gaps confirmed |
| 8 | Figure judge, live | `python .../tests/run_live_figure_check.py "<folder>"` | **22/22 rows cross-checked, 0 errors** |
| 9 | Common-error checker | `python test_runs/error_checker_probe.py` | **37 rules, 37 flags, 27 non-conforming** |
| 10 | Full pipeline through the real API | `uvicorn automation_engine.api.main:app` + `tests/upload_and_check_via_api.py` | **completed in 36.6 s, 97 flags** |

Aggregate: **172 unit tests green, 0 failures.**

## 3. Compliance engine — is it working?

**Yes.** Verified three ways.

* **Deterministic engine** — 25 flags emitted in **0.02 s**, covering Sheet rows 37-61
  (Small Company, CARO, Rotation, Ind AS, XBRL, Vigil, IFC, Internal Audit, Secretarial
  Audit, KMP, Sec 186, Loan-to-director, Cost Audit, Charge form, AOC-1, AOC-2, RPT
  omnibus, CSR, CSR Committee, Deposit declaration, DPT-3, MSME, BEN-2, MGT-8, MGT-7).
* **Threshold matrix** — 47 boundary assertions (at / just below / just above each
  statutory limit) **all pass**.
* **Live run on a real filing** — the same 25 rows are written into
  `Compliance sheet for private` of the produced workbook with verdict + rationale.

### LLM overlay (`AOC4ComplianceLLMJudgeEngine`)

| Metric | Value |
|---|---|
| Requirement rows in LLM scope | 22 / 25 (Small Company, CARO, Rotation are deterministic-only by design) |
| Live calls to `qwen3.5:4b` | **22** — all HTTP 200, 0 errors |
| Avg / max latency | ~1.5 s / 2.34 s |
| Rows actually adjudicated by the LLM | **20 / 22** (BEN-2 and LOAN_186 fell back) |
| Verdicts the LLM changed | **1** — `COMP_AOC_1` "Not Applicable" → "Applicable" (because the RPT table discloses a wholly-owned subsidiary → AOC-1 is due) |
| Deterministic vs hybrid wall clock | 0.02 s → 34.68 s |
| Dead server (`127.0.0.1:9`) | 25 flags in 2.09 s, **verdicts identical to baseline** (circuit breaker works) |

> **Important:** in production the compliance judge is switched **off** —
> `ENABLE_COMPLIANCE_LLM_JUDGE = False` in `rule_engine.py` (documented decision:
> it improved 0 rows and regressed 2 in the 2026-09-25 validation). The live
> *hybrid* compliance results above were produced by driving
> `PrivateComplianceEngine(enable_llm_judge=True)` directly.

## 4. LLM — is it working?

**Yes, on both servers**, and the engine handles the awkward `qwen3.5:4b` response
shape correctly.

* `qwen3.5:4b` returns an **empty `response`** and puts the whole answer in
  `thinking` (verified directly). `AOC4LLMJudgeEngine._extract_model_text()` falls
  back to `thinking`, so the judge still gets an answer — without that fallback every
  row would silently fall back to deterministic.
* Live common-error judge: **5/5** of the narrative rules adjudicated in 7.55 s
  (`RULE_6 Yes`, `RULE_10 Yes`, `RULE_11 No`, `RULE_15 No`, `RULE_17 No`), with
  doc-grounded reasons (e.g. promoter table lacks beginning/end-of-year columns).
* Live figure judge: **22/22** rows cross-checked (`match 4`, `mismatch 3`,
  `not stated 12`, `not extracted 3`), 32.66 s, **0 model errors**.
* Fallback behaviour is correct everywhere: `Cannot determine`, malformed JSON,
  HTTP 4xx/5xx, timeouts and connection errors all keep the deterministic verdict;
  the circuit breaker stops retrying after the first transport failure.

## 5. Findings (defects / limitations)

1. **Units are not applied to values taken from the markdown fallback.**
   The guard in `AOC4RuleEngine.evaluate_all()` (`rule_engine.py:97-100`) sets
   `scale = 1.0` whenever *any* already-extracted value is `>= 100000`, so a
   statement "in Thousands" is never multiplied. KSPL's turnover is stored as
   `504583` (₹5.05 lakh) instead of ₹50.46 crore — visible in the workbook as
   `Turnover (0.05 Cr) <= 100 Cr`. The LLM figure judge itself reads the document
   correctly ("5,04,583 for Revenue from Operations in '000"), which confirms the
   document unit and the stored value disagree. Any company whose turnover sits
   between ~₹10 Cr and ₹100 Cr in thousands would get wrong CARO / IFC / MGT-8 /
   MGT-7 / XBRL answers. *Severity: high (silent, plausible-looking output).*
2. **Missing financial data is coerced to 0, so "Missing Data" is unreachable.**
   `PrivateComplianceEngine.execute()` does `_parse_numeric(...) or 0.0` for
   turnover / PUC / borrowings / net worth / net profit, so those are never `None`.
   On a completely empty input the engine reports **`Small Company: Yes`** and
   "everything not applicable" instead of asking for manual review. Only BEN-2
   (which reads an uncoerced key) still reports `Missing Data`.
   *Severity: high (an extraction failure reads as "nothing to comply with").*
3. **Public companies are treated as "Small Company".** `COMP_SMALL_CO` never checks
   the company type, so a public limited company with turnover ≤ 100 Cr and PUC ≤ 10 Cr
   is marked small and then inherits the small-company CARO exemption
   (`COMP_CARO = "Not Applicable"` instead of `"Applicable"`). Section 2(85) only
   allows *private* companies / OPCs to be small. The engine's own CARO `else` branch
   ("Not a private company" → Applicable) is unreachable for this reason.
   *Severity: medium (engine is scoped to private companies, but the flag text shows
   the intent was to catch this).*
4. `automation_engine/modules/aoc4/tests/test_error_checker.py` is **broken as
   shipped**: it imports `aoc4_error_checker` without adding the module directory to
   `sys.path`, and looks for `tests/excel/ANNFIL COMMONERROR.xlsx` (the workbook is
   `modules/aoc4/excel/ANNFIL COMMONERROR .xlsx`, with a space and a different
   directory). Reproduced with `test_runs/error_checker_probe.py`, which runs the same
   assertion against the real workbook — 37 rules, 37 flags, 27 non-conforming.
5. **No pytest in this environment** — every suite is stdlib `unittest` and must be
   run **by file path** (`python <path>/test_*.py`); each file bootstraps `sys.path`
   itself, so setting `PYTHONPATH` is not required. `tests/test_error_checker.py`
   (item 4) is the only script that does not.

## 6. Artifacts (`test_runs/`)

| File | Contents |
|---|---|
| `TEST_RESULTS.md` | this report |
| `compliance_unit.txt`, `llm_judge_unit.txt`, `figure_unit.txt` | unit-suite console output |
| `llm_smoke_test.py` / `.txt` | raw endpoint probe (both servers) |
| `compliance_engine_probe.py` / `compliance_probe.txt` / `compliance_engine_probe.json` | deterministic vs hybrid vs dead-server compliance run |
| `compliance_threshold_matrix.py` / `compliance_matrix.txt` | 47-boundary statutory matrix + confirmed gaps |
| `live_llm_judge.txt`, `llm_judge_live_report.json` | live common-error judge |
| `live_figure.txt`, `figure_live_report.json` | live figure judge |
| `live_compliance.txt`, `compliance_live_KSPL.json` | shipped `run_live_compliance_check.py` run |
| `error_checker_probe.py` / `error_checker.txt` | common-error checker (legacy script workaround) |
| `e2e_api.txt`, `uvicorn.*.log` | full pipeline through the FastAPI backend |
| `output_compliance_sheet.txt` | dump of the compliance sheet in `output/KSPL/KSPL_AOC4_Populated.xlsx` |

### End-to-end result (real backend, `module_type=aoc4`)

```
status        : completed in 36.6s
flags         : 97 total  (Common Errors 44 | Compliance 25 | RPT & Loans 28)
needs review  : 32 total  (20 | 4 | 8)
PY comparison : 144 line items (138 matched, 6 mismatches)
workbook      : output/KSPL/KSPL_AOC4_Populated.xlsx
sheets        : Common Error, Compliance sheet for private,
                compliance sheet for public, RPT and loans to Director,
                Previous Year Comparison
```
