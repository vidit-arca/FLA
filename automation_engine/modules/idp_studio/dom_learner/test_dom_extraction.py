"""
test_dom_extraction.py — Validates the DOM pipeline by extracting 10 key variables.

Queries the DOM for specific financial line items and exports results to an
Excel file with columns: Variable, DOM Path, FY2025 Value, FY2024 Value, Status.

This script proves the DOM is navigable and values are extractable via
structure-based queries rather than coordinate-based extraction.

Usage:
    cd automation_engine/modules/idp_studio
    python -m dom_learner.test_dom_extraction
"""

from __future__ import annotations

import csv
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_IDP_STUDIO_DIR = _THIS_DIR.parent
if str(_IDP_STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(_IDP_STUDIO_DIR))

from dom_learner.engine.dom_builder import DOMBuilder
from dom_learner.engine.dom_query import DOMQuery
from dom_learner.models import DOMNode, NodeType

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_INPUT = _THIS_DIR / "Docs" / "ocr_output" / "AR_Financials_MSME_Disclosures.md"
_DEFAULT_OUTPUT = _THIS_DIR / "output" / "dom_extraction_test.xlsx"

# Variables to extract — these are the test cases
VARIABLES = [
    "Partners' contribution",
    "Partners' current account",
    "Trade payables",
    "Other current liabilities",
    "Short-term provisions",
    "Trade receivables",
    "Cash and bank balances",
    "Revenue from operations",
    "Employee benefits expense",
    "Professional & Consultancy Charges",
]


# ---------------------------------------------------------------------------
# Extraction result
# ---------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    variable: str
    dom_path: str
    depth: int
    node_id: str
    section: str
    table_id: str
    row_id: str
    fy2025_value: str
    fy2024_value: str
    status: str  # FOUND / PARTIAL / NOT_FOUND


# ---------------------------------------------------------------------------
# Smart variable extractor
# ---------------------------------------------------------------------------

def _looks_like_number(val: str) -> bool:
    """Return True if val looks like a financial number."""
    cleaned = val.replace(",", "").replace(".", "").replace("-", "").strip()
    return bool(cleaned and cleaned.isdigit())


def _find_row_by_label(q: DOMQuery, label: str) -> DOMNode | None:
    """Find a row whose cells contain *label* (case-insensitive substring).

    The standard `q.find_row()` uses row_label metadata which is the first
    cell — but in this document the first cell is often just "(a)", "(b)", etc.
    So we also search all cells within rows for the label text.
    
    If multiple rows match, we use a scoring heuristic to pick the best one.
    This helps bypass OCR artifacts in the main tables by preferring the 
    cleaner detailed note tables.
    """
    label_lower = label.strip().lower()

    # Get all candidate rows
    matches = q.find_row(label)
    if not matches:
        cell_matches = q.find_by_text(label, node_type=NodeType.CELL)
        matches = [c.parent for c in cell_matches if c.parent and c.parent.node_type == NodeType.ROW]

    if not matches:
        return None

    best_row = None
    best_score = -999

    for row in matches:
        fy25, fy24 = _get_value_cells(row)
        score = 0

        # Prefer rows that successfully extracted two values
        if fy25 and fy24:
            score += 10
            
            # Penalize non-numeric values heavily
            if not _looks_like_number(fy25) or not _looks_like_number(fy24):
                score -= 100
            
            # Penalize values that are actually date headers from note tables
            if "march" in fy25.lower() or "march" in fy24.lower():
                score -= 50
                
            # Penalize OCR artifact values (e.g. dots instead of commas)
            if "." in fy25 or "." in fy24:
                score -= 5

        # Prefer exact matches or aggregated totals
        row_text = row.text.lower()
        if label_lower == row_text or f"| {label_lower}" in row_text:
            score += 5
        elif f"total {label_lower}" in row_text:
            score += 8
        elif f"{label_lower} (net)" in row_text:
            score += 8

        if score > best_score:
            best_score = score
            best_row = row

    return best_row


