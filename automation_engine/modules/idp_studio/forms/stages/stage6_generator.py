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
            fields_payload.append({
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
            })

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
