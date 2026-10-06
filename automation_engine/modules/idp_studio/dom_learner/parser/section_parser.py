"""
section_parser.py — Groups parsed blocks into hierarchical sections.

A "section" is the region of the document introduced by a heading and
extending until the next heading of equal-or-higher level.  Nesting is
handled downstream by the DOM builder using a stack-based approach.
This parser produces a flat list of ``SectionDraft`` objects, each
carrying its heading level and contained blocks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from dom_learner.parser.markdown_parser import BlockType, ParsedBlock

logger = logging.getLogger(__name__)


@dataclass
class SectionDraft:
    """Intermediate representation of a section before DOM-tree insertion.

    Attributes:
        heading:       The section title text.
        heading_level: 1–6 (from markdown ``#`` count).
        line_number:   Source line where the heading appeared.
        blocks:        The child ``ParsedBlock`` objects that belong to
                       this section (tables, paragraphs, etc.).
    """
    heading: str
    heading_level: int
    line_number: int
    blocks: list[ParsedBlock] = field(default_factory=list)


class SectionParser:
    """Splits a stream of ``ParsedBlock`` tokens into ``SectionDraft`` objects.

    Every heading creates a new section.  Blocks before the first heading
    are gathered into a synthetic "Preamble" section (level 0).

    Usage::

        sp = SectionParser()
        drafts = sp.parse(blocks)
    """

    def parse(self, blocks: list[ParsedBlock]) -> list[SectionDraft]:
        """Return an ordered list of ``SectionDraft`` objects."""
        sections: list[SectionDraft] = []
        current: SectionDraft | None = None

        for block in blocks:
            if block.block_type == BlockType.HEADING:
                # start a new section
                current = SectionDraft(
                    heading=block.content,
                    heading_level=block.heading_level,
                    line_number=block.line_number,
                )
                sections.append(current)
            else:
                if current is None:
                    # blocks before any heading → preamble
                    current = SectionDraft(
                        heading="Preamble",
                        heading_level=0,
                        line_number=block.line_number,
                    )
                    sections.append(current)
                current.blocks.append(block)

        logger.info("SectionParser: produced %d sections", len(sections))
        return sections
