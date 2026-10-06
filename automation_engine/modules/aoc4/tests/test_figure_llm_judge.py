"""Standalone test-suite for the AOC-4 **figure-verification** judge.

Covers ``automation_engine/modules/aoc4/figure_llm_judge.py`` and its wiring into
``AOC4RuleEngine``. Mirrors ``tests/test_compliance_llm_judge.py``: pytest is not part
of this project, so this is stdlib ``unittest`` with ``requests.post`` mocked (no live
Ollama needed).

The central invariant under test is that the **model never decides the verdict** - it
returns a figure and a quote, and ``_verdict`` decides in Python. A hallucinated figure
must therefore surface as a mismatch instead of overwriting the extracted value.

Run it::

    python automation_engine/modules/aoc4/tests/test_figure_llm_judge.py
"""

import json
import os
import sys
import unittest
from unittest import mock

import requests

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
AOC4_DIR = os.path.dirname(TESTS_DIR)                                     # .../modules/aoc4
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(AOC4_DIR)))

for _path in (PROJECT_ROOT, AOC4_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from automation_engine.modules.aoc4.llm import figure_llm_judge as fig_mod
from automation_engine.modules.aoc4.llm.figure_llm_judge import AOC4FigureLLMJudgeEngine
from automation_engine.modules.aoc4.rule_engine import (
    AOC4RuleEngine,
    ENABLE_COMPLIANCE_LLM_JUDGE,
)

RULES_EXCEL = os.path.join(AOC4_DIR, "excel", "Annual Filing common error Output.xlsx")
LEGACY_EXCEL = os.path.join(AOC4_DIR, "excel", "ANNFIL COMMONERROR .xlsx")
CONFIG = os.path.join(AOC4_DIR, "rules_config.json")
PRIVATE_SHEET = "Compliance sheet for private"
LEGACY_SHEET = "compliance for Private "

#: The financial-particulars block the judge is scoped to, as it appears on the
#: shipped template: the header sits at row 4 and the block runs to row 27.
EXPECTED_ROWS = list(range(5, 28))
LEGACY_EXPECTED_ROWS = list(range(8, 31))

DOC_TEXT = (
    "Balance Sheet as at 31 March 2025. Paid-up share capital of Rs 50,00,000. "
    "Reserves and Surplus Rs 42,50,000. Total Borrowings Rs 1,20,00,000. "
    "Trade Payables Rs 4,10,000. Net worth Rs 92,50,000."
)


class _FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Server Error for url")

    def json(self):
        if self._payload is None:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


def ollama_body(obj_or_raw):
    """Wrap an object/raw string the way Ollama's /api/generate does."""
    inner = obj_or_raw if isinstance(obj_or_raw, str) else json.dumps(obj_or_raw)
    return {"response": inner, "done": True}


def engine(**kwargs):
    kwargs.setdefault("ollama_url", "http://localhost:11434")
    kwargs.setdefault("model", "llama3.2")
    kwargs.setdefault("timeout", 10)
    return AOC4FigureLLMJudgeEngine(**kwargs)


def sheet_rows(sheet, part_col_idx, label_of_row):
    return [sheet.cell(row=r, column=part_col_idx).value for r in label_of_row]


def load_sheet(path=RULES_EXCEL, name=PRIVATE_SHEET):
    try:
        import openpyxl
    except ImportError:  # pragma: no cover
        raise unittest.SkipTest("openpyxl not installed")
    if not os.path.exists(path):
        raise unittest.SkipTest("workbook not found: %s" % path)
    return openpyxl.load_workbook(path, data_only=True)[name]


class TestFigureScope(unittest.TestCase):
    """The judged scope must be exactly the financial-particulars block."""

    def setUp(self):
        self.engine = engine()

    def test_catalogue_is_well_formed(self):
        self.assertTrue(self.engine._FIGURES)
        for key, spec in self.engine._FIGURES.items():
            with self.subTest(figure=key):
                self.assertTrue(spec["name"], "%s has no display name" % key)
                self.assertTrue(spec["anchors"], "%s has no anchors" % key)
                self.assertIn(spec["kind"], ("amount", "count"))
                for anchor in spec["anchors"]:
                    self.assertEqual(anchor, anchor.lower(),
                                     "anchor %r for %s must be lowercase" % (anchor, key))

    def test_anchors_are_wired_into_the_window_builder(self):
        anchors = self.engine._ANCHOR_KEYWORDS
        self.assertEqual(sorted(anchors), sorted(self.engine._FIGURES))
        for key in self.engine._FIGURES:
            self.assertEqual(tuple(anchors[key]), tuple(self.engine._FIGURES[key]["anchors"]))

    def test_real_sheet_block_is_rows_5_to_27(self):
        rule_engine = AOC4RuleEngine(CONFIG)
        sheet = load_sheet()
        rows = rule_engine._financial_block_rows(sheet, 1)
        self.assertEqual(rows, EXPECTED_ROWS,
                         "figure scope drifted from the workbook rows")

    def test_every_real_sheet_row_routes_to_the_catalogue(self):
        rule_engine = AOC4RuleEngine(CONFIG)
        sheet = load_sheet()
        for row in EXPECTED_ROWS:
            label = sheet.cell(row=row, column=1).value
            with self.subTest(row=row, label=label):
                self.assertTrue(self.engine.is_judged_figure(label),
                                "row %d (%r) is not routed" % (row, label))

    def test_rows_below_the_block_are_not_figures(self):
        rule_engine = AOC4RuleEngine(CONFIG)
        sheet = load_sheet()
        for row in (28, 29, 37, 40, 61):
            label = sheet.cell(row=row, column=1).value
            with self.subTest(row=row, label=label):
                self.assertFalse(self.engine.is_judged_figure(label),
                                 "row %d (%r) must not be judged as a figure" % (row, label))

    def test_legacy_template_block_resolves_to_its_own_rows(self):
        rule_engine = AOC4RuleEngine(CONFIG)
        sheet = load_sheet(LEGACY_EXCEL, LEGACY_SHEET)
        rows = rule_engine._financial_block_rows(sheet, 3)
        self.assertEqual(rows, LEGACY_EXPECTED_ROWS,
                         "the judge must not be hardcoded to one workbook layout")

    def test_routing_is_case_and_punctuation_insensitive(self):
        for text in ["Paidup capital", "PAIDUP CAPITAL", "Networth", "Net Worth",
                     "Exprt", "Dues  to  MSME"]:
            with self.subTest(text=text):
                self.assertTrue(self.engine.is_judged_figure(text))

    def test_non_figure_text_is_not_judged(self):
        for text in ["Financial Particulars", "Requirement", "Complied or not",
                     "Is it a Small Company?", "Vigil Mechanism", "", None,
                     "Current Year"]:
            with self.subTest(text=text):
                self.assertFalse(self.engine.is_judged_figure(text))

    def test_dict_input_resolves_via_particulars(self):
        self.assertEqual(
            self.engine.name_for_figure({"particulars": "Networth"}), "networth")


class TestFigureVerdictMapping(unittest.TestCase):
    """The match/mismatch decision is made in Python, not by the model."""

    def setUp(self):
        self.engine = engine()

    def test_exact_amount_is_a_match(self):
        self.assertEqual(self.engine._verdict(5000000.0, 5000000.0, "amount")[0], "match")

    def test_amount_within_tolerance_is_a_match(self):
        self.assertEqual(self.engine._verdict(5000000.0, 5000100.0, "amount")[0], "match")

    def test_amount_outside_tolerance_is_a_mismatch(self):
        self.assertEqual(self.engine._verdict(5000000.0, 9000000.0, "amount")[0], "mismatch")

    def test_ocr_noise_below_the_floor_is_tolerated(self):
        self.assertEqual(self.engine._verdict(100.0, 600.0, "amount")[0], "match")

    def test_amount_reported_in_crore_is_matched_by_scale(self):
        self.assertEqual(self.engine._verdict(5000000.0, 0.5, "amount")[0], "match")

    def test_amount_reported_in_lakhs_is_matched_by_scale(self):
        self.assertEqual(self.engine._verdict(5000000.0, 50.0, "amount")[0], "match")

    def test_scaled_mismatch_is_still_a_mismatch(self):
        self.assertEqual(self.engine._verdict(5000000.0, 0.9, "amount")[0], "mismatch")

    def test_counts_are_compared_exactly(self):
        self.assertEqual(self.engine._verdict(3.0, 3.0, "count")[0], "match")
        self.assertEqual(self.engine._verdict(3.0, 4.0, "count")[0], "mismatch")

    def test_missing_model_figure_is_not_stated(self):
        self.assertEqual(self.engine._verdict(5000000.0, None, "amount")[0], "not stated")

    def test_missing_expected_figure_is_not_extracted(self):
        self.assertEqual(self.engine._verdict(None, 5000000.0, "amount")[0],
                         "not extracted")

    def test_both_missing_is_not_extracted(self):
        """With nothing extracted there is nothing to verify, whatever the doc says."""
        self.assertEqual(self.engine._verdict(None, None, "amount")[0], "not extracted")
        self.assertEqual(self.engine._verdict(None, None, "count")[0], "not extracted")

    def test_verdict_never_depends_on_the_reason_text(self):
        """A model claiming success cannot change the arithmetic outcome."""
        with mock.patch("requests.post") as post:
            post.return_value = _FakeResponse(ollama_body({
                "figure": 99999999.0, "quote": "Paid-up Rs 99,99,99,999",
                "reason": "This is certainly correct and matches perfectly.",
            }))
            result = self.engine.verify("networth", 9250000.0, {"full_text": DOC_TEXT})
        self.assertEqual(result["verdict"], "mismatch")

    def test_tolerance_floor_and_ratio(self):
        self.assertEqual(self.engine.tolerance_for(0.0, "amount"), 1000.0)
        self.assertEqual(self.engine.tolerance_for(100000000.0, "amount"), 1000000.0)
        self.assertEqual(self.engine.tolerance_for(5.0, "count"), 0.0)

    def test_string_figures_are_coerced(self):
        self.assertEqual(self.engine._verdict(5000000.0, "50,00,000", "amount")[0],
                         "match")

    def test_booleans_are_not_treated_as_numbers(self):
        self.assertIsNone(self.engine._to_float(True))
        self.assertIsNone(self.engine._to_float(""))


class TestFigureGuardrails(unittest.TestCase):
    """Nothing is asked of the model unless a real question exists."""

    def setUp(self):
        self.engine = engine()

    def test_out_of_scope_row_makes_no_http_call(self):
        with mock.patch("requests.post") as post:
            self.assertIsNone(self.engine.verify("Vigil Mechanism", 1.0,
                                                 {"full_text": DOC_TEXT}))
        post.assert_not_called()

    def test_missing_full_text_makes_no_http_call(self):
        for data in ({}, {"full_text": ""}, {"full_text": "   "}, {"full_text": None}):
            with self.subTest(data=data), mock.patch("requests.post") as post:
                self.assertIsNone(self.engine.verify("networth", 1.0, data))
            post.assert_not_called()

    def test_verdict_is_never_requested_from_the_model(self):
        with mock.patch("requests.post") as post:
            post.return_value = _FakeResponse(ollama_body({
                "figure": 9250000.0, "quote": "Net worth Rs 92,50,000",
                "reason": "Balance sheet total."}))
            self.engine.verify("networth", 9250000.0, {"full_text": DOC_TEXT})
        prompt = post.call_args[1]["json"]["prompt"]
        self.assertNotIn('"verdict"', prompt)
        self.assertNotIn('"match"', prompt.lower())
        self.assertIn('"figure"', prompt)

    def test_prompt_carries_the_fabrication_guard(self):
        with mock.patch("requests.post") as post:
            post.return_value = _FakeResponse(ollama_body({
                "figure": 1.0, "quote": "x", "reason": "y"}))
            self.engine.verify("networth", 9250000.0, {"full_text": DOC_TEXT})
        prompt = post.call_args[1]["json"]["prompt"]
        self.assertIn("null", prompt)
        self.assertIn("Never supply a number you did not read", prompt)
        self.assertIn("Do not", prompt)

    def test_prompt_includes_the_extracted_figure(self):
        with mock.patch("requests.post") as post:
            post.return_value = _FakeResponse(ollama_body({
                "figure": 1.0, "quote": "x", "reason": "y"}))
            self.engine.verify("networth", 9250000.0, {"full_text": DOC_TEXT})
        prompt = post.call_args[1]["json"]["prompt"]
        self.assertIn("9250000.00", prompt)

    def test_prompt_says_nothing_to_compare_when_nothing_was_extracted(self):
        with mock.patch("requests.post") as post:
            post.return_value = _FakeResponse(ollama_body({
                "figure": 1.0, "quote": "x", "reason": "y"}))
            self.engine.verify("networth", None, {"full_text": DOC_TEXT})
        prompt = post.call_args[1]["json"]["prompt"]
        self.assertIn("not available", prompt)

    def test_request_payload_contract(self):
        with mock.patch("requests.post") as post:
            post.return_value = _FakeResponse(ollama_body({
                "figure": 1.0, "quote": "x", "reason": "y"}))
            self.engine.verify("networth", 1.0, {"full_text": DOC_TEXT})
        payload = post.call_args[1]["json"]
        self.assertEqual(payload["model"], "llama3.2")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"], "json")
        self.assertEqual(payload["options"]["temperature"], 0.0)

    def test_window_contains_the_row_anchors(self):
        with mock.patch("requests.post") as post:
            post.return_value = _FakeResponse(ollama_body({
                "figure": 1.0, "quote": "x", "reason": "y"}))
            self.engine.verify("networth", 1.0, {"full_text": DOC_TEXT})
        prompt = post.call_args[1]["json"]["prompt"]
        self.assertIn("Net worth", prompt)


class TestFigureTransport(unittest.TestCase):
    """Every failure path keeps the extracted figure untouched."""

    def setUp(self):
        self.engine = engine()

    def _verify(self, response):
        with mock.patch("requests.post") as post:
            post.return_value = response
            return self.engine.verify("networth", 9250000.0, {"full_text": DOC_TEXT})

    def test_http_error_returns_none(self):
        self.assertIsNone(self._verify(_FakeResponse(ollama_body({}), status_code=500)))

    def test_transport_error_returns_none(self):
        with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError("x")):
            self.assertIsNone(
                self.engine.verify("networth", 9250000.0, {"full_text": DOC_TEXT}))

    def test_timeout_returns_none(self):
        with mock.patch("requests.post", side_effect=requests.exceptions.Timeout("x")):
            self.assertIsNone(
                self.engine.verify("networth", 9250000.0, {"full_text": DOC_TEXT}))

    def test_bad_body_returns_none(self):
        self.assertIsNone(self._verify(_FakeResponse(None)))

    def test_json_embedded_in_prose_is_parsed(self):
        result = self._verify(_FakeResponse(ollama_body(
            'Here you go: {"figure": 9250000.0, "quote": "Net worth", "reason": "ok"} done')))
        self.assertEqual(result["verdict"], "match")

    def test_answer_is_read_from_thinking_when_response_is_empty(self):
        body = {"response": "", "thinking": json.dumps({
            "figure": 9250000.0, "quote": "Net worth", "reason": "ok"})}
        result = self._verify(_FakeResponse(body))
        self.assertEqual(result["verdict"], "match")

    def test_model_returning_null_figure_is_not_stated(self):
        result = self._verify(_FakeResponse(ollama_body(
            {"figure": None, "quote": "not found", "reason": "absent"})))
        self.assertEqual(result["verdict"], "not stated")

    def test_circuit_breaker_stops_retrying_after_transport_failure(self):
        with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError("x")) as post:
            self.engine.verify("networth", 1.0, {"full_text": DOC_TEXT})
            self.engine.verify("turnover", 1.0, {"full_text": DOC_TEXT})
        self.assertEqual(post.call_count, 1)

    def test_server_error_does_not_trip_the_breaker(self):
        with mock.patch("requests.post") as post:
            post.return_value = _FakeResponse(ollama_body({}), status_code=500)
            self.engine.verify("networth", 1.0, {"full_text": DOC_TEXT})
            self.engine.verify("turnover", 1.0, {"full_text": DOC_TEXT})
        self.assertEqual(post.call_count, 2)

    def test_evidence_is_capped_in_the_reason(self):
        result = self._verify(_FakeResponse(ollama_body(
            {"figure": 1.0, "quote": "x" * 5000, "reason": "r"})))
        self.assertLess(len(result["reason"]), 700)

    def test_model_saying_the_figure_is_absent_is_recorded(self):
        """Silence here would leave the extracted number in place with no flag."""
        result = self._verify(_FakeResponse(ollama_body(
            {"figure": None, "quote": "", "reason": "Not disclosed in the document"})))
        self.assertEqual(result["verdict"], "not stated")
        self.assertIn("not stated in the document", result["reason"])

    def test_empty_answer_is_treated_as_a_failure(self):
        for payload in ({"figure": None}, {"figure": None, "quote": "", "reason": ""},
                        {"figure": None, "quote": "n/a", "reason": ""}):
            with self.subTest(payload=payload), mock.patch("requests.post") as post:
                post.return_value = _FakeResponse(ollama_body(payload))
                self.assertIsNone(
                    self.engine.verify("networth", 9250000.0, {"full_text": DOC_TEXT}))

    def test_absent_figure_still_gets_a_verdict_in_the_sheet(self):
        rule_engine = AOC4RuleEngine(CONFIG)
        sheet = load_sheet()
        target_cells = {PRIVATE_SHEET: {"B5": 5000000.0}}
        with mock.patch("requests.post") as post:
            post.return_value = _FakeResponse(ollama_body(
                {"figure": None, "quote": "", "reason": "Not disclosed"}))
            rule_engine._verify_financial_figures(
                sheet, PRIVATE_SHEET, target_cells,
                part_col_idx=1, cy_col="B", extracted_data={"full_text": DOC_TEXT})
        cells = target_cells[PRIVATE_SHEET]
        self.assertEqual(cells["F5"], "not stated")
        self.assertEqual(cells["B5"], 5000000.0)

    def test_default_reason_is_supplied(self):
        result = self._verify(_FakeResponse(ollama_body(
            {"figure": 9250000.0, "quote": "Net worth", "reason": ""})))
        self.assertTrue(result["reason"])


