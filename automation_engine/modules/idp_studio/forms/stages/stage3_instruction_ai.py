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
        if not self.use_llm_fallback or getattr(self, "_llm_failed", False) or not inst or len(inst.strip()) < 15:
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

        try:
            from automation_engine.modules.idp_studio.core.llm_router import call_llm_json
            return call_llm_json("legal_reasoning", prompt, timeout=3)
        except Exception as e:
            # Fall back gracefully to heuristics if offline or timed out
            self._llm_failed = True
            print(f"[Stage 3 Qwen 14B] Fallback to heuristics for '{field_name[:30]}': {e}")
            return None

    def _parse_table_columns_with_coder(self, name: str, inst: str) -> List[Dict[str, Any]]:
        """
        Dynamically extracts table columns from statutory table instructions using qwen2.5-coder:7b.
        Returns a list of column definitions: [{'key': ..., 'label': ..., 'type': ..., 'required': bool}]
        """
        if not inst and not name:
            return []
        try:
            from automation_engine.modules.idp_studio.core.llm_router import call_llm_json
            prompt = (
                f"You are an MCA Statutory Form Compiler. Extract column definitions from this statutory table.\n"
                f"Table Name: {name}\n"
                f"Instructions: {inst}\n\n"
                f"Return a JSON array of column objects, each with:\n"
                f"- 'key': snake_case unique identifier (e.g. 'cin', 'shareholder_name')\n"
                f"- 'label': human-readable column heading\n"
                f"- 'type': one of 'text', 'number', 'date', 'select', 'radio'\n"
                f"- 'required': boolean\n"
                f"- 'options': list of string options if type is select or radio\n\n"
                f"Respond with strictly valid JSON array only."
            )
            res = call_llm_json("schema_coder", prompt, timeout=30)
            if isinstance(res, list) and res:
                cleaned_cols = []
                for item in res:
                    if isinstance(item, dict) and "key" in item and "label" in item:
                        cleaned_cols.append({
                            "key": re.sub(r"[^a-z0-9_]+", "", str(item["key"]).lower())[:30],
                            "label": str(item["label"]).strip(),
                            "type": item.get("type", "text"),
                            "required": bool(item.get("required", True)),
                            "options": item.get("options", [])
                        })
                return cleaned_cols
        except Exception as e:
            print(f"[SchemaCoder Dynamic Table] Fallback due to: {e}")
        return []

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
                field_type="table" if table_meta else f_type,
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

        # Stage 3.5: Synthesize Missing Self-Explanatory Parent Fields from Child Triggers
        results = self._synthesize_missing_parent_fields(results, raw_rows)
        return results

    @staticmethod
    def _canonical_sort_key(c_str: str) -> Tuple[int, str]:
        c_clean = re.sub(r'[\s\(\)]', '', c_str.lower())
        m = re.match(r'^([0-9]+)([a-z0-9]*)', c_clean)
        if m:
            return (int(m.group(1)), m.group(2))
        return (999, c_str)

    def _synthesize_missing_parent_fields(
        self,
        results: List[SemanticFieldDefinition],
        raw_rows: List[RawStatutoryRow]
    ) -> List[SemanticFieldDefinition]:
        """
        Synthesizes missing parent fields (omitted by MCA as 'self-explanatory')
        by analyzing child instruction trigger clauses and cross-field references.
        E.g. In Form INC-28, fields 3(a, b, d, e), 4, 5(a), 9, 11(a, b), 12(c)
        are omitted from the instruction table, but referenced throughout.
        """
        existing_c_nos = {re.sub(r'[\s\(\)]+', '', r.canonical_no.lower()) for r in results if r.canonical_no}

        ref_pat = re.compile(
            r'field\s+number\s+([0-9]+(?:\s*\([a-zA-Z0-9]+\))*)\s+i\.e\.[\,\s]*[“\"\‘\']([^”\"\'\’]+?)[”\"\'\’]',
            re.I | re.DOTALL
        )
        clause_pat = re.compile(
            r'(?:in\s+case\s+([^.]+?)\s+is\s+selected\s+in\s+field\s+number\s+([0-9]+(?:\s*\([a-zA-Z0-9]+\))*)(?:\s+i\.e\.[\,\s]*[“\"\‘\']([^”\"\'\’]+?)[”\"\'\’])?)',
            re.I | re.DOTALL
        )

        missing_parents: Dict[str, Dict[str, Any]] = {}

        def clean_c_no(c: str) -> str:
            return re.sub(r'\s+', '', c)

        def clean_lbl(raw_lbl: str) -> str:
            lbl = re.sub(r'---\s*PAGE\s*[0-9]+\s*---.*?Field\s+Name\s+Instructions', '', raw_lbl, flags=re.I | re.DOTALL)
            lbl = re.sub(r'\s+', ' ', lbl).strip()
            return lbl.rstrip('?.,;:')

        for r in raw_rows:
            inst = getattr(r, 'instructions', '') or ''

            # 1. Direct references
            for m in ref_pat.finditer(inst):
                c_no = clean_c_no(m.group(1))
                lbl = clean_lbl(m.group(2))
                clean_key = re.sub(r'[\s\(\)]+', '', c_no.lower())
                if clean_key in existing_c_nos:
                    continue
                if clean_key not in missing_parents:
                    missing_parents[clean_key] = {
                        'canonical_no': c_no,
                        'label': lbl,
                        'options': set(),
                        'section_slug': getattr(r, 'section_slug', 'main'),
                        'page': getattr(r, 'page', 1),
                        'physical_idx': getattr(r, 'physical_idx', 0)
                    }
                elif lbl and not missing_parents[clean_key]['label']:
                    missing_parents[clean_key]['label'] = lbl

            # 2. Trigger clauses with option values
            for m in clause_pat.finditer(inst):
                clause = m.group(1) or ''
                c_no = clean_c_no(m.group(2))
                lbl = clean_lbl(m.group(3) or '')
                clean_key = re.sub(r'[\s\(\)]+', '', c_no.lower())
                if clean_key in existing_c_nos:
                    continue
                if clean_key not in missing_parents:
                    missing_parents[clean_key] = {
                        'canonical_no': c_no,
                        'label': lbl,
                        'options': set(),
                        'section_slug': getattr(r, 'section_slug', 'main'),
                        'page': getattr(r, 'page', 1),
                        'physical_idx': getattr(r, 'physical_idx', 0)
                    }
                quotes = re.findall(r'[‘\'“\"]([^’\'”\"]+?)[’\'”\"]', clause)
                for q in quotes:
                    q_clean = re.sub(r'\s+', ' ', q).strip()
                    if len(q_clean) > 2 and not q_clean.lower().startswith("field number"):
                        missing_parents[clean_key]['options'].add(q_clean)

        # 3. Composite Section 3 siblings if 3(a) is an order authority field
        if '3a' in missing_parents and any(k in missing_parents['3a'].get('label', '').lower() for k in ['order passed by', 'court', 'tribunal', 'authority']):
            if not missing_parents['3a']['options']:
                missing_parents['3a']['options'] = {'Court', 'NCLT', 'NCLAT', 'Central Government', 'Regional Director', 'Others'}
            if '3b' not in existing_c_nos and '3b' not in missing_parents:
                missing_parents['3b'] = {
                    'canonical_no': '3(b)',
                    'label': 'Name of the court or tribunal or authority',
                    'options': set(),
                    'section_slug': 'main',
                    'page': 1,
                    'physical_idx': 21
                }
            if '3d' not in existing_c_nos and '3d' not in missing_parents:
                missing_parents['3d'] = {
                    'canonical_no': '3(d)',
                    'label': 'Petition or application or appeal number',
                    'options': set(),
                    'section_slug': 'main',
                    'page': 1,
                    'physical_idx': 23
                }
            if '3e' not in existing_c_nos and '3e' not in missing_parents:
                missing_parents['3e'] = {
                    'canonical_no': '3(e)',
                    'label': 'Order number',
                    'options': set(),
                    'section_slug': 'main',
                    'page': 1,
                    'physical_idx': 24
                }

        # 4. Synthesize 11(a) and 11(b) only if penalty / 11 is explicitly referenced in missing parents
        if ('11a' in missing_parents or '11b' in missing_parents) and any('penalty' in missing_parents[k].get('label', '').lower() for k in ['11a', '11b'] if k in missing_parents):
            if '11a' not in existing_c_nos and '11a' not in missing_parents:
                missing_parents['11a'] = {
                    'canonical_no': '11(a)',
                    'label': 'Whether penalty involved or not',
                    'options': {'Yes', 'No'},
                    'section_slug': 'main',
                    'page': 2,
                    'physical_idx': 80
                }
            if '11b' not in existing_c_nos and '11b' not in missing_parents:
                missing_parents['11b'] = {
                    'canonical_no': '11(b)',
                    'label': 'Amount of penalty (in ₹)',
                    'options': set(),
                    'section_slug': 'main',
                    'page': 2,
                    'physical_idx': 81,
                    'trigger_parent_ref': '11(a)',
                    'trigger_values': ['Yes']
                }

        # 5. Synthesize 12(c) only if 12(c) is referenced in missing parents
        if '12c' in missing_parents:
            if '12c' not in existing_c_nos and not missing_parents['12c'].get('label'):
                missing_parents['12c']['label'] = 'Whether the order provides for increase in authorised share capital of the transferee company'
                missing_parents['12c']['options'] = {'Yes', 'No'}

        if not missing_parents:
            return results

        synthesized_fields: List[SemanticFieldDefinition] = []
        for c_clean, data in missing_parents.items():
            c_no = data['canonical_no']
            lbl = data['label'] or f"Field {c_no}"
            opts = sorted(list(data['options']))

            # Semantic Type Inference
            if re.search(r'\bdd[/\-]mm[/\-]yyyy\b|\bdate\b', lbl, re.I):
                f_type = "date"
                opts = []
            elif lbl.lower().startswith("whether") or "yes/no" in lbl.lower():
                f_type = "radio"
                opts = ["Yes", "No"]
            elif re.search(r'\bamount\b|\bnumber\b|\bcount\b', lbl, re.I) and not any(k in lbl.lower() for k in ["pan", "cin", "din", "srn"]):
                f_type = "number"
                opts = []
            elif len(opts) > 2:
                f_type = "select"
            elif len(opts) > 0:
                f_type = "radio"
            else:
                f_type = "text"

            print(f"[Stage 3] 🌟 Synthesizing missing self-explanatory parent field {c_no} ('{lbl}') -> type: {f_type}, {len(opts)} options")

            parent_field = SemanticFieldDefinition(
                physical_idx=data['physical_idx'],
                page=data['page'],
                canonical_no=c_no,
                label=lbl,
                instructions="Synthesized statutory field inferred from cross-field references.",
                field_type=f_type,
                options=opts,
                required=True,
                section_slug=data['section_slug'],
                raw_trigger_condition=None,
                trigger_parent_ref=data.get('trigger_parent_ref'),
                trigger_values=data.get('trigger_values', []),
                is_root_selector=False
            )
            synthesized_fields.append(parent_field)

            # If 'Others' is in options, synthesize conditional "If others, then specify"
            if any(o.lower() == "others" for o in opts) and c_no not in {"3(a)"}:
                sub_match = re.match(r"^([0-9]+)\(([a-z])\)$", c_no, re.I)
                if sub_match:
                    num_part, char_part = sub_match.group(1), sub_match.group(2)
                    next_char = chr(ord(char_part.lower()) + 1)
                    specify_c_no = f"{num_part}({next_char})"
                else:
                    specify_c_no = f"{c_no}_specify"

                specify_field = SemanticFieldDefinition(
                    physical_idx=data['physical_idx'] + 1,
                    page=data['page'],
                    canonical_no=specify_c_no,
                    label="If others, then specify",
                    instructions="Specify document title if 'Others' is selected.",
                    field_type="text",
                    options=[],
                    required=True,
                    section_slug=data['section_slug'],
                    raw_trigger_condition=f"If Others is selected in field number {c_no}",
                    trigger_parent_ref=c_no,
                    trigger_values=["Others"],
                    is_root_selector=False
                )
                synthesized_fields.append(specify_field)

        # Merge preserving canonical order
        combined = list(results)
        for sf in synthesized_fields:
            insert_idx = len(combined)
            sf_key = self._canonical_sort_key(sf.canonical_no)
            for idx, existing in enumerate(combined):
                ex_key = self._canonical_sort_key(existing.canonical_no or '')
                if ex_key and sf_key < ex_key:
                    insert_idx = idx
                    break
            combined.insert(insert_idx, sf)

        return combined

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

        c_clean = re.sub(r'[\s\(\)]', '', c_no.upper())

        # Archetype 1: Web Dynamic Grid (e.g. BEN-2 5(a)_table, LLP-11 Field 10 Penalties, Field 11 Compounding, INC-28 13A/13B)
        is_archetype_1 = bool(
            c_no.endswith("_table") or 
            name_l.startswith("table:") or 
            name_l.startswith("table :") or 
            re.search(r"\btable:\s*column-", name_l) or
            ("number of row required" in inst_l and ("penalties" in name_l or "compounding" in name_l)) or
            (c_no == "10" and "penalties" in name_l) or
            (c_no == "11" and "compounding" in name_l) or
            ("details of authorized share" in name_l) or
            ("authorized share capital" in name_l) or
            (c_clean in {"13A", "13B"}) or
            ("tabular format" in inst_l and ("add row" in inst_l or "enter" in inst_l)) or
            ("number of row" in inst_l and ("required" in inst_l or "entered" in inst_l)) or
            ("in the table of field" in inst_l) or
            bool(re.search(r"<column\s*\d+>", name_l))
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
            (c_no == '9' and 'tabular format' in inst_l) or
            bool(re.search(r"<column\s*\d+>", name_l) and re.search(r"<row\s*\d+>", name_l))
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
            # 1. Parse columns from "Column-..." tokens or "<Column \d+>" markers
            raw_cols = re.split(r"Column\s*-\s*", name, flags=re.I)[1:]
            for c in raw_cols:
                c_clean_col = re.sub(r"\s+", " ", c).strip()
                if not c_clean_col:
                    continue
                key = re.sub(r"[^a-z0-9]+", "_", c_clean_col.lower())[:30].strip("_")
                is_num = any(k in c_clean_col.lower() for k in ["number", "count"])
                is_sbo = any(k in c_clean_col.lower() for k in ["sbo", "beneficial owner"])
                col_def = {
                    "key": key,
                    "label": c_clean_col,
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

            if not columns:
                col_matches = re.findall(r"<column\s*\d+>\s*['\"]?([^'\"\>]+)['\"]?", name, re.I)
                for cm in col_matches:
                    c_clean_col = cm.strip()
                    columns.append({
                        "key": re.sub(r"[^a-z0-9]+", "_", c_clean_col.lower())[:30].strip("_"),
                        "label": c_clean_col,
                        "type": "number",
                        "required": True
                    })

            # Special case for MCA Form INC-28 Field 13A and 13B (Details of Authorized Share Capital)
            if not columns and (
                "details of authorized share" in name_l or
                "authorized share capital" in name_l or
                c_clean in {"13A", "13B"} or
                ("share capital" in name_l and "add row" in inst_l)
            ):
                columns = [
                    {"key": "share_type", "label": "Type of Share", "type": "select", "options": ["Equity", "Preference", "Unclassified"], "required": True},
                    {"key": "class_of_share", "label": "Class of Share", "type": "text", "required": True},
                    {"key": "nominal_value", "label": "Nominal value per share (in ₹)", "type": "number", "required": True},
                    {"key": "num_shares", "label": "Number of Shares", "type": "number", "required": True},
                    {"key": "total_amount", "label": "Total Amount (in ₹)", "type": "number", "required": True}
                ]
                min_rows = 1
                max_rows = 50

            # Special case for LLP-11 Field 10 (Penalties) and Field 11 (Compounding)
            elif not columns and "penalties" in name_l:
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

            elif not columns and ("shareholder" in name_l or "subscriber" in name_l or "shareholder" in inst_l):
                repeat_count_field = "4(a)"
                columns = [
                    {"key": "shareholder_name", "label": "4(b). Name of shareholder", "type": "text", "required": True},
                    {"key": "bank_name", "label": "4(c). Name of the Bank", "type": "text", "required": True},
                    {"key": "account_number", "label": "4(d). Account number", "type": "text", "required": True},
                    {"key": "date_of_receipt", "label": "4(e). Date of receipt", "type": "date", "required": True},
                    {"key": "amount_of_receipt", "label": "4(f). Amount of receipt", "type": "number", "required": True}
                ]
                min_rows = 1
                max_rows = 50

            # 2. Extract repeat count field
            if not repeat_count_field:
                m_rep = re.search(r"Basis the number entered in field number\s+([0-9\(\)\sA-Za-z]+?)(?:[\“\”\"\'\‘\’]|i\.e\.|\,|$)", inst, re.I)
                if not m_rep:
                    m_rep = re.search(r"based on (?:the )?number entered in field (?:number )?([0-9\(\)\sA-Za-z]+?)(?:[\“\”\"\'\‘\’]|i\.e\.|\,|$)", inst, re.I)
                if m_rep:
                    repeat_count_field = re.sub(r"\s+", "", m_rep.group(1))
                    repeat_count_field = re.sub(r"i\.?$", "", repeat_count_field).strip()

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

        if not columns and (inst or name):
            columns = self._parse_table_columns_with_coder(name, inst)

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

        # 0. Statutory Identifiers (CIN, LLPIN, PAN, DIN, SRN, FCRN)
        is_statutory_id = (
            re.search(r"\b(?:cin|llpin|pan|din|srn|fcrn)\b", name_l) or
            re.search(r"\b(?:corporate identity number|director identification number|permanent account number|limited liability partnership)\b", name_l)
        ) and not any(k in name_l for k in ["number of", "count", "no. of"])
        if is_statutory_id:
            return "text", [], bool(re.search(r"\bmandatory\b|\brequired\b|\bcompulsory\b", inst_l)) or c_no in {"1", "2"}

        # 1. Dates (check before file attachments so 'Certified copy of order (DD/MM/YYYY)' is treated as date)
        if re.search(r"\bdd[/\-]mm[/\-]yyyy\b|^date\b|\bdate of\b", name_l) and not ("copy of order" in name_l and "court" in name_l):
            f_type = "date"

        # 2. File Attachments
        elif any(k in name_l for k in ["attachment", "upload", "copy(s) of"]) or (("copy of" in name_l) and not re.search(r"\bdate\b|\bdd[/\-]mm[/\-]yyyy\b", name_l)) or c_no in {"Attachments", "(a)", "(b)", "(c)", "(d)", "(e)"}:
            f_type = "file"

        # 3. Declarations (text/declaration, not date, even if "dated" appears in text)
        elif name_l.startswith("declaration") or "declare that" in name_l:
            f_type = "text"

        # 4. Dates fallback
        elif re.search(r"\bdd[/\-]mm[/\-]yyyy\b|\bdate\b", name_l) or "dd/mm/yyyy" in inst_l:
            f_type = "date"

        # 5. Numeric Fields
        elif re.search(r"\bnumber\s+of\b|\bcount\b|\bamount\b|\bno\.\s+of\b", name_l) and not any(k in name_l for k in ["pan", "cin", "din"]):
            # If it's "Number of resolutions", provide selectable counts
            if "resolution" in name_l:
                f_type = "select"
                options = ["1", "2", "3", "4", "5"]
            else:
                f_type = "number"

        # 6. Radio / Boolean Options
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

        # 7. Natural Language Radio / Dropdown Options
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
            # Filter out form codes e.g. "CHG-4", "INC-28", "MGT-14", "PAS-6"
            if re.match(r'^(?:form\s*(?:no\.?\s*)?)?[a-z]{2,5}[\s\-]*[0-9]{1,3}[a-z]?$', opt_lower):
                continue
            if opt_str not in clean_opts:
                clean_opts.append(opt_str)

        return clean_opts

    def _extract_trigger_clause(self, inst: str) -> Tuple[Optional[str], List[str], Optional[str]]:
        """
        Extracts statutory conditional triggers (parent field reference and target trigger values).
        Supports both natural language structures:
        - Order A: 'in case [section/option/value] X is selected in field number Y'
        - Order B: 'in case option selected in field number Y is X'
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

        # Pattern A: in case [section/option/value] X is selected in field number Y
        pat_a = re.compile(
            r"(?:in\s+case\s+(?:where\s+|if\s+|of\s+)?|if\s+)(?:section\s+|option\s+|value\s+)?[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+)[\x27\u2019\u201d\']\s+(?:is\s+)?selected\s+in\s+(?:field|filed)\s+(?:number\s+)?([0-9]+(?:\s*\([a-zA-Z0-9]+\))*)",
            re.I
        )
        ma = pat_a.search(inst)
        if ma:
            p_no = re.sub(r'\s+', '', ma.group(2))
            return p_no, [_clean_val(ma.group(1))], ma.group(0)

        # Pattern B: in case option selected in field number Y is X (or Z)
        pat_b = re.compile(
            r"(?:in\s+case\s+(?:where\s+|if\s+|of\s+)?|if\s+)(?:option\s+|value\s+|section\s+)?(?:is\s+)?selected\s+in\s+(?:field|filed)\s+(?:number\s+)?([0-9]+(?:\s*\([a-zA-Z0-9]+\))*)(?:\s*i\.e\.[\,\s]*[“\"\‘\'][^”\"\'\’]+?[”\"\'\’])?\s+is\s+[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+)[\x27\u2019\u201d\'](?:\s+or\s+[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+)[\x27\u2019\u201d\'])?",
            re.I | re.DOTALL
        )
        mb = pat_b.search(inst)
        if mb:
            p_no = re.sub(r'\s+', '', mb.group(1))
            v1 = mb.group(2)
            v2 = mb.group(3)
            vals = [_clean_val(v) for v in [v1, v2] if v]
            return p_no, vals, mb.group(0)

        COND_PAT = re.compile(
            r"(?:in\s+case\s+(?:where\s+|of\s+)?|if\s+)(?:(?:only\s+)?single\s+)?(?:either\s+)?(?:(?:either\s+)?(?:of\s+the\s+)?options?\s+)?(?:[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+)[\x27\u2019\u201d\'](?:\s+or\s+[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+)[\x27\u2019\u201d\'])?|([A-Za-z0-9\s]{3,40}?))\s+(?:is\s+)?selected\s+in\s+(?:field\s+(?:number\s+)?)?([0-9]+(?:\s*\([a-zA-Z0-9]+\))*)(?:\s*i\.e\.)?",
            re.I
        )

        for m in COND_PAT.finditer(inst):
            v1 = m.group(1)
            v2 = m.group(2)
            v3 = m.group(3)
            p_no = re.sub(r'\s+', '', m.group(4))
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
                return p_no, vals, m.group(0)

        # Alternative pattern: selects X from the dropdown present in field number Y
        m2 = re.search(
            r"selects\s+(?:option\s+)?['\"]?([A-Za-z0-9\s\(\)\-]+?)['\"]?\s+(?:from\s+the\s+dropdown\s+present\s+)?in\s+field\s+(?:number\s+)?([0-9]+(?:\s*\([a-zA-Z0-9]+\))*)",
            inst,
            re.I
        )
        if m2:
            return re.sub(r'\s+', '', m2.group(2)), [_clean_val(m2.group(1).strip())], m2.group(0)

        return None, [], None
