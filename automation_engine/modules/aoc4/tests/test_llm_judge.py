"""Standalone test-suite for ``automation_engine/modules/aoc4/llm_judge.py``.

The module is the "LLM as a judge" (an Ollama model - qwen3.5:4b on the company
server by default, llama3.2 locally) layer used by
:class:`AOC4CommonErrorEngine` for the 5 narrative common-error rows. It is
designed to be *defensive*: every failure must return ``None`` so the caller
silently falls back to the deterministic rules.

These tests use only the standard library ``unittest`` (pytest is not part of
this project's requirements) and mock ``requests.post`` so no live Ollama
server is required.

Run it::

    python automation_engine/modules/aoc4/tests/test_llm_judge.py

Set ``AOC4_LLM_LIVE_TEST=1`` to additionally hit the real configured Ollama
endpoint (skipped by default).
"""

import json
import os
import sys
import time
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

# Mirror the import strategy used by aoc4_error_checker.py so we exercise the
# same production import path (falls back to the bare module name).
try:
    from automation_engine.modules.aoc4.llm import llm_judge as judge_mod
    from automation_engine.modules.aoc4.common_error.aoc4_error_checker import AOC4CommonErrorEngine
except ImportError:  # pragma: no cover - only when run from inside aoc4/
    import automation_engine.modules.aoc4.llm.llm_judge as judge_mod
    from automation_engine.modules.aoc4.common_error.aoc4_error_checker import AOC4CommonErrorEngine

AOC4LLMJudgeEngine = judge_mod.AOC4LLMJudgeEngine

RULES_EXCEL_CANDIDATES = [
    os.path.join(AOC4_DIR, "excel", "Annual Filing common error Output.xlsx"),
    os.path.join(AOC4_DIR, "excel", "ANNFIL COMMONERROR .xlsx"),
]

# The five rows that must be routed to the LLM, keyed by their row index in the
# 'Common Error' sheet (identical in both workbooks).
EXPECTED_JUDGED_ROWS = {
    6: "shareholding_more_than_5%",
    10: "reconciliation_of_shares",
    11: "promoter_holding",
    15: "signed_by_directors_and_auditors",
    17: "seal_of_auditor",
}

# Document with NO shareholding evidence (deterministic engine -> "No").
NO_EVIDENCE_TEXT = (
    "Notes to Accounts\n"
    "Share Capital\n"
    "The company has one class of equity shares. Authorised capital is Rs. 10,00,000. "
    "Paid up capital is Rs. 5,00,000. No further disclosures were made in the schedule.\n"
)

# Document WITH shareholding evidence (deterministic engine -> "Yes").
YES_EVIDENCE_TEXT = (
    "Notes to Accounts\n"
    "Share Capital\n"
    "The schedule discloses the details of every shareholder holding of 5% or more. "
    "Mr. X holds 5.5% of the equity share capital of the company.\n"
)

SHAREHOLDING_PARTICULARS = "Whether Shareholding more than 5% is mentioned in Schedule."


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
    if isinstance(obj_or_raw, str):
        inner = obj_or_raw
    else:
        inner = json.dumps(obj_or_raw)
    return {"response": inner, "done": True}


def engine(ollama_url="http://localhost:11434", model="llama3.2", timeout=10):
    return AOC4LLMJudgeEngine(ollama_url=ollama_url, model=model, timeout=timeout)


