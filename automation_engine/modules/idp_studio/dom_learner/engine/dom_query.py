"""
dom_query.py — Navigable query API for the Logical Document Tree.

This is the bridge between the static DOM and the future Selection Resolver /
Rule Learning Engine.  Think of it like ``document.querySelector()`` in the
browser DOM — except queries are over the *logical* structure of financial
or general documents.

Usage::

    dom = DOMBuilder().build(path)
    q   = DOMQuery(dom)

    # find by text
    q.find_by_text("Trade Payables")

    # find by type
    q.find_tables()
    q.find_sections()

    # structural queries
    q.find_cell(row_text="Trade Payables", column_header="March 31, 2025")
    q.find_row("Trade Payables")
    q.find_table_in_section("Balance Sheet")

    # navigation
    cell = q.find_cell(row_text="Trade Payables", column_header="March 31, 2025")
    cell.parent              # → RowNode
    cell.next_sibling        # → next cell in the row
    cell.previous_sibling    # → previous cell
    cell.section             # → parent SectionNode
    cell.table               # → parent TableNode

    # row-level
    q.get_previous_row(row)
    q.get_next_row(row)
    q.get_siblings(node)

    # note lookup
    q.find_note("4")
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from dom_learner.models import DOMNode, DocumentNode, NodeType

logger = logging.getLogger(__name__)


class DOMQuery:
    """Query interface over a ``DocumentNode`` tree.

    All ``find_*`` methods return lists (or ``None`` for singular lookups)
    and never raise on missing matches — they return empty results.
    """

    def __init__(self, document: DocumentNode) -> None:
        self._root = document
        # build lookup indices for fast queries
        self._by_id: dict[str, DOMNode] = {}
        self._by_type: dict[NodeType, list[DOMNode]] = {}
        self._index()

    def _index(self) -> None:
        """Build internal indices by walking the tree once."""
        for node in self._root.walk():
            self._by_id[node.id] = node
            self._by_type.setdefault(node.node_type, []).append(node)
        logger.debug("DOMQuery: indexed %d nodes", len(self._by_id))

    # ===== Lookup by ID / type =============================================

    def get_by_id(self, node_id: str) -> DOMNode | None:
        """Return the node with the given ID, or ``None``."""
        return self._by_id.get(node_id)

    def find_all(self, node_type: NodeType) -> list[DOMNode]:
        """Return all nodes of the given type."""
        return list(self._by_type.get(node_type, []))

    # ===== Convenience finders =============================================

    def find_sections(self) -> list[DOMNode]:
        """Return all SectionNodes."""
        return self.find_all(NodeType.SECTION)

    def find_tables(self) -> list[DOMNode]:
        """Return all TableNodes."""
        return self.find_all(NodeType.TABLE)

    def find_rows(self) -> list[DOMNode]:
        """Return all RowNodes."""
        return self.find_all(NodeType.ROW)

    def find_cells(self) -> list[DOMNode]:
        """Return all CellNodes."""
        return self.find_all(NodeType.CELL)

    # ===== Text search =====================================================

    def find_by_text(
        self,
        text: str,
        *,
        exact: bool = False,
        node_type: NodeType | None = None,
    ) -> list[DOMNode]:
        """Find nodes whose text contains (or exactly matches) *text*.

        Args:
            text:      Search string.
            exact:     If True, require ``node.text == text`` (case-insensitive).
            node_type: Optionally restrict search to a specific type.
        """
        text_lower = text.strip().lower()
        results: list[DOMNode] = []

        candidates = self._by_type.get(node_type, []) if node_type else self._by_id.values()

        for node in candidates:
            node_text = node.text.strip().lower()
            if exact:
                if node_text == text_lower:
                    results.append(node)
            else:
                if text_lower in node_text:
                    results.append(node)

        return results

    # ===== Structural queries ==============================================

    def find_section(self, title: str) -> DOMNode | None:
        """Find the first SectionNode whose title contains *title*."""
        matches = self.find_by_text(title, node_type=NodeType.SECTION)
        return matches[0] if matches else None

    def find_table(self, header_text: str) -> DOMNode | None:
        """Find the first TableNode whose header text contains *header_text*."""
        matches = self.find_by_text(header_text, node_type=NodeType.TABLE)
        return matches[0] if matches else None

    def find_table_in_section(self, section_title: str) -> list[DOMNode]:
        """Find all tables inside the section matching *section_title*."""
        section = self.find_section(section_title)
        if not section:
            return []
        return section.descendants_of_type(NodeType.TABLE)

    def find_row(self, label: str) -> list[DOMNode]:
        """Find RowNodes whose label (row_label metadata or text) matches *label*.

        Returns all matching rows (there may be multiple across tables).
        """
        label_lower = label.strip().lower()
        results: list[DOMNode] = []
        for row in self.find_all(NodeType.ROW):
            row_label = row.metadata.get("row_label", "").strip().lower()
            row_text = row.text.strip().lower()
            if label_lower in row_label or label_lower in row_text:
                results.append(row)
        return results

    def find_cell(
        self,
        *,
        row_text: str | None = None,
        column_header: str | None = None,
        text: str | None = None,
    ) -> DOMNode | None:
        """Find a specific cell by row label and/or column header.

        This is the key query for the future Selection Resolver::

            q.find_cell(row_text="Trade Payables", column_header="March 31, 2025")

        Returns the first match or ``None``.
        """
        candidates = self.find_all(NodeType.CELL)

        for cell in candidates:
            # filter by column header
            if column_header:
                col_h = cell.metadata.get("column_header", "").strip().lower()
                if column_header.strip().lower() not in col_h:
                    continue

            # filter by row label (parent row's text or row_label)
            if row_text:
                parent = cell.parent
                if parent is None:
                    continue
                row_label = parent.metadata.get("row_label", "").strip().lower()
                row_t = parent.text.strip().lower()
                if (row_text.strip().lower() not in row_label
                        and row_text.strip().lower() not in row_t):
                    continue

            # filter by cell text
            if text:
                if text.strip().lower() not in cell.text.strip().lower():
                    continue

            return cell

        return None

    def find_cells_in_row(self, row_text: str) -> list[DOMNode]:
        """Return all cells in rows matching *row_text*."""
        results: list[DOMNode] = []
        for row in self.find_row(row_text):
            results.extend(c for c in row.children if c.node_type == NodeType.CELL)
        return results

    def find_cells_in_column(self, column_header: str) -> list[DOMNode]:
        """Return all cells that belong to the column named *column_header*."""
        col_lower = column_header.strip().lower()
        return [
            c for c in self.find_all(NodeType.CELL)
            if col_lower in c.metadata.get("column_header", "").strip().lower()
        ]

    # ===== Adaptive Structural Scoring =====================================

    def score_candidate_rows(
        self,
        variable_name: str,
        synonyms: list[str] | None = None,
        expected_section: str | None = None,
        target_type: str | None = None,
    ) -> list[tuple[float, DOMNode, int | None]]:
        """Scores all candidate rows in the document for *variable_name* using
        multi-factor fuzzy structural matching.

        Factors:
            • Label match: exact/substring overlap with variable_name & synonyms.
            • Section context: rewards rows inside sections matching expected_section.
            • Content quality: rewards rows having structured, non-header values.
            • OCR garbage penalties: penalizes dates acting as financial numbers.

        Returns:
            List of ``(score, row_node, best_col_index)`` tuples sorted by score descending.
        """
        targets = [variable_name.strip().lower()]
        if synonyms:
            for s in synonyms:
                if s and s.strip():
                    t = s.strip().lower()
                    if t not in targets:
                        targets.append(t)

        candidates: list[DOMNode] = []
        # Find candidate rows matching any target label/synonym
        seen_row_ids = set()
        for t in targets:
            for r in self.find_row(t):
                if r.id not in seen_row_ids:
                    seen_row_ids.add(r.id)
                    candidates.append(r)
            # Also check cell text matches whose parent is a row
            for c in self.find_by_text(t, node_type=NodeType.CELL):
                if c.parent and c.parent.node_type == NodeType.ROW:
                    if c.parent.id not in seen_row_ids:
                        seen_row_ids.add(c.parent.id)
                        candidates.append(c.parent)

        if not candidates:
            # Fallback: check all rows
            candidates = self.find_all(NodeType.ROW)

        scored: list[tuple[float, DOMNode, int | None]] = []

        def _is_numeric(s: str) -> bool:
            clean = s.replace(",", "").replace(".", "").replace("-", "").replace("₹", "").replace("INR", "").strip()
            return bool(clean and clean.isdigit())

        for row in candidates:
            row_text = (row.text or "").strip().lower()
            row_label = (row.metadata.get("row_label") or "").strip().lower()
            combined_label = f"{row_label} {row_text}"

            score = 0.0

            # 1. Label / Synonym Match
            best_label_score = 0.0
            for t in targets:
                if t == row_label or (len(t) > 3 and t == row_text):
                    best_label_score = max(best_label_score, 20.0)
                elif f"| {t}" in combined_label or f"{t} |" in combined_label:
                    best_label_score = max(best_label_score, 18.0)
                elif f"total {t}" in combined_label or f"{t} (net)" in combined_label:
                    best_label_score = max(best_label_score, 16.0)
                elif t in combined_label:
                    # Token overlap ratio
                    t_tokens = set(re.findall(r"[a-z0-9]{3,}", t))
                    r_tokens = set(re.findall(r"[a-z0-9]{3,}", combined_label))
                    overlap = len(t_tokens & r_tokens)
                    if overlap >= 2:
                        best_label_score = max(best_label_score, 10.0 + (overlap * 2.0))
                    elif overlap == 1 and len(t_tokens) == 1:
                        best_label_score = max(best_label_score, 8.0)

            if best_label_score <= 0.0:
                continue

            score += best_label_score

            # 2. Section Context Match
            if expected_section and hasattr(row, 'section') and row.section:
                sec_text = (row.section.text or "").strip().lower()
                clean_exp_sec = re.sub(r'[\d\.\-_/]+', ' ', expected_section.lower()).strip()
                exp_tokens = [w for w in clean_exp_sec.split() if len(w) > 3 and w not in ["schedule", "part", "annexure"]]
                if exp_tokens and any(tk in sec_text for tk in exp_tokens):
                    score += 15.0

            # 3. Cell Quality and Value Extraction Target
            cells = [c for c in row.children if c.node_type == NodeType.CELL]
            best_col = None

            if cells:
                # Inspect cells for data values
                numeric_indices = []
                for idx, c in enumerate(cells):
                    ct = c.text.strip()
                    if _is_numeric(ct):
                        numeric_indices.append((idx, ct))

                if target_type == "number" or "amount" in variable_name.lower() or "shares" in variable_name.lower():
                    if numeric_indices:
                        score += 10.0
                        # Prefer last numeric column (typically current year / total)
                        best_col = numeric_indices[-1][0]
                    else:
                        score -= 10.0
                elif numeric_indices:
                    # Generic row with numeric columns
                    best_col = numeric_indices[-1][0]
                    score += 5.0
                elif len(cells) >= 2:
                    # Non-numeric key-value cell pair
                    best_col = len(cells) - 1
                    score += 5.0

                # Penalize date headers acting as values
                for idx, c in enumerate(cells):
                    ct = c.text.strip().lower()
                    if any(m in ct for m in ["march", "december", "january", "as at", "ended"]):
                        if best_col == idx:
                            score -= 30.0

            scored.append((score, row, best_col))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    # ===== Note queries ====================================================

    def find_note(self, note_number: str) -> list[DOMNode]:
        """Find NoteNodes matching *note_number*."""
        return [
            n for n in self.find_all(NodeType.NOTE)
            if n.metadata.get("note_number", "").strip() == note_number.strip()
        ]

    def find_rows_referring_to_note(self, note_number: str) -> list[DOMNode]:
        """Find RowNodes that contain a reference to *note_number*."""
        notes = self.find_note(note_number)
        rows: list[DOMNode] = []
        for note in notes:
            if note.parent and note.parent.node_type == NodeType.ROW:
                rows.append(note.parent)
        return rows

    # ===== Navigation helpers ==============================================

    def get_parent(self, node: DOMNode) -> DOMNode | None:
        """Return the parent of *node*."""
        return node.parent

    def get_children(self, node: DOMNode) -> list[DOMNode]:
        """Return the children of *node*."""
        return list(node.children)

    def get_siblings(self, node: DOMNode) -> list[DOMNode]:
        """Return siblings (excluding *node* itself)."""
        return node.siblings

    def get_previous_row(self, row: DOMNode) -> DOMNode | None:
        """Return the row before *row* in the same table."""
        return row.previous_sibling

    def get_next_row(self, row: DOMNode) -> DOMNode | None:
        """Return the row after *row* in the same table."""
        return row.next_sibling

    # ===== Structural path =================================================

    def get_structural_path(self, node: DOMNode) -> list[dict]:
        """Return the path from root to *node* as a list of dicts.

        This is the foundation for the Rule Learning Engine — a structural
        path like::

            [
                {"type": "document", "id": "document_1"},
                {"type": "section",  "id": "section_3",  "text": "Balance Sheet"},
                {"type": "table",    "id": "table_2"},
                {"type": "row",      "id": "row_12",     "label": "Trade Payables"},
                {"type": "cell",     "id": "cell_45",    "column": "March 31, 2025"}
            ]
        """
        path: list[dict] = []
        current: DOMNode | None = node
        while current is not None:
            entry: dict = {
                "type": current.node_type.value,
                "id": current.id,
            }
            if current.text:
                entry["text"] = current.text[:80]
            if current.metadata.get("row_label"):
                entry["label"] = current.metadata["row_label"]
            if current.metadata.get("column_header"):
                entry["column"] = current.metadata["column_header"]
            path.append(entry)
            current = current.parent

        path.reverse()
        return path

    # ===== Summary =========================================================

    def summary(self) -> dict[str, int]:
        """Return a count of nodes by type."""
        return {k.value: len(v) for k, v in self._by_type.items()}
