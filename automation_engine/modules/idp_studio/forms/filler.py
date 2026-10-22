"""
Dynamic Semantic Form Filler Engine for MCA Forms.

Leverages Ollama `qwen2.5:14b` as the semantic mapper between source document evidence
and target MCA form fields, wrapped by rigorous deterministic validation and DAG dependency pruning.
"""

import os
import re
import json
import time
import logging
import datetime
from typing import Dict, Any, List, Optional, Tuple
import requests

try:
    from automation_engine.modules.idp_studio.extractors.universal_statutory import (
        parse_and_normalize_date, match_canonical_option
    )
    from automation_engine.modules.idp_studio.core.llm_router import call_llm_json
except ImportError:
    from modules.idp_studio.extractors.universal_statutory import (
        parse_and_normalize_date, match_canonical_option
    )
    from modules.idp_studio.core.llm_router import call_llm_json

logger = logging.getLogger(__name__)

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://192.168.112.2:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")


class DynamicFormFiller:
    """
    Autonomous form-filling engine supporting 54+ MCA forms dynamically.
    Decoupled: LLM does semantic reasoning, Python performs deterministic validation.
    """

    def __init__(self, ollama_url: str = OLLAMA_API_URL, model: str = OLLAMA_MODEL):
        self.ollama_url = ollama_url
        self.model = model

    def fill_form(
        self,
        form_schema: Dict[str, Any],
        evidence_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point:
        1. Formulates prompt with form schema, evidence, and dynamic scenario lexicon.
        2. Calls qwen2.5:14b for semantic mapping.
        3. Injects confirmed HITL branch selections (e.g. nature_of_appointment).
        4. Applies deterministic validation layers (Type, Regex, Canonical Options, DAG).
        5. Returns standardized FormFillExecutionPayload.
        """
        start_time = time.time()
        form_id = form_schema.get("form_id", "unknown_form")
        form_name = form_schema.get("form_name", "MCA Form")
        fields = form_schema.get("fields", [])

        # 1. Deterministic statutory direct mapping pass FIRST
        deterministic_mappings = self._deterministic_mapping_pass(fields, evidence_list)
        unmapped_fields = [f for f in fields if f["id"] not in deterministic_mappings]

        # 2. For fields not deterministically resolved, run LLM semantic mapping
        raw_mappings = dict(deterministic_mappings)
        if unmapped_fields:
            llm_subschema = {**form_schema, "fields": unmapped_fields}
            llm_mappings = self._semantic_mapping_llm(llm_subschema, evidence_list, context=context)
            for f_id, m in llm_mappings.items():
                if m.get("value") is not None and str(m.get("value")).strip() not in ["", "Unknown", "N/A"]:
                    raw_mappings[f_id] = m

        # 3. Inject confirmed HITL branch selections into raw_mappings
        if context and context.get("confirmed_branch"):
            confirmed_branch = context["confirmed_branch"]
            for f in fields:
                flbl = f.get("label", "").lower()
                fid = f.get("id", "").lower()
                if (any(x in fid for x in ["nature_of_appointment", "natureofappointment", "purpose_of_filing", "field_3a", "field_5a", "field_5c_2"])
                    or "purpose of filing" in flbl or "nature of appointment" in flbl):
                    raw_mappings[f["id"]] = {
                        "value": confirmed_branch,
                        "status": "extracted",
                        "confidence": 1.0,
                        "reasoning": "Confirmed via HITL Decision Gate",
                        "source_doc": "HITL Verification",
                        "quote": confirmed_branch
                    }
                if context.get("casual_vacancy_reason") and ("casual_vacan" in fid or "casualvacancy" in fid):
                    raw_mappings[f["id"]] = {
                        "value": context["casual_vacancy_reason"],
                        "status": "extracted",
                        "confidence": 1.0,
                        "reasoning": "Confirmed via HITL Decision Gate",
                        "source_doc": "HITL Verification",
                        "quote": context["casual_vacancy_reason"]
                    }

        # 3. Layer 1 & 2: Type, Regex & Canonical Option Enforcement
        validated_fields = self._validate_and_normalize_values(fields, raw_mappings, evidence_list)

        # 4. Layer 3: DAG Dependency Pruning
        active_fields = self._resolve_dag_dependencies(fields, validated_fields)

        # 5. Layer 4: Audit & Summary Calculation
        execution_payload = self._compile_execution_payload(
            form_id=form_id,
            form_name=form_name,
            fields=fields,
            active_fields=active_fields,
            elapsed_sec=time.time() - start_time
        )

        return execution_payload

    # ─────────────────────────────────────────────────────────────────────────
    # LLM Semantic Mapping Layer
    # ─────────────────────────────────────────────────────────────────────────

    def _semantic_mapping_llm(
        self,
        form_schema: Dict[str, Any],
        evidence_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Prompts qwen2.5:14b with form fields, source document evidence, and dynamic scenario lexicon.
        Returns a dict of {field_id: mapping_dict}.
        """
        fields = form_schema.get("fields", [])
        
        # Prepare lightweight field summary for prompt
        field_summaries = []
        for f in fields:
            summary = {
                "field_id": f["id"],
                "canonical_no": f.get("canonical_no", ""),
                "label": f["label"],
                "type": f.get("type", "text"),
                "options": f.get("options")
            }
            if f.get("instructions"):
                summary["instructions"] = f["instructions"][:150]
            field_summaries.append(summary)

        # Prepare normalized evidence summary
        evidence_items = []
        for idx, ev in enumerate(evidence_list):
            k = ev.get("key") or ev.get("variable_name") or f"Item_{idx}"
            v = ev.get("value") or ev.get("text") or ""
            doc = ev.get("source_doc") or ev.get("document") or "Uploaded Document"
            evidence_items.append({"key": str(k), "value": str(v), "document": str(doc)})

        # Dynamic Lexicon injection if present
        lexicon_section = ""
        if context and context.get("lexicon"):
            lexicon_section = f"""
LEARNED REAL-WORLD ALIASES & ANCHORS FOR THIS SCENARIO:
{json.dumps(context['lexicon'], indent=2)}
Use these learned secretarial aliases as strong hints when matching evidence to target fields.
"""

        prompt = f"""You are an autonomous MCA Form-Filling AI Engine.
Your task is to map source extracted document data to target form fields according to the Form Schema.

TARGET FORM: {form_schema.get('form_name', 'Form')}
GOVERNING LAW: {form_schema.get('governing_law', 'Companies Act')}

TARGET FORM FIELDS:
{json.dumps(field_summaries, indent=2)}

AVAILABLE SOURCE EXTRACTED DATA:
{json.dumps(evidence_items, indent=2)}
{lexicon_section}
STRICT OPERATIONAL RULES:
1. ONLY populate a field if direct or strongly implied evidence is present in the source data.
2. For "select" or "radio" fields, the value MUST EXACTLY match one of the choices listed in the field's "options" list.
3. If information for a field is NOT present in the source data, set "status": "missing" and "value": null.
   DO NOT GUESS OR HALLUCINATE VALUES UNDER ANY CIRCUMSTANCES.
4. If data is conflicting or ambiguous, set "status": "ambiguous", "value": null, and explain in "reasoning".
5. Format dates strictly as DD/MM/YYYY.

6. Extract clean numbers without currency symbols unless requested.

Output strictly valid JSON with this structure:
{{
  "mappings": [
    {{
      "field_id": "<field_id>",
      "status": "populated" | "missing" | "ambiguous",
      "value": "<exact_value_or_null>",
      "confidence": 0.0 to 1.0,
      "reasoning": "<short justification>",
      "source_key": "<matching key from source data>"
    }}
  ]
}}"""

        raw_mappings = {}

        try:
            logger.info(f"[DynamicFormFiller] Calling legal_reasoning model for {len(fields)} fields...")
            parsed = call_llm_json("legal_reasoning", prompt, timeout=90)
            mappings_list = parsed.get("mappings", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
            for m in mappings_list:
                if isinstance(m, dict):
                    f_id = m.get("field_id")
                    if f_id:
                        raw_mappings[f_id] = m

            logger.info(f"[DynamicFormFiller] LLM mapped {len(raw_mappings)} fields successfully.")

        except Exception as e:
            logger.warning(f"[DynamicFormFiller] LLM semantic mapping call failed or timed out: {e}. Falling back to deterministic matching.")
            raw_mappings = self._deterministic_fallback_matching(fields, evidence_list)

        return raw_mappings

    @staticmethod
    def _clean_alpha(s: Any) -> str:
        if not s:
            return ""
        return "".join(c for c in str(s).lower() if c.isalnum())

    def _match_field_deterministically(
        self,
        f: Dict[str, Any],
        evidence_list: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Determines if an evidence item matches a target field with 100% precision.
        Prevents loose single-character substring collisions while reliably catching:
        - Exact ID matches (e.g. formnomgt14.main.field_1)
        - Short ID matches (e.g. field_1)
        - Canonical number matches (e.g. 1, 2a, 5g)
        - Exact normalized label matches
        - Standard MCA statutory aliases (CIN, Company Name, PAN, etc.)
        - Safe multi-word token overlap
        """
        BAD_VALUES = {None, "", "Unknown", "N/A", "Empty / N/A", "None", "null"}
        valid_evs = [ev for ev in evidence_list if ev.get("value") not in BAD_VALUES and str(ev.get("value")).strip() not in BAD_VALUES]
        if not valid_evs:
            return None

        f_id = f.get("id", "")
        f_short = f_id.split(".")[-1]
        f_canonical = str(f.get("canonical_no", "")).strip().lower()
        f_label = f.get("label", "")
        f_label_lower = f_label.lower()
        f_label_clean = self._clean_alpha(f_label)
        f_type = f.get("type", "text")

        # 1. Exact field ID match
        for ev in valid_evs:
            k = str(ev.get("key") or "")
            if k == f_id:
                return ev

        # 2. Short ID match (strip namespaces e.g. formnomgt14.main.field_1 -> field_1)
        for ev in valid_evs:
            k = str(ev.get("key") or "")
            k_short = k.split(".")[-1]
            if k_short == f_short and f_short not in ["", "main"]:
                return ev

        # 3. Canonical number match
        if f_canonical:
            for ev in valid_evs:
                k = str(ev.get("key") or "").strip().lower()
                k_clean = self._clean_alpha(k)
                if k == f_canonical or k == f"field_{f_canonical}" or k_clean == f"canonical{f_canonical}":
                    return ev

        # 4. Normalized exact label match
        if f_label_clean and len(f_label_clean) > 3:
            for ev in valid_evs:
                k = str(ev.get("key") or "")
                k_clean = self._clean_alpha(k)
                if k_clean == f_label_clean:
                    return ev

        # 5. Standard MCA Statutory Aliases
        # 5A. CIN
        is_cin = f_type == "cin" or f_short == "field_1" or "cin" in f_short.lower() or "corporate identity number" in f_label_lower or (" cin" in f_label_lower and "vaccine" not in f_label_lower)
        if is_cin:
            for ev in valid_evs:
                k_clean = self._clean_alpha(ev.get("key"))
                if k_clean in ["cin", "cinnumber", "corporateidentitynumber", "cinno"]:
                    return ev

        # 5B. Company Name
        is_comp = ("company name" in f_label_lower or "name of the company" in f_label_lower or "name of the indian company" in f_label_lower or (f_short == "field_2a" and "document" not in f_label_lower))
        if is_comp:
            for ev in valid_evs:
                k_clean = self._clean_alpha(ev.get("key"))
                if k_clean in ["companyname", "nameofthecompany", "nameoftheindiancompany", "nameofcompany"]:
                    return ev

        # 5C. PAN
        is_pan = f_type == "pan" or "permanent account number" in f_label_lower or (" pan" in f_label_lower and "company" not in f_label_lower)
        if is_pan:
            for ev in valid_evs:
                k_clean = self._clean_alpha(ev.get("key"))
                if k_clean in ["pan", "pannumber", "permanentaccountnumber", "panno"]:
                    return ev

        # 5D. Registered Office Address
        is_addr = "registered office" in f_label_lower or "address of the company" in f_label_lower
        if is_addr:
            for ev in valid_evs:
                k_clean = self._clean_alpha(ev.get("key"))
                if k_clean in ["registeredofficeaddress", "registeredaddress", "companyaddress", "address"]:
                    return ev

        # 5E. Email
        is_email = "email" in f_label_lower
        if is_email:
            for ev in valid_evs:
                k_clean = self._clean_alpha(ev.get("key"))
                if k_clean in ["email", "emailid", "emailaddress", "emailheadofinstitution", "emailofcontactperson"]:
                    return ev

        # 5F. GNL-2 Section 2(a) - Document being filed & 2(b) If others specify
        if "indicate the document being filed" in f_label_lower or (f_short == "field_2a" and "document" in f_label_lower):
            options = f.get("options") or []
            for ev in valid_evs:
                ev_val = str(ev.get("value") or "").strip()
                k_clean = self._clean_alpha(ev.get("key"))
                if "field_2a" in k_clean or "document" in k_clean or "filing" in k_clean or "indicate" in k_clean:
                    matched_opt = self._match_canonical_option(ev_val, options)
                    if matched_opt:
                        return {"key": ev.get("key"), "value": matched_opt}
                    else:
                        return {"key": ev.get("key"), "value": "Others"}

        if "if others, then specify" in f_label_lower or f_short == "field_2b":
            for ev in valid_evs:
                k_clean = self._clean_alpha(ev.get("key"))
                if "field_2b" in k_clean or "other" in k_clean or "specify" in k_clean or "documenttitle" in k_clean or "customdoc" in k_clean:
                    return ev

        # 6. High-Precision Token Overlap (Avoid loose 1-char / number matches)
        f_tokens = set(re.findall(r"[a-z0-9]{4,}", f_label_lower))
        if len(f_tokens) >= 2:
            for ev in valid_evs:
                k = str(ev.get("key") or "").lower()
                if len(k.strip()) < 4 or k.strip().isdigit():
                    continue
                k_tokens = set(re.findall(r"[a-z0-9]{4,}", k))
                if len(k_tokens) >= 2 and k_tokens.issubset(f_tokens):
                    return ev

        return None

    def _deterministic_mapping_pass(
        self,
        fields: List[Dict[str, Any]],
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Maps fields deterministically prior to LLM evaluation."""
        mappings = {}
        for f in fields:
            f_id = f["id"]
            matched_ev = self._match_field_deterministically(f, evidence_list)
            if matched_ev:
                val = matched_ev.get("value")
                mappings[f_id] = {
                    "field_id": f_id,
                    "status": "populated",
                    "value": val,
                    "confidence": 0.95,
                    "reasoning": f"Deterministic statutory field match from source key '{matched_ev.get('key')}'",
                    "source_key": matched_ev.get("key")
                }
        return mappings

    def _deterministic_fallback_matching(
        self,
        fields: List[Dict[str, Any]],
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Rule-based fallback matching if LLM is temporarily unreachable."""
        fallback = self._deterministic_mapping_pass(fields, evidence_list)
        for f in fields:
            f_id = f["id"]
            if f_id not in fallback:
                fallback[f_id] = {
                    "field_id": f_id,
                    "status": "missing",
                    "value": None,
                    "confidence": 0.0,
                    "reasoning": "No matching evidence found in source documents",
                    "source_key": None
                }
        return fallback

    # ─────────────────────────────────────────────────────────────────────────
    # Deterministic Guardrails: Validation & Canonical Option Matching
    # ─────────────────────────────────────────────────────────────────────────

    def _validate_and_normalize_values(
        self,
        fields: List[Dict[str, Any]],
        raw_mappings: Dict[str, Dict[str, Any]],
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Validates formats, types, and aligns options to canonical schema values.
        """
        validated = {}
        field_map = {f["id"]: f for f in fields}

        for f_id, field_def in field_map.items():
            raw = raw_mappings.get(f_id, {
                "status": "missing",
                "value": None,
                "confidence": 0.0,
                "reasoning": "Field not evaluated by mapper"
            })

            status = raw.get("status", "missing")
            value = raw.get("value")
            confidence = float(raw.get("confidence", 0.0))
            reasoning = raw.get("reasoning", "")
            source_key = raw.get("source_key")

            validation_info = {"is_valid": True, "error": None}

            if status == "populated" and value is not None:
                val_str = str(value).strip()
                f_type = field_def.get("type", "text")
                options = field_def.get("options")

                # 1. Canonical Option Normalization (Select / Radio)
                if options and f_type in ["select", "radio"]:
                    matched_option = self._match_canonical_option(val_str, options)
                    if matched_option:
                        value = matched_option
                    else:
                        validation_info = {
                            "is_valid": False,
                            "error": f"Value '{val_str}' is not in allowed options: {options}"
                        }
                        status = "validation_error"

                # 2. Type & Regex Guardrails
                elif f_type == "cin":
                    # Indian CIN format: U/L + 5 digits + 2 letters + 4 digits + 3 letters + 6 digits
                    cin_val = re.sub(r"\s+", "", val_str).upper()
                    if re.match(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$", cin_val):
                        value = cin_val
                    else:
                        validation_info = {"is_valid": False, "error": f"Invalid CIN format: '{val_str}'"}

                elif f_type == "pan":
                    pan_val = re.sub(r"\s+", "", val_str).upper()
                    if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", pan_val):
                        value = pan_val
                    else:
                        validation_info = {"is_valid": False, "error": f"Invalid PAN format: '{val_str}'"}

                elif f_type == "date":
                    normalized_date = self._normalize_date(val_str)
                    if normalized_date:
                        value = normalized_date
                    else:
                        validation_info = {"is_valid": False, "error": f"Invalid date format: '{val_str}'. Expected DD/MM/YYYY"}

                elif f_type == "number":
                    cleaned_num = re.sub(r"[^\d.-]", "", val_str)
                    try:
                        value = float(cleaned_num) if "." in cleaned_num else int(cleaned_num)
                    except ValueError:
                        validation_info = {"is_valid": False, "error": f"Value '{val_str}' cannot be parsed as a number"}

            validated[f_id] = {
                "field_id": f_id,
                "canonical_no": field_def.get("canonical_no", ""),
                "label": field_def.get("label", ""),
                "type": field_def.get("type", "text"),
                "status": status,
                "value": value,
                "confidence": confidence,
                "reasoning": reasoning,
                "source_evidence": self._find_source_evidence(source_key, evidence_list),
                "validation": validation_info
            }

        return validated

    @staticmethod
    def _match_canonical_option(val: str, options: List[str]) -> Optional[str]:
        """Case-insensitive and fuzzy token matching to canonical schema option."""
        val_clean = val.strip().lower()
        
        # Exact case-insensitive match
        for opt in options:
            if opt.strip().lower() == val_clean:
                return opt

        # Token subset match (e.g. "appointment at agm" -> "Appointment/ Re-appointment in AGM")
        val_tokens = set(re.findall(r"\w+", val_clean))
        best_match = None
        best_overlap = 0

        for opt in options:
            opt_tokens = set(re.findall(r"\w+", opt.lower()))
            overlap = len(val_tokens & opt_tokens)
            if overlap > best_overlap and overlap >= max(2, len(val_tokens) // 2):
                best_overlap = overlap
                best_match = opt

        return best_match

    @staticmethod
    def _normalize_date(date_str: str) -> Optional[str]:
        """Normalizes various standard and alphanumeric date formats (e.g. '24th april 2025') to DD/MM/YYYY."""
        return parse_and_normalize_date(date_str)

    @staticmethod
    def _find_source_evidence(source_key: Optional[str], evidence_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not source_key:
            return None
        for ev in evidence_list:
            if ev.get("key") == source_key:
                return {
                    "document": ev.get("source_doc") or ev.get("document") or "Source Document",
                    "key": source_key,
                    "value": ev.get("value")
                }
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Deterministic Guardrails: DAG Dependency Resolution
    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_dag_dependencies(
        self,
        fields: List[Dict[str, Any]],
        validated_fields: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Evaluates depends_on rules top-down.
        If a parent field is missing or does not meet condition, dependent child fields
        are deactivated (is_active: false, status: 'inactive_by_rule').
        """
        field_map = {f["id"]: f for f in fields}
        active_state = {}

        for f in fields:
            f_id = f["id"]
            raw_field = validated_fields.get(f_id, {})
            field_data = raw_field.copy() if isinstance(raw_field, dict) else {"value": raw_field}
            dep = f.get("depends_on")

            if not dep:
                # Root level field — always active
                field_data["is_active"] = True
            else:
                parent_id = dep.get("field")
                parent_raw = validated_fields.get(parent_id)
                if not parent_raw and parent_id:
                    p_short = parent_id.split(".")[-1]
                    for k_v, v_v in validated_fields.items():
                        if k_v.endswith(f".{p_short}") or k_v == p_short:
                            parent_raw = v_v
                            break
                parent_data = parent_raw if isinstance(parent_raw, dict) else ({"value": parent_raw} if parent_raw is not None else None)

                if not parent_data or parent_data.get("value") is None:
                    # Parent has no value yet: if child was directly extracted with valid data, keep child active
                    has_direct_val = field_data.get("value") is not None and str(field_data.get("value")).strip() not in ["", "Unknown", "N/A"]
                    if has_direct_val:
                        field_data["is_active"] = True
                    else:
                        field_data["is_active"] = False
                        field_data["status"] = "inactive_by_rule"
                        field_data["value"] = None
                else:
                    operator = dep.get("operator", "equals")
                    target_val = dep.get("value")
                    parent_val = parent_data.get("value")

                    is_met = self._evaluate_condition(parent_val, operator, target_val)

                    field_data["is_active"] = is_met
                    if not is_met:
                        field_data["status"] = "inactive_by_rule"
                        field_data["value"] = None

            active_state[f_id] = field_data

        return active_state

    @staticmethod
    def _evaluate_condition(actual: Any, operator: str, expected: Any) -> bool:
        """Evaluates condition matching."""
        act_str = str(actual).strip().lower()
        if operator == "equals":
            return act_str == str(expected).strip().lower()
        elif operator == "not_equals":
            return act_str != str(expected).strip().lower()
        elif operator == "in":
            if isinstance(expected, list):
                return act_str in [str(x).strip().lower() for x in expected]
            return act_str in str(expected).strip().lower()
        elif operator == "not_empty":
            return bool(act_str)
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Execution Payload Compilation
    # ─────────────────────────────────────────────────────────────────────────

    def _compile_execution_payload(
        self,
        form_id: str,
        form_name: str,
        fields: List[Dict[str, Any]],
        active_fields: Dict[str, Dict[str, Any]],
        elapsed_sec: float
    ) -> Dict[str, Any]:
        """Compiles clean, audited form execution payload."""
        total_count = len(fields)
        active_count = sum(1 for f in active_fields.values() if f.get("is_active"))
        populated_count = sum(1 for f in active_fields.values() if f.get("is_active") and f.get("status") == "populated")
        
        # Missing required active fields
        missing_required = []
        for f in fields:
            f_id = f["id"]
            curr = active_fields.get(f_id, {})
            if curr.get("is_active") and f.get("required") and curr.get("status") != "populated":
                missing_required.append({
                    "field_id": f_id,
                    "canonical_no": f.get("canonical_no"),
                    "label": f.get("label"),
                    "reason": "Mandatory field requires source document evidence"
                })

        ambiguous_count = sum(1 for f in active_fields.values() if f.get("status") == "ambiguous")
        completion_pct = round((populated_count / max(1, active_count)) * 100, 1)

        return {
            "form_id": form_id,
            "form_name": form_name,
            "execution_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "execution_time_sec": round(elapsed_sec, 2),
            "summary": {
                "total_fields": total_count,
                "active_fields": active_count,
                "populated_count": populated_count,
                "missing_required_count": len(missing_required),
                "ambiguous_count": ambiguous_count,
                "completion_percentage": completion_pct
            },
            "fields": active_fields,
            "active_fields": [
                dict(id=fid, **fdata)
                for fid, fdata in active_fields.items()
                if fdata.get("is_active", True)
            ],
            "missing_required_fields": missing_required
        }
