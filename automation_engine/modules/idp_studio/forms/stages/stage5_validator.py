"""
Stage 5 — Validation and Review Gate
Performs pre-commit integrity audits: option completeness, dependency reachability,
no orphan references, no instruction bleed, and no dropped statutory rows.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from .stage4_dag_engine import ConnectedDagNode
from .stage2_structure import RawStatutoryRow


@dataclass
class ValidationReport:
    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class Stage5Validator:
    """
    Automated statutory quality gate ensuring template completeness and logical consistency.
    """

    def validate(
        self,
        nodes: List[ConnectedDagNode],
        raw_rows: List[RawStatutoryRow],
        branches: List[Dict[str, Any]]
    ) -> ValidationReport:
        errors = []
        warnings = []
        node_ids = [n.id for n in nodes]
        id_set = set()

        # 1. Duplicate canonical IDs
        for nid in node_ids:
            if nid in id_set:
                errors.append(f"Duplicate canonical ID detected: {nid}")
            id_set.add(nid)

        id_to_node = {n.id: n for n in nodes}

        # 2. Orphan dependencies & Option completeness
        for n in nodes:
            dep = n.depends_on
            if dep:
                parent_id = dep.get("field")
                if not parent_id or parent_id not in id_set:
                    errors.append(f"Orphan dependency: Node {n.id} points to missing parent {parent_id}")
                else:
                    # Option completeness check
                    parent_node = id_to_node[parent_id]
                    target_val = dep.get("value")
                    target_list = target_val if isinstance(target_val, list) else [target_val]
                    for t in target_list:
                        s_t = str(t).strip().lower()
                        if parent_node.options and not any(s_t == str(o).strip().lower() for o in parent_node.options):
                            warnings.append(
                                f"Option mismatch: Node {n.id} expects parent {parent_id} to be '{t}', "
                                f"but parent options are {parent_node.options}"
                            )

        # 3. Instruction bleed check
        for n in nodes:
            lbl = n.label.lower()
            if "field no." in lbl or "field name" in lbl:
                errors.append(f"Instruction bleed into label in field {n.id}: {n.label}")

        # 4. Unnumbered statutory rows retained
        unnum_raw = [r for r in raw_rows if not r.canonical_no and len(r.field_name) > 4]
        unnum_nodes = [n for n in nodes if not n.canonical_no]
        if len(unnum_nodes) < len(unnum_raw):
            warnings.append(
                f"Unnumbered statutory row discrepancy: {len(unnum_raw)} in kit vs {len(unnum_nodes)} in schema."
            )

        metrics = {
            "total_raw_rows": len(raw_rows),
            "total_nodes": len(nodes),
            "conditional_nodes": sum(1 for n in nodes if n.depends_on),
            "branches_detected": len(branches)
        }

        return ValidationReport(
            ok=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metrics=metrics
        )
