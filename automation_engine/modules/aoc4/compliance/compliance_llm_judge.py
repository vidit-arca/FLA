"""LLM-as-a-judge for the AOC-4 **compliance sheet "Requirement" table**.

This is the compliance-sheet twin of :mod:`llm_judge` (which adjudicates the
common-error narrative rows). It follows exactly the same hybrid contract:

    PrivateComplianceEngine (deterministic thresholds)
        -> AOC4ComplianceLLMJudgeEngine.judge()   (LLM overrides)
        -> deterministic result kept when the LLM is unavailable/undecided

Why an LLM here at all: the deterministic compliance engine decides each
requirement purely from financial thresholds (`turnover`, `paid_up_capital`,
`borrowings`, ...). Requirements such as *Vigil Mechanism*, *Internal Audit*,
*Secretarial Audit*, *AOC-1/AOC-2*, *MGT-8* or *Ben-2* however are really
questions about what the uploaded financial statements / audit report
**disclose**, which keyword matching cannot answer. The judge reads the OCR
text and answers those from evidence.

Scope
-----
Only the requirement rows listed in ``JUDGED_REQUIREMENT_KEYS`` are sent to the
model. On ``Compliance sheet for private`` (the sheet the pipeline populates)
the requirement table starts at row 36, so these are the table rows 5-26, i.e.
sheet rows **40-61** (IND AS applicability ... Certification of MGT 7). Trim or
extend the list to change the scope - no other code change is needed.
"""

import re

import requests

from automation_engine.modules.aoc4.llm.llm_judge import AOC4LLMJudgeEngine
from automation_engine.modules.aoc4.logger import get_aoc4_logger

logger = get_aoc4_logger("AOC4_LLMJudge")

# Requirement-table rows adjudicated by the LLM, in sheet order.
# Rows 37-39 (Small Company / CARO / Rotation of Auditors) are deliberately
# excluded: they are pure financial-threshold tests the rule engine computes
# far more reliably than an LLM.
JUDGED_REQUIREMENT_KEYS = [
    "COMP_IND_AS",
    "COMP_XBRL",
    "COMP_VIGIL",
    "COMP_IFC",
    "COMP_INT_AUDIT",
    "COMP_SEC_AUDIT",
    "COMP_KMP",
    "COMP_LOAN_186",
    "COMP_LOAN_DIRECTOR",
    "COMP_COST_AUDIT",
    "COMP_CHARGE_FORM",
    "COMP_AOC_1",
    "COMP_AOC_2",
    "COMP_RPT_OMNIBUS",
    "COMP_CSR",
    "COMP_CSR_COMMITTEE",
    "COMP_DEPOSIT_DEC",
    "COMP_DPT_3",
    "COMP_MSME",
    "COMP_BEN_2",
    "COMP_MGT_8",
    "COMP_MGT_7_CERT",
]


