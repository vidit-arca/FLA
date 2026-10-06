"""
Stage 1 — PDF Understanding
Extracts page layout, metadata, character geometry, and dynamically detects column boundaries.
"""

import re
import pdfplumber
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class PageLine:
    y: float
    c1_text: str  # Field No. column (< col1_max)
    c2_text: str  # Field Name column (col1_max to col2_max)
    c3_text: str  # Instructions column (>= col2_max)
    full_text: str


@dataclass
class PageLayout:
    page_number: int
    lines: List[PageLine]
    col1_max: float
    col2_max: float


class Stage1PdfLayout:
    """
    Extracts PDF metadata, performs character-level deduplication,
    locates Part III pages, and segments each line into the 3 statutory columns.
    """

    @staticmethod
    def _deduplicate_chars(chars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Removes faux-bold overlapping duplicate characters drawn within ~4pt."""
        sorted_chars = sorted(chars, key=lambda c: (round(c['top'], 1), round(c['x0'], 1)))
        deduped = []
        for c in sorted_chars:
            if deduped:
                prev = deduped[-1]
                if prev['text'] == c['text'] and abs(prev['x0'] - c['x0']) < 3.5 and abs(prev['top'] - c['top']) < 4.0:
                    continue
            deduped.append(c)
        return deduped

    def process(self, pdf_bytes_or_path: Any) -> Tuple[List[PageLayout], str, str, int, int]:
        """
        Parses PDF into Part III PageLayout objects with column-segmented lines.
        Returns: (layouts, form_name, governing_law, part3_start, part3_end)
        """
        import io
        import os
        if isinstance(pdf_bytes_or_path, (str, os.PathLike)):
            pdf_ctx = pdfplumber.open(pdf_bytes_or_path)
        elif isinstance(pdf_bytes_or_path, bytes):
            pdf_ctx = pdfplumber.open(io.BytesIO(pdf_bytes_or_path))
        else:
            pdf_ctx = pdfplumber.open(pdf_bytes_or_path)

        with pdf_ctx as pdf:
            total = len(pdf.pages)
            form_name = "MCA Form"
            governing_law = "Companies Act, 2013 / LLP Act, 2008"

            # 1. Metadata extraction from initial 4 pages
            for i in range(min(4, total)):
                txt = pdf.pages[i].extract_text() or ""
                m_fn = re.search(r"Instruction\s+Kit\s+for\s+(?:webform\s+)?((?:LLP\s+)?Form\s+(?:No\.?\s*)?[A-Za-z0-9\-]+(?:\s+[A-Za-z0-9\-]+)?)", txt, re.I)
                if not m_fn:
                    m_fn = re.search(r"Instruction\s+Kit\s+for\s+(?:webform\s+)?([A-Za-z0-9\s\.\-]+?)(?:\s*\n|\s*\(|$)", txt, re.I)
                if m_fn and m_fn.group(1).strip() and len(m_fn.group(1).strip()) < 50:
                    form_name = m_fn.group(1).strip()
                    break

                for pat in [
                    r"Pursuant to ([^\n\.]{10,150})",
                    r"Under section ([^\n\.]{10,80}(?:Act|Rules)[^\n\.]{0,40})",
                ]:
                    m2 = re.search(pat, txt, re.I)
                    if m2:
                        governing_law = m2.group(0).strip()
                        break

            # 2. Locate Part III pages (strictly skipping Table of Contents)
            part3_start = None
            part3_end = total
            for i in range(total):
                txt = pdf.pages[i].extract_text() or ""
                if 'about this document' in txt.lower() or len(re.findall(r'\.{5,}', txt)) >= 3:
                    continue
                if part3_start is None:
                    if re.search(r'(?:^|\n)\s*(?:3\s+)?PART\s+(?:III|3)\s*[–\-–]', txt, re.M | re.I):
                        part3_start = i
                else:
                    if re.search(r'(?:^|\n)\s*(?:4\s+)?PART\s+(?:IV|4)\s*[–\-]|(?:^|\n)\s*3\.2\s+Other|KEY\s+POINT', txt, re.M | re.I):
                        part3_end = i
                        break
            if part3_start is None:
                part3_start = 0

            # 3. Dynamic Column Bounding Calibration across Part III
            col1_max = 120.0
            col2_max = 280.0
            hdr_top = 160.0
            for i in range(part3_start, min(part3_end, total)):
                p = pdf.pages[i]
                words = [w for w in p.extract_words() if 70 <= w['top'] <= 220]
                name_words = [w for w in words if w['text'].lower() == 'name' and 120 < w['x0'] < 200]
                for nw in name_words:
                    matching_inst = [w for w in words if 'instruction' in w['text'].lower() and w['x0'] > 250 and abs(w['top'] - nw['top']) < 20]
                    if matching_inst:
                        col2_max = matching_inst[0]['x0'] - 4.0
                        preceding_field = [w for w in words if w['text'].lower() == 'field' and 115 < w['x0'] < nw['x0'] and abs(w['top'] - nw['top']) < 10]
                        if preceding_field:
                            col1_max = preceding_field[0]['x0'] - 4.0
                        else:
                            col1_max = nw['x0'] - 30.0
                        hdr_top = min([nw['top'], matching_inst[0]['top']]) - 5.0
                        break
                if col2_max != 280.0:
                    break

            # 4. Extract lines per page
            layouts = []
            for p_idx in range(part3_start, min(part3_end, total)):
                p = pdf.pages[p_idx]
                deduped = self._deduplicate_chars(p.chars)
                body_chars = [c for c in deduped if 70 <= c['top'] <= 745]
                if p_idx == part3_start:
                    body_chars = [c for c in body_chars if c['top'] >= hdr_top]

                page_lines_map: Dict[float, List[Dict[str, Any]]] = {}
                for c in body_chars:
                    y = round(c['top'] / 7.5) * 7.5
                    page_lines_map.setdefault(y, []).append(c)

                page_lines = []
                for y in sorted(page_lines_map.keys()):
                    lc = sorted(page_lines_map[y], key=lambda c: c['x0'])
                    c1 = ''.join(c['text'] for c in lc if c['x0'] < col1_max).strip()
                    c2 = ''.join(c['text'] for c in lc if col1_max <= c['x0'] < col2_max).strip()
                    c3 = ''.join(c['text'] for c in lc if c['x0'] >= col2_max).strip()
                    full = ''.join(c['text'] for c in lc).strip()
                    page_lines.append(PageLine(y=y, c1_text=c1, c2_text=c2, c3_text=c3, full_text=full))

                layouts.append(PageLayout(
                    page_number=p_idx + 1,
                    lines=page_lines,
                    col1_max=col1_max,
                    col2_max=col2_max
                ))

            return layouts, form_name, governing_law, part3_start, part3_end
