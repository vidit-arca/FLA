"""
markdown_parser.py — Line-by-line tokenizer for OCR markdown.

Reads a ``.md`` file and classifies every line into one of:
    HEADING, TABLE_ROW, TABLE_SEPARATOR, IMAGE, PARAGRAPH, BLANK

Then groups consecutive table lines into TABLE blocks so downstream
consumers receive coherent table chunks rather than individual rows.

Design notes:
    • Fully generic — no domain-specific keywords.
    • Strips inline HTML tags (``<br>``, ``<b>``, ``<del>``, etc.) that
      appear frequently in OCR output.
    • Treats ``![…](…)`` image references as IMAGE blocks (skipped in PoC).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Block type enum
# ---------------------------------------------------------------------------

class BlockType(Enum):
    """Classification for a single line or merged block."""
    HEADING         = auto()
    TABLE_ROW       = auto()
    TABLE_SEPARATOR = auto()
    TABLE           = auto()   # merged block of TABLE_ROW + TABLE_SEPARATOR
    IMAGE           = auto()
    PARAGRAPH       = auto()
    BLANK           = auto()


# ---------------------------------------------------------------------------
# Parsed block dataclass
# ---------------------------------------------------------------------------

@dataclass
class ParsedBlock:
    """A token produced by the markdown parser.

    For TABLE blocks, ``lines`` contains all the raw table lines
    (header + separator + body rows).
    """
    block_type: BlockType
    content: str                     # primary text content
    line_number: int                 # 1-indexed source line
    heading_level: int = 0           # 1–6 for headings, 0 otherwise
    lines: list[str] = field(default_factory=list)  # raw lines (for TABLE blocks)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_RE_HEADING      = re.compile(r'^(#{1,6})\s+(.*)')
_RE_TABLE_ROW    = re.compile(r'^\s*\|')
_RE_TABLE_SEP    = re.compile(r'^\s*\|[\s\-:|]+\|\s*$')
_RE_IMAGE        = re.compile(r'^!\[.*?\]\(.*?\)')
_RE_HTML_TAG     = re.compile(r'<[^>]+>')
_RE_BOLD_STARS   = re.compile(r'\*\*(.+?)\*\*')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class MarkdownParser:
    """Tokenizes OCR markdown into a list of ``ParsedBlock`` objects.

    Usage::

        parser = MarkdownParser()
        blocks = parser.parse(Path("document.md"))
    """

    @staticmethod
    def clean_html(text: str) -> str:
        """Strip inline HTML tags and bold markers from *text*."""
        text = _RE_HTML_TAG.sub(" ", text)
        text = _RE_BOLD_STARS.sub(r"\1", text)
        # collapse multiple spaces
        text = re.sub(r" {2,}", " ", text).strip()
        return text

    # ----- line classification ---------------------------------------------

    @staticmethod
    def _classify_line(line: str) -> tuple[BlockType, int]:
        """Return ``(BlockType, heading_level)`` for a single line."""
        stripped = line.strip()

        if not stripped:
            return BlockType.BLANK, 0

        if _RE_IMAGE.match(stripped):
            return BlockType.IMAGE, 0

        m = _RE_HEADING.match(stripped)
        if m:
            return BlockType.HEADING, len(m.group(1))

        if _RE_TABLE_SEP.match(stripped):
            return BlockType.TABLE_SEPARATOR, 0

        if _RE_TABLE_ROW.match(stripped):
            return BlockType.TABLE_ROW, 0

        return BlockType.PARAGRAPH, 0

    # ----- parse -----------------------------------------------------------

    def parse(self, path: Path) -> list[ParsedBlock]:
        """Read *path* and return a list of ``ParsedBlock`` tokens.

        Consecutive table rows and separators are merged into single
        ``TABLE`` blocks.
        """
        raw_lines = path.read_text(encoding="utf-8").splitlines()
        logger.info("MarkdownParser: read %d lines from %s", len(raw_lines), path.name)

        # -- Step 1: classify each line -------------------------------------
        classified: list[tuple[BlockType, int, str, int]] = []
        for idx, line in enumerate(raw_lines, start=1):
            btype, hlevel = self._classify_line(line)
            classified.append((btype, hlevel, line, idx))

        # -- Step 2: merge consecutive table lines into TABLE blocks --------
        blocks: list[ParsedBlock] = []
        i = 0
        while i < len(classified):
            btype, hlevel, line, lineno = classified[i]

            if btype in (BlockType.TABLE_ROW, BlockType.TABLE_SEPARATOR):
                # accumulate table lines
                table_lines: list[str] = []
                start_line = lineno
                while i < len(classified) and classified[i][0] in (
                    BlockType.TABLE_ROW,
                    BlockType.TABLE_SEPARATOR,
                ):
                    table_lines.append(classified[i][2])
                    i += 1
                blocks.append(ParsedBlock(
                    block_type=BlockType.TABLE,
                    content="",
                    line_number=start_line,
                    lines=table_lines,
                ))
            elif btype == BlockType.HEADING:
                content = self.clean_html(_RE_HEADING.match(line.strip()).group(2))  # type: ignore[union-attr]
                blocks.append(ParsedBlock(
                    block_type=BlockType.HEADING,
                    content=content,
                    line_number=lineno,
                    heading_level=hlevel,
                ))
                i += 1
            elif btype == BlockType.PARAGRAPH:
                # merge consecutive paragraph lines into one block
                para_lines: list[str] = []
                start_line_p = lineno
                while i < len(classified) and classified[i][0] == BlockType.PARAGRAPH:
                    para_lines.append(self.clean_html(classified[i][2]))
                    i += 1
                blocks.append(ParsedBlock(
                    block_type=BlockType.PARAGRAPH,
                    content=" ".join(para_lines),
                    line_number=start_line_p,
                ))
            else:
                # BLANK or IMAGE — skip
                i += 1

        logger.info(
            "MarkdownParser: produced %d blocks (headings=%d, tables=%d, paragraphs=%d)",
            len(blocks),
            sum(1 for b in blocks if b.block_type == BlockType.HEADING),
            sum(1 for b in blocks if b.block_type == BlockType.TABLE),
            sum(1 for b in blocks if b.block_type == BlockType.PARAGRAPH),
        )
        return blocks
