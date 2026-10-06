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
