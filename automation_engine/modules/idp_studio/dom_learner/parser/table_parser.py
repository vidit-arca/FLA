"""
table_parser.py — Parses a block of markdown table lines into structured data.

Handles OCR-typical quirks:
    • Inline HTML (``<br>``, ``<b>``, ``<del>``, etc.)
    • Leading/trailing whitespace and pipe characters
    • Separator rows (``|---|---|``)
    • Variable column counts across rows (pads shorter rows)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from dom_learner.parser.markdown_parser import MarkdownParser

logger = logging.getLogger(__name__)

_RE_SEPARATOR_CELL = re.compile(r'^[\s\-:|]+$')


@dataclass
class ParsedTable:
    """Structured representation of a markdown table.

    Attributes:
        headers:  Column header strings (first non-separator row).
        rows:     List of body rows; each row is a list of cell strings.
        raw_lines: Original markdown lines for debugging.
    """
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)


class TableParser:
    """Parses raw markdown table lines into a ``ParsedTable``.

    Usage::

        tp = TableParser()
        table = tp.parse(table_lines)
    """

    @staticmethod
    def _split_row(line: str) -> list[str]:
        """Split a markdown table row by ``|`` and clean each cell."""
        # strip outer pipes
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        cells = line.split("|")
        return [MarkdownParser.clean_html(c.strip()) for c in cells]

    @staticmethod
    def _is_separator(line: str) -> bool:
        """Return True if *line* is a markdown table separator (``|---|---|``)."""
        cells = line.strip().strip("|").split("|")
        return all(_RE_SEPARATOR_CELL.match(c) for c in cells if c.strip())

    def parse(self, lines: list[str]) -> ParsedTable:
        """Parse *lines* (a block of raw markdown table lines) into a ``ParsedTable``.

        The first non-separator row is treated as the header.
        Subsequent non-separator rows are body rows.
        All rows are padded/trimmed to match the header column count.
        """
        result = ParsedTable(raw_lines=list(lines))
        header_found = False

        for line in lines:
            if self._is_separator(line):
                continue

            cells = self._split_row(line)

            if not header_found:
                result.headers = cells
                header_found = True
            else:
                result.rows.append(cells)

        # normalize column count
        if result.headers:
            col_count = len(result.headers)
            for i, row in enumerate(result.rows):
                if len(row) < col_count:
                    result.rows[i] = row + [""] * (col_count - len(row))
                elif len(row) > col_count:
                    result.rows[i] = row[:col_count]

        logger.info(
            "TableParser: parsed table with %d columns × %d rows",
            len(result.headers),
            len(result.rows),
        )
        return result
