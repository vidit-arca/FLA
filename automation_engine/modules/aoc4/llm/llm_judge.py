import json
import os
import re

import requests

from automation_engine.modules.aoc4.logger import get_aoc4_logger

logger = get_aoc4_logger("AOC4_LLMJudge")


class AOC4LLMJudgeEngine:
    """LLM-as-a-judge for targeted AOC-4 common-error narrative rules.

    Only the rules listed in _LLM_JUDGED_RULES_NAMES are adjudicated by the LLM
    (Qwen 3.5 4B on the company Ollama server; override with AOC4_LLM_MODEL for
    e.g. llama3.2 on a local Ollama). Every call is defensive: any failure
    returns None so the caller falls back to the deterministic engine (hybrid
    approach).
    """

    DEFAULT_URL = "http://192.168.112.2:11434"
    #: The company server ships qwen3.5:4b - NOT llama3.2, so this default is
    #: what makes a bare AOC4LLMJudgeEngine() work against DEFAULT_URL.
    DEFAULT_MODEL = "qwen3.5:4b"
    #: Measured on qwen3.5:4b (1-6s per call, but ~78s spikes while the shared
    #: server loads another model), so 90s would abort live answers.
    DEFAULT_TIMEOUT = 180
    #: Context window sent to the model. Override with AOC4_LLM_NUM_CTX when
    #: switching to a long-context model (e.g. qwen3.5 supports 262k).
    DEFAULT_NUM_CTX = 8192
    DEFAULT_TEMPERATURE = 0.0

    _LLM_JUDGED_RULES_NAMES = [
        "shareholding_more_than_5%",
        "reconciliation_of_shares",
        "promoter_holding",
        "signed_by_directors_and_auditors",
        "seal_of_auditor",
    ]

    # Generic locators used to build the extract that is shown to the model.
    _GENERIC_KEYWORDS = (
        "shareholding", "promoter", "reconciliation", "signed", "signature", "seal",
        "stamp", "auditor", "chartered accountant", "partner", "membership", "frn",
    )

    # Rule-specific locators: the sections that actually carry the evidence for a
    # checkpoint. They are ranked first when assembling the extract, because a
    # long document can otherwise push the relevant schedule past the extract
    # budget (the merged selection used to be truncated from the front, so
    # evidence appearing late in the document was never shown to the model).
    _ANCHOR_KEYWORDS = {
        "shareholding_more_than_5%": (
            "holding more than 5", "% of holding", "shareholder", "shareholding",
        ),
        "reconciliation_of_shares": (
            "reconciliation of number of shares", "reconciliation of shares",
            "beginning of the year", "end of the year", "reconciliation",
        ),
        "promoter_holding": (
            "promoter", "% of total shares", "change in holding",
        ),
        "signed_by_directors_and_auditors": (
            "as per our report of even date", "for and on behalf", "signature",
            "signed", "director", "chartered accountants", "proprietor",
            "membership",
        ),
        "seal_of_auditor": (
            "seal", "stamp", "chartered accountants", "frn", "membership", "auditor",
        ),
    }

    _INTENTS = {
        "shareholding_more_than_5%": (
            "Check whether the Share Capital Notes / Schedule disclose that a shareholder "
            "holds more than 5% of the equity share capital. The schedule is usually an OCR'd "
            "markdown table: read its ROWS literally and do not discard a row because a column "
            "header was mangled by OCR. PASS if there is an explicit statement or a schedule row "
            "naming a shareholder with a holding STRICTLY ABOVE 5% (e.g. '5.01 %', '6%', "
            "'12.5%'). A bare mention of '5%' with no shareholder exceeding it, or no "
            "shareholding schedule at all, is a FAIL."
        ),
        "reconciliation_of_shares": (
            "Check whether the financial statements give a reconciliation of the number of shares "
            "outstanding at the beginning and end of the year (e.g. opening shares, allotments, "
            "buy-backs/cancellations and closing shares, explicitly tied to the reconciliation of "
            "equity shares O/S). PASS if such an opening/closing share reconciliation is given even "
            "in a compact form. FAIL if only a share capital total/face-value ledger is shown with no "
            "beginning-versus-end reconciliation."
        ),
        "promoter_holding": (
            "Check whether promoter holding is disclosed in the prescribed schedule format: a "
            "promoter-wise table (name of promoters / promoter group, shares held at beginning, "
            "shares held at end, % holding, and change during the year). The table is usually an "
            "OCR'd markdown table: read its ROWS literally even if a header is mangled. PASS if "
            "promoter-wise shareholding with percentages is disclosed. FAIL if only a single "
            "aggregate 'promoter holding' figure is present without the schedule, or no promoter "
            "disclosure at all."
        ),
        "signed_by_directors_and_auditors": (
            "Find (a) an auditor signature block - a firm name with 'Chartered Accountants' and "
            "usually 'FRN' or 'Membership No.'/'M. No.' - and (b) a director signature block - a "
            "person designated 'Director', 'Managing Director', 'MD & CEO' or 'Chairman', usually "
            "with a DIN. OCR may have split these blocks across lines and they may sit next to the "
            "audit report rather than inside the notes. If both (a) and (b) can be found in the "
            "extract, answer Yes; if only one or neither is found, answer No."
        ),
        "seal_of_auditor": (
            "Check whether the financials and audit report bear the seal/stamp of the auditor or the "
            "audit firm. Evidence: explicit words 'seal' or 'stamp' near auditor details, or an "
            "embedded image of a firm's round seal/stamp near the auditor signature block (images "
            "appear in markdown text as ![..](..) placeholders near 'Chartered Accountants', "
            "'Partner', 'Membership No.', 'FRN'). PASS if text or image evidence of the auditor's "
            "seal/stamp exists. FAIL if there is no seal/stamp text and no image near the auditor "
            "signature."
        ),
    }

    def __init__(self, ollama_url=None, model=None, timeout=None):
        self.ollama_url = (
            ollama_url
            or os.environ.get("AOC4_OLLAMA_URL")
            or self.DEFAULT_URL
        )
        self.model = model or os.environ.get("AOC4_LLM_MODEL") or self.DEFAULT_MODEL
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        #: Optional "think" flag. Reasoning models (e.g. qwen3.5) can otherwise
        #: spend the whole context on a thinking block before the JSON answer.
        #: Unset by default so older servers see no new field.
        self.think = os.environ.get("AOC4_LLM_THINK")

    # ------------------------------------------------------------------ request

    def _request_options(self):
        """Sampling/context options, overridable per deployment (env)."""
        try:
            num_ctx = int(os.environ.get("AOC4_LLM_NUM_CTX") or self.DEFAULT_NUM_CTX)
        except (TypeError, ValueError):
            num_ctx = self.DEFAULT_NUM_CTX
        try:
            temperature = float(os.environ.get("AOC4_LLM_TEMPERATURE")
                                or self.DEFAULT_TEMPERATURE)
        except (TypeError, ValueError):
            temperature = self.DEFAULT_TEMPERATURE
        return {"temperature": temperature, "num_ctx": num_ctx}

    @staticmethod
    def _extract_model_text(body):
        """Return the model's answer text from an Ollama ``/api/generate`` body.

        Reasoning models (verified with ``qwen3.5:4b``) return an **empty**
        ``response`` and put the whole answer in ``thinking`` while thinking mode
        is on. Reading only ``response`` would make every row silently fall back
        to the deterministic engine, so the thinking text is used as a fallback.
        """
        if not isinstance(body, dict):
            return ""
        response = str(body.get("response") or "")
        if response.strip():
            return response
        thinking = str(body.get("thinking") or "")
        # Contract: "" always means "the model produced no answer".
        return thinking if thinking.strip() else ""

    def _request_headers(self):
        """Auth header, when the deployment sits behind an authenticated gateway."""
        api_key = os.environ.get("AOC4_LLM_API_KEY")
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def _request_payload(self, prompt):
        """The /api/generate body shared by every judge in this module."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": self._request_options(),
        }
        if self.think is not None:
            payload["think"] = str(self.think).strip().lower() in ("1", "true", "yes", "on")
        return payload

    def is_judged_rule(self, particulars):
        p = str(particulars).lower()
        return self.name_for_rule(particulars) is not None

    def name_for_rule(self, particulars):
        p = str(particulars).lower()
        if "shareholding more than 5%" in p:
            return "shareholding_more_than_5%"
        if "reconciliation" in p and "shares" in p:
            return "reconciliation_of_shares"
        if "promoter holding" in p:
            return "promoter_holding"
        if "signed by both" in p:
            return "signed_by_directors_and_auditors"
        if "seal of the auditor" in p:
            return "seal_of_auditor"
        return None

    def judge(self, rule: dict, input_data: dict):
        """Judge a targeted rule with the configured Ollama model.

        Returns {"user_value": "Yes"/"No", "reason": ...} on a usable verdict,
        otherwise None so the caller keeps the deterministic result.
        """
        rule_name = self.name_for_rule(rule.get("particulars", ""))
        if not rule_name:
            return None

        full_text = input_data.get("full_text", "")
        if not isinstance(full_text, str) or not full_text.strip():
            return None

        intent = self._INTENTS.get(rule_name)
        if not intent:
            return None

        window = self._relevant_window(full_text, rule_name=rule_name)
        prompt = self._build_prompt(
            strat=rule.get("particulars", ""),
            intent=intent,
            window=window,
        )
        verdict = self._ask_llm(prompt)
        logger.info(
            "  judge | rule=%s | window_chars=%d | model=%s | outcome=%s",
            rule_name, len(window), self.model,
            verdict.get("user_value") if isinstance(verdict, dict)
            else "no verdict -> keep deterministic",
        )
        return verdict

    def _relevant_window(self, full_text, rule_name=None, max_chars=6000, window=1400):
        """Extract the most relevant slice(s) of the document for judgement.

        The rule's own evidence sections (chunks containing an
        ``_ANCHOR_KEYWORDS`` entry) are collected first and are emitted first, so
        they can never be trimmed away; the remaining budget is shared
        proportionally among the other keyword chunks for context. Front
        truncating a merged selection would hide evidence that appears late in
        long documents.
        """
        if len(full_text) <= max_chars:
            return full_text

        low = full_text.lower()
        anchors = tuple(a for a in self._ANCHOR_KEYWORDS.get(rule_name, ()) if a in low)
        keywords = list(anchors) + [k for k in self._GENERIC_KEYWORDS if k not in anchors]

        spans = []
        for kw in keywords:
            for m in re.finditer(re.escape(kw), low):
                spans.append(m.span())
        if not spans:
            return full_text[:max_chars]

        chunks = []
        for s, e in sorted(spans):
            start = max(0, s - window)
            end = min(len(full_text), e + window)
            if chunks and start <= chunks[-1][1]:
                chunks[-1] = (chunks[-1][0], max(chunks[-1][1], end))
            else:
                chunks.append((start, end))

        def _anchor_hits(chunk):
            s, e = chunk
            return [h for h in (low.find(anchor, s, e) for anchor in anchors) if h >= 0]

        anchor_chunks = [c for c in chunks if _anchor_hits(c)]
        # Most anchor hits first: the section that actually answers the checkpoint.
        anchor_chunks.sort(key=lambda c: (-len(_anchor_hits(c)), c[0]))
        context_chunks = [c for c in chunks if not _anchor_hits(c)]

        separator = "\n[...]\n"
        pieces = []

        # Pass 1 - the evidence itself, cropped around the anchor keyword.
        anchor_budget = max_chars if not context_chunks else int(max_chars * 0.75)
        for index, (s, e) in enumerate(anchor_chunks):
            if anchor_budget <= 0:
                break
            share = min(anchor_budget, max(1500, anchor_budget // (len(anchor_chunks) - index)))
            start = max(s, min(_anchor_hits((s, e))) - 200)
            piece = full_text[start:e][:share]
            pieces.append(piece)
            anchor_budget -= len(piece) + len(separator)

        # Pass 2 - surrounding context, never overshooting the total budget.
        budget = max_chars - sum(len(p) + len(separator) for p in pieces)
        for index, (s, e) in enumerate(context_chunks):
            if budget <= 0:
                break
            share = budget // (len(context_chunks) - index)
            if share <= 0:
                break
            piece = full_text[s:e][:share]
            pieces.append(piece)
            budget -= len(piece) + len(separator)

        return separator.join(pieces)[:max_chars]

    def _build_prompt(self, strat, intent, window):
        return (
            "You are a strict statutory-audit judge for an Indian Companies Act AOC-4 "
            "annual-filing review. Adjudicate ONE compliance checkpoint using ONLY the "
            "extract below. Do not speculate and do not rely on text outside the extract.\n\n"
            f"CHECKPOINT:\n{strat}\n\n"
            f"ADJUDICATION GUIDANCE:\n{intent}\n\n"
            'Reply with JSON ONLY in this exact shape:\n'
            '{"verdict": "Yes" | "No" | "Cannot determine", "reason": "<concise audit explanation>"}\n\n'
            "RELEVANT DOCUMENT EXTRACT:\n"
            "=====\n"
            f"{window}\n"
            "=====\n"
        )

    def _ask_llm(self, prompt):
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json=self._request_payload(prompt),
                timeout=self.timeout,
                headers=self._request_headers() or None,
            )
            resp.raise_for_status()
            raw = self._extract_model_text(resp.json())
        except Exception as e:
            print(f"[!] AOC4 LLM Judge: request failed ({e}) -> falling back to deterministic.")
            logger.warning("request failed (%s) -> keep deterministic.", e)
            return None

        data = self._parse_json(raw)
        if not isinstance(data, dict):
            if data is not None:
                print("[!] AOC4 LLM Judge: model returned a JSON "
                      f"{type(data).__name__} instead of an object -> falling back to deterministic.")
            return None

        verdict = str(data.get("verdict", "")).strip().lower()
        reason = str(data.get("reason", "")).strip()
        if verdict in ("yes", "no"):
            return {
                "user_value": "Yes" if verdict == "yes" else "No",
                "reason": reason or f"Judged by AOC4 LLM ({self.model}).",
                "_judged_by": "llm",
            }
        print(f"[!] AOC4 LLM Judge: model returned no verdict ({verdict}) -> falling back to deterministic.")
        logger.warning("model returned no verdict (%s) -> keep deterministic.", verdict)
        return None

    #: Reasoning models may emit inline thinking; strip it before parsing JSON.
    _RE_THINK_BLOCK = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
    _RE_THINK_OPEN = re.compile(r"<think(?:ing)?>", re.IGNORECASE)

    @classmethod
    def _strip_thinking(cls, raw):
        """Remove `` thinking...`` blocks some reasoning models inline.

        An *unterminated* thinking block means the answer never arrived (typically a
        context cut-off), so the trailing reasoning is dropped entirely - otherwise a
        JSON object written inside the reasoning could be mistaken for the verdict.
        """
        text = cls._RE_THINK_BLOCK.sub(" ", str(raw))
        unclosed = cls._RE_THINK_OPEN.search(text)
        if unclosed:
            text = text[:unclosed.start()]
        return text

    @classmethod
    def _parse_json(cls, raw):
        if not raw:
            return None
        cleaned = cls._strip_thinking(raw).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except Exception as e:
                print(f"[!] AOC4 LLM Judge: JSON parse failed ({e}).")
                return None