class AOC4ComplianceLLMJudgeEngine(AOC4LLMJudgeEngine):
    """Adjudicates compliance-sheet requirements from document evidence.

    Inherits the transport, JSON parsing and rule-aware window builder from
    :class:`AOC4LLMJudgeEngine`; only the prompts, the requirement catalogue and
    the verdict mapping are compliance-specific.
    """

    # Generic locators for the extract shown to the model (compliance oriented).
    _GENERIC_KEYWORDS = (
        "auditor", "audit", "director", "board", "committee", "company secretary",
        "related party", "notes to accounts", "disclosure", "resolution",
        "shareholder", "borrowings", "share capital", "csr", "msme", "deposit",
        "charge", "internal", "secretarial", "cost",
    )

    # Requirement catalogue: key -> display name + evidence anchors + the
    # adjudication brief handed to the model. Anchors are lowercase; they are
    # matched case-insensitively against the OCR text.
    _REQUIREMENTS = {
        "COMP_IND_AS": {
            "name": "IND AS applicability",
            "anchors": ("ind as", "indian accounting standard", "accounting standards"),
            "intent": (
                "Decide whether the financial statements are prepared under Indian Accounting "
                "Standards (Ind AS) rather than the older Accounting Standards. Evidence: a "
                "basis-of-preparation note, an 'Accounting Standards' row in the notes, or an "
                "audit-report reference. Applicable = Ind AS is used; Not Applicable = the "
                "statements state that AS (not Ind AS) apply."
            ),
        },
        "COMP_XBRL": {
            "name": "XBRL filing",
            "anchors": ("xbrl",),
            "intent": (
                "Decide whether XBRL filing applies: a listed company, an Ind AS company, or a "
                "company with paid-up capital of Rs 5 crore or more, or turnover of Rs 100 crore "
                "or more, must file its financials in XBRL. Evidence: the paid-up capital and "
                "turnover figures in the extract, a listing/Ind AS statement, or an explicit "
                "mention of XBRL. Applicable if any limb is met or XBRL is mentioned; otherwise "
                "Not Applicable."
            ),
        },
        "COMP_VIGIL": {
            "name": "Vigil Mechanism",
            "anchors": ("vigil", "whistle blower", "whistle-blower", "whistleblower"),
            "intent": (
                "Decide whether the company must establish a vigil (whistle-blower) mechanism, "
                "which applies to companies with borrowings above Rs 50 crore and to companies "
                "that must constitute an audit committee. Evidence: a vigil mechanism / "
                "whistle-blower policy disclosure in the board's report or notes, or borrowings "
                "above the threshold. Applicable if the threshold is met or such a policy is "
                "disclosed; Not Applicable only when borrowings are below Rs 50 crore and no "
                "vigil mechanism is required or disclosed."
            ),
        },
        "COMP_IFC": {
            "name": "Internal Financial Controls",
            "anchors": ("internal financial control", "internal financial controls", "ifc"),
            "intent": (
                "Decide whether reporting on the adequacy and operating effectiveness of "
                "Internal Financial Controls (IFC) applies and whether the auditor's report "
                "contains it. IFC reporting is required for listed companies and for private "
                "companies with turnover of Rs 50 crore or more or borrowings of Rs 25 crore or "
                "more. Evidence: an 'Internal Financial Controls' paragraph in the Independent "
                "Auditor's Report, or the turnover/borrowings figures. Applicable if a threshold "
                "is met or IFC reporting is present; Not Applicable if the company is below all "
                "thresholds and no IFC reporting exists."
            ),
        },
        "COMP_INT_AUDIT": {
            "name": "Internal Audit",
            "anchors": ("internal audit", "internal auditor", "internal auditors"),
            "intent": (
                "Decide whether internal audit applies and whether it was carried out. It "
                "applies to listed companies, private companies with turnover of Rs 200 crore or "
                "more or borrowings of Rs 100 crore or more, and public companies with paid-up "
                "capital of Rs 50 crore or more. Evidence: an internal audit report, an internal "
                "auditor's appointment, or the threshold figures. Applicable if any threshold is "
                "met or an internal audit report is referenced; Not Applicable when the company "
                "is below all thresholds and nothing is disclosed."
            ),
        },
        "COMP_SEC_AUDIT": {
            "name": "Secretarial Audit",
            "anchors": ("secretarial audit", "secretarial auditor", "mr-3", "mr 3", "form mr-3"),
            "intent": (
                "Decide whether a secretarial audit applies and was conducted. It applies to "
                "listed companies, public companies with paid-up capital of Rs 50 crore or more "
                "or turnover of Rs 250 crore or more, and companies with borrowings of Rs 100 "
                "crore or more. Evidence: a Secretarial Audit Report (Form MR-3) or a secretarial "
                "auditor's appointment/signature. Applicable if a threshold is met or such a "
                "report exists; Not Applicable for an unlisted private company below the "
                "thresholds with no such report."
            ),
        },
        "COMP_KMP": {
            "name": "KMP appointment",
            "anchors": ("key managerial", "kmp", "company secretary", "chief financial officer",
                        "managing director"),
            "intent": (
                "Decide whether Key Managerial Personnel (company secretary, chief financial "
                "officer, manager/CEO) are required and appointed. They are required for listed "
                "companies, public companies with paid-up capital of Rs 10 crore or more, and any "
                "company that must appoint a company secretary (paid-up capital of Rs 5 crore or "
                "more). Evidence: a signatory/KMP block naming the CS, CFO or CEO, the board's "
                "report, or the master data. Applicable and satisfied when a KMP is named; "
                "Applicable but incomplete when a threshold is crossed with no KMP disclosed; "
                "Not Applicable below the thresholds."
            ),
        },
        "COMP_LOAN_186": {
            "name": "Loan Investment Guarantee - 186",
            "aliases": ("Loan and Investments", "Loan Investment Guarantee"),
            "anchors": ("section 186", "loans and investments", "corporate guarantee",
                        "investments made", "loans given"),
            "intent": (
                "Decide whether the company has given loans, made investments or given "
                "guarantees that attract Section 186 - which requires a board/special resolution "
                "beyond the prescribed limits (60% of paid-up capital plus free reserves, or "
                "100% of free reserves, whichever is higher). Evidence: loans given, investments "
                "or corporate guarantees in the balance sheet, the related party notes, and any "
                "special resolution. Applicable when such transactions exist; Not Applicable "
                "when the amounts are nil or within the limits."
            ),
        },
        "COMP_LOAN_DIRECTOR": {
            "name": "Loan to Director or Related entities",
            "anchors": ("section 185", "loan to director", "loans to directors",
                        "director or his relative", "director related"),
            "intent": (
                "Decide whether the company advanced loans or gave guarantees/security to a "
                "director or to a person/entity in whom a director is interested, which Section "
                "185 restricts. Evidence: loans to directors or director-related entities in the "
                "balance sheet, the related party disclosures, or a special resolution. "
                "Applicable when such an advance exists; Not Applicable when the amount is nil "
                "or the disclosure shows none."
            ),
        },
        "COMP_COST_AUDIT": {
            "name": "Cost Audit",
            "anchors": ("cost audit", "cost auditor", "cost records", "cost accounting"),
            "intent": (
                "Decide whether cost audit applies. It applies to companies in specified "
                "regulated industries (for example drugs, fertilisers, sugar, cement, steel, "
                "telecom, mining) above the turnover thresholds, and where turnover is Rs 20 "
                "crore or more for the products covered by the Cost Records and Audit Rules. "
                "Evidence: a cost auditor's appointment or report, the industry described in the "
                "notes/company overview, or an explicit statement that cost audit is not "
                "applicable. Applicable if the company falls in a covered industry or a cost "
                "auditor is mentioned; Not Applicable if it is stated as not applicable or the "
                "industry is not covered."
            ),
        },
        "COMP_CHARGE_FORM": {
            "name": "Charge form",
            "anchors": ("charge", "chg-1", "chg 1", "chg-4", "satisfaction of charge",
                        "index of charges"),
            "intent": (
                "Decide whether any charge (mortgage/hypothecation) created or modified by the "
                "company required Form CHG-1, or its satisfaction Form CHG-4, to be filed with "
                "the Registrar. Evidence: secured loans or charges in the balance sheet/notes, "
                "the index of charges, or a mention of CHG-1/CHG-4 with an SRN. Applicable when "
                "the company has secured borrowings or a charge; Not Applicable when there are no "
                "secured loans, charges or guarantees."
            ),
        },
        "COMP_AOC_1": {
            "name": "AOC 1",
            "anchors": ("aoc-1", "aoc 1", "aoc1", "subsidiary", "associate company",
                        "joint venture"),
            "intent": (
                "Decide whether Form AOC-1 (statement containing the salient features of the "
                "financial statements of subsidiaries, associates and joint ventures) is required "
                "and whether it is evidenced. AOC-1 is required when the company has a subsidiary, "
                "associate or joint venture. Evidence: a note/annexure listing subsidiaries, "
                "associates or joint ventures, an AOC-1 reference, or investments in such "
                "entities. Applicable if the company has any such entity or mentions AOC-1; Not "
                "Applicable when the company has none."
            ),
        },
        "COMP_AOC_2": {
            "name": "AOC 2",
            "anchors": ("aoc-2", "aoc 2", "aoc2", "related party", "arm's length",
                        "ordinary course of business"),
            "intent": (
                "Decide whether Form AOC-2 (disclosure of particulars of contracts/arrangements "
                "with related parties) is required and evidenced. AOC-2 is required when there "
                "are related-party transactions that are not at arm's length or not in the "
                "ordinary course of business. Evidence: an AOC-2 annexure, related party "
                "transaction notes, or a statement that no such transactions exist. Applicable "
                "if related-party transactions are disclosed; Not Applicable when the company "
                "reports no such transactions."
            ),
        },
        "COMP_RPT_OMNIBUS": {
            "name": "RPT Resolution for omnibus approval",
            "anchors": ("omnibus", "related party", "audit committee", "rpt"),
            "intent": (
                "Decide whether an omnibus approval by the audit committee for related-party "
                "transactions is required and evidenced. Omnibus approval is expected for "
                "repetitive related-party transactions that are in the ordinary course of "
                "business and at arm's length. Evidence: a mention of omnibus approval, an "
                "audit-committee approval, or the related-party transaction disclosures. "
                "Applicable if such repetitive transactions exist or omnibus approval is "
                "mentioned; Not Applicable when there are no related-party transactions."
            ),
        },
        "COMP_CSR": {
            "name": "Corporate Social Responsibility",
            "anchors": ("csr", "corporate social responsibility", "section 135",
                        "social responsibility"),
            "intent": (
                "Decide whether Corporate Social Responsibility (Section 135) applies and "
                "whether the required CSR disclosure is present. It applies to companies with "
                "net worth of Rs 500 crore or more, turnover of Rs 1000 crore or more, or net "
                "profit of Rs 5 crore or more. Evidence: the net worth/turnover/profit figures, "
                "or a CSR note disclosing the amount required to be spent, the amount spent, the "
                "shortfall and the reasons for it. Applicable if a threshold is met or CSR is "
                "disclosed; Not Applicable when the company is below all thresholds and no CSR "
                "disclosure exists."
            ),
        },
        "COMP_CSR_COMMITTEE": {
            "name": "CSR Committee",
            "anchors": ("csr committee", "corporate social responsibility committee",
                        "social responsibility committee"),
            "intent": (
                "Decide whether a CSR Committee must be constituted and whether it is "
                "evidenced. A CSR Committee is required where CSR applies and the CSR "
                "obligation exceeds Rs 50 lakh in a financial year. Evidence: a CSR Committee "
                "composition/disclosure in the board's report or notes, or the CSR spend "
                "figures. Applicable if the company must constitute the committee and it is "
                "disclosed (or the obligation exceeds Rs 50 lakh); Not Applicable when CSR does "
                "not apply or the obligation is below Rs 50 lakh."
            ),
        },
        "COMP_DEPOSIT_DEC": {
            "name": "Deposit declaration",
            "anchors": ("deposit", "declaration", "dpt", "chapter v"),
            "intent": (
                "Decide whether the requirement to disclose that the company has not accepted "
                "deposits (the directors' declaration / notes statement under the deposit rules) "
                "applies and is evidenced, and whether any loan from directors or their relatives "
                "exists that would trigger it. Evidence: a note or declaration stating that the "
                "company has not accepted deposits, loans from directors/relatives in the balance "
                "sheet, or a DPT reference. Applicable when such loans exist or the declaration "
                "is referenced; Not Applicable when the company reports no deposits or loans from "
                "directors."
            ),
        },
        "COMP_DPT_3": {
            "name": "DPT 3",
            "anchors": ("dpt-3", "dpt 3", "dpt3", "return of deposits"),
            "intent": (
                "Decide whether Form DPT-3 (return of deposits and particulars of transactions "
                "not considered as deposits) is required and whether it is evidenced. It is "
                "required where the company has borrowings/advances that are exempt deposits or "
                "has accepted deposits. Evidence: a DPT-3 reference with a filing date/SRN, "
                "borrowings or customer advances in the balance sheet, or an explicit statement "
                "that DPT-3 is not applicable. Applicable if such borrowings/advances exist or "
                "DPT-3 is mentioned; Not Applicable when the company has none."
            ),
        },
        "COMP_MSME": {
            "name": "MSME",
            "anchors": ("msme", "msmed", "micro, small", "micro small", "trade payables"),
            "intent": (
                "Decide whether the MSME disclosure requirement applies and is evidenced: the "
                "balance sheet must disclose dues to micro and small enterprises separately, and "
                "the auditor reports on delays in payment. Evidence: an MSME dues note or a trade "
                "payables split showing dues to MSME, the auditor's report clause on MSME, or the "
                "dues figure. Applicable if any dues to MSME are disclosed or MSME is mentioned; "
                "Not Applicable when the company reports no MSME dues."
            ),
        },
        "COMP_BEN_2": {
            "name": "Ben 2",
            "anchors": ("ben-2", "ben 2", "ben2", "beneficial", "significant beneficial owner"),
            "intent": (
                "Decide whether Form BEN-2 (return of significant beneficial ownership) is "
                "required and evidenced, which arises when the company has significant beneficial "
                "owners, typically corporate shareholders or holders with a 10% or greater stake. "
                "Evidence: a mention of beneficial ownership, BEN-2, a schedule of shareholders "
                "showing corporate or major holders, or the number of corporate shareholders. "
                "Applicable if such shareholders exist or BEN-2 is mentioned; Not Applicable when "
                "there are none."
            ),
        },
        "COMP_MGT_8": {
            "name": "MGT 8 Applicability",
            "anchors": ("mgt-8", "mgt 8", "mgt8", "secretarial standards"),
            "intent": (
                "Decide whether MGT-8 certification applies. It is required for listed "
                "companies, and for unlisted public companies with paid-up capital of Rs 10 crore "
                "or more or turnover of Rs 50 crore or more, and for private companies with "
                "turnover of Rs 50 crore or more or borrowings of Rs 25 crore or more. Evidence: "
                "a MGT-8 reference or certificate, or the paid-up capital/turnover/borrowings "
                "figures. Applicable if a threshold is met or MGT-8 is mentioned; Not Applicable "
                "when the company is below all thresholds."
            ),
        },
        "COMP_MGT_7_CERT": {
            "name": "Certification of MGT 7",
            "anchors": ("mgt-7", "mgt 7", "mgt7", "annual return", "company secretary in practice"),
            "intent": (
                "Decide whether certification of the annual return (MGT-7 by a practising "
                "company secretary) applies and is evidenced. Certification is required for "
                "companies that must appoint a company secretary, or where the paid-up capital "
                "is Rs 10 crore or more or turnover is Rs 50 crore or more. Evidence: a MGT-7 "
                "reference or certificate, a practising company secretary's name/membership "
                "number, or the paid-up capital/turnover figures. Applicable if a threshold is "
                "met or MGT-7 certification is evidenced; Not Applicable when the company is "
                "below all thresholds."
            ),
        },
    }

    # Windows are built per requirement from the anchors above.
    _ANCHOR_KEYWORDS = {key: spec["anchors"] for key, spec in _REQUIREMENTS.items()}

    # Financial facts copied from the deterministic extraction into the prompt, so
    # the model judges thresholds against real figures instead of guessing.
    _FACT_KEYS = (
        ("company_type", "Company type"),
        ("is_listed", "Listed company"),
        ("is_ind_as", "Ind AS applicable"),
        ("is_subsidiary_or_holding", "Holding/subsidiary company"),
        ("paid_up_capital", "Paid-up capital (Rs)"),
        ("reserves_and_surplus", "Reserves and surplus (Rs)"),
        ("net_worth", "Net worth (Rs)"),
        ("turnover", "Turnover (Rs)"),
        ("total_revenue", "Total revenue (Rs)"),
        ("net_profit_before_tax", "Profit before tax (Rs)"),
        ("borrowings", "Total borrowings (Rs)"),
        ("secured_loan", "Secured loan (Rs)"),
        ("loan_from_directors", "Loan from directors/relatives (Rs)"),
        ("advance_from_customers", "Advances from customers (Rs)"),
        ("dues_to_msme", "Dues to MSME (Rs)"),
        ("investments_made", "Investments made (Rs)"),
        ("loan_given_by_company", "Loans given (Rs)"),
        ("loan_to_directors_assets", "Loans to directors (Rs)"),
        ("corporate_guarantees", "Corporate guarantees (Rs)"),
        ("has_corporate_shareholders", "Bodies corporate holding more than 10%"),
    )

    @staticmethod
    def _format_facts(input_data):
        """Render the extracted financial facts as bullet lines.

        Missing values are rendered as ``not available`` rather than omitted, so
        the model can tell "unknown" apart from "zero" - the fabrication guard in
        the prompt depends on this.
        """
        if not isinstance(input_data, dict):
            return "- all facts not available"
        lines = []
        for key, label in AOC4ComplianceLLMJudgeEngine._FACT_KEYS:
            value = input_data.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                lines.append("- %s: not available" % label)
                continue
            if isinstance(value, bool):
                lines.append("- %s: %s" % (label, "Yes" if value else "No"))
            elif isinstance(value, (int, float)):
                lines.append("- %s: %s (Rs %.2f crore)"
                             % (label, format(value, ",.0f"), value / 10000000.0))
            else:
                lines.append("- %s: %s" % (label, value))
        return "\n".join(lines)

    def __init__(self, ollama_url=None, model=None, timeout=None,
                 allow_unreachable_retry=False):
        super().__init__(ollama_url=ollama_url, model=model, timeout=timeout)
        #: Set once the server proves unreachable so the remaining requirements
        #: fall back immediately instead of costing `timeout` seconds each.
        self._unreachable = False
        self._allow_unreachable_retry = allow_unreachable_retry

    # ------------------------------------------------------------------ routing

    def name_for_requirement(self, flag):
        """Resolve a compliance flag to a catalogue key, or ``None``.

        Accepts either the flag dict produced by ``PrivateComplianceEngine`` or
        the bare requirement text (so the sheet itself can be adjudicated).
        """
        flag_id = ""
        text = ""
        if isinstance(flag, dict):
            flag_id = str(flag.get("id", "")).strip().upper()
            if flag_id in self._REQUIREMENTS:
                return flag_id
            text = str(flag.get("particulars", ""))
        else:
            text = str(flag or "")

        norm = self._normalize(text)
        if not norm:
            return None
        labels = []
        for key, spec in self._REQUIREMENTS.items():
            labels.append((key, self._normalize(spec["name"])))
            for alias in spec.get("aliases", ()):
                labels.append((key, self._normalize(alias)))
        for key, label in labels:
            if norm == label:
                return key
        for key, label in labels:
            if label and (label in norm or norm in label):
                return key
        return None

    def is_judged_requirement(self, flag):
        """True when this compliance requirement is in the LLM scope."""
        key = self.name_for_requirement(flag)
        return key is not None and key in JUDGED_REQUIREMENT_KEYS

    @staticmethod
    def _normalize(text):
        return re.sub(r"[^a-z0-9]", "", str(text).lower())

    # ------------------------------------------------------------------ judging

    def judge(self, flag, input_data):
        """Adjudicate one compliance requirement.

        Returns a dict the caller merges into the flag (``user_value``,
        ``status``, ``rationale``) or ``None`` to keep the deterministic result.
        """
        if self._unreachable and not self._allow_unreachable_retry:
            return None

        key = self.name_for_requirement(flag)
        if not key or key not in JUDGED_REQUIREMENT_KEYS:
            return None

        full_text = input_data.get("full_text", "")
        if not isinstance(full_text, str) or not full_text.strip():
            return None

        spec = self._REQUIREMENTS[key]
        window = self._relevant_window(full_text, rule_name=key)
        prompt = self._build_compliance_prompt(
            checkpoint=spec["name"],
            intent=spec["intent"],
            window=window,
            deterministic=(flag or {}).get("user_value") if isinstance(flag, dict) else None,
            facts=self._format_facts(input_data),
        )
        verdict = self._ask_llm_compliance(prompt)
        logger.info(
            "  judge | requirement=%s | checkpoint=%s | window_chars=%d | model=%s | outcome=%s",
            key, spec["name"], len(window), self.model,
            verdict.get("user_value") if isinstance(verdict, dict)
            else "no verdict -> keep deterministic",
        )
        return verdict

    # ------------------------------------------------------------------ transport

    def _build_compliance_prompt(self, checkpoint, intent, window, deterministic=None,
                                 facts=""):
        """Prompt for one compliance requirement (structured two-field answer)."""
        prior = ""
        if deterministic:
            prior = ("The rule engine's preliminary answer, derived only from financial "
                     f"thresholds, is: {deterministic}. You may disagree if the documents show "
                     "otherwise.\n\n")
        return (
            "You are a strict statutory-audit judge reviewing the compliance sheet of an Indian "
            "company's AOC-4 annual filing. Adjudicate ONE requirement using ONLY the facts and "
            "the extract below. Do not speculate and do not rely on anything outside them.\n\n"
            f"REQUIREMENT:\n{checkpoint}\n\n"
            f"ADJUDICATION BRIEF:\n{intent}\n\n"
            f"{prior}"
            "FINANCIAL FACTS EXTRACTED FROM THE FILING (use these for every threshold; a value "
            "marked 'not available' is unknown):\n"
            f"{facts or '- not available'}\n\n"
            "RULES:\n"
            "1. Never assume a financial figure that is not listed above. If the figure a "
            "threshold depends on is 'not available', answer \"Cannot determine\".\n"
            "2. The evidence field must be copied verbatim from the extract or the facts list. "
            "If there is no such text, write 'not found'.\n\n"
            "Reply with JSON ONLY in this exact shape:\n"
            '{"applicability": "Applicable" | "Not Applicable" | "Cannot determine", '
            '"complied": "Yes" | "No" | "Not Applicable" | "Cannot determine", '
            '"evidence": "<verbatim quote, or \'not found\'>", '
            '"reason": "<concise audit explanation>"}\n\n'
            "RELEVANT DOCUMENT EXTRACT:\n"
            "=====\n"
            f"{window}\n"
            "=====\n"
        )

    def _ask_llm_compliance(self, prompt):
        """Send the prompt and map the structured answer onto the flag fields."""
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
            print(f"[!] AOC4 Compliance LLM Judge: request failed ({e}) -> falling back to "
                  "deterministic.")
            logger.warning("request failed (%s) -> keep deterministic.", e)
            return None

        data = self._parse_json(raw)
        if not isinstance(data, dict):
            if data is not None:
                print("[!] AOC4 Compliance LLM Judge: model returned a JSON "
                      f"{type(data).__name__} instead of an object -> falling back to "
                      "deterministic.")
            return None

        applicability = str(data.get("applicability", "")).strip()
        complied = str(data.get("complied", "")).strip()
        evidence = str(data.get("evidence", "")).strip()
        reason = str(data.get("reason", "")).strip()

        verdict_key = re.sub(r"\s+", " ", applicability).strip().lower()
        if verdict_key not in ("applicable", "not applicable"):
            print(f"[!] AOC4 Compliance LLM Judge: undecided applicability "
                  f"({applicability!r}) -> falling back to deterministic.")
            return None
        is_applicable = verdict_key == "applicable"
        complied_key = re.sub(r"\s+", " ", complied).strip().lower()

        if not is_applicable:
            complied_label = "Not applicable"
        elif complied_key in ("yes", "y", "true"):
            complied_label = "Complied: Yes"
        elif complied_key in ("no", "n", "false"):
            complied_label = "Complied: No"
        else:
            complied_label = "Complied: not stated"

        rationale = ("%s - %s" % (complied_label,
                                  reason or "Judged by AOC4 Compliance LLM (%s)."
                                  % self.model))
        if evidence and evidence.lower() not in ("not found", "none", "n/a", "-"):
            rationale += " Evidence: %s" % evidence[:300]

        return {
            "user_value": "Applicable" if is_applicable else "Not Applicable",
            "status": "Failed" if is_applicable else "Passed",
            "rationale": rationale,
            "_judged_by": "llm",
        }

    def _mark_unreachable(self, exc):
        """Trip the circuit breaker after a transport failure.

        Without this, an unreachable server would cost ``timeout`` seconds for
        every one of the requirement rows in scope.
        """
        if isinstance(exc, (requests.exceptions.ConnectionError,
                            requests.exceptions.Timeout)):
            if not self._unreachable:
                self._unreachable = True
                print("[!] AOC4 Compliance LLM Judge: server unreachable - remaining "
                      "requirement rows fall back to the deterministic engine without retrying.")