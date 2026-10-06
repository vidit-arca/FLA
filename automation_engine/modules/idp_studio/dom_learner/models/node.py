"""
node.py — All DOM node types for the Logical Document Tree.

Every node carries:
    id          — unique, human-readable identifier (e.g. "section_3", "row_12")
    node_type   — enum member (NodeType.SECTION, NodeType.CELL, …)
    text        — raw text content of the node
    parent      — reference to the parent DOMNode (None for root)
    children    — ordered list of child DOMNodes
    metadata    — extensible dict (bbox, page, confidence, plus type-specific fields)

Design decisions:
    • All types live in one file for PoC maintainability.
    • Bounding box / page / confidence are pre-wired in metadata for future
      OCR-coordinate integration (even though current input lacks them).
    • Nodes are NOT dataclasses because we need mutable parent/child
      references and custom __init__ logic.  We use __slots__ for memory
      efficiency when dealing with large documents.
"""

from __future__ import annotations

import itertools
import logging
from enum import Enum
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node-type enum
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    """Exhaustive set of node types in the DOM."""
    DOCUMENT  = "document"
    SECTION   = "section"
    HEADING   = "heading"
    TABLE     = "table"
    HEADER    = "header"       # table header row
    ROW       = "row"
    CELL      = "cell"
    PARAGRAPH = "paragraph"
    NOTE      = "note"


# ---------------------------------------------------------------------------
# ID factory — produces deterministic, human-readable IDs
# ---------------------------------------------------------------------------

class _IDFactory:
    """Thread-safe counter-based ID generator.

    Produces IDs like ``section_1``, ``table_2``, ``row_14``.
    Call ``reset()`` between documents to restart counters.
    """

    def __init__(self) -> None:
        self._counters: dict[str, itertools.count] = {}

    def next(self, prefix: str) -> str:
        """Return the next ID for *prefix* (e.g. ``'section'`` → ``'section_1'``)."""
        if prefix not in self._counters:
            self._counters[prefix] = itertools.count(1)
        return f"{prefix}_{next(self._counters[prefix])}"

    def reset(self) -> None:
        """Clear all counters — call between independent documents."""
        self._counters.clear()


id_factory = _IDFactory()


# ---------------------------------------------------------------------------
# Base node
# ---------------------------------------------------------------------------

class DOMNode:
    """Base class for every node in the Logical Document Tree.

    Attributes:
        id:        Unique human-readable identifier.
        node_type: ``NodeType`` enum member.
        text:      Raw text content (may be empty for container nodes).
        parent:    Reference to the parent node (``None`` for the root).
        children:  Ordered list of child nodes.
        metadata:  Extensible dict.  Always contains at minimum:
                       ``bbox``       — bounding box ``[x0, y0, x1, y1]`` or ``None``
                       ``page``       — 0-indexed page number or ``None``
                       ``confidence`` — OCR confidence 0.0–1.0 or ``None``
    """

    __slots__ = ("id", "node_type", "text", "parent", "children", "metadata")

    def __init__(
        self,
        node_type: NodeType,
        text: str = "",
        *,
        node_id: str | None = None,
        parent: DOMNode | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
        page: int | None = None,
        confidence: float | None = None,
    ) -> None:
        self.id: str = node_id or id_factory.next(node_type.value)
        self.node_type: NodeType = node_type
        self.text: str = text
        self.parent: Optional[DOMNode] = parent
        self.children: list[DOMNode] = []
        self.metadata: dict[str, Any] = metadata or {}

        # --- future-proof spatial fields ---
        self.metadata.setdefault("bbox", bbox)
        self.metadata.setdefault("page", page)
        self.metadata.setdefault("confidence", confidence)

    # ----- child management ------------------------------------------------

    def add_child(self, child: DOMNode) -> DOMNode:
        """Append *child*, setting its parent to ``self``.  Returns *child*."""
        child.parent = self
        self.children.append(child)
        return child

    def add_children(self, children: list[DOMNode]) -> None:
        """Append multiple children at once."""
        for child in children:
            self.add_child(child)

    # ----- sibling navigation ----------------------------------------------

    @property
    def index_in_parent(self) -> int:
        """0-based index among siblings.  Returns -1 if no parent."""
        if self.parent is None:
            return -1
        try:
            return self.parent.children.index(self)
        except ValueError:
            return -1

    @property
    def previous_sibling(self) -> DOMNode | None:
        """The preceding sibling, or ``None``."""
        idx = self.index_in_parent
        if idx > 0:
            return self.parent.children[idx - 1]  # type: ignore[union-attr]
        return None

    @property
    def next_sibling(self) -> DOMNode | None:
        """The following sibling, or ``None``."""
        idx = self.index_in_parent
        if self.parent and 0 <= idx < len(self.parent.children) - 1:
            return self.parent.children[idx + 1]
        return None

    @property
    def siblings(self) -> list[DOMNode]:
        """All siblings (excluding self)."""
        if self.parent is None:
            return []
        return [c for c in self.parent.children if c is not self]

    # ----- ancestor navigation ---------------------------------------------

    @property
    def section(self) -> DOMNode | None:
        """Walk up to the nearest SectionNode ancestor."""
        return self._ancestor_of_type(NodeType.SECTION)

    @property
    def table(self) -> DOMNode | None:
        """Walk up to the nearest TableNode ancestor."""
        return self._ancestor_of_type(NodeType.TABLE)

    def _ancestor_of_type(self, target: NodeType) -> DOMNode | None:
        node = self.parent
        while node is not None:
            if node.node_type == target:
                return node
            node = node.parent
        return None

    # ----- depth -----------------------------------------------------------

    @property
    def depth(self) -> int:
        """Distance from the root (root depth == 0)."""
        d, node = 0, self.parent
        while node is not None:
            d += 1
            node = node.parent
        return d

    # ----- tree traversal --------------------------------------------------

    def walk(self) -> Iterator[DOMNode]:
        """Pre-order depth-first traversal of this subtree (yields self first)."""
        yield self
        for child in self.children:
            yield from child.walk()

    def descendants_of_type(self, target: NodeType) -> list[DOMNode]:
        """Return all descendants matching *target* type."""
        return [n for n in self.walk() if n.node_type == target and n is not self]

    # ----- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Recursive serialization to a JSON-compatible dict."""
        return {
            "id": self.id,
            "type": self.node_type.value,
            "text": self.text,
            "parent_id": self.parent.id if self.parent else None,
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata,
        }

    # ----- repr ------------------------------------------------------------

    def __repr__(self) -> str:
        text_preview = (self.text[:40] + "…") if len(self.text) > 40 else self.text
        return f"<{self.__class__.__name__} id={self.id!r} text={text_preview!r}>"


