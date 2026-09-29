import os
import re
import json
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from .stage2_structure import RawStatutoryRow

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://192.168.112.2:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")


@dataclass
class SemanticFieldDefinition:
    physical_idx: int
    page: int
    canonical_no: str
    label: str
    instructions: str
    field_type: str  # 'text' | 'number' | 'date' | 'radio' | 'select' | 'file'
    options: List[str] = field(default_factory=list)
    required: bool = False
    section_slug: str = "main"
    raw_trigger_condition: Optional[str] = None
    trigger_parent_ref: Optional[str] = None
    trigger_values: List[str] = field(default_factory=list)
    is_root_selector: bool = False
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)
    is_prefilled: bool = False
    prefill_source: Optional[str] = None


class Stage3InstructionAI:
    """
    Parses instruction text to semantically extract field data types,
    genuine option lists, and statutory conditional triggers.
    Enriched with local Qwen 2.5 14B LLM for complex statutory validation rules.
    """

    def __init__(self, ollama_url: str = OLLAMA_API_URL, model: str = OLLAMA_MODEL, use_llm_fallback: bool = True):
        self.ollama_url = ollama_url
        self.model = model
        self.use_llm_fallback = use_llm_fallback

    def _analyze_complex_with_qwen(self, field_name: str, inst: str) -> Optional[Dict[str, Any]]:
        """
        Invokes local Qwen 2.5 14B model on 192.168.112.2 to extract deep validation rules,
        date comparisons, conditional triggers, or prefill constraints.
        """
        if not self.use_llm_fallback or not inst or len(inst.strip()) < 15:
            return None

        # Fast keyword filter: only invoke LLM when actual date comparisons or statutory validation constraints exist
        triggers = [
            "equal to or greater than", "greater than", "less than", "prior to",
            "date of incorporation", "not be earlier than", "not be later than",
            "active/under cirp", "under liquidation"
        ]
        if not any(t in inst.lower() for t in triggers):
            return None

        prompt = (
            f"You are an MCA Statutory Regulatory Form Analyzer.\n"
            f"Analyze this form field and instructions:\n"
            f"Field Name: {field_name}\n"
            f"Instructions: {inst}\n\n"
            f"Extract a JSON object with these keys (use null or empty list if not applicable):\n"
            f"- field_type: (one of: 'text', 'number', 'date', 'select', 'radio', 'file')\n"
            f"- options: list of string options if field is select or radio\n"
            f"- is_mandatory: boolean\n"
            f"- is_prefilled: boolean\n"
            f"- prefill_source: string description if prefilled\n"
            f"- validation_rules: list of objects with {{'operator': 'gte'|'lte'|'eq'|'in'|'not in', 'compare_target': string, 'description': string}}\n"
            f"Respond with strictly valid JSON only."
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0}
        }

        try:
            req = urllib.request.Request(
                self.ollama_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read())
                raw_txt = data.get("response", "").strip()
                if raw_txt:
                    return json.loads(raw_txt)
        except Exception as e:
            # Fall back gracefully to heuristics if offline or timed out
            print(f"[Stage 3 Qwen 14B] Fallback to heuristics for '{field_name[:30]}': {e}")
            return None
        return None

    def process(self, raw_rows: List[RawStatutoryRow], root_branches: List[Dict[str, Any]]) -> List[SemanticFieldDefinition]:
        """
        Transforms raw statutory rows into semantically enriched field definitions.
        """
        results: List[SemanticFieldDefinition] = []

        root_branch_options = [b["option"] for b in root_branches] if root_branches else []

        for row in raw_rows:
            if row.row_type == "section_header":
                continue

            name = row.field_name.strip()
            inst = row.instructions.strip()
            c_no = row.canonical_no.strip()
            sec = row.section_slug

            # 1. Infer field type, options, and mandatory flag via heuristics
            f_type, options, is_req = self._infer_semantics(c_no, name, inst, root_branch_options)

            # 2. Extract statutory condition clause
            parent_ref, trigger_vals, raw_cond = self._extract_trigger_clause(inst)

            is_root = bool(root_branch_options and row.physical_idx == 0)
            if is_root:
                f_type = "radio"
                options = root_branch_options

            # 3. LLM Deep Logic Extraction with Qwen 2.5 14B (when instructions contain complex rules)
            val_rules: List[Dict[str, Any]] = []
            is_prefilled = False
            prefill_src = None

            qwen_res = self._analyze_complex_with_qwen(name, inst)
            if qwen_res:
                if qwen_res.get("validation_rules") and isinstance(qwen_res["validation_rules"], list):
                    val_rules = qwen_res["validation_rules"]
                if qwen_res.get("is_prefilled"):
                    is_prefilled = True
                    prefill_src = qwen_res.get("prefill_source")
                if qwen_res.get("is_mandatory") is True:
                    is_req = True
                if qwen_res.get("field_type") in {"date", "file", "radio", "select"} and f_type == "text":
                    f_type = qwen_res["field_type"]

            results.append(SemanticFieldDefinition(
                physical_idx=row.physical_idx,
                page=row.page,
                canonical_no=c_no,
                label=name,
                instructions=inst,
                field_type=f_type,
                options=options,
                required=is_req,
                section_slug=sec,
                raw_trigger_condition=raw_cond,
                trigger_parent_ref=parent_ref,
                trigger_values=trigger_vals,
                is_root_selector=is_root,
                validation_rules=val_rules,
                is_prefilled=is_prefilled,
                prefill_source=prefill_src
            ))

        return results

    def _infer_semantics(self, c_no: str, name: str, inst: str, root_branch_options: List[str]) -> Tuple[str, List[str], bool]:
        """
        Determines field type, options, and required flag.
        """
        name_l = name.lower()
        inst_l = inst.lower()
        f_type = "text"
        options: List[str] = []

        # 1. File Attachments
        if any(k in name_l for k in ["attachment", "copy of", "upload", "copy(s) of"]) or c_no in {"Attachments", "(a)", "(b)", "(c)", "(d)", "(e)"}:
            f_type = "file"

        # 2. Declarations (text/declaration, not date, even if "dated" appears in text)
        elif name_l.startswith("declaration") or "declare that" in name_l:
            f_type = "text"

        # 3. Dates
        elif re.search(r"\bdd[/\-]mm[/\-]yyyy\b|\bdate\b", name_l) or "dd/mm/yyyy" in inst_l:
            f_type = "date"

        # 4. Numeric Fields
        elif re.search(r"\bnumber\s+of\b|\bcount\b|\bamount\b|\bno\.\s+of\b", name_l) and not any(k in name_l for k in ["pan", "cin", "din"]):
            # If it's "Number of resolutions", provide selectable counts
            if "resolution" in name_l:
                f_type = "select"
                options = ["1", "2", "3", "4", "5"]
            else:
                f_type = "number"

        # 5. Radio / Boolean Options
        elif "whether" in name_l or ("yes" in name_l and "no" in name_l):
            f_type = "radio"
            options = ["Yes", "No"]
        elif "associate" in name_l and ("fellow" in name_l or "felow" in name_l):
            f_type = "radio"
            options = ["Associate", "Fellow"]
        elif "category of auditor" in name_l:
            f_type = "radio"
            options = ["Auditor's Firm", "Individual"]
        elif "designation" in name_l:
            f_type = "select"
            options = [
                "Director", "Manager", "Company Secretary", "CEO", "CFO",
                "Insolvency Resolution Professional (IRP)", "Resolution Professional (RP)", "Liquidator"
            ]

        # 6. Natural Language Radio / Dropdown Options
        elif "select" in inst_l or "dropdown" in inst_l or "radio" in inst_l:
            if "radio" in inst_l and ("yes" in inst_l and "no" in inst_l and "whether" in inst_l):
                f_type = "radio"
                options = ["Yes", "No"]
            elif "associate" in inst_l and ("fellow" in inst_l or "felow" in inst_l):
                f_type = "select"
                options = ["Associate", "Fellow"]
            else:
                f_type = "select"
                options = self._extract_clean_options(inst, name)

        # Mandatory Flag
        is_req = bool(re.search(r"\bmandatory\b|\brequired\b|\bcompulsory\b", inst_l)) or c_no in {"1", "2", "3(a)", "4(a)"}

        return f_type, options, is_req

    def _extract_clean_options(self, inst: str, field_name: str) -> List[str]:
        """
        Extracts genuine selectable options from instruction text, filtering out
        quoted field names, form titles (e.g. INC-28), and instructions.
        """
        # Exclude phrases that are definitely field labels or references
        EXCLUDED_OPTION_PHRASES = {
            "specify the srn", "srn of relevant form", "field number",
            "corporate identity number", "name of the company",
            "registration of", "purpose of passing", "instructions",
            "mandatory", "optional"
        }

        # Look for bulleted or quoted option lists
        q_opts = re.findall(r"[\x27\u2018\u201c]([A-Za-z0-9\s\(\)\-\.,]{2,50})[\x27\u2019\u201d]", inst)
        clean_opts = []

        for opt in q_opts:
            opt_str = opt.strip()
            opt_lower = opt_str.lower()
            if opt_lower == "felow":
                opt_str = "Fellow"
                opt_lower = "fellow"
            if len(opt_str) < 2 or len(opt_str) > 45:
                continue
            if any(ex in opt_lower for ex in EXCLUDED_OPTION_PHRASES):
                continue
            if opt_lower == field_name.lower():
                continue
            if opt_str not in clean_opts:
                clean_opts.append(opt_str)

        return clean_opts

    def _extract_trigger_clause(self, inst: str) -> Tuple[Optional[str], List[str], Optional[str]]:
        """
        Extracts statutory conditional triggers (parent field reference and target trigger values).
        """
        if not inst:
            return None, [], None

        def _clean_val(v: str) -> str:
            v = v.strip()
            v = re.sub(r'\s*\(\s*s\s*\)', '(s)', v)
            # Strip trailing clause indicators like (a), (b), (i) but NOT (s)
            v = re.sub(r'\s*\([a-rt-z0-9ivx]+\)$', '', v, flags=re.I).strip()
            if v.lower() == "felow":
                v = "Fellow"
            return v

        COND_PAT = re.compile(
            r"(?:in\s+case\s+(?:where\s+|of\s+)?|if\s+)(?:(?:only\s+)?single\s+)?(?:either\s+)?(?:(?:either\s+)?(?:of\s+the\s+)?options?\s+)?(?:[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+)[\x27\u2019\u201d\'](?:\s+or\s+[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+)[\x27\u2019\u201d\'])?|([A-Za-z0-9\s]{3,40}?))\s+(?:is\s+)?selected\s+in\s+(?:field\s+(?:number\s+)?)?([0-9]+(?:\s*\([a-zA-Z0-9]+\))*)(?:\s*i\.e\.)?",
            re.I
        )

        for m in COND_PAT.finditer(inst):
            v1 = m.group(1)
            v2 = m.group(2)
            v3 = m.group(3)
            p_no = m.group(4)
            vals = []
            if v1 and v2:
                vals = [_clean_val(v1), _clean_val(v2)]
            elif v1:
                vals = [_clean_val(v1)]
            elif v3:
                v3_clean = v3.strip()
                if v3_clean.lower() in {'more than one option', 'any option', 'any of the options', 'option'}:
                    continue
                vals = [_clean_val(v3_clean)]
            if vals:
                return p_no.strip(), vals, m.group(0)

        # Alternative pattern: selects X from the dropdown present in field number Y
        m2 = re.search(
            r"selects\s+(?:option\s+)?['\"]?([A-Za-z0-9\s\(\)\-]+?)['\"]?\s+(?:from\s+the\s+dropdown\s+present\s+)?in\s+field\s+(?:number\s+)?([0-9]+(?:\s*\([a-zA-Z0-9]+\))*)",
            inst,
            re.I
        )
        if m2:
            return m2.group(2).strip(), [_clean_val(m2.group(1).strip())], m2.group(0)

        return None, [], None
