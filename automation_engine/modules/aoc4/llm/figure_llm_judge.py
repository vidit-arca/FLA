"""LLM figure verification for the AOC-4 private compliance sheet rows 5-27.

Covers the *Financial Particulars* block of ``Compliance sheet for private`` — the
23 rows between the header at row 4 and the ``Is the Company a Holding or a
Subsidiary Company`` flag at row 28::

    r5  Paidup capital          r16 Dues to MSME
    r6  Reserves and Surplus    r17 Networth
    r7  Total Borrowings        r18 Turnover
    ...                         ...
    r27 Number of Bodies Corporate Shareholder holding more than 10%

Why an LLM here at all
----------------------
Those rows are written by :meth:`AOC4ExcelExtractor` and the parser's text fallback,
then formatted into the sheet by ``AOC4RuleEngine``. Regex and table scraping cannot
tell whether the figure that landed in the cell is the figure the balance sheet
actually shows, so an OCR slip or a mis-scraped row stays invisible. The judge reads
the document and reports what it finds for each row.

Division of labour — the model never decides the verdict
--------------------------------------------------------
Live validation of the sibling compliance judge
(``tests/live_check_artifacts/RESULTS_2026-09-25.md``) found its characteristic
failure mode was *keyword-triggered and substance-blind*: it treated any mention of a
topic as evidence. The same weakness applied to figures would mean confirming a
number because the right words sat near it.

So this judge is deliberately built the other way round. The model is asked for one
thing only — **the figure it can actually see, and the text it saw it in** — and the
match/mismatch decision is made in Python by :meth:`_verdict`. A hallucinated figure
therefore fails the comparison and is reported as a mismatch with the model's quote
attached, rather than being written over the extracted value.

Nothing this judge returns is ever written back into the extracted figures. It only
produces a verdict and an evidence quote per row, which land in the unused columns F
and G of the same sheet.
"""

import re

import requests

from automation_engine.modules.aoc4.logger import get_aoc4_logger

logger = get_aoc4_logger("AOC4_LLMJudge")

from automation_engine.modules.aoc4.llm.llm_judge import AOC4LLMJudgeEngine

#: Tolerance idioms, mirroring the MCA-vs-financials comparison already used by
#: ``AOC4CommonErrorEngine``: tolerate OCR noise and rounding on rupee amounts, but
#: require an exact match on counts.
_AMOUNT_FLOOR = 1000.0
_AMOUNT_RATIO = 0.01

#: OCR frequently reports an amount in its displayed unit ("in Cr" per the sheet
#: header at row 4) while the extracted value is in absolute rupees. Each candidate
#: reading is compared against the expected value under every known scale.
_SCALE_FACTORS = (1.0, 10000000.0, 100000.0, 1000.0)

#: What a model writes into "quote" when there is genuinely nothing to quote. Treated
#: as no evidence both when deciding whether an answer is empty and when rendering it.
_PLACEHOLDER_QUOTES = frozenset({
    "not found", "none", "n/a", "na", "-", "--", "not applicable",
    "not disclosed", "not stated", "not mentioned", "nil",
})

_SCALAR_LABELS = (
    "match",
    "mismatch",
    "not stated",
    "not extracted",
    "not checked",
)


