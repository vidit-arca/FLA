import io
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Union
import pdfplumber
from sqlalchemy import or_
from ..core.db import SessionLocal
from ..core import models

logger = logging.getLogger("idp_studio.spatial")

def get_effective_rules(
    template_name: str,
    company_id: Optional[str] = None,
    scenario: Optional[str] = None,
    document_type: Optional[str] = None
) -> Dict[str, models.SchemaAliasRule]:
    """
    Implements 3-Tier Multi-Tenant Hierarchical Shadowing Cascade:
      Priority 3: Company-specific rule (scope_id == company_id / CIN)
      Priority 2: Scenario-specific rule (scope_id == scenario e.g. 'casual_vacancy')
      Priority 1: Global base rule (scope_type == 'GLOBAL')
    
    Returns a dictionary of {form_field: SchemaAliasRule}, where higher priority rules
    cleanly shadow lower priority rules.
    """
    db = SessionLocal()
    try:
        query = db.query(models.SchemaAliasRule).filter(
            models.SchemaAliasRule.template_name == template_name
        )

        # Document type filter if specified
        if document_type and document_type != "generic":
            query = query.filter(
                or_(
                    models.SchemaAliasRule.document_type == document_type,
                    models.SchemaAliasRule.document_type == "generic",
                    models.SchemaAliasRule.document_type.is_(None)
                )
            )

        # Build scope filters
        scope_conditions = [models.SchemaAliasRule.scope_type == "GLOBAL"]
        if scenario:
            scope_conditions.append(
                (models.SchemaAliasRule.scope_type == "SCENARIO") &
                (
                    (models.SchemaAliasRule.scope_id == scenario) |
                    (models.SchemaAliasRule.scope_id == "default") |
                    (models.SchemaAliasRule.scope_id.is_(None))
                )
            )
        else:
            scope_conditions.append(
                (models.SchemaAliasRule.scope_type == "SCENARIO") &
                (
                    (models.SchemaAliasRule.scope_id == "default") |
                    (models.SchemaAliasRule.scope_id.is_(None))
                )
            )
        if company_id:
            scope_conditions.append(
                (models.SchemaAliasRule.scope_type == "COMPANY") &
                (
                    (models.SchemaAliasRule.scope_id == company_id) |
                    (models.SchemaAliasRule.scope_id == "default") |
                    (models.SchemaAliasRule.scope_id.is_(None))
                )
            )

        query = query.filter(or_(*scope_conditions)).order_by(models.SchemaAliasRule.priority.desc())
        all_rules = query.all()

        # Shadowing deduplication: First occurrence per form_field wins (highest priority)
        effective = {}
        for r in all_rules:
            if r.form_field not in effective:
                effective[r.form_field] = r

        return effective
    except Exception as e:
        print(f"[IDP Spatial] Error fetching effective rules: {e}")
        return {}
    finally:
        db.close()