class TestRuleRouting(unittest.TestCase):
    """name_for_rule()/is_judged_rule() must match the REAL Excel rule text."""

    def setUp(self):
        self.engine = engine()

    def _load_particulars(self):
        """Return {row_index: particulars} from the production rules workbook."""
        try:
            import pandas as pd
        except ImportError:  # pragma: no cover
            self.skipTest("pandas is not installed")

        existing = [p for p in RULES_EXCEL_CANDIDATES if os.path.exists(p)]
        if not existing:
            self.skipTest("no rules workbook found in %s" % os.path.dirname(
                RULES_EXCEL_CANDIDATES[0]))
        return existing

    def test_every_judged_rule_name_has_intent(self):
        names = AOC4LLMJudgeEngine._LLM_JUDGED_RULES_NAMES
        self.assertEqual(len(names), len(set(names)), "duplicate names in _LLM_JUDGED_RULES_NAMES")
        for name in names:
            with self.subTest(rule=name):
                self.assertIn(name, AOC4LLMJudgeEngine._INTENTS,
                              "judged rule %s has no adjudication guidance" % name)

    def test_excel_rows_route_to_expected_judged_rules(self):
        """Integration: the real workbook rows must map exactly to the 5 rules."""
        for excel_path in self._load_particulars():
            with self.subTest(workbook=os.path.basename(excel_path)):
                import pandas as pd
                df = pd.read_excel(excel_path, sheet_name="Common Error")
                routed = {}
                for idx, row in df.iterrows():
                    name = self.engine.name_for_rule(str(row.get("Particulars", "")))
                    if name:
                        routed[idx] = name
                self.assertEqual(
                    routed, EXPECTED_JUDGED_ROWS,
                    "LLM judged-rule routing drifted from the workbook: %r" % (routed,))

    def test_all_five_rules_reachable_from_real_particulars(self):
        """Each _LLM_JUDGED_RULES_NAMES entry must be reachable via name_for_rule."""
        reached = set()
        for excel_path in self._load_particulars():
            import pandas as pd
            df = pd.read_excel(excel_path, sheet_name="Common Error")
            for _, row in df.iterrows():
                name = self.engine.name_for_rule(str(row.get("Particulars", "")))
                if name:
                    reached.add(name)
        self.assertEqual(reached, set(EXPECTED_JUDGED_ROWS.values()))
        # Any name that can never be produced by name_for_rule is dead config.
        unreachable = set(AOC4LLMJudgeEngine._LLM_JUDGED_RULES_NAMES) - reached
        self.assertFalse(unreachable, "unreachable judged rules: %r" % (unreachable,))

    def test_is_judged_rule_positive(self):
        for particulars in [
            SHAREHOLDING_PARTICULARS,
            "Whether reconciliation  of shares O/S at the beginning and end of the year is given \n",
            "Whether promoter holding is disclosed as per format",
            "Check whether Notes to Accounts last page is Signed by both the directors and the Auditors.",
            "Check if the financials and audit report has the seal of the auditor/firm",
        ]:
            with self.subTest(particulars=particulars):
                self.assertTrue(self.engine.is_judged_rule(particulars))

    def test_is_judged_rule_is_case_insensitive(self):
        self.assertTrue(self.engine.is_judged_rule(SHAREHOLDING_PARTICULARS.upper()))

    def test_is_judged_rule_negative_for_non_narrative_rules(self):
        for particulars in [
            "Whether the Shareholding given in the Schedule matched with Statutory Register",
            "Whether the Authorised Capital is mentioned correctly as per MCA",
            "Check for UDIN",
            "Whether EPS & Diluted EPS is mentioned in PL",
            "(c) shortfall at the end of the year,",
            "TM to check with company if Directors were abroad during any part of the FY",
            "Share capital Notes",
            "",
            None,
        ]:
            with self.subTest(particulars=particulars):
                self.assertFalse(self.engine.is_judged_rule(particulars))


class TestJudgeGuardrails(unittest.TestCase):
    """judge() must bail out early and never touch the network unnecessarily."""

    @mock.patch.object(judge_mod.requests, "post")
    def test_non_judged_rule_returns_none_without_http(self, post):
        result = engine().judge(
            {"particulars": "Check for UDIN"}, {"full_text": YES_EVIDENCE_TEXT})
        self.assertIsNone(result)
        post.assert_not_called()

    @mock.patch.object(judge_mod.requests, "post")
    def test_missing_full_text_returns_none_without_http(self, post):
        result = engine().judge({"particulars": SHAREHOLDING_PARTICULARS}, {})
        self.assertIsNone(result)
        post.assert_not_called()

    @mock.patch.object(judge_mod.requests, "post")
    def test_blank_or_non_string_full_text_returns_none_without_http(self, post):
        for bad in ["", "   \n\t ", None, 12345, ["text"]]:
            with self.subTest(full_text=bad):
                result = engine().judge(
                    {"particulars": SHAREHOLDING_PARTICULARS}, {"full_text": bad})
                self.assertIsNone(result)
        post.assert_not_called()

    @mock.patch.object(judge_mod.requests, "post")
    def test_rule_without_particulars_returns_none_without_http(self, post):
        for rule in [{}, {"particulars": None}]:
            with self.subTest(rule=rule):
                self.assertIsNone(engine().judge(rule, {"full_text": YES_EVIDENCE_TEXT}))
        post.assert_not_called()

    def test_judge_uses_the_checkers_rule_dict_contract(self):
        """The checker passes the whole rule dict; judge() only needs 'particulars'."""
        captured = {}

        def fake_post(url, json=None, timeout=None, **kwargs):
            captured["prompt"] = json["prompt"]
            captured["url"] = url
            return _FakeResponse(ollama_body({"verdict": "Yes", "reason": "ok"}))

        with mock.patch.object(judge_mod.requests, "post", side_effect=fake_post):
            result = engine().judge(
                {"id": "RULE_6", "particulars": SHAREHOLDING_PARTICULARS,
                 "source": "Share capital Notes"},
                {"full_text": YES_EVIDENCE_TEXT})

        self.assertEqual(result["user_value"], "Yes")
        self.assertIn(SHAREHOLDING_PARTICULARS, captured["prompt"])
        self.assertTrue(captured["url"].endswith("/api/generate"))


