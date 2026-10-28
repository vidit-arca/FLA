"""
Universal Field and Schema Normalizer for MCA IDP Studio.

Single Source of Truth for:
  - Canonical field type normalization
  - Conservative field-type guards (numeric counts, classification codes)
  - Option sanitization (filtering out instruction-kit text bleed)
  - Provenance tracking and logging of all schema adjustments
"""

import re
import copy
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("idp_studio.normalizer")

# Patterns identifying numeric count fields (e.g. "Number of resolution(s)", "Number of transferor company(s)")
COUNT_FIELD_PATTERNS = [
    re.compile(r'\b(?:total\s+)?number\s+of\s+(?:resolutions?|persons?|partners?|directors?|members?|shares?|days?|months?|entities?|attachments?|entries|rows|forms?|clauses?|charges?|offences?|(?:significant\s+)?beneficial\s+owners?|sbos?|(?:transferor\s+|transferee\s+)?compan(?:y|ies|y\(s\)|ies\(s\)|ys?))\b', re.IGNORECASE),
    re.compile(r'\bno\.\s*of\s+(?:resolutions?|persons?|partners?|directors?|members?|shares?|days?|months?|entities?|attachments?|entries|rows|forms?|clauses?|charges?|offences?|(?:significant\s+)?beneficial\s+owners?|sbos?|(?:transferor\s+|transferee\s+)?compan(?:y|ies|y\(s\)|ies\(s\)|ys?))\b', re.IGNORECASE),
    re.compile(r'\bcount\s+of\b', re.IGNORECASE),
]

# Patterns explicitly excluding statutory identifiers from numeric count guards
IDENTIFIER_EXCLUSION_PATTERN = re.compile(
    r'\b(?:identification|registration|membership|license|licence|folio|account|serial|certificate)\s+number\b|\b(?:din|cin|pan|srn|llpin)\b',
    re.IGNORECASE
)

# Patterns identifying classification / identity code fields
CODE_FIELD_PATTERNS = [
    re.compile(r'\bsub[\s\-]*class\b', re.IGNORECASE),
    re.compile(r'\bnic[\s\-]*code\b', re.IGNORECASE),
    re.compile(r'\bindustry[\s\-]*sub[\s\-]*class\b', re.IGNORECASE),
    re.compile(r'\bcin\b', re.IGNORECASE),
    re.compile(r'\bdin\b', re.IGNORECASE),
    re.compile(r'\bpan\b', re.IGNORECASE),
    re.compile(r'\bsrn\b', re.IGNORECASE),
    re.compile(r'\bfcrn\b', re.IGNORECASE),
    re.compile(r'\bllpin\b', re.IGNORECASE),
]

# Patterns identifying instruction kit header bleed in options
INSTRUCTION_HEADER_PATTERNS = [
    re.compile(r'^(?:resolution\(s\)|type\s+of\s+resolution|attachment\(s\)|instruction(?:\s+kit)?|annexure|table\s+[0-9]+|form\s+no\.?)$', re.IGNORECASE),
    re.compile(r'^type\s+of\s+al+otment\s+of\s+securities$', re.IGNORECASE),
]

# Max acceptable length for a valid dropdown / radio option title
MAX_OPTION_TEXT_LENGTH = 75


