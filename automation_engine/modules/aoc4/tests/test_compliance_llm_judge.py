"""Standalone test-suite for the AOC-4 **compliance-sheet** LLM judge.

Covers ``automation_engine/modules/aoc4/compliance_llm_judge.py`` and its hybrid
wiring into ``PrivateComplianceEngine``. Mirrors ``tests/test_llm_judge.py``:
pytest is not part of this project, so this is stdlib ``unittest`` with
``requests.post`` mocked (no live Ollama needed).

Run it::

    python automation_engine/modules/aoc4/tests/test_compliance_llm_judge.py
"""

import json
import os
import sys
import unittest
from unittest import mock

import requests

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
AOC4_DIR = os.path.dirname(TESTS_DIR)                                     # .../modules/aoc4
# aoc4 -> modules -> automation_engine -> repository root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(AOC4_DIR)))

for _path in (PROJECT_ROOT, AOC4_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from automation_engine.modules.aoc4.compliance import compliance_llm_judge as compl_mod
from automation_engine.modules.aoc4.compliance.compliance_engine import PrivateComplianceEngine
from automation_engine.modules.aoc4.compliance.compliance_llm_judge import (
    JUDGED_REQUIREMENT_KEYS,
    AOC4ComplianceLLMJudgeEngine,
)

RULES_EXCEL = os.path.join(AOC4_DIR, "excel", "Annual Filing common error Output.xlsx")
PRIVATE_SHEET = "Compliance sheet for private"

# The requirement table on 'Compliance sheet for private' starts at row 36, so
# the judged scope is sheet rows 40-61 (the "rows 5-26" slice of that table).
EXPECTED_FIRST_ROW = 40
EXPECTED_JUDGED_ROWS = dict(zip(range(40, 62), JUDGED_REQUIREMENT_KEYS))
EXCLUDED_ROWS = (37, 38, 39)   # Small Company / CARO / Rotation of Auditors

DOC_TEXT = (
    "Notes to Accounts. The company has not accepted any deposits during the year. "
    "Internal financial controls are adequate and operating effectively. "
    "There are no related party transactions. Dues to micro and small enterprises: Nil."
)

FLAG_VIGIL = {"id": "COMP_VIGIL", "particulars": "Vigil Mechanism",
              "user_value": "Not Applicable", "status": "Passed",
              "rationale": "Total Borrowings (0.23 Cr) <= 50 Cr.", "source": "Compliance Engine"}


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
    return AOC4ComplianceLLMJudgeEngine(**kwargs)
class TestComplianceScope(unittest.TestCase):
    """The judged scope must be exactly the requirement-table rows 40-61."""

    def setUp(self):
        self.engine = engine()

    def test_scope_and_catalogue_agree(self):
        self.assertEqual(len(JUDGED_REQUIREMENT_KEYS), 22)
        self.assertEqual(len(set(JUDGED_REQUIREMENT_KEYS)), 22)
        self.assertEqual(sorted(JUDGED_REQUIREMENT_KEYS), sorted(self.engine._REQUIREMENTS))

    def test_every_requirement_has_anchors_and_intent(self):
        for key, spec in self.engine._REQUIREMENTS.items():
            with self.subTest(requirement=key):
                self.assertTrue(spec["intent"], "%s has no adjudication brief" % key)
                self.assertTrue(spec["anchors"], "%s has no evidence anchors" % key)
                for anchor in spec["anchors"]:
                    self.assertEqual(anchor, anchor.lower(),
                                     "anchor %r for %s must be lowercase" % (anchor, key))

    def test_anchors_are_wired_into_the_window_builder(self):
        anchors = self.engine._ANCHOR_KEYWORDS
        self.assertEqual(sorted(anchors), sorted(JUDGED_REQUIREMENT_KEYS))
        for key in JUDGED_REQUIREMENT_KEYS:
            self.assertEqual(tuple(anchors[key]),
                             tuple(self.engine._REQUIREMENTS[key]["anchors"]))

    def test_real_sheet_requirement_rows_route_to_scope(self):
        try:
            import openpyxl
        except ImportError:  # pragma: no cover
            self.skipTest("openpyxl not installed")
        if not os.path.exists(RULES_EXCEL):
            self.skipTest("rules workbook not found")

        ws = openpyxl.load_workbook(RULES_EXCEL, data_only=True)[PRIVATE_SHEET]
        routed = {}
        for row in range(37, 62):
            key = self.engine.name_for_requirement(ws.cell(row=row, column=1).value)
            if key:
                routed[row] = key
        self.assertEqual(routed, EXPECTED_JUDGED_ROWS,
                         "compliance LLM scope drifted from the workbook rows")

    def test_threshold_requirements_are_excluded(self):
        try:
            import openpyxl
        except ImportError:  # pragma: no cover
            self.skipTest("openpyxl not installed")
        if not os.path.exists(RULES_EXCEL):
            self.skipTest("rules workbook not found")

        ws = openpyxl.load_workbook(RULES_EXCEL, data_only=True)[PRIVATE_SHEET]
        for row in EXCLUDED_ROWS:
            text = ws.cell(row=row, column=1).value
            with self.subTest(row=row, text=text):
                self.assertFalse(self.engine.is_judged_requirement(text))

    def test_non_requirement_text_is_not_judged(self):
        for text in ["Requirement", "", None, "Current Year", "Complied or not",
                     "Financial Particulars", "Paidup capital"]:
            with self.subTest(text=text):
                self.assertFalse(self.engine.is_judged_requirement(text))

    def test_routing_is_case_and_punctuation_insensitive(self):
        for text in ["vigil mechanism", "VIGIL MECHANISM", "Vigil  Mechanism",
                     "Certification of MGT-7?", "dpt3", "Loan and Investments"]:
            with self.subTest(text=text):
                self.assertTrue(self.engine.is_judged_requirement(text))

    def test_engine_flags_in_scope(self):
        flags = PrivateComplianceEngine(enable_llm_judge=False).execute({})
        self.assertEqual(len(flags), 25)
        in_scope = [f for f in flags if self.engine.is_judged_requirement(f)]
        self.assertEqual(len(in_scope), 22)
        self.assertEqual({f["id"] for f in in_scope}, set(JUDGED_REQUIREMENT_KEYS))


class TestComplianceVerdictMapping(unittest.TestCase):
    """The structured answer must map onto the flag fields the sheet consumes."""

    def _call(self, payload=None, side_effect=None, status_code=200, raw=None):
        body = {"response": raw, "done": True} if raw is not None else payload
        with mock.patch.object(compl_mod.requests, "post") as post:
            if side_effect is not None:
                post.side_effect = side_effect
            else:
                post.return_value = _FakeResponse(body, status_code=status_code)
            return engine().judge(FLAG_VIGIL, {"full_text": DOC_TEXT}), post

    def test_applicable_and_complied(self):
        result, _ = self._call(ollama_body({
            "applicability": "Applicable", "complied": "Yes",
            "evidence": "the company has a whistle blower policy",
            "reason": "Vigil mechanism policy is disclosed."}))
        self.assertEqual(result["user_value"], "Applicable")
        self.assertEqual(result["status"], "Failed")
        self.assertEqual(result["_judged_by"], "llm")
        self.assertIn("Complied: Yes", result["rationale"])
        self.assertIn("Vigil mechanism policy is disclosed.", result["rationale"])
        self.assertIn("Evidence: the company has a whistle blower policy", result["rationale"])

    def test_not_applicable_maps_to_passed(self):
        result, _ = self._call(ollama_body({
            "applicability": "Not Applicable", "complied": "Not Applicable",
            "reason": "Borrowings are below Rs 50 crore."}))
        self.assertEqual(result["user_value"], "Not Applicable")
        self.assertEqual(result["status"], "Passed")
        self.assertIn("Not applicable", result["rationale"])

    def test_applicable_but_not_complied(self):
        result, _ = self._call(ollama_body({
            "applicability": "Applicable", "complied": "No", "evidence": "not found",
            "reason": "No secretarial audit report is attached."}))
        self.assertEqual(result["user_value"], "Applicable")
        self.assertEqual(result["status"], "Failed")
        self.assertIn("Complied: No", result["rationale"])
        self.assertNotIn("Evidence:", result["rationale"])

    def test_verdicts_are_case_and_whitespace_insensitive(self):
        cases = [("applicable", "Applicable"), ("  NOT   APPLICABLE  ", "Not Applicable"),
                 ("Applicable", "Applicable")]
        for raw, expected in cases:
            with self.subTest(applicability=raw):
                result, _ = self._call(ollama_body(
                    {"applicability": raw, "complied": "YES", "reason": "r"}))
                self.assertEqual(result["user_value"], expected)
        for raw, label in [("yes", "Complied: Yes"), ("NO", "Complied: No"),
                           ("maybe", "Complied: not stated")]:
            with self.subTest(complied=raw):
                result, _ = self._call(ollama_body(
                    {"applicability": "Applicable", "complied": raw, "reason": "r"}))
                self.assertIn(label, result["rationale"])

    def test_missing_reason_gets_default(self):
        result, _ = self._call(ollama_body({"applicability": "Applicable", "complied": "Yes"}))
        self.assertIn("Judged by AOC4 Compliance LLM", result["rationale"])

    def test_evidence_is_truncated(self):
        result, _ = self._call(ollama_body({
            "applicability": "Applicable", "complied": "Yes",
            "evidence": "x" * 900, "reason": "r"}))
        self.assertLessEqual(len(result["rationale"]), 700)

    def test_cannot_determine_falls_back(self):
        for raw in ["Cannot determine", "", None, "unknown", "TRUE"]:
            with self.subTest(applicability=raw):
                result, _ = self._call(ollama_body(
                    {"applicability": raw, "complied": "Yes", "reason": "r"}))
                self.assertIsNone(result)


FLAG_SMALL_CO = {"id": "COMP_SMALL_CO", "particulars": "Is it a Small Company?",
                 "user_value": "Yes", "status": "Passed", "rationale": "Small.",
                 "source": "Compliance Engine"}
FLAG_IFC = {"id": "COMP_IFC", "particulars": "Internal Financial Controls",
            "user_value": "Not Applicable", "status": "Passed", "rationale": "x",
            "source": "Compliance Engine"}
FLAG_MSME = {"id": "COMP_MSME", "particulars": "MSME", "user_value": "Not Applicable",
             "status": "Passed", "rationale": "x", "source": "Compliance Engine"}
FLAG_AOC_1 = {"id": "COMP_AOC_1", "particulars": "AOC 1", "user_value": "Not Applicable",
              "status": "Passed", "rationale": "x", "source": "Compliance Engine"}


class TestComplianceGuardrails(unittest.TestCase):
    """Out-of-scope rows must never reach the network."""

    @mock.patch.object(compl_mod.requests, "post")
    def test_out_of_scope_requirement_makes_no_http_call(self, post):
        self.assertIsNone(engine().judge(FLAG_SMALL_CO, {"full_text": DOC_TEXT}))
        post.assert_not_called()

    @mock.patch.object(compl_mod.requests, "post")
    def test_missing_or_invalid_full_text_makes_no_http_call(self, post):
        for bad in [{}, {"full_text": ""}, {"full_text": "  \n\t "}, {"full_text": None},
                    {"full_text": 12345}, {"full_text": ["x"]}]:
            with self.subTest(input_data=bad):
                self.assertIsNone(engine().judge(FLAG_VIGIL, bad))
        post.assert_not_called()

    @mock.patch.object(compl_mod.requests, "post")
    def test_flag_without_id_or_text_makes_no_http_call(self, post):
        for bad in [{}, {"id": None, "particulars": None}, {"particulars": ""}, None]:
            with self.subTest(flag=bad):
                self.assertIsNone(engine().judge(bad, {"full_text": DOC_TEXT}))
        post.assert_not_called()

    def test_request_payload_contract(self):
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"applicability": "Applicable", "complied": "Yes",
                                    "reason": "r"}))) as post:
            engine().judge(FLAG_VIGIL, {"full_text": DOC_TEXT})
        kwargs = post.call_args.kwargs
        self.assertEqual(post.call_args.args[0], "http://localhost:11434/api/generate")
        self.assertEqual(kwargs["json"]["model"], "llama3.2")
        self.assertFalse(kwargs["json"]["stream"])
        self.assertEqual(kwargs["json"]["format"], "json")
        self.assertEqual(kwargs["json"]["options"]["temperature"], 0.0)
        self.assertEqual(kwargs["json"]["options"]["num_ctx"], 8192)
        self.assertEqual(kwargs["timeout"], 10)
        prompt = kwargs["json"]["prompt"]
        for block in ("REQUIREMENT:", "ADJUDICATION BRIEF:", "RELEVANT DOCUMENT EXTRACT:",
                      '"applicability"', '"complied"'):
            self.assertIn(block, prompt)
        self.assertIn("Vigil Mechanism", prompt)

    def test_prompt_includes_the_deterministic_preliminary_answer(self):
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"applicability": "Applicable", "complied": "Yes",
                                    "reason": "r"}))) as post:
            engine().judge(FLAG_VIGIL, {"full_text": DOC_TEXT})
        prompt = post.call_args.kwargs["json"]["prompt"]
        self.assertIn("preliminary answer", prompt)
        self.assertIn("Not Applicable", prompt)

    def test_facts_block_renders_values_and_missing_markers(self):
        facts = engine()._format_facts({"borrowings": 0.0, "turnover": 504583000.0,
                                        "paid_up_capital": 2294000.0, "is_listed": "No"})
        self.assertIn("- Total borrowings (Rs): 0 (Rs 0.00 crore)", facts)
        self.assertIn("- Turnover (Rs): 504,583,000 (Rs 50.46 crore)", facts)
        self.assertIn("- Paid-up capital (Rs): 2,294,000 (Rs 0.23 crore)", facts)
        self.assertIn("- Listed company: No", facts)
        self.assertIn("- Net worth (Rs): not available", facts)

    def test_facts_block_handles_missing_and_non_dict_input(self):
        self.assertEqual(engine()._format_facts(None), "- all facts not available")
        facts = engine()._format_facts({})
        self.assertIn("- Total borrowings (Rs): not available", facts)
        self.assertIn("- Company type: not available", facts)

    def test_facts_block_renders_booleans(self):
        facts = engine()._format_facts({"is_listed": True, "is_ind_as": False})
        self.assertIn("- Listed company: Yes", facts)
        self.assertIn("- Ind AS applicable: No", facts)

    def test_prompt_contains_facts_and_the_fabrication_guard(self):
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"applicability": "Not Applicable",
                                    "complied": "Not Applicable", "reason": "r"}))) as post:
            engine().judge(FLAG_VIGIL, {"full_text": DOC_TEXT, "borrowings": 0.0,
                                        "turnover": 504583000.0})
        prompt = post.call_args.kwargs["json"]["prompt"]
        self.assertIn("FINANCIAL FACTS EXTRACTED FROM THE FILING", prompt)
        self.assertIn("- Turnover (Rs): 504,583,000 (Rs 50.46 crore)", prompt)
        self.assertIn("Never assume a financial figure that is not listed", prompt)
        self.assertIn("Cannot determine", prompt)

    def test_prompt_marks_absent_facts_as_unavailable(self):
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"applicability": "Not Applicable", "reason": "r"}))) as post:
            engine().judge(FLAG_VIGIL, {"full_text": DOC_TEXT})
        prompt = post.call_args.kwargs["json"]["prompt"]
        self.assertIn("- Total borrowings (Rs): not available", prompt)
        self.assertIn("- Turnover (Rs): not available", prompt)