class TestAskLLM(unittest.TestCase):
    """_ask_llm() verdict mapping and failure handling (HTTP mocked)."""

    def _call(self, body=None, side_effect=None, status_code=200, raw=None):
        payload = {"response": raw, "done": True} if raw is not None else body
        with mock.patch.object(judge_mod.requests, "post") as post:
            if side_effect is not None:
                post.side_effect = side_effect
            else:
                post.return_value = _FakeResponse(payload, status_code=status_code)
            return engine()._ask_llm("PROMPT"), post

    def test_yes_verdict(self):
        result, _ = self._call(ollama_body({"verdict": "Yes", "reason": "Seal present."}))
        self.assertEqual(result["user_value"], "Yes")
        self.assertEqual(result["reason"], "Seal present.")
        self.assertEqual(result["_judged_by"], "llm")

    def test_no_verdict(self):
        result, _ = self._call(ollama_body({"verdict": "No", "reason": "No schedule row."}))
        self.assertEqual(result["user_value"], "No")
        self.assertEqual(result["_judged_by"], "llm")

    def test_verdict_is_case_and_whitespace_insensitive(self):
        for raw_verdict, expected in [("  yes  ", "Yes"), ("NO", "No"), (" Yes\n", "Yes")]:
            with self.subTest(verdict=raw_verdict):
                result, _ = self._call(ollama_body({"verdict": raw_verdict, "reason": "r"}))
                self.assertEqual(result["user_value"], expected)

    def test_missing_reason_gets_default(self):
        result, _ = self._call(ollama_body({"verdict": "Yes"}))
        # The default must name the configured model (llama3.2 here, qwen3.5:4b
        # in production), never a hard-coded model name.
        self.assertEqual(result["reason"], "Judged by AOC4 LLM (llama3.2).")

    def test_cannot_determine_falls_back_to_deterministic(self):
        result, _ = self._call(ollama_body({"verdict": "Cannot determine", "reason": "unclear"}))
        self.assertIsNone(result)

    def test_unknown_verdict_falls_back(self):
        for bad in ["maybe", "", "true", None]:
            with self.subTest(verdict=bad):
                result, _ = self._call(ollama_body({"verdict": bad, "reason": "x"}))
                self.assertIsNone(result)

    def test_json_embedded_in_prose_is_parsed(self):
        result, _ = self._call(ollama_body(
            'Sure, here is my verdict:\n{"verdict": "Yes", "reason": "ok"}\nHope that helps.'))
        self.assertEqual(result["user_value"], "Yes")

    def test_non_json_response_falls_back(self):
        result, _ = self._call(ollama_body("I am not able to answer in JSON."))
        self.assertIsNone(result)

    def test_empty_response_falls_back(self):
        for empty in ["", "   "]:
            with self.subTest(response=empty):
                result, _ = self._call(ollama_body(empty))
                self.assertIsNone(result)

    def test_non_object_json_response_falls_back(self):
        """A model that answers with a JSON array/string must not crash the run."""
        for raw in ["[1, 2, 3]", '"yes"', "null", "123"]:
            with self.subTest(raw=raw):
                result, _ = self._call(raw=raw)
                self.assertIsNone(result)


    def test_http_error_falls_back(self):
        for status in [400, 404, 500, 503]:
            with self.subTest(status=status):
                result, _ = self._call(ollama_body({"verdict": "Yes"}), status_code=status)
                self.assertIsNone(result)

    def test_connection_and_timeout_errors_fall_back(self):
        for exc in [requests.exceptions.ConnectionError("refused"),
                    requests.exceptions.ConnectTimeout("timed out"),
                    requests.exceptions.ReadTimeout("timed out"),
                    requests.exceptions.HTTPError("boom")]:
            with self.subTest(exc=type(exc).__name__):
                result, _ = self._call(side_effect=exc)
                self.assertIsNone(result)

    def test_body_without_response_key_falls_back(self):
        result, _ = self._call({"done": True})
        self.assertIsNone(result)

    def test_body_that_is_not_json_falls_back(self):
        result, _ = self._call(body=None)  # /api/generate answered with non-JSON
        self.assertIsNone(result)

    def test_request_payload_contract(self):
        _, post = self._call(ollama_body({"verdict": "Yes", "reason": "r"}))
        kwargs = post.call_args.kwargs
        self.assertEqual(post.call_args.args[0], "http://localhost:11434/api/generate")
        self.assertEqual(kwargs["json"]["model"], "llama3.2")
        self.assertFalse(kwargs["json"]["stream"])
        self.assertEqual(kwargs["json"]["format"], "json")
        self.assertEqual(kwargs["json"]["options"]["temperature"], 0.0)
        self.assertEqual(kwargs["json"]["options"]["num_ctx"], 8192)
        self.assertEqual(kwargs["timeout"], 10)
        self.assertEqual(kwargs["json"]["prompt"], "PROMPT")


