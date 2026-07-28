"""
demo.py — CLI entry point for the Intelligent DOM Learning Engine PoC.

Runs the full pipeline:
    OCR Markdown → Parse → Build DOM → Build Relationships → Export

Usage:
    cd automation_engine/modules/idp_studio
    python -m dom_learner.demo

    # or with custom paths:
    python -m dom_learner.demo --input path/to/file.md --output path/to/output/

Outputs:
    output/logical_document_tree.json
    output/relationships.json
    output/tree.txt
    output/tree.html
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Resolve project paths so imports work when run from idp_studio/
_THIS_DIR = Path(__file__).resolve().parent
_IDP_STUDIO_DIR = _THIS_DIR.parent
if str(_IDP_STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(_IDP_STUDIO_DIR))

from dom_learner.engine.dom_builder import DOMBuilder
from dom_learner.engine.relationship_builder import RelationshipBuilder
from dom_learner.engine.dom_query import DOMQuery
from dom_learner.exporters.json_exporter import export_dom_json, export_relationships_json
from dom_learner.exporters.tree_exporter import export_tree_txt, export_tree_html


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_INPUT = _THIS_DIR / "Docs" / "ocr_output" / "AR_Financials_MSME_Disclosures.md"
_DEFAULT_OUTPUT = _THIS_DIR / "output"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(input_path: Path | None = None, output_dir: Path | None = None) -> None:
    """Run the full DOM Learning Engine pipeline."""

    input_path = input_path or _DEFAULT_INPUT
    output_dir = output_dir or _DEFAULT_OUTPUT

    # -- Setup logging --
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("dom_learner.demo")

    log.info("=" * 70)
    log.info("   Intelligent DOM Learning Engine — PoC Demo")
    log.info("=" * 70)
    log.info("Input:  %s", input_path)
    log.info("Output: %s", output_dir)

    if not input_path.exists():
        log.error("Input file not found: %s", input_path)
        sys.exit(1)

    t0 = time.perf_counter()

    # ---- Step 1: Build DOM ------------------------------------------------
    log.info("")
    log.info("── Step 1: Building Logical Document Tree ──")
    builder = DOMBuilder()
    document = builder.build(input_path)

    # ---- Step 2: Build Relationships --------------------------------------
    log.info("")
    log.info("── Step 2: Building Semantic Relationships ──")
    rel_builder = RelationshipBuilder()
    relationships = rel_builder.build(document)

    # ---- Step 3: Create Query API and run demos ---------------------------
    log.info("")
    log.info("── Step 3: DOM Query API Demo ──")
    q = DOMQuery(document)
    _run_query_demos(q, log)

    # ---- Step 4: Export ---------------------------------------------------
    log.info("")
    log.info("── Step 4: Exporting Outputs ──")
    output_dir.mkdir(parents=True, exist_ok=True)

    export_dom_json(document, output_dir / "logical_document_tree.json")
    export_relationships_json(relationships, output_dir / "relationships.json")
    export_tree_txt(document, output_dir / "tree.txt")

    stats_summary = _stats_string(q, relationships)
    export_tree_html(document, output_dir / "tree.html", stats=stats_summary)

    # ---- Summary ----------------------------------------------------------
    elapsed = time.perf_counter() - t0
    log.info("")
    log.info("=" * 70)
    log.info("   DONE in %.2fs", elapsed)
    log.info("=" * 70)
    log.info("")
    log.info("Node counts:")
    for ntype, count in sorted(q.summary().items()):
        log.info("    %-12s  %d", ntype, count)
    log.info("")
    log.info("Relationship counts:")
    rel_counts: dict[str, int] = {}
    for r in relationships:
        rel_counts[r.rel_type.value] = rel_counts.get(r.rel_type.value, 0) + 1
    for rtype, count in sorted(rel_counts.items()):
        log.info("    %-24s  %d", rtype, count)
    log.info("")
    log.info("Generated files:")
    for f in sorted(output_dir.iterdir()):
        size = f.stat().st_size / 1024
        log.info("    %s  (%.1f KB)", f.name, size)


def _run_query_demos(q: DOMQuery, log: logging.Logger) -> None:
    """Demonstrate the DOM Query API with some example queries."""

    # Find a specific row
    rows = q.find_row("Trade payables")
    if rows:
        log.info("  find_row('Trade payables') → found %d match(es)", len(rows))
        for row in rows[:2]:
            log.info("    %s", row)
            path = q.get_structural_path(row)
            log.info("    Path: %s", " → ".join(p.get("text", p["type"])[:30] for p in path))
    else:
        log.info("  find_row('Trade payables') → no matches")

    # Find a cell by row + column
    cell = q.find_cell(row_text="Trade payables", column_header="March 31, 2025")
    if cell:
        log.info("  find_cell(row='Trade payables', col='March 31, 2025') → %s = '%s'",
                 cell.id, cell.text)
    else:
        log.info("  find_cell(row='Trade payables', col='March 31, 2025') → not found")

    # Find all sections
    sections = q.find_sections()
    log.info("  find_sections() → %d sections", len(sections))
    for s in sections[:5]:
        log.info("    %s", s)

    # Find notes
    notes = q.find_note("4")
    log.info("  find_note('4') → %d note reference(s)", len(notes))

    # Find tables
    tables = q.find_tables()
    log.info("  find_tables() → %d tables", len(tables))


def _stats_string(q: DOMQuery, relationships: list) -> str:
    """Format a stats summary for the HTML export."""
    parts = []
    summary = q.summary()
    total = sum(summary.values())
    parts.append(f"{total} nodes")
    parts.append(f"{len(relationships)} relationships")
    for ntype, count in sorted(summary.items()):
        parts.append(f"{count} {ntype}s")
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    """Parse CLI arguments and run."""
    parser = argparse.ArgumentParser(
        description="Intelligent DOM Learning Engine — PoC Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=None,
        help=f"Path to the OCR markdown file (default: {_DEFAULT_INPUT.name})",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help=f"Output directory (default: {_DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    main(args.input, args.output)


if __name__ == "__main__":
    _cli()