class TestFigureSheetIntegration(unittest.TestCase):
    """The pass writes to F/G and never disturbs the extracted figures."""

    def setUp(self):
        self.rule_engine = AOC4RuleEngine(CONFIG)
        self.sheet = load_sheet()

    def _cells(self, response, seeded):
        target_cells = {PRIVATE_SHEET: dict(seeded)}
        with mock.patch("requests.post") as post:
            post.return_value = response
            self.rule_engine._verify_financial_figures(
                self.sheet, PRIVATE_SHEET, target_cells,
                part_col_idx=1, cy_col="B",
                extracted_data={"full_text": DOC_TEXT},
            )
        return target_cells[PRIVATE_SHEET], post

    def test_writes_verdict_and_evidence_to_f_and_g(self):
        cells, _ = self._cells(
            _FakeResponse(ollama_body({"figure": 5000000.0, "quote": "Paid-up",
                                       "reason": "ok"})),
            {"B5": 5000000.0})
        self.assertEqual(cells["F5"], "match")
        self.assertIn("agrees with the extracted figure", cells["G5"])
        self.assertEqual(cells["F4"], "LLM Figure Check")
        self.assertEqual(cells["G4"], "Evidence")

    def test_extracted_figures_are_never_modified(self):
        seeded = {"B5": 5000000.0, "B17": 9250000.0}
        cells, _ = self._cells(
            _FakeResponse(ollama_body({"figure": 1.0, "quote": "x", "reason": "y"})),
            seeded)
        self.assertEqual(cells["B5"], 5000000.0)
        self.assertEqual(cells["B17"], 9250000.0)

    def test_mismatch_does_not_overwrite_the_cell(self):
        cells, _ = self._cells(
            _FakeResponse(ollama_body({"figure": 777.0, "quote": "x", "reason": "y"})),
            {"B5": 5000000.0})
        self.assertEqual(cells["F5"], "mismatch")
        self.assertEqual(cells["B5"], 5000000.0)

    def test_duplicate_exprt_label_costs_one_call(self):
        cells, post = self._cells(
            _FakeResponse(ollama_body({"figure": 1.0, "quote": "x", "reason": "y"})),
            {"B5": 1.0})
        self.assertEqual(post.call_count, 22,
                         "23 rows but 'Exprt' repeats, so 22 distinct figures")
        self.assertIn("F23", cells)
        self.assertIn("F24", cells)
        self.assertEqual(cells["F23"], cells["F24"])

    def test_no_verdicts_when_the_server_is_unreachable(self):
        with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError("x")):
            target_cells = {PRIVATE_SHEET: {"B5": 5000000.0}}
            self.rule_engine._verify_financial_figures(
                self.sheet, PRIVATE_SHEET, target_cells,
                part_col_idx=1, cy_col="B",
                extracted_data={"full_text": DOC_TEXT},
            )
        cells = target_cells[PRIVATE_SHEET]
        self.assertEqual(cells["B5"], 5000000.0)
        self.assertNotIn("F5", cells)

    def test_missing_block_is_reported_not_fatal(self):
        self.assertEqual(
            self.rule_engine._financial_block_rows(self.sheet, 5), [])


class TestComplianceJudgeDisabled(unittest.TestCase):
    """The requirement table (rows 40-61) must stay deterministic-only."""

    def setUp(self):
        self.rule_engine = AOC4RuleEngine(CONFIG)

    def test_flag_is_off(self):
        self.assertFalse(ENABLE_COMPLIANCE_LLM_JUDGE)

    def test_compliance_engine_has_no_judge(self):
        self.assertIsNone(self.rule_engine.compliance_engine.llm_judge)

    def test_compliance_flags_still_produce_a_deterministic_answer(self):
        flags = self.rule_engine.compliance_engine.execute({"full_text": DOC_TEXT})
        self.assertEqual(len(flags), 25)
        for flag in flags:
            with self.subTest(flag=flag["id"]):
                self.assertNotIn("judged_by", flag)

    def test_common_error_judge_is_untouched(self):
        self.assertIsNotNone(self.rule_engine.checker.llm_judge)


if __name__ == "__main__":
    unittest.main(verbosity=2)