class AOC4FigureLLMJudgeEngine(AOC4LLMJudgeEngine):
    """Cross-checks the private sheet's financial rows against the source document.

    Inherits the transport, JSON parsing and rule-aware window builder from
    :class:`AOC4LLMJudgeEngine`; only the row catalogue, the prompt and the
    numeric comparison are specific to figures.
    """

    #: Row catalogue: normalised sheet label -> display name, evidence anchors and
    #: whether the row holds an amount or a count. Anchors are lowercase and matched
    #: case-insensitively against the OCR text.
    _FIGURES = {
        "paidupcapital": {
            "name": "Paidup capital",
            "kind": "amount",
            "anchors": ("paid-up share capital", "paid up share capital",
                        "paid-up capital", "paid up capital", "share capital"),
        },
        "reservesandsurplus": {
            "name": "Reserves and Surplus",
            "kind": "amount",
            "anchors": ("reserves and surplus", "reserves & surplus",
                        "other reserves", "surplus"),
        },
        "totalborrowings": {
            "name": "Total Borrowings",
            "kind": "amount",
            "anchors": ("total borrowings", "borrowings", "long-term borrowings",
                        "short-term borrowings", "total debt"),
        },
        "loangivenbycompanytodirectorsordirectorrelatedentitiesassets": {
            "name": "Loan given by Company to Directors or Director related entities (assets)",
            "kind": "amount",
            "anchors": ("loan to director", "loans to directors", "loan to related",
                        "director related", "related party", "loans and advances"),
        },
        "loansgivenbycompanyassets": {
            "name": "Loans given by Company (assets)",
            "kind": "amount",
            "anchors": ("loans given", "loans and advances", "advance given",
                        "other financial assets", "loans to others"),
        },
        "investmentsmadebycompanyassets": {
            "name": "Investments made by Company (assets)",
            "kind": "amount",
            "anchors": ("investments made", "non-current investments",
                        "long-term investment", "investments", "equity investment"),
        },
        "corporateguaranteesgivenbycompany": {
            "name": "Corporate Guarantees given by Company",
            "kind": "amount",
            "anchors": ("corporate guarantee", "guarantee given", "guarantees",
                        "contingent liabilities"),
        },
        "loanfromdirectorsortheirrelativesliabilities": {
            "name": "Loan from Directors or their relatives (Liabilities)",
            "kind": "amount",
            "anchors": ("loan from director", "borrowings from director",
                        "loan from related part", "unsecured loans",
                        "loan from director"),
        },
        "loanfromshareholdersliabilities": {
            "name": "Loan from Shareholders (Liabilities)",
            "kind": "amount",
            "anchors": ("loan from shareholder", "shareholder loan",
                        "loan from related part", "unsecured loan"),
        },
        "securedloan": {
            "name": "Secured Loan",
            "kind": "amount",
            "anchors": ("secured loan", "secured borrowing", "charge", "hypothecation",
                        "mortgage"),
        },
        "advancefromcustomersshareholderssecuritydepositsliabilitys": {
            "name": "Advance from Customers, Shareholders, Security Deposits (Liabilities)",
            "kind": "amount",
            "anchors": ("advance from customer", "security deposit", "unearned revenue",
                        "customer advance", "contract liability", "advances from"),
        },
        "duestomsme": {
            "name": "Dues to MSME",
            "kind": "amount",
            "anchors": ("micro and small", "msme", "trade payable", "trade payables",
                        "dues to micro"),
        },
        "networth": {
            "name": "Networth",
            "kind": "amount",
            "anchors": ("net worth", "networth", "total equity", "shareholders funds",
                        "shareholders funds"),
        },
        "turnover": {
            "name": "Turnover",
            "kind": "amount",
            "anchors": ("turnover", "revenue from operations", "revenue from sale",
                        "total operating income", "sales"),
        },
        "totalrevenue": {
            "name": "Total Revenue",
            "kind": "amount",
            "anchors": ("total revenue", "total income", "revenue from operations"),
        },
        "profitbeforetax": {
            "name": "Profit Before Tax",
            "kind": "amount",
            "anchors": ("profit before tax", "profit before taxation",
                        "profit before tax and", "earnings before tax"),
        },
        "edwtd1monthlyremuneration": {
            "name": "ED / WTD - 1 Monthly Remuneration",
            "kind": "amount",
            "anchors": ("monthly remuneration", "managerial remuneration",
                        "remuneration", "executive director", "whole time director"),
        },
        "edwtd2monthlyremuneration": {
            "name": "ED / WTD - 2 Monthly Remuneration",
            "kind": "amount",
            "anchors": ("monthly remuneration", "managerial remuneration",
                        "remuneration", "executive director", "whole time director"),
        },
        "edwtd5monthlyremuneration": {
            "name": "ED / WTD - 5 Monthly Remuneration",
            "kind": "amount",
            "anchors": ("monthly remuneration", "managerial remuneration",
                        "remuneration", "executive director", "whole time director"),
        },
        "exprt": {
            "name": "Exprt",
            "kind": "amount",
            "anchors": ("export", "export sales", "overseas sale", "export of goods",
                        "foreign currency", "export of services"),
        },
        "sittingfeestodirectors": {
            "name": "Sitting Fees to Directors",
            "kind": "amount",
            "anchors": ("sitting fee", "sitting fees", "directors remuneration",
                        "commission", "remuneration"),
        },
        "numberofbodiescorporateshareholderholdingmorethan10": {
            "name": "Number of Bodies Corporate Shareholder holding more than 10%",
            "kind": "count",
            "anchors": ("body corporate", "beneficial owner", "shareholding pattern",
                        "shareholder", "10%"),
        },
    }

    #: Windows are built per row from the anchors above; ``_relevant_window`` in the
    #: base class consumes this mapping unchanged.
    _ANCHOR_KEYWORDS = {key: spec["anchors"] for key, spec in _FIGURES.items()}

    def __init__(self, ollama_url=None, model=None, timeout=None,
                 allow_unreachable_retry=False):
        super().__init__(ollama_url=ollama_url, model=model, timeout=timeout)
        #: Set once the server proves unreachable so the remaining rows fall back
        #: immediately instead of costing ``timeout`` seconds each.
        self._unreachable = False
        self._allow_unreachable_retry = allow_unreachable_retry

    # ------------------------------------------------------------------ routing

    @staticmethod
    def _normalize(text):
        return re.sub(r"[^a-z0-9]", "", str(text or "").lower())

    def name_for_figure(self, label):
        """Resolve a sheet row label to a catalogue key, or ``None``.

        Accepts the raw label text from column A, or a dict carrying a
        ``particulars`` key, so callers can pass either.
        """
        if isinstance(label, dict):
            label = label.get("particulars")
        norm = self._normalize(label)
        if not norm:
            return None
        if norm in self._FIGURES:
            return norm
        for key, spec in self._FIGURES.items():
            if spec["name"].lower() == str(label or "").strip().lower():
                return key
        for key, spec in self._FIGURES.items():
            candidate = self._normalize(spec["name"])
            if candidate and (candidate in norm or norm in candidate):
                return key
        return None

    def is_judged_figure(self, label):
        """True when this financial row is in the judge's scope."""
        return self.name_for_figure(label) is not None

    # ------------------------------------------------------------------ comparing

    @staticmethod
    def _to_float(value):
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[^\d.\-]", "", value)
            if not cleaned or cleaned in {"-", ".", "-."}:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    @classmethod
    def tolerance_for(cls, expected, kind):
        """Absolute tolerance used for the comparison.

        Counts are compared exactly; amounts absorb OCR noise and rounding using the
        same floor/ratio idiom as the MCA-vs-financials comparison in the common-error
        checker.
        """
        if kind == "count":
            return 0.0
        return max(_AMOUNT_FLOOR, abs(expected) * _AMOUNT_RATIO)

    def _verdict(self, expected, seen, kind):
        """Decide match / mismatch in Python from the two figures.

        ``seen`` is whatever number the model reported, which may be in the unit the
        document displays rather than absolute rupees, so every known scale is tried
        and the closest reading wins. Returns ``(verdict, normalised_seen)``.

        A missing ``expected`` wins over a missing ``seen``: with nothing extracted
        there is no figure to verify, whatever the document does or does not say.
        """
        expected = self._to_float(expected)
        seen = self._to_float(seen)
        if expected is None:
            return "not extracted", None
        if seen is None:
            return "not stated", None

        tolerance = self.tolerance_for(expected, kind)
        best_value, best_delta = None, None
        for factor in _SCALE_FACTORS:
            candidate = seen * factor
            delta = abs(candidate - expected)
            if best_delta is None or delta < best_delta:
                best_value, best_delta = candidate, delta

        if best_delta <= tolerance:
            return "match", best_value
        return "mismatch", best_value

    # ------------------------------------------------------------------ judging

    def verify(self, label, expected, input_data):
        """Cross-check one financial row against the document.

        Returns ``{"verdict", "expected", "seen", "quote", "reason"}`` when the
        document was inspected, or ``None`` when nothing could be asked (out of scope,
        no text, server unreachable) so the caller keeps the plain extracted figure.
        """
        if self._unreachable and not self._allow_unreachable_retry:
            return None

        key = self.name_for_figure(label)
        if not key:
            return None

        full_text = input_data.get("full_text", "")
        if not isinstance(full_text, str) or not full_text.strip():
            return None

        spec = self._FIGURES[key]
        window = self._relevant_window(full_text, rule_name=key)
        prompt = self._build_figure_prompt(
            row_name=spec["name"],
            kind=spec["kind"],
            expected=expected,
            window=window,
        )
        verdict = self._ask_llm_figure(prompt, expected, spec["kind"])
        logger.info(
            "  verify | row=%s | kind=%s | expected=%s | window_chars=%d | model=%s | outcome=%s",
            key, spec["kind"], expected, len(window), self.model,
            verdict.get("verdict") if isinstance(verdict, dict)
            else "no verdict -> keep extracted figure",
        )
        return verdict

    # ------------------------------------------------------------------ prompt

    def _build_figure_prompt(self, row_name, kind, expected, window):
        """Prompt for one financial row.

        The expected figure is shown so the model knows what it is looking for, but
        the verdict is never asked for: the answer is the figure plus the text it was
        read from, and the comparison happens in Python.
        """
        if expected is None:
            expectation = ("The pipeline did not extract a figure for this row, so "
                           "expected is not available.")
        else:
            expectation = ("The pipeline extracted %s for this row. Report the figure "
                           "the document states, whatever unit it is shown in. Do not "
                           "assume it is the same as the extracted figure."
                           % self._format_expected(expected))
        if kind == "count":
            expectation = expectation.replace(
                "The pipeline extracted", "The pipeline counted")

        return (
            "You are reading an Indian company's financial statements to verify one "
            "line item. Report ONLY what the document actually states. Do not "
            "calculate, round, infer or reconcile anything.\n\n"
            f"LINE ITEM:\n{row_name}\n\n"
            f"{expectation}\n\n"
            "RULES:\n"
            "1. If the document states this line item, copy the number exactly as "
            "shown, keeping the unit it is shown in.\n"
            "2. If the document does not state this line item anywhere, return null for "
            "the figure and 'not found' for the quote. Never supply a number you did "
            "not read.\n"
            "3. The quote must be copied verbatim from the extract, including the "
            "line item's own words.\n"
            "4. If several figures are shown (current year and previous year, or a "
            "total and its components), quote the one matching the line item and say so "
            "in the reason.\n\n"
            "Reply with JSON ONLY in this exact shape:\n"
            '{"figure": <the number you read, as a JSON number, or null>, '
            '"quote": "<verbatim text, or \'not found\'>", '
            '"reason": "<one short sentence>"}\n\n'
            "RELEVANT DOCUMENT EXTRACT:\n"
            "=====\n"
            f"{window}\n"
            "=====\n"
        )

    @staticmethod
    def _format_expected(expected):
        value = AOC4FigureLLMJudgeEngine._to_float(expected)
        if value is None:
            return str(expected)
        return "%.2f" % value

    # ------------------------------------------------------------------ transport

    def _ask_llm_figure(self, prompt, expected, kind):
        """Send the prompt and map the answer onto a verdict computed in Python."""
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
            self._mark_unreachable(e)
            print(f"[!] AOC4 Figure Judge: request failed ({e}) -> leaving the row "
                  "on the extracted figure.")
            logger.warning("request failed (%s) -> keep extracted figure.", e)
            return None

        data = self._parse_json(raw)
        if not isinstance(data, dict):
            if data is not None:
                print("[!] AOC4 Figure Judge: model returned a JSON "
                      f"{type(data).__name__} instead of an object -> leaving the row "
                      "on the extracted figure.")
            return None

        seen = self._to_float(data.get("figure"))
        quote = self._real_quote(str(data.get("quote", "") or "").strip())
        reason = str(data.get("reason", "") or "").strip()

        verdict, normalised = self._verdict(self._to_float(expected), seen, kind)

        # A model that says the figure is absent *is* the finding, so it gets recorded.
        # Only an answer with nothing in it at all is treated as a failure, otherwise a
        # missing figure would silently keep the extracted number with no verdict.
        if verdict == "not stated" and not (quote or reason):
            return None

        if verdict == "match":
            detail = "agrees with the extracted figure"
        elif verdict == "mismatch":
            detail = "differs from the extracted figure"
        elif verdict == "not stated":
            detail = "not stated in the document"
        else:
            detail = "no figure was extracted to check against"

        rendered = "%s (%s)" % (verdict, detail)
        if normalised is not None and verdict != "not extracted":
            rendered += " - document shows %s" % format(normalised, ",.2f")
        if reason:
            rendered += ". %s" % reason
        if quote:
            rendered += " Evidence: %s" % quote[:300]

        return {
            "verdict": verdict,
            "expected": expected,
            "seen": normalised,
            "quote": quote,
            "reason": rendered,
            "_judged_by": "llm",
        }

    @staticmethod
    def _real_quote(quote):
        """Drop the placeholders a model uses to mean "there is no evidence"."""
        if not quote or quote.lower() in _PLACEHOLDER_QUOTES:
            return ""
        return quote

    def _mark_unreachable(self, exc):
        """Trip the circuit breaker after a transport failure.

        Without this, an unreachable server would cost ``timeout`` seconds for every
        one of the financial rows.
        """
        if isinstance(exc, (requests.exceptions.ConnectionError,
                            requests.exceptions.Timeout)):
            if not self._unreachable:
                self._unreachable = True
                print("[!] AOC4 Figure Judge: server unreachable - remaining financial "
                      "rows keep their extracted figures without retrying.")
