"""
Stage 6 — Dynamic Form Generator
Generates the final structured schema JSON consumed by IDP Studio, FormTemplateViewer.jsx,
and the FormFiller DAG engine.
"""

import re
from typing import List, Dict, Any
from .stage4_dag_engine import ConnectedDagNode
from .stage5_validator import ValidationReport


class Stage6FormGenerator:
    """
    Serializes validated DAG nodes into production form schema JSON.
    """

    def generate(
        self,
        form_name: str,
        governing_law: str,
        nodes: List[ConnectedDagNode],
        report: ValidationReport
    ) -> Dict[str, Any]:
        form_slug = re.sub(r'[^a-z0-9]+', '', form_name.lower()) or "form"

        fields_payload = []
        for n in nodes:
            f_data = {
                "id": n.id,
                "canonical_no": n.canonical_no,
                "label": n.label,
                "type": n.type,
                "options": list(n.options),
                "required": n.required,
                "section": n.section,
                "depends_on": n.depends_on,
                "validation_rules": getattr(n, "validation_rules", []),
                "is_prefilled": getattr(n, "is_prefilled", False),
                "prefill_source": getattr(n, "prefill_source", None)
            }
            if n.type == "table":
                f_data["table_archetype"] = getattr(n, "table_archetype", "web_dynamic_grid")
                f_data["repeat_count_field"] = getattr(n, "repeat_count_field", None)
                f_data["min_rows"] = getattr(n, "min_rows", 1)
                f_data["max_rows"] = getattr(n, "max_rows", 10)
                f_data["columns"] = getattr(n, "columns", [])
                f_data["row_template_fields"] = getattr(n, "row_template_fields", [])
                if getattr(n, "table_metadata", None):
                    f_data["table_metadata"] = n.table_metadata
            fields_payload.append(f_data)

        return {
            "form_id": form_slug,
            "form_name": form_name,
            "template_name": form_name,
            "governing_law": governing_law,
            "version": "2.0.0",
            "fields": fields_payload,
            "validation_report": {
                "ok": report.ok,
                "errors": report.errors,
                "warnings": report.warnings,
                "metrics": report.metrics
            }
        }