class FieldNormalizer:
    """
    Stateless, conservative normalizer ensuring every field and option
    in an MCA template conforms to strict statutory data structures.
    """

    @classmethod
    def normalize_field(cls, field_def: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Normalizes a single field definition.
        Returns (normalized_field_dict, list_of_correction_audit_logs).
        Preserves original fields and records modifications in 'provenance'.
        """
        f = copy.deepcopy(field_def)
        corrections: List[Dict[str, Any]] = []

        fid = f.get("id") or "unassigned_field"
        label = str(f.get("label") or "").strip()
        orig_type = str(f.get("type") or "text").lower().strip()
        orig_options = f.get("options")

        # 1. Standardize base type enum
        normalized_type = orig_type
        if "date" in orig_type:
            normalized_type = "date"
        elif "select" in orig_type or "dropdown" in orig_type:
            normalized_type = "select"
        elif "radio" in orig_type:
            normalized_type = "radio"
        elif "table" in orig_type:
            normalized_type = "table"
        elif "textarea" in orig_type:
            normalized_type = "textarea"
        elif "number" in orig_type or "numeric" in orig_type or "integer" in orig_type:
            normalized_type = "number"
        elif orig_type not in ["text", "number", "date", "select", "radio", "textarea", "file", "email", "cin", "pan", "din", "table"]:
            normalized_type = "text"

        # 2. Conservative Guard A: Numeric Count Fields (e.g. "Number of resolution(s)", "Number of person(s)")
        is_count_field = (
            any(p.search(label) for p in COUNT_FIELD_PATTERNS)
            and not IDENTIFIER_EXCLUSION_PATTERN.search(label)
            and "director_identification_number" not in fid
        )
        if is_count_field and normalized_type != "table":
            if normalized_type != "number":
                corrections.append({
                    "field_id": fid,
                    "field_label": label,
                    "rule": "count_field_enforce_number",
                    "before_type": normalized_type,
                    "after_type": "number",
                    "reason": "Field label indicates a count/cardinality requirement."
                })
                normalized_type = "number"

            # Inspect options: Count fields should not have multi-sentence text options
            if orig_options and isinstance(orig_options, list):
                has_text_bleed = any(
                    isinstance(o, str) and not o.strip().isdigit() and len(o.strip()) > 5
                    for o in orig_options
                )
                if has_text_bleed:
                    rejected = [str(o) for o in orig_options]
                    corrections.append({
                        "field_id": fid,
                        "field_label": label,
                        "rule": "reject_instruction_bleed_in_count_options",
                        "rejected_options": rejected,
                        "reason": "Count fields must not retain instruction-kit text bleed in options."
                    })
                    f["options"] = None

        # 3. Conservative Guard B: Code / Sub-Class / SRN Fields (e.g. "Search and select industry sub-class")
        is_code_field = any(p.search(label) for p in CODE_FIELD_PATTERNS)
        if is_code_field and normalized_type in ["select", "radio"]:
            # If options are spurious boolean echoes (e.g. ['Yes'] or ['Yes', 'Type of Company'])
            if orig_options and isinstance(orig_options, list):
                opts_lower = [str(o).lower().strip() for o in orig_options]
                if set(opts_lower).issubset({"yes", "no", "type of company", "ifsc company"}):
                    corrections.append({
                        "field_id": fid,
                        "field_label": label,
                        "rule": "code_field_reject_spurious_boolean_options",
                        "rejected_options": orig_options,
                        "before_type": normalized_type,
                        "after_type": "text",
                        "reason": "Classification code fields (NIC/SRN) must not be rendered as boolean toggles."
                    })
                    normalized_type = "text"
                    f["options"] = None

        # 4. Conservative Guard C: Option Text Sanity Filter for genuine Select / Radio fields
        sanitized_options: Optional[List[Any]] = None
        current_options = f.get("options")
        if normalized_type in ["select", "radio"] and current_options:
            if isinstance(current_options, list):
                valid_opts = []
                for opt in current_options:
                    opt_str = str(opt).strip()
                    # Filter out instruction kit header row bleed
                    if any(hp.search(opt_str) for hp in INSTRUCTION_HEADER_PATTERNS):
                        # Safeguard legitimate MCA registration/filing use-case options (e.g. "Registration of" -> "Resolution(s)")
                        if re.search(r'\b(?:registration|filing)\s+of\b', label, re.IGNORECASE) and opt_str.lower().startswith("resolution"):
                            valid_opts.append(opt)
                            continue
                        corrections.append({
                            "field_id": fid,
                            "field_label": label,
                            "rule": "reject_instruction_header_option",
                            "rejected_option": opt_str,
                            "reason": "Option matches an instruction kit header row artifact."
                        })
                        continue

                    # Filter out instruction sentences or excessively long text
                    if len(opt_str) > MAX_OPTION_TEXT_LENGTH:
                        corrections.append({
                            "field_id": fid,
                            "field_label": label,
                            "rule": "reject_oversized_instruction_option",
                            "rejected_option": opt_str[:60] + "...",
                            "reason": f"Option exceeds maximum length of {MAX_OPTION_TEXT_LENGTH} chars."
                        })
                        continue
                    
                    # Filter out options that merely repeat instructional markers
                    if opt_str.endswith(".") and len(opt_str.split()) > 6:
                        corrections.append({
                            "field_id": fid,
                            "field_label": label,
                            "rule": "reject_sentence_instruction_option",
                            "rejected_option": opt_str,
                            "reason": "Option appears to be an instructional sentence."
                        })
                        continue

                    valid_opts.append(opt)

                if len(valid_opts) < 2:
                    corrections.append({
                        "field_id": fid,
                        "field_label": label,
                        "rule": "convert_insufficient_options_to_text",
                        "before_type": normalized_type,
                        "after_type": "text",
                        "reason": f"Insufficient valid options remaining ({len(valid_opts)}) for select/radio field."
                    })
                    normalized_type = "text"
                    sanitized_options = None
                else:
                    sanitized_options = valid_opts
            else:
                sanitized_options = [str(current_options)]

        f["type"] = normalized_type
        if normalized_type in ["select", "radio"]:
            f["options"] = sanitized_options
        elif normalized_type not in ["table"]:
            f["options"] = None

        # Track provenance if any correction occurred
        if corrections:
            f["provenance"] = {
                "original_type": orig_type,
                "original_options": orig_options,
                "normalization_applied": True,
                "corrections": corrections
            }
            for c in corrections:
                logger.info(f"[Normalizer] {fid}: {c['rule']} ({c['reason']})")

        return f, corrections

    @classmethod
    def normalize_schema(cls, schema: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Normalizes all fields within a form schema and returns (normalized_schema, audit_trail).
        """
        normalized_schema = copy.deepcopy(schema)
        all_corrections: List[Dict[str, Any]] = []

        fields = normalized_schema.get("fields", [])
        clean_fields = []

        for f in fields:
            norm_f, f_corrections = cls.normalize_field(f)
            clean_fields.append(norm_f)
            all_corrections.extend(f_corrections)

        normalized_schema["fields"] = clean_fields
        if all_corrections:
            normalized_schema["normalization_audit"] = {
                "total_corrections": len(all_corrections),
                "timestamp": None  # Will be populated by caller if persisted
            }

        return normalized_schema, all_corrections
