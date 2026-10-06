"""
relationship_builder.py — Generates semantic relationships from a DOM tree.

Produces both hierarchical and semantic edges that form a relationship graph
over the DOM nodes.  This graph enables structure-based navigation without
walking the raw tree.

Relationship types (expanded per user feedback):

    Hierarchical:
        HAS_SECTION, HAS_TABLE, HAS_ROW, HAS_CELL, BELONGS_TO

    Positional:
        NEXT_ROW, PREVIOUS_ROW, NEXT_COLUMN, PREVIOUS_COLUMN

    Semantic:
        REFERS_TO_NOTE, ROW_HAS_LABEL, CELL_IN_COLUMN, CELL_IN_ROW,
        TABLE_IN_SECTION, SECTION_IN_DOCUMENT, HEADER_FOR_COLUMN
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from dom_learner.models import DOMNode, DocumentNode, NodeType

logger = logging.getLogger(__name__)


class RelType(str, Enum):
    """All supported relationship types."""
    # hierarchical
    HAS_SECTION          = "HAS_SECTION"
    HAS_TABLE            = "HAS_TABLE"
    HAS_ROW              = "HAS_ROW"
    HAS_CELL             = "HAS_CELL"
    BELONGS_TO           = "BELONGS_TO"

    # positional
    NEXT_ROW             = "NEXT_ROW"
    PREVIOUS_ROW         = "PREVIOUS_ROW"
    NEXT_COLUMN          = "NEXT_COLUMN"
    PREVIOUS_COLUMN      = "PREVIOUS_COLUMN"

    # semantic
    REFERS_TO_NOTE       = "REFERS_TO_NOTE"
    ROW_HAS_LABEL        = "ROW_HAS_LABEL"
    CELL_IN_COLUMN       = "CELL_IN_COLUMN"
    CELL_IN_ROW          = "CELL_IN_ROW"
    TABLE_IN_SECTION     = "TABLE_IN_SECTION"
    SECTION_IN_DOCUMENT  = "SECTION_IN_DOCUMENT"
    HEADER_FOR_COLUMN    = "HEADER_FOR_COLUMN"


@dataclass(frozen=True)
class Relationship:
    """A single directed edge in the relationship graph.

    Attributes:
        source_id:  ID of the source node.
        target_id:  ID of the target node.
        rel_type:   Relationship type.
        metadata:   Optional extra info (e.g. column name, note number).
    """
    source_id: str
    target_id: str
    rel_type: RelType
    metadata: dict | None = None

    def to_dict(self) -> dict:
        d = {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.rel_type.value,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class RelationshipBuilder:
    """Traverses a ``DocumentNode`` tree and emits ``Relationship`` edges.

    Usage::

        rb = RelationshipBuilder()
        relationships = rb.build(document)
    """

    def build(self, document: DocumentNode) -> list[Relationship]:
        """Walk the tree and return all relationships."""
        rels: list[Relationship] = []

        for node in document.walk():
            self._hierarchical(node, rels)
            self._semantic(node, rels)

        self._positional(document, rels)

        logger.info(
            "RelationshipBuilder: generated %d relationships across %d types",
            len(rels),
            len({r.rel_type for r in rels}),
        )
        return rels

    # ----- hierarchical edges ----------------------------------------------

    def _hierarchical(self, node: DOMNode, rels: list[Relationship]) -> None:
        """Emit parent → child ownership and child → parent BELONGS_TO."""
        for child in node.children:
            # ownership edges
            if node.node_type == NodeType.DOCUMENT and child.node_type == NodeType.SECTION:
                rels.append(Relationship(node.id, child.id, RelType.HAS_SECTION))
            elif child.node_type == NodeType.TABLE:
                rels.append(Relationship(node.id, child.id, RelType.HAS_TABLE))
            elif child.node_type == NodeType.ROW:
                rels.append(Relationship(node.id, child.id, RelType.HAS_ROW))
            elif child.node_type == NodeType.HEADER:
                rels.append(Relationship(node.id, child.id, RelType.HAS_ROW))
            elif child.node_type == NodeType.CELL:
                rels.append(Relationship(node.id, child.id, RelType.HAS_CELL))

            # universal BELONGS_TO (child → parent)
            rels.append(Relationship(child.id, node.id, RelType.BELONGS_TO))

    # ----- semantic edges --------------------------------------------------

    def _semantic(self, node: DOMNode, rels: list[Relationship]) -> None:
        """Emit semantic relationships."""

        # TABLE_IN_SECTION
        if node.node_type == NodeType.TABLE and node.parent and node.parent.node_type == NodeType.SECTION:
            rels.append(Relationship(
                node.id, node.parent.id, RelType.TABLE_IN_SECTION,
                {"section_title": node.parent.text},
            ))

        # SECTION_IN_DOCUMENT
        if node.node_type == NodeType.SECTION and node.parent and node.parent.node_type == NodeType.DOCUMENT:
            rels.append(Relationship(
                node.id, node.parent.id, RelType.SECTION_IN_DOCUMENT,
            ))

        # ROW_HAS_LABEL
        if node.node_type == NodeType.ROW:
            label = node.metadata.get("row_label", "")
            if label:
                # First cell is typically the label
                if node.children:
                    first_cell = node.children[0]
                    rels.append(Relationship(
                        node.id, first_cell.id, RelType.ROW_HAS_LABEL,
                        {"label": label},
                    ))

        # CELL_IN_ROW and CELL_IN_COLUMN
        if node.node_type == NodeType.CELL:
            # CELL_IN_ROW
            if node.parent and node.parent.node_type in (NodeType.ROW, NodeType.HEADER):
                rels.append(Relationship(
                    node.id, node.parent.id, RelType.CELL_IN_ROW,
                ))
            # CELL_IN_COLUMN
            col_header = node.metadata.get("column_header", "")
            if col_header:
                rels.append(Relationship(
                    node.id, node.id, RelType.CELL_IN_COLUMN,
                    {"column_name": col_header, "column_index": node.metadata.get("column_index")},
                ))

        # REFERS_TO_NOTE
        if node.node_type == NodeType.NOTE:
            # link from parent row to this note
            if node.parent:
                rels.append(Relationship(
                    node.parent.id, node.id, RelType.REFERS_TO_NOTE,
                    {"note_number": node.metadata.get("note_number", "")},
                ))

        # HEADER_FOR_COLUMN — link header cells to their column index
        if node.node_type == NodeType.HEADER:
            for cell in node.children:
                if cell.node_type == NodeType.CELL and cell.text.strip():
                    rels.append(Relationship(
                        cell.id, cell.id, RelType.HEADER_FOR_COLUMN,
                        {
                            "column_name": cell.text,
                            "column_index": cell.metadata.get("column_index"),
                        },
                    ))

    # ----- positional edges ------------------------------------------------

    def _positional(self, document: DocumentNode, rels: list[Relationship]) -> None:
        """Emit NEXT_ROW/PREVIOUS_ROW and NEXT_COLUMN/PREVIOUS_COLUMN edges."""
        tables = document.descendants_of_type(NodeType.TABLE)

        for table in tables:
            rows = [c for c in table.children if c.node_type in (NodeType.ROW, NodeType.HEADER)]

            # row adjacency
            for i in range(len(rows) - 1):
                rels.append(Relationship(rows[i].id, rows[i + 1].id, RelType.NEXT_ROW))
                rels.append(Relationship(rows[i + 1].id, rows[i].id, RelType.PREVIOUS_ROW))

            # column adjacency within each row
            for row in rows:
                cells = [c for c in row.children if c.node_type == NodeType.CELL]
                for i in range(len(cells) - 1):
                    rels.append(Relationship(cells[i].id, cells[i + 1].id, RelType.NEXT_COLUMN))
                    rels.append(Relationship(cells[i + 1].id, cells[i].id, RelType.PREVIOUS_COLUMN))
