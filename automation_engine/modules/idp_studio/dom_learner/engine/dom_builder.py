"""
dom_builder.py — Orchestrates parsers to build the Logical Document Tree.

Pipeline:
    1.  MarkdownParser.parse()  →  list[ParsedBlock]
    2.  SectionParser.parse()   →  list[SectionDraft]
    3.  For each SectionDraft:
        • Create SectionNode + HeadingNode
        • TABLE blocks  → TableParser → TableNode / HeaderNode / RowNode / CellNode
        • PARAGRAPH blocks → ParagraphNode
    4.  Nest sections by heading level (stack-based)
    5.  Return DocumentNode root

Design:
    • The builder owns the ID factory reset — each call to ``build()``
      produces deterministic IDs starting from 1.
    • Note references are detected in cells that match the "Note" column
      header pattern, creating NoteNode children on the row.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from dom_learner.models import (
    CellNode,
    DocumentNode,
    HeaderNode,
    HeadingNode,
    NoteNode,
    NodeType,
    ParagraphNode,
    RowNode,
    SectionNode,
    TableNode,
    id_factory,
)
from dom_learner.parser.markdown_parser import BlockType, MarkdownParser
from dom_learner.parser.section_parser import SectionDraft, SectionParser
from dom_learner.parser.table_parser import TableParser

logger = logging.getLogger(__name__)

_RE_NOTE_REF = re.compile(r'(?:Note|Ref)\s*[-:]?\s*(\d+[a-z]?)', re.IGNORECASE)
_NOTE_COLUMN_NAMES = {"note", "notes", "ref", "reference"}


class DOMBuilder:
    """Builds a ``DocumentNode`` tree from an OCR markdown file.

    Usage::

        builder = DOMBuilder()
        document = builder.build(Path("document.md"))
    """

    def __init__(self) -> None:
        self._md_parser = MarkdownParser()
        self._section_parser = SectionParser()
        self._table_parser = TableParser()

    def build(self, markdown_path: Path) -> DocumentNode:
        """Parse *markdown_path* and return the root ``DocumentNode``."""
        id_factory.reset()

        # --- Step 1 & 2: tokenize and section ---
        blocks = self._md_parser.parse(markdown_path)
        drafts = self._section_parser.parse(blocks)

        # --- Step 3: create document root ---
        document = DocumentNode(source_file=str(markdown_path))

        # --- Step 4: nest sections by heading level (stack-based) ---
        # The stack holds (heading_level, SectionNode) pairs.
        # A new section goes under the deepest section on the stack
        # whose level is strictly less than its own.
        stack: list[tuple[int, SectionNode]] = []

        for draft in drafts:
            section_node = self._build_section(draft)

            # pop sections from the stack that are same-or-deeper level
            while stack and stack[-1][0] >= draft.heading_level:
                stack.pop()

            if stack:
                # nest under the deepest parent
                stack[-1][1].add_child(section_node)
            else:
                # top-level section → child of document
                document.add_child(section_node)

            stack.append((draft.heading_level, section_node))

        stats = self._collect_stats(document)
        logger.info(
            "DOMBuilder: built tree with %d nodes (%s)",
            sum(stats.values()),
            ", ".join(f"{k}={v}" for k, v in sorted(stats.items())),
        )
        return document

    # ----- helpers ---------------------------------------------------------

    def _build_section(self, draft: SectionDraft) -> SectionNode:
        """Convert a ``SectionDraft`` into a ``SectionNode`` subtree."""
        section = SectionNode(
            text=draft.heading,
            heading_level=draft.heading_level,
        )

        # Add heading child
        heading = HeadingNode(text=draft.heading, level=draft.heading_level)
        section.add_child(heading)

        # Process child blocks
        for block in draft.blocks:
            if block.block_type == BlockType.TABLE:
                table_node = self._build_table(block.lines)
                section.add_child(table_node)
            elif block.block_type == BlockType.PARAGRAPH:
                if block.content.strip():
                    para = ParagraphNode(text=block.content)
                    section.add_child(para)

        return section

    def _build_table(self, lines: list[str]) -> TableNode:
        """Parse raw table lines and produce a ``TableNode`` subtree."""
        parsed = self._table_parser.parse(lines)

        table = TableNode(
            text="",
            column_count=len(parsed.headers),
        )

        # -- header row --
        header_node = HeaderNode()
        for col_idx, header_text in enumerate(parsed.headers):
            cell = CellNode(
                text=header_text,
                column_index=col_idx,
                column_header=header_text,
            )
            header_node.add_child(cell)
        table.add_child(header_node)

        # Detect which column (if any) is a "Note" column
        note_col_indices = {
            i for i, h in enumerate(parsed.headers)
            if h.strip().lower() in _NOTE_COLUMN_NAMES
        }

        # -- body rows --
        for row_idx, row_cells in enumerate(parsed.rows):
            row_node = RowNode(row_index=row_idx)

            # Build label from first non-empty cell for row text
            row_label_parts: list[str] = []

            for col_idx, cell_text in enumerate(row_cells):
                col_header = (
                    parsed.headers[col_idx]
                    if col_idx < len(parsed.headers)
                    else ""
                )
                cell = CellNode(
                    text=cell_text,
                    column_index=col_idx,
                    column_header=col_header,
                )
                row_node.add_child(cell)

                # collect label text (first meaningful cell)
                if cell_text.strip() and col_idx < 2:
                    row_label_parts.append(cell_text.strip())

                # Note reference detection
                if col_idx in note_col_indices and cell_text.strip():
                    note_num = cell_text.strip()
                    note = NoteNode(
                        text=f"Note {note_num}",
                        note_number=note_num,
                    )
                    row_node.add_child(note)
                else:
                    # check for inline note references like "Note 4"
                    m = _RE_NOTE_REF.search(cell_text)
                    if m:
                        note = NoteNode(
                            text=f"Note {m.group(1)}",
                            note_number=m.group(1),
                        )
                        row_node.add_child(note)

            row_node.text = " | ".join(row_label_parts) if row_label_parts else ""
            row_node.metadata["row_label"] = row_label_parts[0] if row_label_parts else ""
            table.add_child(row_node)

        # Set table text from first section heading or first row label
        if parsed.rows:
            first_label = parsed.rows[0][0].strip() if parsed.rows[0] else ""
            # also check header for table context
            header_text = " | ".join(h for h in parsed.headers if h.strip())
            table.text = header_text

        return table

    @staticmethod
    def _collect_stats(document: DocumentNode) -> dict[str, int]:
        """Count nodes by type."""
        stats: dict[str, int] = {}
        for node in document.walk():
            key = node.node_type.value
            stats[key] = stats.get(key, 0) + 1
        return stats