class TestParseJson(unittest.TestCase):
    """_parse_json() must never raise, whatever the model returns."""

    def test_plain_object(self):
        self.assertEqual(judge_mod.AOC4LLMJudgeEngine._parse_json('{"verdict": "Yes"}'),
                         {"verdict": "Yes"})

    def test_object_wrapped_in_markdown_fence(self):
        raw = '```json\n{"verdict": "No", "reason": "missing"}\n```'
        self.assertEqual(judge_mod.AOC4LLMJudgeEngine._parse_json(raw),
                         {"verdict": "No", "reason": "missing"})

    def test_returns_none_on_garbage_and_empty(self):
        for raw in ["", "   ", None, "no json here", "{broken json", "{'single': 'quotes'}"]:
            with self.subTest(raw=raw):
                self.assertIsNone(judge_mod.AOC4LLMJudgeEngine._parse_json(raw))


class TestPromptAndWindow(unittest.TestCase):
    """The prompt must contain the extract and must not be corrupted."""

    def test_prompt_contains_every_required_block(self):
        prompt = engine()._build_prompt(
            SHAREHOLDING_PARTICULARS,
            judge_mod.AOC4LLMJudgeEngine._INTENTS["shareholding_more_than_5%"],
            "WINDOW-MARKER")
        self.assertIn("CHECKPOINT:", prompt)
        self.assertIn(SHAREHOLDING_PARTICULARS, prompt)
        self.assertIn("ADJUDICATION GUIDANCE:", prompt)
        self.assertIn("RELEVANT DOCUMENT EXTRACT:", prompt)
        self.assertIn("WINDOW-MARKER", prompt)
        self.assertIn('"verdict"', prompt)
        self.assertIn("Cannot determine", prompt)

    def test_intent_text_has_no_stray_double_percent_escapes(self):
        """'5%%' would leak a literal double percent into the prompt."""
        for name, intent in judge_mod.AOC4LLMJudgeEngine._INTENTS.items():
            with self.subTest(rule=name):
                self.assertNotIn("%%", intent, "intent for %s contains a stray '%%'" % name)

    def test_short_document_is_passed_through_unchanged(self):
        self.assertEqual(engine()._relevant_window(YES_EVIDENCE_TEXT), YES_EVIDENCE_TEXT)

    def test_long_document_is_trimmed_and_keeps_keyword_context(self):
        filler = "lorem ipsum dolor sit amet " * 4000  # ~108k chars
        text = filler + "\nSEAL_KEYWORD: For XYZ Chartered Accountants, Partner, FRN 1234\n" + filler
        window = engine()._relevant_window(text)
        self.assertLessEqual(len(window), 6000)
        self.assertIn("SEAL_KEYWORD", window)
        self.assertIn("FRN", window)

    def test_long_document_without_keywords_returns_prefix(self):
        text = "x" * 20000
        self.assertEqual(engine()._relevant_window(text), text[:6000])

    def test_keyword_at_start_and_end_does_not_crash(self):
        text = "auditor" + ("y" * 20000) + "promoter"
        window = engine()._relevant_window(text)
        self.assertTrue(window.startswith("auditor"))
        self.assertLessEqual(len(window), 6000)

    @staticmethod
    def _late_evidence_document(evidence):
        """Mimics the real KSPL file: 8 early keyword clusters, evidence at the end."""
        noise = ("auditor chartered accountant frn signed" + ("x" * 3400)) * 8
        return noise + ("z" * 3000) + evidence

    def test_rule_aware_window_keeps_late_evidence(self):
        """Regression (KSPL FY2025-26, 184k-char input).

        The shareholding/promoter schedules sat ~65k chars into the document.
        The old code concatenated every keyword chunk and truncated from the
        front, so that schedule was never shown to the model and it answered
        'No' for a document that clearly discloses four >5% shareholders.
        """
        evidence = ("(c) Details of shares held by shareholders holding more than 5% of the "
                    "aggregate shares in the Company | Mr.Veeraraghavan | 43.68% "
                    "| Mr. Kamesh Gupta | 6.10%")
        text = self._late_evidence_document(evidence)

        generic = engine()._relevant_window(text)  # rule-unaware path
        anchored = engine()._relevant_window(text, rule_name="shareholding_more_than_5%")

        self.assertNotIn("43.68%", generic,
                         "test document no longer reproduces the starvation bug")
        self.assertIn("43.68%", anchored)
        self.assertLessEqual(len(anchored), 6000)

    def test_anchors_defined_for_every_judged_rule(self):
        for name in AOC4LLMJudgeEngine._LLM_JUDGED_RULES_NAMES:
            with self.subTest(rule=name):
                anchors = AOC4LLMJudgeEngine._ANCHOR_KEYWORDS.get(name)
                self.assertTrue(anchors, "no anchor keywords configured for %s" % name)
                for anchor in anchors:
                    self.assertEqual(anchor, anchor.lower(),
                                     "anchor %r for %s must be lowercase" % (anchor, name))

    def test_judge_sends_the_rule_aware_window(self):
        evidence = ("(c) Details of shares held by shareholders holding more than 5% | "
                    "Mr.Veeraraghavan | 43.68%")
        text = self._late_evidence_document(evidence)

        with mock.patch.object(judge_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"verdict": "Yes", "reason": "r"}))) as post:
            engine().judge({"particulars": SHAREHOLDING_PARTICULARS}, {"full_text": text})

        prompt = post.call_args.kwargs["json"]["prompt"]
        self.assertIn("43.68%", prompt)


