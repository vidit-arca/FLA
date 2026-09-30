"""
Stage 2 — Document Structure Identification
Identifies Part III boundaries, full-width section banners, numbered & unnumbered statutory rows,
and continuation lines, preserving strict Part III physical sequence.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
from .stage1_pdf_layout import PageLayout, PageLine


@dataclass
class RawStatutoryRow:
    physical_idx: int
    page: int
    row_type: str  # 'field' | 'section_header'
    canonical_no: str
    field_name: str
    instructions: str
    section_slug: str = "main"
    is_numbered: bool = True


@dataclass
class SectionBlock:
    section_slug: str
    title: str
    start_row_idx: int
    end_row_idx: int = -1


# Statutory Regexes: Supports digits, Roman numerals (I, II, IV, etc.), trailing letters/dots (6., 7a), and parenthesized sub-items
FIELD_NO_PAT = re.compile(
    r"^(?:(?:[0-9]{1,2}(?:\.[0-9]+)?|[IVXLCDM]+)[a-z]?(?:[\s\.\-]*(?:[0-9]{1,2}|[IVXLCDM]+)[a-z]?)*(?:\s*\([a-z0-9IVXLCDM]+\))*|\([a-z0-9IVXLCDM]+\))\s*\.?$",
    re.IGNORECASE
)

SECTION_HEADERS = [
    'particulars for creation or modification or satisfaction of charges',
    'part a: statement of account and solvency',
    'part b: particulars for creation or modification or satisfaction of charges',
    'part b: particulars for creation or modification',
    'statement of account and solvency',
    'creation or modification or satisfaction of charges',
    'creation or modification of charges',
    'satisfaction of charges',
]

UNNUMBERED_FIELDS = [
    'attachments', 'attachment', 'verification', 'certificate',
    'declaration', 'instrument of creation', 'instrument evidencing',
    'letter of charge holder', 'copy of agreement', 'copy(s) of resolution',
    'optional attachment', 'designation', 'director identification',
    'whether associate or fellow', 'category', 'din or pan of the manager'
]


class Stage2DocumentStructure:
    """
    Identifies statutory document structure: boundaries, sections,
    rows, continuation cells, and attachments.
    """

    def process(self, layouts: List[PageLayout]) -> Tuple[List[RawStatutoryRow], List[SectionBlock]]:
        """
        Parses page lines into raw statutory rows and section blocks in strict physical order.
        """
        raw_rows: List[RawStatutoryRow] = []
        current_section = "main"
        section_blocks: List[SectionBlock] = []

        for p_layout in layouts:
            for line in p_layout.lines:
                c1 = line.c1_text
                c2 = line.c2_text
                c3 = line.c3_text
                full_line = line.full_text
                full_line_clean = re.sub(r'\s+', ' ', full_line).lower()

                # Skip table header lines
                if 'field no' in full_line_clean[:30] or (c1.lower() == 'field' and 'name' in c2.lower()) or c1.lower() == 'field no.':
                    continue

                c1_clean = re.sub(r'\s+', '', c1)
                c1_clean = re.sub(r'\(([a-z])\)\1', r'(\1)', c1_clean)

                # If line is only in instructions column (c1 and c2 empty), it is ALWAYS continuation
                if not c1 and not c2 and c3:
                    if raw_rows and raw_rows[-1].row_type == "field":
                        raw_rows[-1].instructions = (raw_rows[-1].instructions + " " + c3).strip()
                    continue

                is_field_no = bool(FIELD_NO_PAT.match(c1_clean))
                matched_sec = next((s for s in SECTION_HEADERS if full_line_clean.startswith(s)), None) if (c2 or full_line_clean.startswith("part")) else None
                is_purpose_sec = bool(not c1 and not c3 and re.match(r"^for\s+(?:declaration|change|creation|modification|satisfaction|appointment|cessation)\b", c2.strip(), re.I))
                is_table_start = bool(not c1 and (c2.lower().strip().startswith("table:") or c2.lower().strip().startswith("table :") or c2.lower().strip() == "table"))
                is_unnumbered = next((u for u in UNNUMBERED_FIELDS if (c2.lower().startswith(u) or full_line_clean.startswith(u))), None)

                if matched_sec or is_purpose_sec:
                    sec_title = full_line if matched_sec else c2
                    sec_slug = re.sub(r'[^a-z0-9]+', '_', sec_title.lower()).strip('_')[:40]
                    if section_blocks:
                        section_blocks[-1].end_row_idx = len(raw_rows) - 1
                    section_blocks.append(SectionBlock(
                        section_slug=sec_slug,
                        title=sec_title,
                        start_row_idx=len(raw_rows)
                    ))
                    current_section = sec_slug

                    raw_rows.append(RawStatutoryRow(
                        physical_idx=len(raw_rows),
                        page=p_layout.page_number,
                        row_type="section_header",
                        canonical_no="",
                        field_name=sec_title,
                        instructions="",
                        section_slug=current_section,
                        is_numbered=False
                    ))
                elif is_table_start:
                    canonical = ""
                    if raw_rows:
                        prev_fields = [r for r in raw_rows if r.row_type == "field" and r.canonical_no]
                        if prev_fields:
                            prev_c = prev_fields[-1].canonical_no
                            base_c = re.sub(r"\([ivxlcdm0-9]+\)$", "", prev_c, flags=re.I).strip()
                            canonical = f"{base_c}_table" if base_c else f"{prev_c}_table"
                    raw_rows.append(RawStatutoryRow(
                        physical_idx=len(raw_rows),
                        page=p_layout.page_number,
                        row_type="field",
                        canonical_no=canonical or "table",
                        field_name=c2,
                        instructions=c3,
                        section_slug=current_section,
                        is_numbered=False
                    ))
                elif is_field_no:
                    raw_rows.append(RawStatutoryRow(
                        physical_idx=len(raw_rows),
                        page=p_layout.page_number,
                        row_type="field",
                        canonical_no=c1_clean,
                        field_name=c2,
                        instructions=c3,
                        section_slug=current_section,
                        is_numbered=True
                    ))
                elif is_unnumbered:
                    raw_rows.append(RawStatutoryRow(
                        physical_idx=len(raw_rows),
                        page=p_layout.page_number,
                        row_type="field",
                        canonical_no="",
                        field_name=c2 or full_line,
                        instructions=c3,
                        section_slug=current_section,
                        is_numbered=False
                    ))
                elif raw_rows:
                    # Continuation line for the previous field or section header
                    last = raw_rows[-1]
                    if c2:
                        last.field_name = (last.field_name + " " + c2).strip()
                    if c3 and last.row_type == "field":
                        last.instructions = (last.instructions + " " + c3).strip()

        if section_blocks:
            section_blocks[-1].end_row_idx = len(raw_rows) - 1

        return raw_rows, section_blocks