def _get_value_cells(row: DOMNode) -> tuple[str, str]:
    """Extract FY2025 and FY2024 values from a row.

    Strategy: the last two cells with numeric-looking content are typically
    the current year and previous year values.  We also look at column
    headers containing "2025" and "2024".
    """
    cells = [c for c in row.children if c.node_type == NodeType.CELL]

    fy2025 = ""
    fy2024 = ""

    # Strategy 1: look for cells whose column header contains year
    for cell in cells:
        col_header = cell.metadata.get("column_header", "").lower()
        text = cell.text.strip()
        if not text or text in ("", "(empty)"):
            continue

        if "2025" in col_header:
            fy2025 = text
        elif "2024" in col_header:
            fy2024 = text

    # Strategy 2: if headers don't have year, use positional (last two numeric cells)
    if not fy2025 and not fy2024:
        numeric_cells = []
        for cell in cells:
            text = cell.text.strip()
            # check if text looks numeric (contains digits and commas)
            cleaned = text.replace(",", "").replace(".", "").replace("-", "").replace(" ", "")
            if cleaned and any(c.isdigit() for c in cleaned):
                numeric_cells.append(cell)

        if len(numeric_cells) >= 2:
            fy2025 = numeric_cells[-2].text.strip()
            fy2024 = numeric_cells[-1].text.strip()
        elif len(numeric_cells) == 1:
            fy2025 = numeric_cells[0].text.strip()

    return fy2025, fy2024


def _format_dom_path(q: DOMQuery, node: DOMNode) -> str:
    """Format the structural path for display."""
    path = q.get_structural_path(node)
    parts = []
    for p in path:
        label = p.get("label") or p.get("text") or p["type"]
        # truncate long labels
        if len(label) > 40:
            label = label[:37] + "..."
        parts.append(f"{p['type']}({label})")
    return " → ".join(parts)


def extract_variables(q: DOMQuery) -> list[ExtractionResult]:
    """Query the DOM for all test variables and return results."""
    results: list[ExtractionResult] = []

    for var_name in VARIABLES:
        row = _find_row_by_label(q, var_name)

        if row is None:
            results.append(ExtractionResult(
                variable=var_name,
                dom_path="—",
                depth=0,
                node_id="—",
                section="—",
                table_id="—",
                row_id="—",
                fy2025_value="—",
                fy2024_value="—",
                status="NOT_FOUND",
            ))
            continue

        # Get values
        fy2025, fy2024 = _get_value_cells(row)

        # Get structural context
        dom_path = _format_dom_path(q, row)
        section_node = row.section
        table_node = row.table

        status = "FOUND" if fy2025 else "PARTIAL"

        results.append(ExtractionResult(
            variable=var_name,
            dom_path=dom_path,
            depth=row.depth,
            node_id=row.id,
            section=section_node.text[:60] if section_node else "—",
            table_id=table_node.id if table_node else "—",
            row_id=row.id,
            fy2025_value=fy2025,
            fy2024_value=fy2024,
            status=status,
        ))

    return results


# ---------------------------------------------------------------------------
# Excel export (using openpyxl if available, falls back to CSV)
# ---------------------------------------------------------------------------