class TestConfiguration(unittest.TestCase):
    """Constructor arguments and environment overrides."""

    def test_defaults(self):
        inst = AOC4LLMJudgeEngine()
        self.assertEqual(inst.ollama_url, AOC4LLMJudgeEngine.DEFAULT_URL)
        self.assertEqual(inst.model, AOC4LLMJudgeEngine.DEFAULT_MODEL)
        self.assertEqual(inst.timeout, AOC4LLMJudgeEngine.DEFAULT_TIMEOUT)

    def test_environment_overrides(self):
        env = {"AOC4_OLLAMA_URL": "http://10.0.0.9:11434", "AOC4_LLM_MODEL": "llama3.1"}
        with mock.patch.dict(os.environ, env, clear=False):
            inst = AOC4LLMJudgeEngine()
            self.assertEqual(inst.ollama_url, "http://10.0.0.9:11434")
            self.assertEqual(inst.model, "llama3.1")

    def test_constructor_arguments_win_over_environment(self):
        with mock.patch.dict(os.environ, {"AOC4_OLLAMA_URL": "http://ignored:1"},
                             clear=False):
            inst = engine(ollama_url="http://explicit:11434", model="llama3.3", timeout=7)
            self.assertEqual(inst.ollama_url, "http://explicit:11434")
            self.assertEqual(inst.model, "llama3.3")
            self.assertEqual(inst.timeout, 7)