def get_scenario_lexicon(template_name: str, scenario: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Data-Driven Keyword Harvester:
    Harvests real-world keywords and anchor texts directly from:
      1. SchemaAliasRule.extracted_key
      2. SchemaAliasRule.spatial_meta_json (anchor_text)
      3. DomExtractionRule (variable_name / dom_path)
    
    Zero manual/hardcoded dictionaries — pulls actual drafting terminology
    recorded from previous mappings under this legal scenario!
    """
    db = SessionLocal()
    lexicon = {}
    try:
        # 1. Harvest from SchemaAliasRule
        scope_conditions = [models.SchemaAliasRule.scope_type == "GLOBAL"]
        if scenario:
            scope_conditions.append(
                (models.SchemaAliasRule.scope_type == "SCENARIO") &
                (models.SchemaAliasRule.scope_id == scenario)
            )

        rules = db.query(models.SchemaAliasRule).filter(
            models.SchemaAliasRule.template_name == template_name,
            or_(*scope_conditions)
        ).all()

        for r in rules:
            field = r.form_field
            if field not in lexicon:
                lexicon[field] = []

            # Add extracted_key if not empty
            if r.extracted_key and r.extracted_key.strip():
                k = r.extracted_key.strip()
                if k not in lexicon[field]:
                    lexicon[field].append(k)

            # Add anchor_text from spatial metadata if present
            if r.spatial_meta_json:
                try:
                    meta = json.loads(r.spatial_meta_json) if isinstance(r.spatial_meta_json, str) else r.spatial_meta_json
                    anchor = meta.get("anchor_text") or meta.get("anchor")
                    if anchor and anchor.strip() and anchor.strip() not in lexicon[field]:
                        lexicon[field].append(anchor.strip())
                except Exception:
                    pass

        # 2. Harvest from DomExtractionRule (untouched table read)
        dom_scope_conditions = [models.DomExtractionRule.scope_type == "GLOBAL"]
        if scenario:
            dom_scope_conditions.append(
                (models.DomExtractionRule.scope_type == "SCENARIO") &
                (models.DomExtractionRule.scope_id == scenario)
            )

        dom_rules = db.query(models.DomExtractionRule).filter(
            models.DomExtractionRule.template_name == template_name,
            or_(*dom_scope_conditions)
        ).all()

        for dr in dom_rules:
            var = dr.variable_name
            if var and var.strip():
                v = var.strip()
                # Find matching field in lexicon
                matched_field = None
                for f in lexicon.keys():
                    if f.lower() in v.lower() or v.lower() in f.lower():
                        matched_field = f
                        break
                if matched_field:
                    if v not in lexicon[matched_field]:
                        lexicon[matched_field].append(v)

        return lexicon
    except Exception as e:
        print(f"[IDP Spatial] Error harvesting scenario lexicon: {e}")
        return {}
    finally:
        db.close()


def get_spatial_rules(
    template_name: str,
    company_id: Optional[str] = None,
    scenario: Optional[str] = None
) -> Dict[str, models.SpatialRule]:
    """Fetches effective spatial rules honoring 3-tier cascade."""
    return get_effective_rules(template_name, company_id=company_id, scenario=scenario)


def extract_text_from_spatial_meta(
    pdf_input: Union[bytes, str, io.BytesIO, pdfplumber.PDF],
    spatial_meta: Union[Dict[str, Any], str],
    opened_pdf: Optional[pdfplumber.PDF] = None
) -> Optional[str]:
    """
    Extracts text from a PDF page using spatial bounding-box or anchor-relative geometry.

    Supports:
      1. Normalized [0.0, 1.0] coordinates or absolute PDF points [72 pt/in].
      2. Direct Bounding Box: {page, x, y, width, height}.
      3. Anchor-Relative: {anchor_text, dx, dy, width, height, page}.
      4. Digital text layer extraction with fallback to image-crop OCR for scanned PDFs.
    """
    if not spatial_meta:
        return None

    if isinstance(spatial_meta, str):
        try:
            spatial_meta = json.loads(spatial_meta)
        except Exception:
            return None

    if not isinstance(spatial_meta, dict):
        return None

    close_pdf = False
    pdf_ctx = opened_pdf

    if pdf_ctx is None:
        if isinstance(pdf_input, pdfplumber.PDF) or hasattr(pdf_input, "pages"):
            pdf_ctx = pdf_input
        elif isinstance(pdf_input, bytes):
            pdf_ctx = pdfplumber.open(io.BytesIO(pdf_input))
            close_pdf = True
        elif isinstance(pdf_input, io.BytesIO):
            pdf_ctx = pdfplumber.open(pdf_input)
            close_pdf = True
        elif isinstance(pdf_input, (str, os.PathLike)) and os.path.exists(pdf_input):
            pdf_ctx = pdfplumber.open(pdf_input)
            close_pdf = True
        else:
            return None

    try:
        total_pages = len(pdf_ctx.pages)
        if total_pages == 0:
            return None

        # Determine target page (1-based index from meta, fallback to page 1)
        target_page_num = int(spatial_meta.get("page") or 1)
        if target_page_num < 1 or target_page_num > total_pages:
            target_page_num = 1
        page = pdf_ctx.pages[target_page_num - 1]

        pw = float(page.width)
        ph = float(page.height)

        anchor_text = spatial_meta.get("anchor_text") or spatial_meta.get("anchor")
        x = spatial_meta.get("x")
        y = spatial_meta.get("y")
        width = spatial_meta.get("width")
        height = spatial_meta.get("height")
        dx = float(spatial_meta.get("dx") or 0.0)
        dy = float(spatial_meta.get("dy") or 0.0)

        # Mode A: Anchor-Relative Matching
        if anchor_text and (dx != 0.0 or dy != 0.0 or width is not None):
            anchor_clean = str(anchor_text).strip().lower()
            words = page.extract_words() if hasattr(page, "extract_words") else []
            matching_words = [w for w in words if anchor_clean in w.get('text', '').lower() or w.get('text', '').lower() in anchor_clean]
            
            if matching_words:
                # Use bounding box of the matching anchor word(s)
                anc_x0 = min(w['x0'] for w in matching_words)
                anc_top = min(w['top'] for w in matching_words)
                anc_x1 = max(w['x1'] for w in matching_words)
                anc_bottom = max(w['bottom'] for w in matching_words)

                # Offset relative to anchor
                w_pts = float(width * pw) if (width is not None and width <= 1.0) else (float(width) if width else 150.0)
                h_pts = float(height * ph) if (height is not None and height <= 1.0) else (float(height) if height else (anc_bottom - anc_top + 4.0))

                dx_pts = float(dx * pw) if abs(dx) <= 1.0 and dx != 0.0 else float(dx)
                dy_pts = float(dy * ph) if abs(dy) <= 1.0 and dy != 0.0 else float(dy)

                x0 = max(0.0, anc_x1 + dx_pts)
                top = max(0.0, anc_top + dy_pts)
                x1 = min(pw, x0 + w_pts)
                bottom = min(ph, top + h_pts)
            else:
                x0, top, x1, bottom = None, None, None, None
        else:
            x0, top, x1, bottom = None, None, None, None

        # Mode B: Direct Bounding Box via bbox list [ymin, xmin, ymax, xmax] or [x0, top, x1, bottom]
        bbox_list = spatial_meta.get("bbox") or spatial_meta.get("bounding_box")
        if x0 is None and isinstance(bbox_list, (list, tuple)) and len(bbox_list) == 4:
            c0, c1, c2, c3 = [float(v) for v in bbox_list]
            if max(c0, c1, c2, c3) <= 1.0:
                if c0 <= c2 and c1 <= c3:
                    # Marker [ymin, xmin, ymax, xmax] format
                    top = c0 * ph
                    x0 = c1 * pw
                    bottom = c2 * ph
                    x1 = c3 * pw
                else:
                    x0 = c0 * pw
                    top = c1 * ph
                    x1 = c2 * pw
                    bottom = c3 * ph
            else:
                top, x0, bottom, x1 = c0, c1, c2, c3

        # Mode C: Direct Bounding Box (x, y, width, height)
        if x0 is None and x is not None and y is not None and width is not None and height is not None:
            raw_x = float(x)
            raw_y = float(y)
            raw_w = float(width)
            raw_h = float(height)

            if raw_x <= 1.0 and raw_y <= 1.0 and raw_w <= 1.0 and raw_h <= 1.0:
                # Normalized coordinates
                x0 = max(0.0, raw_x * pw)
                top = max(0.0, raw_y * ph)
                x1 = min(pw, x0 + (raw_w * pw))
                bottom = min(ph, top + (raw_h * ph))
            else:
                # Absolute PDF points
                x0 = max(0.0, raw_x)
                top = max(0.0, raw_y)
                x1 = min(pw, x0 + raw_w)
                bottom = min(ph, top + raw_h)

        if x0 is None or top is None or x1 is None or bottom is None:
            return None

        # Ensure valid non-zero dimensions
        if x1 <= x0:
            x1 = min(pw, x0 + 10.0)
        if bottom <= top:
            bottom = min(ph, top + 10.0)

        # 1. Digital text extraction via within_bbox
        bbox = (x0, top, x1, bottom)
        try:
            cropped = page.within_bbox(bbox)
            text = cropped.extract_text()
            if text and text.strip():
                clean_txt = text.strip()
                # Strip leading colon or hyphen if captured from label
                clean_txt = re.sub(r'^[:\|\-\s]+', '', clean_txt).strip()
                if clean_txt:
                    return clean_txt
        except Exception as crop_err:
            logger.debug(f"[Spatial] pdfplumber within_bbox error: {crop_err}")

        # 2. Image-Crop OCR Fallback for scanned documents
        try:
            cropped_page = page.within_bbox(bbox)
            img = cropped_page.to_image(resolution=300).original
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            raw_img_bytes = img_byte_arr.getvalue()

            # Attempt Triton OCR on cropped image
            import tritonclient.http as httpclient
            import numpy as np
            client = httpclient.InferenceServerClient(
                url="192.168.112.2:8000",
                network_timeout=5.0,
                connection_timeout=2.0
            )
            input_tensor = httpclient.InferInput("PDF_BYTES", [1], "BYTES")
            input_tensor.set_data_from_numpy(np.array([raw_img_bytes], dtype=np.object_))
            output_tensor = httpclient.InferRequestedOutput("MARKDOWN")
            resp = client.infer(model_name="marker_model", inputs=[input_tensor], outputs=[output_tensor])
            ocr_text = resp.as_numpy("MARKDOWN")[0].decode("utf-8").strip()
            clean_ocr = re.sub(r'^[:\|\-\s]+', '', ocr_text).strip()
            if clean_ocr:
                return clean_ocr
        except Exception:
            pass

        return None

    finally:
        if close_pdf and pdf_ctx is not None:
            try:
                pdf_ctx.close()
            except Exception:
                pass


def apply_spatial_overrides(
    template_name: str,
    ocr_data: Dict[str, Any],
    extracted_data: Dict[str, Any],
    company_id: Optional[str] = None,
    scenario: Optional[str] = None,
    document_type: Optional[str] = None,
    rules: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Applies cascaded IDP spatial rules (Company > Scenario > Global) to extract values
    directly from PDF/OCR bounding box mathematics, overriding upstream regex or LLM results.
    """
    if rules is None:
        rules = get_effective_rules(template_name, company_id=company_id, scenario=scenario, document_type=document_type)
    if not rules:
        return extracted_data

    # Normalize rules into a dictionary if passed as a list
    rules_dict = {}
    if isinstance(rules, list):
        for r in rules:
            fid = getattr(r, "field_id", None) or getattr(r, "form_field", None)
            if fid:
                rules_dict[fid] = r
    elif isinstance(rules, dict):
        rules_dict = rules

    # Locate PDF input from ocr_data or parameters
    pdf_source = None
    if isinstance(ocr_data, dict):
        pdf_source = ocr_data.get("pdf_path") or ocr_data.get("pdf_bytes") or ocr_data.get("file_path") or ocr_data.get("pdf")
        if not pdf_source and "board_report" in ocr_data:
            pdf_source = ocr_data["board_report"].get("pdf_path")
        if not pdf_source and "financials" in ocr_data:
            pdf_source = ocr_data["financials"].get("pdf_path")
    elif isinstance(ocr_data, (str, bytes)):
        pdf_source = ocr_data
    elif hasattr(ocr_data, "pages"):
        pdf_source = ocr_data

    if not pdf_source:
        return extracted_data

    applied_count = 0
    try:
        if hasattr(pdf_source, "pages"):
            for form_field, rule in rules_dict.items():
                meta = getattr(rule, "spatial_meta_json", None)
                if not isinstance(meta, (dict, str)):
                    meta = getattr(rule, "bounding_box", None)
                if not isinstance(meta, (dict, str)):
                    meta = getattr(rule, "spatial_meta", None)
                if isinstance(meta, (dict, str)):
                    val = extract_text_from_spatial_meta(pdf_source, meta, opened_pdf=pdf_source)
                    if val and val.strip():
                        extracted_data[form_field] = val.strip()
                        applied_count += 1
                        logger.info(f"[IDP Spatial] Applied override: '{form_field}' = '{val.strip()}' (Priority {getattr(rule, 'priority', 100)})")
        else:
            with pdfplumber.open(io.BytesIO(pdf_source) if isinstance(pdf_source, bytes) else pdf_source) as pdf:
                for form_field, rule in rules_dict.items():
                    meta = getattr(rule, "spatial_meta_json", None)
                    if not isinstance(meta, (dict, str)):
                        meta = getattr(rule, "bounding_box", None)
                    if not isinstance(meta, (dict, str)):
                        meta = getattr(rule, "spatial_meta", None)
                    if isinstance(meta, (dict, str)):
                        val = extract_text_from_spatial_meta(pdf, meta, opened_pdf=pdf)
                        if val and val.strip():
                            extracted_data[form_field] = val.strip()
                            applied_count += 1
                            logger.info(f"[IDP Spatial] Applied override: '{form_field}' = '{val.strip()}' (Priority {getattr(rule, 'priority', 100)})")
    except Exception as e:
        logger.warning(f"[IDP Spatial] Error executing spatial overrides: {e}")

    if applied_count > 0:
        print(f"[IDP Studio] Successfully applied {applied_count} spatial overrides for {template_name}")

    return extracted_data
