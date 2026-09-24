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

        # 1. Run Semantic Mapping via LLM (incorporating context & dynamic lexicon)
        raw_mappings = self._semantic_mapping_llm(form_schema, evidence_list, context=context)

        # 2. Inject confirmed HITL branch selections into raw_mappings
        if context and context.get("confirmed_branch"):
            confirmed_branch = context["confirmed_branch"]
            for f in fields:
                fid = f["id"].lower()
                if "nature_of_appointment" in fid or "natureofappointment" in fid:
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
            logger.info(f"[DynamicFormFiller] Calling {self.model} for {len(fields)} fields...")
            resp = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.05, "num_predict": 3000}
                },
                timeout=90
            )
            resp.raise_for_status()
            res_json = resp.json()
            raw_text = res_json.get("response", "").strip()

            parsed = json.loads(raw_text)
            mappings_list = parsed.get("mappings", [])
            for m in mappings_list:
                f_id = m.get("field_id")
                if f_id:
                    raw_mappings[f_id] = m

            logger.info(f"[DynamicFormFiller] LLM mapped {len(raw_mappings)} fields successfully.")

        except Exception as e:
            logger.warning(f"[DynamicFormFiller] LLM semantic mapping call failed or timed out: {e}. Falling back to deterministic matching.")
            raw_mappings = self._deterministic_fallback_matching(fields, evidence_list)

        return raw_mappings

    def _deterministic_fallback_matching(
        self,
        fields: List[Dict[str, Any]],
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Rule-based fallback matching if LLM is temporarily unreachable."""
        fallback = {}
        for f in fields:
            f_id = f["id"]
            label_lower = f["label"].lower()
            matched_ev = None

            for ev in evidence_list:
                k = str(ev.get("key") or "").lower()
                if k in label_lower or label_lower in k:
                    matched_ev = ev
                    break

            if matched_ev:
                val = matched_ev.get("value")
                fallback[f_id] = {
                    "field_id": f_id,
                    "status": "populated",
                    "value": val,
                    "confidence": 0.7,
                    "reasoning": "Fallback deterministic key-substring match",
                    "source_key": matched_ev.get("key")
                }
            else:
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
        """Normalizes various date formats to DD/MM/YYYY."""
        cleaned = re.sub(r"[^\d/-]", "/", date_str.strip())
        patterns = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"]
        for p in patterns:
            try:
                dt = datetime.datetime.strptime(cleaned, p)
                # Expand 2-digit years if needed
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                return dt.strftime("%d/%m/%Y")
            except ValueError:
                continue
        return None

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
                parent_data = parent_raw if isinstance(parent_raw, dict) else ({"value": parent_raw} if parent_raw is not None else None)

                if not parent_data or parent_data.get("value") is None:
                    # Parent has no value yet -> child inactive
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
            "missing_required_fields": missing_required
        }