class TestComplianceTransport(unittest.TestCase):
    """Every transport/parse failure must degrade to the deterministic engine."""

    def _call(self, payload=None, side_effect=None, status_code=200, raw=None):
        body = {"response": raw, "done": True} if raw is not None else payload
        with mock.patch.object(compl_mod.requests, "post") as post:
            if side_effect is not None:
                post.side_effect = side_effect
            else:
                post.return_value = _FakeResponse(body, status_code=status_code)
            return engine().judge(FLAG_VIGIL, {"full_text": DOC_TEXT}), post

    def test_http_errors_fall_back(self):
        for status in [400, 404, 500, 503]:
            with self.subTest(status=status):
                result, _ = self._call(ollama_body({"applicability": "Applicable"}),
                                       status_code=status)
                self.assertIsNone(result)

    def test_transport_errors_fall_back(self):
        for exc in [requests.exceptions.ConnectionError("refused"),
                    requests.exceptions.ConnectTimeout("timed out"),
                    requests.exceptions.ReadTimeout("timed out"),
                    requests.exceptions.HTTPError("boom"),
                    ValueError("unexpected")]:
            with self.subTest(exc=type(exc).__name__):
                result, _ = self._call(side_effect=exc)
                self.assertIsNone(result)

    def test_bad_bodies_fall_back(self):
        for raw in ["I cannot answer in JSON.", "", "   ", "[1, 2, 3]", "123", '"applicable"']:
            with self.subTest(raw=raw):
                result, _ = self._call(raw=raw)
                self.assertIsNone(result)
        result, _ = self._call({"done": True})
        self.assertIsNone(result)
        result, _ = self._call(None)
        self.assertIsNone(result)

    def test_json_embedded_in_prose_is_parsed(self):
        result, _ = self._call(raw='Here you go:\n{"applicability": "Applicable", '
                                   '"complied": "Yes", "reason": "ok"}\nDone.')
        self.assertEqual(result["user_value"], "Applicable")

    def test_circuit_breaker_stops_retrying_after_transport_failure(self):
        eng = engine()
        with mock.patch.object(compl_mod.requests, "post",
                               side_effect=requests.exceptions.ConnectTimeout("timed out")) as post:
            self.assertIsNone(eng.judge(FLAG_VIGIL, {"full_text": DOC_TEXT}))
            self.assertEqual(post.call_count, 1)
            for flag in (FLAG_IFC, FLAG_MSME, FLAG_AOC_1):
                self.assertIsNone(eng.judge(flag, {"full_text": DOC_TEXT}))
            self.assertEqual(post.call_count, 1, "circuit breaker did not stop retrying")
            self.assertTrue(eng._unreachable)

    def test_circuit_breaker_can_be_disabled(self):
        eng = engine(allow_unreachable_retry=True)
        with mock.patch.object(compl_mod.requests, "post",
                               side_effect=requests.exceptions.ConnectionError("refused")) as post:
            eng.judge(FLAG_VIGIL, {"full_text": DOC_TEXT})
            eng.judge(FLAG_IFC, {"full_text": DOC_TEXT})
            self.assertEqual(post.call_count, 2)

    def test_server_error_does_not_trip_the_breaker(self):
        """A 5xx means the server is alive, so later rows should still be tried."""
        eng = engine()
        with mock.patch.object(compl_mod.requests, "post") as post:
            post.return_value = _FakeResponse(
                ollama_body({"applicability": "Applicable"}), status_code=500)
            eng.judge(FLAG_VIGIL, {"full_text": DOC_TEXT})
            eng.judge(FLAG_IFC, {"full_text": DOC_TEXT})
            self.assertEqual(post.call_count, 2)
            self.assertFalse(eng._unreachable)