class TestModelPortability(unittest.TestCase):
    """Hardening needed to run on a different model/server (e.g. qwen3.5)."""

    def test_shipped_defaults_target_the_company_server(self):
        """The port is only complete if a bare engine() hits qwen3.5:4b.

        The company Ollama server does NOT have llama3.2 installed, so a
        llama3.2 default would make every call fail and silently fall back to
        the deterministic engine.
        """
        # Guard the deployment env vars so this asserts the shipped defaults.
        with mock.patch.dict(os.environ, {"AOC4_OLLAMA_URL": "",
                                          "AOC4_LLM_MODEL": ""}, clear=False):
            inst = AOC4LLMJudgeEngine()
        self.assertEqual(inst.ollama_url, "http://192.168.112.2:11434")
        self.assertEqual(inst.model, "qwen3.5:4b")
        self.assertEqual(inst.timeout, 180)

    def test_shipped_defaults_are_inherited_by_the_compliance_judge(self):
        from automation_engine.modules.aoc4.compliance.compliance_llm_judge import (
            AOC4ComplianceLLMJudgeEngine,
        )
        self.assertEqual(AOC4ComplianceLLMJudgeEngine.DEFAULT_URL,
                         AOC4LLMJudgeEngine.DEFAULT_URL)
        self.assertEqual(AOC4ComplianceLLMJudgeEngine.DEFAULT_MODEL,
                         "qwen3.5:4b")
        self.assertEqual(AOC4ComplianceLLMJudgeEngine.DEFAULT_TIMEOUT, 180)

    def test_options_default_to_the_shipped_values(self):
        opts = engine()._request_options()
        self.assertEqual(opts, {"temperature": 0.0, "num_ctx": 8192})

    def test_options_are_overridable_by_environment(self):
        env = {"AOC4_LLM_NUM_CTX": "32768", "AOC4_LLM_TEMPERATURE": "0.3"}
        with mock.patch.dict(os.environ, env, clear=False):
            opts = engine()._request_options()
        self.assertEqual(opts, {"temperature": 0.3, "num_ctx": 32768})

    def test_invalid_option_values_fall_back_to_defaults(self):
        env = {"AOC4_LLM_NUM_CTX": "not-a-number", "AOC4_LLM_TEMPERATURE": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            opts = engine()._request_options()
        self.assertEqual(opts, {"temperature": 0.0, "num_ctx": 8192})

    def test_api_key_header_only_when_configured(self):
        self.assertEqual(engine()._request_headers(), {})
        with mock.patch.dict(os.environ, {"AOC4_LLM_API_KEY": "s3cret"}, clear=False):
            self.assertEqual(engine()._request_headers(),
                             {"Authorization": "Bearer s3cret"})

    def test_think_flag_is_omitted_by_default_and_not_sent_to_the_server(self):
        self.assertNotIn("think", engine()._request_payload("P"))
        with mock.patch.dict(os.environ, {"AOC4_LLM_THINK": "false"}, clear=False):
            self.assertIs(engine()._request_payload("P")["think"], False)
        with mock.patch.dict(os.environ, {"AOC4_LLM_THINK": "true"}, clear=False):
            self.assertIs(engine()._request_payload("P")["think"], True)

    def test_configured_options_and_headers_reach_the_request(self):
        env = {"AOC4_LLM_NUM_CTX": "16384", "AOC4_LLM_API_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.object(judge_mod.requests, "post",
                                   return_value=_FakeResponse(ollama_body(
                                       {"verdict": "Yes", "reason": "r"}))) as post:
                engine()._ask_llm("PROMPT")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["options"]["num_ctx"], 16384)
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer k"})

    def test_thinking_blocks_are_stripped_before_parsing(self):
        raw = ('<think>Let me check the schedule... {"verdict": "No"} ...</think>'
               '{"verdict": "Yes", "reason": "schedule shows 12.5%"}')
        self.assertEqual(AOC4LLMJudgeEngine._parse_json(raw),
                         {"verdict": "Yes", "reason": "schedule shows 12.5%"})
        self.assertEqual(AOC4LLMJudgeEngine._parse_json(
            "Thinking...\n\n{\"verdict\": \"No\"}"), {"verdict": "No"})

    def test_complete_thinking_block_is_stripped_case_insensitively(self):
        raw = ('<THINK>candidate {"verdict": "maybe"} is wrong</THINK>'
               '{"verdict": "No", "reason": "no evidence"}')
        self.assertEqual(AOC4LLMJudgeEngine._parse_json(raw),
                         {"verdict": "No", "reason": "no evidence"})

    def test_unterminated_thinking_block_never_yields_a_verdict(self):
        """A JSON object inside truncated reasoning must not become the answer."""
        raw = '<THINK>maybe {"verdict": "Yes"} fits, but the table shows otherwise...'
        self.assertIsNone(AOC4LLMJudgeEngine._parse_json(raw))
        with mock.patch.object(judge_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(raw))):
            self.assertIsNone(engine()._ask_llm("PROMPT"))

    def test_answer_in_thinking_is_read_when_response_is_empty(self):
        """Verified on qwen3.5:4b: response='' and the JSON sits in `thinking`."""
        body = {"response": "", "thinking": '{"verdict": "No", "reason": "no policy found"}',
                "done": True}
        with mock.patch.object(judge_mod.requests, "post",
                               return_value=_FakeResponse(body)):
            result = engine()._ask_llm("PROMPT")
        self.assertEqual(result["user_value"], "No")
        self.assertEqual(result["reason"], "no policy found")

    def test_response_wins_over_thinking_when_both_are_present(self):
        body = {"response": '{"verdict": "Yes", "reason": "real answer"}',
                "thinking": '{"verdict": "No", "reason": "draft"}', "done": True}
        self.assertEqual(AOC4LLMJudgeEngine._extract_model_text(body),
                         '{"verdict": "Yes", "reason": "real answer"}')

    def test_extract_model_text_handles_odd_bodies(self):
        cases = [{}, {"response": None, "thinking": None}, None, "not-a-dict", 42,
                 {"thinking": "  "}]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(AOC4LLMJudgeEngine._extract_model_text(body), "")

    def test_whitespace_only_response_falls_through_to_thinking(self):
        body = {"response": "   \n ", "thinking": '{"verdict": "Yes"}'}
        self.assertEqual(AOC4LLMJudgeEngine._extract_model_text(body),
                         '{"verdict": "Yes"}')

    def test_thinking_only_response_yields_no_verdict(self):
        result, _ = TestAskLLM()._call(raw="<think>still reasoning</think>")
        self.assertIsNone(result)

    def test_thinking_block_with_braces_does_not_break_parsing(self):
        raw = ('<think>candidate {"verdict": "maybe"} is wrong</think>'
               '{"verdict": "No", "reason": "no evidence"}')
        self.assertEqual(AOC4LLMJudgeEngine._parse_json(raw),
                         {"verdict": "No", "reason": "no evidence"})