# ---------------------------------------------------------------------------
# Concrete node types
# ---------------------------------------------------------------------------

class DocumentNode(DOMNode):
    """Root of the logical document tree."""

    def __init__(self, source_file: str = "", **kwargs: Any) -> None:
        super().__init__(NodeType.DOCUMENT, **kwargs)
        self.metadata["source_file"] = source_file


class SectionNode(DOMNode):
    """A document section introduced by a heading."""

    def __init__(self, text: str = "", *, heading_level: int = 1, **kwargs: Any) -> None:
        super().__init__(NodeType.SECTION, text=text, **kwargs)
        self.metadata["heading_level"] = heading_level


class HeadingNode(DOMNode):
    """A heading line (H1–H6)."""

    def __init__(self, text: str = "", *, level: int = 1, **kwargs: Any) -> None:
        super().__init__(NodeType.HEADING, text=text, **kwargs)
        self.metadata["level"] = level


class TableNode(DOMNode):
    """A markdown table."""

    def __init__(self, text: str = "", *, column_count: int = 0, **kwargs: Any) -> None:
        super().__init__(NodeType.TABLE, text=text, **kwargs)
        self.metadata["column_count"] = column_count


class HeaderNode(DOMNode):
    """Header row of a table."""

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        super().__init__(NodeType.HEADER, text=text, **kwargs)


class RowNode(DOMNode):
    """A body row inside a table."""

    def __init__(self, text: str = "", *, row_index: int = 0, **kwargs: Any) -> None:
        super().__init__(NodeType.ROW, text=text, **kwargs)
        self.metadata["row_index"] = row_index


class CellNode(DOMNode):
    """A single cell inside a row."""

    def __init__(
        self,
        text: str = "",
        *,
        column_index: int = 0,
        column_header: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(NodeType.CELL, text=text, **kwargs)
        self.metadata["column_index"] = column_index
        self.metadata["column_header"] = column_header


class ParagraphNode(DOMNode):
    """Free-form text between headings or tables."""

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        super().__init__(NodeType.PARAGRAPH, text=text, **kwargs)


class NoteNode(DOMNode):
    """A note reference (e.g. 'Note 4')."""

    def __init__(self, text: str = "", *, note_number: str = "", **kwargs: Any) -> None:
        super().__init__(NodeType.NOTE, text=text, **kwargs)
        self.metadata["note_number"] = note_number