class TestComplianceHybridIntegration(unittest.TestCase):
    """PrivateComplianceEngine must use the LLM verdict and keep the safety net."""

    @staticmethod
    def _by_id(flags, flag_id):
        for flag in flags:
            if flag["id"] == flag_id:
                return flag
        raise AssertionError("flag %s was not produced" % flag_id)

    @staticmethod
    def _deterministic():
        return PrivateComplianceEngine(enable_llm_judge=False).execute({"full_text": DOC_TEXT})

    def test_engine_wiring_instantiates_the_judge_by_default(self):
        self.assertIsInstance(PrivateComplianceEngine().llm_judge,
                              AOC4ComplianceLLMJudgeEngine)
        self.assertIsNone(PrivateComplianceEngine(enable_llm_judge=False).llm_judge)

    def test_injected_judge_is_used_verbatim(self):
        sentinel = AOC4ComplianceLLMJudgeEngine(ollama_url="http://sentinel:11434")
        self.assertIs(PrivateComplianceEngine(llm_judge=sentinel).llm_judge, sentinel)

    def test_llm_verdict_overrides_the_deterministic_flag(self):
        det = self._by_id(self._deterministic(), "COMP_VIGIL")
        self.assertEqual(det["user_value"], "Not Applicable")  # precondition

        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body({
                                   "applicability": "Applicable", "complied": "No",
                                   "evidence": "borrowings note",
                                   "reason": "Borrowings exceed Rs 50 crore."}))):
            flags = PrivateComplianceEngine(llm_judge=engine()).execute(
                {"full_text": DOC_TEXT})

        flag = self._by_id(flags, "COMP_VIGIL")
        self.assertEqual(flag["user_value"], "Applicable")
        self.assertEqual(flag["status"], "Failed")
        self.assertIn("Borrowings exceed Rs 50 crore.", flag["rationale"])
        self.assertEqual(flag["judged_by"], "llm")

    def test_out_of_scope_flags_are_never_touched(self):
        det = {f["id"]: f for f in self._deterministic()}
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body({
                                   "applicability": "Applicable", "complied": "Yes",
                                   "reason": "r"}))):
            flags = PrivateComplianceEngine(llm_judge=engine()).execute(
                {"full_text": DOC_TEXT})

        for flag in flags:
            if flag["id"] not in JUDGED_REQUIREMENT_KEYS:
                self.assertEqual(flag, det[flag["id"]], "%s was altered" % flag["id"])
                self.assertNotIn("judged_by", flag)

    def test_only_scope_rows_reach_the_model(self):
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body({
                                   "applicability": "Not Applicable",
                                   "complied": "Not Applicable", "reason": "r"}))) as post:
            flags = PrivateComplianceEngine(llm_judge=engine()).execute(
                {"full_text": DOC_TEXT})

        self.assertEqual(len(flags), 25)
        self.assertEqual(post.call_count, len(JUDGED_REQUIREMENT_KEYS))

    def test_deterministic_result_survives_when_the_server_is_down(self):
        with mock.patch.object(compl_mod.requests, "post",
                               side_effect=requests.exceptions.ConnectionError("refused")) as post:
            flags = PrivateComplianceEngine(llm_judge=engine()).execute(
                {"full_text": DOC_TEXT})

        self.assertEqual(flags, self._deterministic())
        self.assertEqual(post.call_count, 1,
                         "the circuit breaker should cap an outage at one attempt")

    def test_undecided_llm_keeps_the_deterministic_flag(self):
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body({
                                   "applicability": "Cannot determine",
                                   "reason": "unclear"}))):
            flags = PrivateComplianceEngine(llm_judge=engine()).execute(
                {"full_text": DOC_TEXT})

        self.assertEqual(flags, self._deterministic())

    def test_blank_document_keeps_the_deterministic_flag(self):
        with mock.patch.object(compl_mod.requests, "post") as post:
            flags = PrivateComplianceEngine(llm_judge=engine()).execute({"full_text": ""})
        self.assertEqual(flags, self._deterministic())
        post.assert_not_called()