class TestHybridIntegration(unittest.TestCase):
    """End-to-end: the LLM verdict must override the deterministic result, and
    the deterministic result must survive whenever the LLM is unavailable."""

    @classmethod
    def setUpClass(cls):
        cls.excel_path = next((p for p in RULES_EXCEL_CANDIDATES if os.path.exists(p)), None)
        if not cls.excel_path:
            raise unittest.SkipTest("rules workbook not found")

    def _checker(self, judge):
        return AOC4CommonErrorEngine(self.excel_path, llm_judge=judge)

    @staticmethod
    def _flag_for(flags, particulars):
        for flag in flags:
            if flag["particulars"] == particulars:
                return flag
        raise AssertionError("rule %r was not evaluated" % particulars)

    def _deterministic_flag(self, text, particulars):
        checker = AOC4CommonErrorEngine(self.excel_path, enable_llm_judge=False)
        return self._flag_for(checker.execute({"full_text": text}), particulars)

    def test_engine_wiring_instantiates_the_judge_by_default(self):
        checker = AOC4CommonErrorEngine(self.excel_path)
        self.assertIsInstance(checker.llm_judge, AOC4LLMJudgeEngine)
        self.assertIsNone(AOC4CommonErrorEngine(
            self.excel_path, enable_llm_judge=False).llm_judge)

    def test_injected_judge_is_used_verbatim(self):
        sentinel = AOC4LLMJudgeEngine(ollama_url="http://sentinel:11434")
        checker = AOC4CommonErrorEngine(self.excel_path, llm_judge=sentinel)
        self.assertIs(checker.llm_judge, sentinel)

    def test_llm_yes_overrides_deterministic_no(self):
        deterministic = self._deterministic_flag(NO_EVIDENCE_TEXT, SHAREHOLDING_PARTICULARS)
        self.assertEqual(deterministic["user_value"], "No")  # precondition

        judge = engine()
        with mock.patch.object(judge_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"verdict": "Yes",
                                    "reason": "Schedule discloses a 12.5% holder."}))):
            flags = self._checker(judge).execute({"full_text": NO_EVIDENCE_TEXT})

        flag = self._flag_for(flags, SHAREHOLDING_PARTICULARS)
        self.assertEqual(flag["user_value"], "Yes")
        self.assertEqual(flag["status"], "Passed")
        self.assertEqual(flag["reason"], "Schedule discloses a 12.5% holder.")

    def test_llm_no_overrides_deterministic_yes(self):
        deterministic = self._deterministic_flag(YES_EVIDENCE_TEXT, SHAREHOLDING_PARTICULARS)
        self.assertEqual(deterministic["user_value"], "Yes")  # precondition

        judge = engine()
        with mock.patch.object(judge_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"verdict": "No",
                                    "reason": "Only an aggregate figure is shown."}))):
            flags = self._checker(judge).execute({"full_text": YES_EVIDENCE_TEXT})

        flag = self._flag_for(flags, SHAREHOLDING_PARTICULARS)
        self.assertEqual(flag["user_value"], "No")
        self.assertEqual(flag["status"], "Failed")
        # The checker rewraps a failed reason as "Why it is No: <llm reason>".
        self.assertIn("Only an aggregate figure is shown.", flag["reason"])

    def test_deterministic_result_survives_when_llm_is_down(self):
        judge = engine()
        with mock.patch.object(judge_mod.requests, "post",
                               side_effect=requests.exceptions.ConnectionError("refused")):
            flags = self._checker(judge).execute({"full_text": NO_EVIDENCE_TEXT})

        self.assertEqual(self._flag_for(flags, SHAREHOLDING_PARTICULARS),
                         self._deterministic_flag(NO_EVIDENCE_TEXT, SHAREHOLDING_PARTICULARS))

    def test_deterministic_result_survives_undecided_llm(self):
        judge = engine()
        with mock.patch.object(judge_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"verdict": "Cannot determine", "reason": "blurry scan"}))):
            flags = self._checker(judge).execute({"full_text": YES_EVIDENCE_TEXT})

        self.assertEqual(self._flag_for(flags, SHAREHOLDING_PARTICULARS),
                         self._deterministic_flag(YES_EVIDENCE_TEXT, SHAREHOLDING_PARTICULARS))

    def test_only_judged_rules_reach_the_llm(self):
        judge = engine()
        with mock.patch.object(judge_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"verdict": "Yes", "reason": "r"}))) as post:
            checker = self._checker(judge)
            flags = checker.execute({"full_text": YES_EVIDENCE_TEXT})

        judged = [r for r in checker.rules if judge.is_judged_rule(r["particulars"])]
        self.assertEqual(len(judged), 5,
                         "expected 5 judged rules, got %r" % ([r["particulars"] for r in judged],))
        self.assertEqual(post.call_count, len(judged),
                         "HTTP called %d times for %d judged rules" % (post.call_count,
                                                                      len(judged)))
        self.assertEqual(len(flags), len(checker.rules))

    def test_non_judged_rules_are_never_modified_by_the_llm(self):
        judge = engine()
        with mock.patch.object(judge_mod.requests, "post",
                               return_value=_FakeResponse(ollama_body(
                                   {"verdict": "Yes", "reason": "r"}))):
            flags = self._checker(judge).execute({"full_text": YES_EVIDENCE_TEXT})

        det = {f["particulars"]: f for f in AOC4CommonErrorEngine(
            self.excel_path, enable_llm_judge=False).execute({"full_text": YES_EVIDENCE_TEXT})}
        for flag in flags:
            if not judge.is_judged_rule(flag["particulars"]):
                self.assertEqual(flag["user_value"], det[flag["particulars"]]["user_value"],
                                 "non-judged rule %r was altered" % flag["particulars"])

    def test_blank_document_still_produces_flags(self):
        """No extract at all must not crash the judge-driven run."""
        flags = self._checker(engine()).execute({"full_text": ""})
        self.assertEqual(len(flags), len(self._checker(engine()).rules))
        self.assertEqual(self._flag_for(flags, SHAREHOLDING_PARTICULARS)["user_value"], "No")


