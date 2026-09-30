"""
Stage 4 — Rule & Dependency DAG Engine
Resolves canonical hierarchical field IDs, section branch inheritance, cross-field conditional triggers,
and executes Reverse Option Harvesting to guarantee that parent dropdowns/radios contain all child options.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from .stage3_instruction_ai import SemanticFieldDefinition


@dataclass
class ConnectedDagNode:
    id: str
    canonical_no: str
    label: str
    instructions: str
    type: str  # 'text' | 'number' | 'date' | 'radio' | 'select' | 'file' | 'table'
    options: List[str]
    required: bool
    section: str
    depends_on: Optional[Dict[str, Any]] = None
    physical_idx: int = 0
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


class Stage4DagEngine:
    """
    Constructs the statutory dependency DAG and executes Reverse Option Harvesting.
    """

    def process(
        self,
        semantic_fields: List[SemanticFieldDefinition],
        form_name: str,
        branches: List[Dict[str, Any]]
    ) -> List[ConnectedDagNode]:
        form_slug = re.sub(r'[^a-z0-9]+', '', form_name.lower()) or "form"
        nodes: List[ConnectedDagNode] = []
        slug_counts: Dict[str, int] = {}

        # 1. Build Canonical Hierarchical IDs
        canonical_map: Dict[str, Dict[str, str]] = {}  # { section_slug: { clean_canonical_no: field_id } }
        root_field_id: Optional[str] = None

        for sf in semantic_fields:
            c_no = sf.canonical_no
            sec = sf.section_slug

            # Generate base slug
            if c_no:
                base_slug = f"field_{re.sub(r'[^a-z0-9]+', '', c_no.lower())}"
            else:
                words = re.sub(r'[^a-zA-Z0-9\s]', '', sf.label).split()[:4]
                slug_suffix = '_'.join(w.lower() for w in words)
                base_slug = f"field_{slug_suffix}" if slug_suffix else "field_node"

            full_slug = f"{form_slug}.{sec}.{base_slug}"
            cnt = slug_counts.get(full_slug, 1)
            slug_counts[full_slug] = cnt + 1
            f_id = f"{full_slug}_{cnt}" if cnt > 1 else full_slug

            if sf.is_root_selector:
                root_field_id = f_id

            node = ConnectedDagNode(
                id=f_id,
                canonical_no=c_no,
                label=sf.label,
                instructions=sf.instructions,
                type=sf.field_type,
                options=list(sf.options),
                required=sf.required,
                section=sec,
                depends_on=None,
                physical_idx=sf.physical_idx,
                validation_rules=list(sf.validation_rules),
                is_prefilled=sf.is_prefilled,
                prefill_source=sf.prefill_source,
                table_archetype=sf.table_archetype,
                repeat_count_field=sf.repeat_count_field,
                columns=list(sf.columns),
                min_rows=sf.min_rows,
                max_rows=sf.max_rows,
                table_metadata=sf.table_metadata,
                row_template_fields=list(sf.row_template_fields)
            )
            nodes.append(node)

            if c_no:
                clean_no = re.sub(r'\s+', '', c_no.lower())
                canonical_map.setdefault(sec, {})[clean_no] = f_id

        # 2. Section Branch Dependency
        branch_opt_map = {f"section_{i+1}": b["option"] for i, b in enumerate(branches)}

        for node in nodes:
            sec = node.section
            sec_branch_opt = branch_opt_map.get(sec)
            if sec_branch_opt and root_field_id and node.id != root_field_id:
                node.depends_on = {
                    "field": root_field_id,
                    "operator": "equals",
                    "value": sec_branch_opt
                }

        # 3. Intra-section and Cross-field Trigger Resolution & Repeat Count Field Resolution
        for i, sf in enumerate(semantic_fields):
            node = nodes[i]

            # Resolve repeat_count_field to DAG node ID
            if node.repeat_count_field:
                clean_rep = re.sub(r'\s+', '', node.repeat_count_field.lower())
                parent_rep_id = canonical_map.get(node.section, {}).get(clean_rep)
                if not parent_rep_id:
                    for s_map in canonical_map.values():
                        if clean_rep in s_map:
                            parent_rep_id = s_map[clean_rep]
                            break
                if parent_rep_id:
                    node.repeat_count_field = parent_rep_id

            if sf.trigger_parent_ref:
                clean_ref = re.sub(r'\s+', '', sf.trigger_parent_ref.lower())
                
                # Look up parent in current section, then in any section
                parent_id = canonical_map.get(node.section, {}).get(clean_ref)
                if not parent_id:
                    for s_map in canonical_map.values():
                        if clean_ref in s_map:
                            parent_id = s_map[clean_ref]
                            break

                if parent_id and parent_id != node.id:
                    vals = sf.trigger_values
                    if len(vals) == 1:
                        node.depends_on = {
                            "field": parent_id,
                            "operator": "equals",
                            "value": vals[0]
                        }
                    elif len(vals) > 1:
                        node.depends_on = {
                            "field": parent_id,
                            "operator": "in",
                            "value": vals
                        }

        # 4. REVERSE OPTION HARVESTING (Critical Feature)
        id_to_node_map = {n.id: n for n in nodes}
        for node in nodes:
            if not node.depends_on:
                continue
            parent_id = node.depends_on.get("field")
            target_val = node.depends_on.get("value")
            if not parent_id or not target_val:
                continue

            parent_node = id_to_node_map.get(parent_id)
            if not parent_node:
                continue

            target_list = target_val if isinstance(target_val, list) else [target_val]

            # If parent options are boolean ['Yes', 'No'] but children depend on non-boolean values,
            # replace boolean with the harvested options
            is_non_boolean = any(str(v).lower() not in {"yes", "no"} for v in target_list)
            if is_non_boolean and set(o.lower() for o in parent_node.options) <= {"yes", "no"}:
                parent_node.options = []

            for val_str in target_list:
                s_val = str(val_str).strip()
                if s_val and s_val not in parent_node.options:
                    if not any(s_val.lower() == existing.lower() for existing in parent_node.options):
                        parent_node.options.append(s_val)

            # Ensure parent type is selectable if options exist
            if parent_node.options:
                if parent_node.type not in {"select", "radio"}:
                    parent_node.type = "radio" if len(parent_node.options) <= 4 else "select"

        return nodes