class TestComplianceConfiguration(unittest.TestCase):
    """Constructor arguments and the shared environment variables."""

    def test_defaults(self):
        inst = AOC4ComplianceLLMJudgeEngine()
        self.assertEqual(inst.ollama_url, AOC4ComplianceLLMJudgeEngine.DEFAULT_URL)
        self.assertEqual(inst.model, AOC4ComplianceLLMJudgeEngine.DEFAULT_MODEL)
        self.assertEqual(inst.timeout, AOC4ComplianceLLMJudgeEngine.DEFAULT_TIMEOUT)
        self.assertFalse(inst._unreachable)

    def test_shared_environment_variables(self):
        env = {"AOC4_OLLAMA_URL": "http://10.0.0.9:11434", "AOC4_LLM_MODEL": "llama3.1"}
        with mock.patch.dict(os.environ, env, clear=False):
            inst = AOC4ComplianceLLMJudgeEngine()
            self.assertEqual(inst.ollama_url, "http://10.0.0.9:11434")
            self.assertEqual(inst.model, "llama3.1")

    def test_constructor_arguments_win_over_environment(self):
        with mock.patch.dict(os.environ, {"AOC4_OLLAMA_URL": "http://ignored:1"},
                             clear=False):
            inst = engine(ollama_url="http://explicit:11434", model="llama3.3", timeout=7)
            self.assertEqual(inst.ollama_url, "http://explicit:11434")
            self.assertEqual(inst.model, "llama3.3")
            self.assertEqual(inst.timeout, 7)

    def test_compliance_judge_shares_the_model_portability_knobs(self):
        """num_ctx / temperature / think / api-key must work for this judge too."""
        env = {"AOC4_LLM_NUM_CTX": "16384", "AOC4_LLM_API_KEY": "k",
               "AOC4_LLM_THINK": "false"}
        with mock.patch.dict(os.environ, env, clear=False):
            inst = engine()
            self.assertEqual(inst._request_options()["num_ctx"], 16384)
            self.assertEqual(inst._request_headers(), {"Authorization": "Bearer k"})
            self.assertIs(inst._request_payload("P")["think"], False)

    def test_compliance_judge_sends_configured_options(self):
        with mock.patch.dict(os.environ, {"AOC4_LLM_NUM_CTX": "12288"}, clear=False):
            with mock.patch.object(compl_mod.requests, "post",
                                   return_value=_FakeResponse(ollama_body(
                                       {"applicability": "Applicable", "complied": "Yes",
                                        "reason": "r"}))) as post:
                engine()._ask_llm_compliance("PROMPT")
        self.assertEqual(post.call_args.kwargs["json"]["options"]["num_ctx"], 12288)

    def test_compliance_judge_handles_thinking_blocks(self):
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   ' thinkingweighing the thresholds... {"applicability": "x"} '
                                   'is not my answer'
                                   '{"applicability": "Not Applicable", '
                                   '"complied": "Not Applicable", "reason": "ok"}'))):
            result = engine()._ask_llm_compliance("PROMPT")
        self.assertIsNone(result, "an unterminated thinking block must fall back to the engine")

    def test_compliance_judge_parses_answer_after_a_complete_thinking_block(self):
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   "<THINK>weighing the thresholds...</THINK>"
                                   '{"applicability": "Applicable", "complied": "No", '
                                   '"reason": "borrowings exceed the limit"}'))) as post:
            result = engine()._ask_llm_compliance("PROMPT")
        self.assertEqual(result["user_value"], "Applicable")
        self.assertIn("Complied: No", result["rationale"])

    def test_compliance_reads_the_answer_from_thinking_when_response_is_empty(self):
        """Verified on qwen3.5:4b (thinking mode leaves `response` empty)."""
        body = {"response": "", "done": True,
                "thinking": '{"applicability": "Applicable", "complied": "No", '
                            '"reason": "no secretarial audit report attached"}'}
        with mock.patch.object(compl_mod.requests, "post",
                               return_value=_FakeResponse(body)):
            result = engine()._ask_llm_compliance("PROMPT")
        self.assertEqual(result["user_value"], "Applicable")
        self.assertIn("Complied: No", result["rationale"])


if __name__ == "__main__":
    unittest.main(verbosity=2)