def _export_excel(results: list[ExtractionResult], output_path: Path) -> Path:
    """Export results to Excel. Falls back to CSV if openpyxl is not installed."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        return _export_xlsx(results, output_path)
    except ImportError:
        # fallback to CSV
        csv_path = output_path.with_suffix(".csv")
        return _export_csv(results, csv_path)


def _export_xlsx(results: list[ExtractionResult], output_path: Path) -> Path:
    """Export to a styled Excel file."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DOM Extraction Test"

    # --- Styles ---
    header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    found_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    partial_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    not_found_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # --- Title row ---
    ws.merge_cells("A1:I1")
    title_cell = ws["A1"]
    title_cell.value = "DOM Learning Engine — Extraction Test Results"
    title_cell.font = Font(name="Calibri", bold=True, size=14, color="2F5496")
    title_cell.alignment = Alignment(horizontal="center")

    # --- Blank row ---
    ws.append([])

    # --- Headers ---
    headers = [
        "Variable",
        "Status",
        "FY2025 Value",
        "FY2024 Value",
        "DOM Depth",
        "Node ID",
        "Section",
        "Table ID",
        "DOM Path / Location",
    ]
    ws.append(headers)
    for col_idx, _ in enumerate(headers, start=1):
        cell = ws.cell(row=3, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = thin_border

    # --- Data rows ---
    for i, r in enumerate(results, start=4):
        row_data = [
            r.variable,
            r.status,
            r.fy2025_value,
            r.fy2024_value,
            r.depth,
            r.node_id,
            r.section,
            r.table_id,
            r.dom_path,
        ]
        ws.append(row_data)

        # status coloring
        status_cell = ws.cell(row=i, column=2)
        if r.status == "FOUND":
            status_cell.fill = found_fill
        elif r.status == "PARTIAL":
            status_cell.fill = partial_fill
        else:
            status_cell.fill = not_found_fill

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=i, column=col_idx)
            cell.border = thin_border
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    # --- Summary row ---
    ws.append([])
    summary_row = len(results) + 5
    found = sum(1 for r in results if r.status == "FOUND")
    partial = sum(1 for r in results if r.status == "PARTIAL")
    not_found = sum(1 for r in results if r.status == "NOT_FOUND")

    ws.cell(row=summary_row, column=1, value="Summary").font = Font(bold=True)
    ws.cell(row=summary_row + 1, column=1, value=f"Found: {found}/{len(results)}")
    ws.cell(row=summary_row + 1, column=1).fill = found_fill
    ws.cell(row=summary_row + 2, column=1, value=f"Partial: {partial}/{len(results)}")
    ws.cell(row=summary_row + 2, column=1).fill = partial_fill
    ws.cell(row=summary_row + 3, column=1, value=f"Not Found: {not_found}/{len(results)}")
    ws.cell(row=summary_row + 3, column=1).fill = not_found_fill

    # --- Column widths ---
    col_widths = [35, 12, 18, 18, 10, 12, 40, 12, 80]
    for i, width in enumerate(col_widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = width

    # --- Save ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    return output_path


def _export_csv(results: list[ExtractionResult], output_path: Path) -> Path:
    """Fallback CSV export."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Variable", "Status", "FY2025 Value", "FY2024 Value",
            "DOM Depth", "Node ID", "Section", "Table ID", "DOM Path",
        ])
        for r in results:
            writer.writerow([
                r.variable, r.status, r.fy2025_value, r.fy2024_value,
                r.depth, r.node_id, r.section, r.table_id, r.dom_path,
            ])
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("dom_learner.test")

    log.info("=" * 70)
    log.info("   DOM Extraction Test — 10 Variables")
    log.info("=" * 70)

    # Build DOM
    log.info("Building DOM from %s...", _DEFAULT_INPUT.name)
    t0 = time.perf_counter()
    document = DOMBuilder().build(_DEFAULT_INPUT)
    q = DOMQuery(document)
    log.info("DOM built in %.3fs (%d nodes)", time.perf_counter() - t0, sum(q.summary().values()))

    # Extract variables
    log.info("")
    log.info("Extracting %d variables...", len(VARIABLES))
    log.info("-" * 70)
    results = extract_variables(q)

    # Print results to console
    for r in results:
        icon = "✅" if r.status == "FOUND" else ("⚠️" if r.status == "PARTIAL" else "❌")
        log.info(
            "  %s %-40s FY2025=%-15s FY2024=%-15s [%s]",
            icon, r.variable, r.fy2025_value or "—", r.fy2024_value or "—", r.node_id,
        )

    # Summary
    found = sum(1 for r in results if r.status == "FOUND")
    partial = sum(1 for r in results if r.status == "PARTIAL")
    not_found = sum(1 for r in results if r.status == "NOT_FOUND")

    log.info("-" * 70)
    log.info("  ✅ Found: %d/%d   ⚠️ Partial: %d/%d   ❌ Not Found: %d/%d",
             found, len(results), partial, len(results), not_found, len(results))

    # Export to Excel
    log.info("")
    output_path = _export_excel(results, _DEFAULT_OUTPUT)
    log.info("Exported results → %s", output_path)
    log.info("=" * 70)


if __name__ == "__main__":
    main()
