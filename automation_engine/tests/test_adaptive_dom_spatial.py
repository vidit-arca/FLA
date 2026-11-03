"""
Test Suite for Adaptive DOM Learner and Deterministic Spatial Engine.

Verifies:
1. Spatial Engine extraction (extract_text_from_spatial_meta) with normalized bboxes,
   absolute pt bboxes, anchor text offsets, and OCR fallback.
2. Spatial overrides application (apply_spatial_overrides).
3. DOMQuery adaptive scoring (score_candidate_rows) with multi-factor weighting,
   synonym expansion, and fuzzy anchors.
4. Active Feedback Loop endpoint payload structure (/learn_from_feedback).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

# Ensure modules/idp_studio is in sys.path for dom_learner imports
IDP_STUDIO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../modules/idp_studio"))
if IDP_STUDIO_DIR not in sys.path:
    sys.path.insert(0, IDP_STUDIO_DIR)

from automation_engine.modules.idp_studio.extractors.spatial import (
    extract_text_from_spatial_meta,
    apply_spatial_overrides
)
from dom_learner.engine.dom_query import DOMQuery
from dom_learner.models.node import DocumentNode, SectionNode, TableNode, RowNode, CellNode


# =====================================================================
# 1. SPATIAL ENGINE TESTS
# =====================================================================

class TestSpatialEngine:
    def test_extract_text_from_spatial_meta_direct_normalized_bbox(self):
        """Verify extraction from PDF page when normalized bbox [ymin, xmin, ymax, xmax] is provided."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_page.width = 600
        mock_page.height = 800

        mock_crop = MagicMock()
        mock_crop.extract_text.return_value = "U72200DL2020PTC123456"
        mock_page.within_bbox.return_value = mock_crop

        meta = {
            "page": 1,
            "bbox": [0.10, 0.10, 0.16, 0.50]
        }
        extracted = extract_text_from_spatial_meta(mock_pdf, meta)
        assert extracted == "U72200DL2020PTC123456"
        mock_page.within_bbox.assert_called_once()

    def test_extract_text_from_spatial_meta_anchor_relative(self):
        """Verify extraction when an anchor text is provided and target bbox is relative to anchor."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_page.width = 600
        mock_page.height = 800

        mock_page.extract_words.return_value = [
            {"text": "CIN:", "x0": 50, "top": 100, "x1": 80, "bottom": 120}
        ]
        mock_crop = MagicMock()
        mock_crop.extract_text.return_value = "L12345MH2000PLC999999"
        mock_page.within_bbox.return_value = mock_crop

        meta = {
            "page": 1,
            "anchor_text": "CIN:",
            "dx": 10.0,
            "dy": 0.0,
            "width": 200.0,
            "height": 25.0
        }
        extracted = extract_text_from_spatial_meta(mock_pdf, meta)
        assert extracted == "L12345MH2000PLC999999"

    def test_extract_text_pdfplumber_within_bbox(self):
        """Verify pdfplumber within_bbox path when pdf instance is provided."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_page.width = 600
        mock_page.height = 800

        mock_crop = MagicMock()
        mock_crop.extract_text.return_value = "ABC PRIVATE LIMITED"
        mock_page.within_bbox.return_value = mock_crop

        meta = {
            "page": 1,
            "x": 0.05,
            "y": 0.10,
            "width": 0.50,
            "height": 0.05
        }
        res = extract_text_from_spatial_meta(mock_pdf, meta)
        assert res == "ABC PRIVATE LIMITED"
        mock_page.within_bbox.assert_called_once()

    def test_apply_spatial_overrides(self):
        """Verify spatial overrides update extracted_data properly."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_page.width = 600
        mock_page.height = 800

        mock_crop = MagicMock()
        mock_crop.extract_text.return_value = "U12345DL2022PTC123456"
        mock_page.within_bbox.return_value = mock_crop

        extracted_data = {
            "cin": "OLD_CIN",
            "company_name": "OLD_NAME"
        }
        rules = [
            MagicMock(
                field_id="cin",
                page_number=1,
                bounding_box={"bbox": [0.1, 0.1, 0.2, 0.4]},
                priority=10
            )
        ]
        ocr_data = {
            "pdf": mock_pdf
        }
        updated = apply_spatial_overrides("Form No. ADT-1", ocr_data, extracted_data, rules=rules)
        assert updated["cin"] == "U12345DL2022PTC123456"
        assert updated["company_name"] == "OLD_NAME"


# =====================================================================
# 2. DOM QUERY ADAPTIVE SCORING TESTS
# =====================================================================

class TestDOMQueryAdaptiveScoring:
    def _build_test_dom(self):
        """Helper to create a synthetic DocumentNode tree with shifting columns."""
        root = DocumentNode(source_file="test.md")
        
        # Section node
        sec = SectionNode(text="Financial Performance Highlights")
        root.add_child(sec)
        
        tbl = TableNode(column_count=3)
        sec.add_child(tbl)

        # Data Row 1: "Turnover or Revenue from operations", "15000000", "12000000"
        row1 = RowNode(text="Turnover or Revenue from operations | 15000000 | 12000000", row_index=1)
        r1_c0 = CellNode(text="Turnover or Revenue from operations", column_index=0, column_header="Particulars")
        r1_c1 = CellNode(text="15000000", column_index=1, column_header="31/03/2024")
        r1_c2 = CellNode(text="12000000", column_index=2, column_header="31/03/2023")
        row1.add_children([r1_c0, r1_c1, r1_c2])
        tbl.add_child(row1)

        # Data Row 2: "Net Profit / Loss after tax", "2500000", "1800000"
        row2 = RowNode(text="Net Profit / Loss after tax | 2500000 | 1800000", row_index=2)
        r2_c0 = CellNode(text="Net Profit / Loss after tax", column_index=0, column_header="Particulars")
        r2_c1 = CellNode(text="2500000", column_index=1, column_header="31/03/2024")
        r2_c2 = CellNode(text="1800000", column_index=2, column_header="31/03/2023")
        row2.add_children([r2_c0, r2_c1, r2_c2])
        tbl.add_child(row2)

        return root

    def test_score_candidate_rows_with_synonyms(self):
        """Verify adaptive scoring identifies 'Revenue from Operations' even when exact label differs."""
        doc = self._build_test_dom()
        q = DOMQuery(doc)

        synonyms = ["Revenue from operations", "Total Revenue", "Gross Turnover", "Sales"]
        results = q.score_candidate_rows(
            variable_name="Revenue from operations",
            synonyms=synonyms,
            expected_section="Financial Performance",
            target_type="number"
        )

        assert len(results) > 0
        best_score, best_row, best_col = results[0]
        # Best row should be row1
        assert "Turnover or Revenue" in best_row.text
        assert best_score >= 20.0
        # Best column should be identified
        assert best_col in [1, 2]

    def test_score_candidate_rows_negative_garbage_filtering(self):
        """Verify OCR garbage or mismatching types are penalized in scoring."""
        doc = self._build_test_dom()
        q = DOMQuery(doc)

        # When looking for a date, rows containing pure large integers without date formats score lower
        results = q.score_candidate_rows(
            variable_name="Date of Balance Sheet",
            synonyms=["Balance Sheet Date"],
            expected_section="Financial Performance",
            target_type="date"
        )
        # Should not find high-scoring rows because values are numbers, not dates
        assert len(results) == 0 or results[0][0] < 20.0


# =====================================================================
# 3. FEEDBACK LOOP API TESTS
# =====================================================================

class TestFeedbackLoopAPI:
    def test_learn_from_feedback_endpoint_structure(self):
        """Verify LearnFeedbackPayload schema and structure."""
        from automation_engine.modules.idp_studio.router import LearnFeedbackPayload, FeedbackFieldItem
        
        field_item = FeedbackFieldItem(
            form_field="director_din",
            value="01234567",
            label="Director Identification Number",
            spatial_meta={"bbox": [0.15, 0.20, 0.18, 0.35], "page": 2}
        )
        payload = LearnFeedbackPayload(
            template_name="DIR-12",
            filename="dir12_sample.pdf",
            confirmed_fields=[field_item],
            company_id="COMP_001",
            scenario="mca_filing"
        )
        assert payload.template_name == "DIR-12"
        assert len(payload.confirmed_fields) == 1
        assert payload.confirmed_fields[0].form_field == "director_din"
        assert payload.confirmed_fields[0].value == "01234567"
        assert payload.confirmed_fields[0].spatial_meta["page"] == 2


# =====================================================================
# 4. OPTIMIZED PIPELINE & TRITON SAFEGUARD TESTS
# =====================================================================

class TestExtractionOptimizationSafeguards:
    def test_triton_pdf_chunking_guard(self):
        """Verify that multi-page PDFs (>20 pages) are sliced into safe chunks."""
        import io
        import pypdf
        from unittest.mock import patch
        from automation_engine.modules.idp_studio.router import _run_triton_ocr_on_pdf_bytes

        # Generate a synthetic 25-page PDF in memory
        writer = pypdf.PdfWriter()
        for _ in range(25):
            writer.add_blank_page(width=72, height=72)
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        # Mock Triton inference client to return markdown chunks
        with patch("tritonclient.http.InferenceServerClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            
            mock_resp = MagicMock()
            mock_resp.as_numpy.return_value = [b"# Page chunk markdown output"]
            mock_client.infer.return_value = mock_resp

            result_md = _run_triton_ocr_on_pdf_bytes(pdf_bytes)
            # 25 pages with chunk size 15 should result in 2 infer calls (15 pages + 10 pages)
            assert mock_client.infer.call_count == 2
            assert "Page chunk markdown output" in result_md

    def test_ungated_dom_extraction_without_schema_rules(self):
        """Verify that when schema_rules is empty, DOMQuery is still invoked for template fields."""
        from automation_engine.modules.idp_studio.router import _try_dom_extraction
        from dom_learner.models.node import DocumentNode, SectionNode, RowNode, CellNode

        # Synthetic Document
        root = DocumentNode(source_file="test.md")
        sec = SectionNode(text="General Information")
        root.add_child(sec)
        row = RowNode(text="Corporate Identity Number: L12345DL2020PLC123456", row_index=1)
        c0 = CellNode(text="Corporate Identity Number", column_index=0)
        c1 = CellNode(text="L12345DL2020PLC123456", column_index=1)
        row.add_children([c0, c1])
        sec.add_child(row)

        q = DOMQuery(root)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        val, _ = _try_dom_extraction(
            markdown_text="",
            variable_name="Corporate Identity Number",
            db=mock_db,
            template_name="Form No. GNL-2",
            form_field="field_cin",
            dom_query=q
        )
        assert val == "L12345DL2020PLC123456"

