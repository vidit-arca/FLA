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
    field_type: str  # 'text' | 'number' | 'date' | 'radio' | 'select' | 'file' | 'table'
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
    table_archetype: Optional[str] = None
    repeat_count_field: Optional[str] = None
    columns: List[Dict[str, Any]] = field(default_factory=list)
    min_rows: int = 1
    max_rows: int = 10
    table_metadata: Optional[Dict[str, Any]] = None
    row_template_fields: List[Dict[str, Any]] = field(default_factory=list)
    default_rows: List[Dict[str, Any]] = field(default_factory=list)


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

        for r_idx, row in enumerate(raw_rows):
            if row.row_type == "section_header":
                continue

            name = row.field_name.strip()
            inst = row.instructions.strip()
            c_no = row.canonical_no.strip()
            sec = row.section_slug

            # Check if this row is a dynamic table or repeating group
            table_meta = self._extract_table_metadata(c_no, name, inst, raw_rows, r_idx)

            # 1. Infer field type, options, and mandatory flag via heuristics
            f_type, options, is_req = self._infer_semantics(c_no, name, inst, root_branch_options)

            # 2. Extract statutory condition clause
            parent_ref, trigger_vals, raw_cond = self._extract_trigger_clause(inst)

            if table_meta:
                f_type = "table"
                is_req = True
                options = []
                if name.lower().startswith("table:"):
                    col_names = [c["label"] for c in table_meta.get("columns", [])]
                    name = f"Summary Table ({', '.join(col_names[:2])})" if col_names else "Dynamic Table"

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
                prefill_source=prefill_src,
                table_archetype=table_meta.get("table_archetype") if table_meta else None,
                repeat_count_field=table_meta.get("repeat_count_field") if table_meta else None,
                columns=table_meta.get("columns", []) if table_meta else [],
                min_rows=table_meta.get("min_rows", 1) if table_meta else 1,
                max_rows=table_meta.get("max_rows", 10) if table_meta else 10,
                table_metadata=table_meta,
                default_rows=table_meta.get("default_rows", []) if table_meta else []
            ))

        return results

    def _extract_table_metadata(
        self,
        c_no: str,
        name: str,
        inst: str,
        raw_rows: List[RawStatutoryRow],
        current_idx: int
    ) -> Optional[Dict[str, Any]]:
        name_l = name.lower()
        inst_l = inst.lower()

        # Archetype 1: Web Dynamic Grid (e.g. BEN-2 5(a)_table, LLP-11 Field 10 Penalties, Field 11 Compounding)
        is_archetype_1 = bool(
            c_no.endswith("_table") or 
            name_l.startswith("table:") or 
            name_l.startswith("table :") or 
            re.search(r"\btable:\s*column-", name_l) or
            ("number of row required" in inst_l and ("penalties" in name_l or "compounding" in name_l)) or
            (c_no == "10" and "penalties" in name_l) or
            (c_no == "11" and "compounding" in name_l)
        )

        # Archetype 2: Excel Utility Bridge (e.g. LLP-8 Field 7 Download Excel, LLP-11 Field 7 & 8 Partners)
        is_archetype_2 = bool(
            "download excel" in name_l or 
            re.search(r"download\s+excel.*?import", inst_l, re.DOTALL) or
            ("excel" in name_l and ("import" in name_l or "template" in inst_l)) or
            ("excel file that user can download" in inst_l and ("partner" in name_l or "details" in name_l)) or
            (c_no == "7" and "individual" in name_l and "partner" in name_l) or
            (c_no == "8" and "bodies corporate" in name_l and "partner" in name_l)
        )

        # Archetype 3: Financial Statement & Summary Matrix (e.g. LLP-8 Field 5 Part B, LLP-11 Field 9 Summary of Partners)
        is_archetype_3 = bool(
            ('statement of account' in name_l and 'solvency' not in name_l and 'as at' not in name_l) or
            ('part b: statement of account' in name_l) or
            ('statement of assets and liabilities' in name_l) or
            ('statement of account' in inst_l and 'rupees only' in inst_l and 'as at' not in name_l) or
            ('summary of designated partner' in name_l) or
            (c_no == '9' and 'tabular format' in inst_l)
        )

        if not is_archetype_1 and not is_archetype_2 and not is_archetype_3:
            return None

        archetype = "web_dynamic_grid" if is_archetype_1 else ("excel_utility_bridge" if is_archetype_2 else "financial_matrix")
        columns = []
        repeat_count_field = None
        min_rows = 1
        max_rows = 10
        default_rows = []

        if is_archetype_1:
            # 1. Parse columns from "Column-..." tokens
            raw_cols = re.split(r"Column\s*-\s*", name, flags=re.I)[1:]
            for c in raw_cols:
                c_clean = re.sub(r"\s+", " ", c).strip()
                if not c_clean:
                    continue
                key = re.sub(r"[^a-z0-9]+", "_", c_clean.lower())[:30].strip("_")
                is_num = any(k in c_clean.lower() for k in ["number", "count"])
                is_sbo = any(k in c_clean.lower() for k in ["sbo", "beneficial owner"])
                col_def = {
                    "key": key,
                    "label": c_clean,
                    "type": "number" if is_num else "text",
                    "readonly": is_sbo,
                    "required": is_num
                }
                if is_sbo:
                    col_def["default_pattern"] = "SBO{index}"
                if is_num:
                    col_def["min"] = 1
                    col_def["max"] = 10
                columns.append(col_def)

            # Special case for LLP-11 Field 10 (Penalties) and Field 11 (Compounding)
            if not columns and "penalties" in name_l:
                repeat_count_field = "10(a)"
                columns = [
                    {"key": "section", "label": "Section of the Act / Rule", "type": "text", "required": True},
                    {"key": "offence", "label": "Particulars of offence / default", "type": "text", "required": True},
                    {"key": "person_name", "label": "Name of Person", "type": "text", "required": True},
                    {"key": "order_date", "label": "Order Number & Date", "type": "text", "required": True},
                    {"key": "penalty_amount", "label": "Penalty Imposed (in ₹)", "type": "number", "required": True}
                ]
            elif not columns and "compounding" in name_l:
                repeat_count_field = "11(a)"
                columns = [
                    {"key": "section", "label": "Section of the Act / Rule", "type": "text", "required": True},
                    {"key": "offence", "label": "Particulars of offence", "type": "text", "required": True},
                    {"key": "order_date", "label": "Date of Compounding", "type": "date", "required": True},
                    {"key": "authority", "label": "Compounding Authority", "type": "text", "required": True},
                    {"key": "fee_amount", "label": "Fee / Amount (in ₹)", "type": "number", "required": True}
                ]

            # 2. Extract repeat count field
            if not repeat_count_field:
                m_rep = re.search(r"Basis the number entered in field number\s+([0-9\(\)\sA-Za-z]+?)(?:[\“\”\"\'\‘\’]|i\.e\.|\,|$)", inst, re.I)
                if m_rep:
                    repeat_count_field = re.sub(r"\s+", "", m_rep.group(1))

            # 3. Min/Max rows
            if "greater than zero" in inst_l:
                min_rows = 1
            m_max = re.search(r"equal to or less than\s+([0-9]+)", inst, re.I)
            if m_max:
                max_rows = int(m_max.group(1))

        elif is_archetype_2:
            # 1. Extract repeat count field
            m_rep = re.search(r"field number\s+([0-9\(\)\sA-Za-z]+?)(?:\s+i\.e\.|\s*[\“\”\"\'\‘\’]|\s+to\b|\,|$)", inst, re.I)
            if not m_rep:
                m_rep = re.search(r"equal to the number of rows entered in field number\s+([0-9\(\)\sA-Za-z]+)", inst, re.I)
            if m_rep:
                repeat_count_field = re.sub(r"\s+", "", m_rep.group(1))

            max_rows = 50

            # 2. Schema definition for Archetype 2
            if ("partner" in name_l and "individual" in name_l) or (c_no == "7" and "individual" in name_l):
                columns = [
                    {"key": "designation", "label": "Designation", "type": "select", "options": ["Designated Partner", "Partner"], "required": True},
                    {"key": "dpin_pan", "label": "DPIN / PAN / Passport", "type": "text", "required": True},
                    {"key": "partner_name", "label": "Name of Partner", "type": "text", "required": True},
                    {"key": "obligation_contribution", "label": "Obligation of Contribution (in ₹)", "type": "number", "required": True},
                    {"key": "contribution_received", "label": "Contribution Received & Accounted for (in ₹)", "type": "number", "required": True},
                    {"key": "is_resident", "label": "Resident in India", "type": "select", "options": ["Yes", "No"], "required": True},
                    {"key": "llp_count", "label": "No. of LLPs as partner", "type": "number", "required": False},
                    {"key": "company_count", "label": "No. of Companies as director", "type": "number", "required": False}
                ]
            elif ("partner" in name_l and ("bodies corporate" in name_l or "body corporate" in name_l)) or (c_no == "8" and "bodies corporate" in name_l):
                columns = [
                    {"key": "body_type", "label": "Type of Body Corporate", "type": "select", "options": ["LLP", "Company", "Foreign Body Corporate", "Others"], "required": True},
                    {"key": "cin_llpin", "label": "CIN / LLPIN / Reg No.", "type": "text", "required": True},
                    {"key": "company_name", "label": "Name of Body Corporate", "type": "text", "required": True},
                    {"key": "obligation_contribution", "label": "Obligation of Contribution (in ₹)", "type": "number", "required": True},
                    {"key": "contribution_received", "label": "Contribution Received & Accounted for (in ₹)", "type": "number", "required": True},
                    {"key": "nominee_name", "label": "Name of Nominee", "type": "text", "required": True},
                    {"key": "nominee_dpin", "label": "DPIN / PAN of Nominee", "type": "text", "required": True},
                    {"key": "is_resident", "label": "Resident in India", "type": "select", "options": ["Yes", "No"], "required": True}
                ]
            else:
                # Look ahead for detail fields under the same section (e.g. LLP-8 Field 7 -> 8(b), 8(d)...)
                detail_prefix = None
                for next_r in raw_rows[current_idx + 1:current_idx + 20]:
                    next_c = next_r.canonical_no
                    if not next_c or next_r.row_type != "field":
                        continue
                    if "import" in next_r.field_name.lower():
                        continue
                    if "(" in next_c and not next_c.endswith("(a)"):
                        m_pfx = re.match(r"^([0-9]+)\(", next_c)
                        if m_pfx:
                            pfx = m_pfx.group(1)
                            if detail_prefix is None:
                                detail_prefix = pfx
                            elif pfx != detail_prefix:
                                break
                        c_clean = next_r.field_name.strip()
                        key = re.sub(r"[^a-z0-9]+", "_", c_clean.lower())[:25].strip("_")
                        c_type = "select" if "category" in c_clean.lower() else "text"
                        col_def = {
                            "canonical_no": next_c,
                            "key": key,
                            "label": c_clean,
                            "type": c_type,
                            "required": True
                        }
                        if "category" in c_clean.lower():
                            col_def["options"] = ["Bank", "Financial Institution", "Non-Banking Financial Company", "Others"]
                        columns.append(col_def)
                    elif not "(" in next_c and columns:
                        break

        elif is_archetype_3:
            if "summary of designated partner" in name_l or (c_no == "9" and "partner" in name_l) or (c_no == "9" and "tabular format" in inst_l):
                min_rows = 1
                max_rows = 10
                columns = [
                    {
                        "key": "category",
                        "label": "Category of Partner",
                        "type": "text",
                        "readonly": True,
                        "required": True
                    },
                    {
                        "key": "num_designated_partners",
                        "label": "Number of Designated Partners",
                        "type": "number",
                        "required": True,
                        "placeholder": "0"
                    },
                    {
                        "key": "num_partners",
                        "label": "Number of Partners",
                        "type": "number",
                        "required": True,
                        "placeholder": "0"
                    },
                    {
                        "key": "total_partners",
                        "label": "Total Number of Partners",
                        "type": "number",
                        "required": True,
                        "placeholder": "0"
                    },
                    {
                        "key": "obligation_contribution",
                        "label": "Obligation of Contribution (in ₹)",
                        "type": "number",
                        "required": True,
                        "placeholder": "Enter amount in ₹"
                    },
                    {
                        "key": "contribution_received",
                        "label": "Contribution Received & Accounted for (in ₹)",
                        "type": "number",
                        "required": True,
                        "placeholder": "Enter amount in ₹"
                    }
                ]
                default_rows = [
                    {
                        "category": "(a) Individuals",
                        "num_designated_partners": "",
                        "num_partners": "",
                        "total_partners": "",
                        "obligation_contribution": "",
                        "contribution_received": ""
                    },
                    {
                        "category": "(b) Bodies Corporate",
                        "num_designated_partners": "",
                        "num_partners": "",
                        "total_partners": "",
                        "obligation_contribution": "",
                        "contribution_received": ""
                    },
                    {
                        "category": "Total",
                        "num_designated_partners": "",
                        "num_partners": "",
                        "total_partners": "",
                        "obligation_contribution": "",
                        "contribution_received": ""
                    }
                ]
            else:
                min_rows = 1
                max_rows = 35
                columns = [
                    {
                        "key": "financial_head",
                        "label": "Particulars / Financial Head",
                        "type": "text",
                        "readonly": True,
                        "required": True
                    },
                    {
                        "key": "current_year",
                        "label": "Current Financial Year (in ₹)",
                        "type": "number",
                        "required": True,
                        "placeholder": "Enter amount in ₹"
                    },
                    {
                        "key": "previous_year",
                        "label": "Previous Financial Year (in ₹)",
                        "type": "number",
                        "required": True,
                        "placeholder": "0 if first financial year"
                    }
                ]
                default_rows = [
                    # Statement of Assets and Liabilities
                    {"financial_head": "I. Contribution received by all partners", "current_year": "", "previous_year": ""},
                    {"financial_head": "II. Reserves and Surplus", "current_year": "", "previous_year": ""},
                    {"financial_head": "III. Secured Loans", "current_year": "", "previous_year": ""},
                    {"financial_head": "IV. Unsecured Loans", "current_year": "", "previous_year": ""},
                    {"financial_head": "V. Short-term Borrowings", "current_year": "", "previous_year": ""},
                    {"financial_head": "VI. Trade Payables", "current_year": "", "previous_year": ""},
                    {"financial_head": "VII. Other Liabilities", "current_year": "", "previous_year": ""},
                {"financial_head": "Total Liabilities", "current_year": "", "previous_year": ""},
                {"financial_head": "VIII. Gross Fixed Assets", "current_year": "", "previous_year": ""},
                {"financial_head": "IX. Less: Depreciation / Amortisation", "current_year": "", "previous_year": ""},
                {"financial_head": "X. Net Fixed Assets", "current_year": "", "previous_year": ""},
                {"financial_head": "XI. Investments", "current_year": "", "previous_year": ""},
                {"financial_head": "XII. Inventories", "current_year": "", "previous_year": ""},
                {"financial_head": "XIII. Trade Receivables", "current_year": "", "previous_year": ""},
                {"financial_head": "XIV. Cash and Bank Balances", "current_year": "", "previous_year": ""},
                {"financial_head": "XV. Loans and Advances", "current_year": "", "previous_year": ""},
                {"financial_head": "XVI. Other Assets", "current_year": "", "previous_year": ""},
                {"financial_head": "Total Assets", "current_year": "", "previous_year": ""},
                # Statement of Income and Expenditure
                {"financial_head": "XVII. Turnover / Gross Revenue", "current_year": "", "previous_year": ""},
                {"financial_head": "XVIII. Other Income", "current_year": "", "previous_year": ""},
                {"financial_head": "Total Revenue", "current_year": "", "previous_year": ""},
                {"financial_head": "XIX. Purchases / Cost of Goods Sold", "current_year": "", "previous_year": ""},
                {"financial_head": "XX. Personnel Expenses", "current_year": "", "previous_year": ""},
                {"financial_head": "XXI. Administrative & Other Expenses", "current_year": "", "previous_year": ""},
                {"financial_head": "Total Expenses", "current_year": "", "previous_year": ""},
                {"financial_head": "XXII. Profit / (Loss) Before Tax", "current_year": "", "previous_year": ""},
                {"financial_head": "XXIII. Provision for Tax", "current_year": "", "previous_year": ""},
                {"financial_head": "XXIV. Profit / (Loss) After Tax", "current_year": "", "previous_year": ""},
            ]

        return {
            "table_archetype": archetype,
            "repeat_count_field": repeat_count_field,
            "min_rows": min_rows,
            "max_rows": max_rows,
            "columns": columns,
            "default_rows": default_rows
        }


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
