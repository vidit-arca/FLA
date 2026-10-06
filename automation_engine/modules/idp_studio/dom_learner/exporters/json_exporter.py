"""
json_exporter.py — Serialize the DOM tree and relationships to JSON files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from dom_learner.models import DocumentNode
from dom_learner.engine.relationship_builder import Relationship

logger = logging.getLogger(__name__)


def export_dom_json(document: DocumentNode, output_path: Path) -> Path:
    """Write the full DOM tree to *output_path* as pretty-printed JSON.

    Returns the path written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = document.to_dict()

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    size_kb = output_path.stat().st_size / 1024
    logger.info("Exported DOM JSON → %s (%.1f KB)", output_path.name, size_kb)
    return output_path


def export_relationships_json(
    relationships: list[Relationship],
    output_path: Path,
) -> Path:
    """Write all relationships to *output_path* as pretty-printed JSON.

    Returns the path written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Group by relationship type for readability
    data = {
        "total_count": len(relationships),
        "by_type": {},
        "relationships": [r.to_dict() for r in relationships],
    }

    for r in relationships:
        key = r.rel_type.value
        data["by_type"][key] = data["by_type"].get(key, 0) + 1

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    size_kb = output_path.stat().st_size / 1024
    logger.info("Exported relationships JSON → %s (%.1f KB)", output_path.name, size_kb)
    return output_path