@unittest.skipUnless(os.environ.get("AOC4_LLM_LIVE_TEST") == "1",
                     "set AOC4_LLM_LIVE_TEST=1 to exercise the real Ollama endpoint")
class TestLiveOllama(unittest.TestCase):
    """Opt-in check against the configured Ollama server (needs the real model)."""

    def test_live_endpoint_and_verdict(self):
        inst = AOC4LLMJudgeEngine(timeout=30)
        try:
            resp = requests.get("%s/api/tags" % inst.ollama_url, timeout=5)
            resp.raise_for_status()
        except Exception as exc:
            self.skipTest("Ollama not reachable at %s (%s)" % (inst.ollama_url, exc))

        result = inst.judge({"particulars": SHAREHOLDING_PARTICULARS},
                            {"full_text": YES_EVIDENCE_TEXT})
        self.assertIsNotNone(result, "live model returned no usable verdict")
        self.assertIn(result["user_value"], ("Yes", "No"))


def report_endpoint_status():
    """Informational (not a test): is the configured Ollama server reachable?"""
    inst = AOC4LLMJudgeEngine()
    try:
        resp = requests.get("%s/api/tags" % inst.ollama_url, timeout=3)
        resp.raise_for_status()
        models = [m.get("name") for m in resp.json().get("models", [])]
        print("[live] Ollama REACHABLE at %s | model=%s | installed=%s"
              % (inst.ollama_url, inst.model, models or "none reported"))
    except Exception as exc:
        print("[live] Ollama UNREACHABLE at %s (%s: %s) -> judge() falls back to the "
              "deterministic result, but only after up to %ss per judged rule."
              % (inst.ollama_url, type(exc).__name__, exc, inst.timeout))


if __name__ == "__main__":
    report_endpoint_status()
    unittest.main(verbosity=2)

