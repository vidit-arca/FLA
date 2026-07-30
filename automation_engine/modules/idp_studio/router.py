from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid
import datetime
import pandas as pd
import json
import io
import os
import sys

from .db import get_db, engine
from . import models

# Ensure tables are created
models.Base.metadata.create_all(bind=engine)

router = APIRouter()

class IdpTemplateResponse(BaseModel):
    template_id: str
    template_name: str
    fields_json: str
    
    class Config:
        orm_mode = True

def get_default_fla_template_fields():
    try:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        config_path = os.path.join(root_dir, "modules", "fla", "rules_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            field_keys = set()
            for r_type in ["company_extraction_rules", "financial_extraction_rules"]:
                if r_type in cfg:
                    field_keys.update(cfg[r_type].keys())
            if "cell_mappings" in cfg:
                for sec, cells in cfg["cell_mappings"].items():
                    for cell_id, cell_cfg in cells.items():
                        if cell_cfg.get("field"):
                            field_keys.add(cell_cfg.get("field"))
            field_keys.update([
                "equity_shares_count_fy", "equity_shares_count_py",
                "equity_face_value", "part_pref_shares_count_fy",
                "part_pref_shares_count_py", "non_part_pref_shares_count_fy",
                "non_part_pref_shares_count_py"
            ])
            fields = []
            for k in sorted(field_keys):
                label = k.replace("_", " ").title()
                fields.append({"id": k, "label": label})
            return fields
    except Exception as e:
        print(f"[!] Error loading FLA fields for default template: {e}")
    return []

@router.get("/templates", response_model=List[IdpTemplateResponse])
def get_all_templates(db: Session = Depends(get_db)):
    templates = db.query(models.IdpTemplate).all()
    existing_names = {t.template_name for t in templates}
    
    # Always include standard FLA Return form schema at the top of the dropdown
    fla_template_name = "FLA Return (Standard Form)"
    if fla_template_name not in existing_names:
        default_fields = get_default_fla_template_fields()
        templates.insert(0, models.IdpTemplate(
            template_id="default-fla-return",
            template_name=fla_template_name,
            fields_json=json.dumps(default_fields)
        ))
        existing_names.add(fla_template_name)
    
    saved_rules = db.query(models.SchemaAliasRule.template_name).distinct().all()
    for (t_name,) in saved_rules:
        if t_name and t_name not in existing_names:
            templates.append(
                models.IdpTemplate(
                    template_id=t_name,
                    template_name=t_name,
                    fields_json="[]"
                )
            )
            existing_names.add(t_name)
            
    return templates


@router.post("/templates/upload")
async def upload_pdf_template(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for form template upload")
        
    contents = await file.read()
    try:
        import pdfplumber as _pdfplumber
        
        fields = []
        seen_labels = set()
        
        with _pdfplumber.open(io.BytesIO(contents)) as pdf:
            page_width = pdf.pages[0].width if pdf.pages else 612.0
            # Left half = field labels. Right half = values (ignore).
            # Use 45% of page width as cutoff to be safe on narrow forms.
            label_x_cutoff = page_width * 0.45

            for page in pdf.pages:
                words = page.extract_words()
                if not words:
                    continue

                # Group words by approximate row (bucket y into 8pt bands)
                rows: dict = {}
                for w in words:
                    # Only keep words in the label (left) column
                    if w['x0'] >= label_x_cutoff:
                        continue
                    row_key = round(float(w['top']) / 8) * 8
                    rows.setdefault(row_key, []).append(w)

                for row_key in sorted(rows.keys()):
                    row_words = sorted(rows[row_key], key=lambda w: w['x0'])
                    line_text = ' '.join(w['text'] for w in row_words).strip()

                    # Skip very short lines, pure numbers, headers, checkmarks, etc.
                    if len(line_text) < 4:
                        continue
                    if line_text.replace(',', '').replace('.', '').replace('-', '').isdigit():
                        continue
                    # Skip lines that are clearly header/meta (page titles, instructions)
                    skip_prefixes = ('refer instruction', 'all fields marked', 'pursuant to', 'llp form no', 'm2')
                    if any(line_text.lower().startswith(p) for p in skip_prefixes):
                        continue
                    # Skip checkmark lines
                    if '✔' in line_text or '✓' in line_text:
                        continue

                    clean_label = line_text.replace('\n', ' ').strip()
                    # Truncate very long descriptions (keep first 120 chars)
                    if len(clean_label) > 120:
                        clean_label = clean_label[:120].strip()

                    if clean_label not in seen_labels:
                        seen_labels.add(clean_label)
                        field_id = ''.join(e for e in clean_label.lower() if e.isalnum() or e == '_')[:50]
                        fields.append({
                            "id": f"field_{field_id}",
                            "label": clean_label
                        })

        template_name = file.filename.replace(".pdf", "").replace(".PDF", "")
        template_id = str(uuid.uuid4())
        
        db_template = models.IdpTemplate(
            template_id=template_id,
            template_name=template_name,
            fields_json=json.dumps(fields)
        )
        db.add(db_template)
        db.commit()
        db.refresh(db_template)
        
        return {"message": "Template created from PDF", "template_id": template_id, "fields": fields}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error parsing PDF template: {str(e)}")


from typing import Optional, Dict, Any

class SchemaAliasCreate(BaseModel):
    template_name: str
    form_field: str
    extracted_key: str
    spatial_meta: Optional[Dict[str, Any]] = None

class SchemaAliasResponse(SchemaAliasCreate):
    rule_id: str
    
    class Config:
        orm_mode = True

class RuleHistoryResponse(BaseModel):
    rule_id: str
    variable_name: str
    dom_path: str
    success_count: int
    created_at: datetime.datetime
    
    class Config:
        orm_mode = True

@router.get("/rules_history/{template_name}", response_model=List[RuleHistoryResponse])
def get_rule_history(template_name: str, db: Session = Depends(get_db)):
    """Fetch all DOM extraction rules (historical memory) for a specific template."""
    rules = db.query(models.DomExtractionRule).filter(
        models.DomExtractionRule.template_name == template_name
    ).order_by(models.DomExtractionRule.created_at.desc()).all()
    return rules

# ==============================================================================
# NEW: POST /test_fla_engine — Bridge to the Old FLA Module
# ==============================================================================
@router.post("/test_fla_engine")
async def test_fla_engine(payload: Dict[str, Any] = Body(...)):
    """
    Takes the mapped dictionary from IDP Studio, feeds it into the old 
    FLA RuleEngine, and returns the computed state.
    """
    try:
        # Dynamically import the old RuleEngine to keep modules independent
        import sys
        import os
        # Add root to sys path if not there
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if root_dir not in sys.path:
            sys.path.append(root_dir)
            
        from modules.fla.rule_engine import RuleEngine
        
        # Initialize engine (assumes it runs from root or handles its own path)
        engine = RuleEngine(config_path="modules/fla/rules_config.json")
        
        # Evaluate using the provided payload
        computed_state = engine.evaluate_all(payload)
        
        return {
            "status": "success",
            "computed_state": computed_state
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"FLA Engine Error: {str(e)}")

# ==============================================================================
# NEW: POST /generate_excel — Generate and download populated Excel from IDP mappings
# ==============================================================================
@router.post("/generate_excel")
async def generate_excel_from_idp(payload: Dict[str, Any] = Body(...)):
    """
    Takes the mapped dictionary from IDP Studio, evaluates it via legacy FLA RuleEngine,
    populates the skeletal Excel template, and returns the physical .xlsx file.
    """
    try:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if root_dir not in sys.path:
            sys.path.append(root_dir)
            
        from modules.fla.rule_engine import RuleEngine
        from core.excel_writer import ExcelWriter
        
        # 1. Compute target cells via legacy RuleEngine
        engine = RuleEngine(config_path="modules/fla/rules_config.json")
        target_cells = engine.evaluate_all(payload)
        
        # 2. Setup paths
        skeletal_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fla", "excel", "FLA Return existing skeletal.xlsx"))
        if not os.path.exists(skeletal_path):
            raise FileNotFoundError(f"Skeletal Excel not found at: {skeletal_path}")
            
        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "output", "idp_generated"))
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"FLA_Return_Populated_{uuid.uuid4().hex[:8]}.xlsx"
        output_path = os.path.join(output_dir, output_filename)
        
        # 3. Write Excel
        writer = ExcelWriter(skeletal_path, output_path)
        writer.write_values(target_cells)
        
        # 4. Return file response for download
        return FileResponse(
            path=output_path,
            filename="FLA_Return_Populated.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Excel Generation Error: {str(e)}")

@router.get("/rules/{template_name}", response_model=List[SchemaAliasResponse])
def get_rules_for_template(template_name: str, db: Session = Depends(get_db)):
    rules = db.query(models.SchemaAliasRule).filter(models.SchemaAliasRule.template_name == template_name).all()
    return rules

@router.post("/rules", response_model=SchemaAliasResponse)
def create_schema_alias_rule(rule: SchemaAliasCreate, db: Session = Depends(get_db)):
    # Delete existing rule for this template + form_field combination if it exists
    existing = db.query(models.SchemaAliasRule).filter(
        models.SchemaAliasRule.template_name == rule.template_name,
        models.SchemaAliasRule.form_field == rule.form_field
    ).first()
    
    if existing:
        db.delete(existing)
        db.commit()
        
    spatial_json = None
    if rule.spatial_meta:
        import json as python_json
        spatial_json = python_json.dumps(rule.spatial_meta)
        
    db_rule = models.SchemaAliasRule(
        rule_id=str(uuid.uuid4()),
        template_name=rule.template_name,
        form_field=rule.form_field,
        extracted_key=rule.extracted_key,
        spatial_meta_json=spatial_json
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule

@router.delete("/rules/{rule_id}")
def delete_schema_alias_rule(rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(models.SchemaAliasRule).filter(models.SchemaAliasRule.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"message": "Deleted successfully"}

import requests
import pdfplumber
import sys
import os
import tempfile
import datetime

# ==============================================================================
# DOM LEARNER HELPERS
# ==============================================================================

def _get_dom_query_from_markdown(markdown_text: str):
    """
    Converts OCR markdown text into a DOMQuery object using the dom_learner engine.
    Returns the DOMQuery object, or None if building fails.
    """
    try:
        # Ensure the dom_learner package is importable from router.py context
        _idp_studio_dir = os.path.dirname(os.path.abspath(__file__))
        if _idp_studio_dir not in sys.path:
            sys.path.insert(0, _idp_studio_dir)

        from dom_learner.engine.dom_builder import DOMBuilder
        from dom_learner.engine.dom_query import DOMQuery

        # DOMBuilder expects a file path, so write markdown to a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp:
            tmp.write(markdown_text)
            tmp_path = tmp.name

        try:
            from pathlib import Path
            builder = DOMBuilder()
            document = builder.build(Path(tmp_path))
            q = DOMQuery(document)
            return q
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        print(f"[DOM] Failed to build DOM from markdown: {e}")
        return None


def _looks_like_number(val: str) -> bool:
    """Checks if extracted text looks like a financial number."""
    cleaned = val.replace(",", "").replace(".", "").replace("-", "").strip()
    return bool(cleaned and cleaned.isdigit())


def _find_best_row_for_variable(q, label: str, target_y: float = None):
    """
    Finds the most reliable RowNode in the DOM for a given financial line item label.
    Uses token overlap scoring and vertical position ratio target_y to intersect pre-built DOM nodes.
    Returns the best RowNode or None.
    """
    try:
        from dom_learner.models import NodeType
        label_clean = label.strip().lower()
        # Extract meaningful word tokens (ignoring numbers and 1-2 letter noise)
        tokens = [w for w in label_clean.split() if len(w) >= 3 and not w.isdigit()]

        all_rows = q.find_all(NodeType.ROW)
        if not all_rows:
            return None

        best_row = None
        best_score = -999.0

        for idx, row in enumerate(all_rows):
            row_text_lower = row.text.lower()
            cells = [c for c in row.children if c.node_type == NodeType.CELL]
            numeric_cells = [c for c in cells if _looks_like_number(c.text.strip())]

            score = 0.0

            # Token overlap scoring
            if tokens:
                matched_count = sum(1 for t in tokens if t in row_text_lower)
                overlap_ratio = matched_count / len(tokens)
                score += overlap_ratio * 60.0

            # Vertical position proximity scoring
            if target_y is not None and len(all_rows) > 0:
                row_rel_y = idx / float(len(all_rows))
                y_dist = abs(row_rel_y - target_y)
                # Give high bonus to rows within 10% vertical distance
                score += max(0.0, (1.0 - y_dist * 4.0)) * 30.0

            # Table row with numbers bonus
            if len(numeric_cells) >= 1:
                score += 10.0

            # Exact match bonus
            if label_clean == row_text_lower:
                score += 40.0

            if score > best_score:
                best_score = score
                best_row = row

        # Only return row if it achieved a solid confidence threshold
        if best_score >= 15.0:
            return best_row
        return None
    except Exception as e:
        print(f"[DOM] Scoring error: {e}")
        return None



def _extract_value_from_dom_row(row) -> str:
    """
    Given a matched RowNode, extract the most recent year's numeric value (last 2nd numeric cell).
    Returns the value string or empty string.
    """
    try:
        from dom_learner.models import NodeType
        cells = [c for c in row.children if c.node_type == NodeType.CELL]
        numeric_cells = [c for c in cells if _looks_like_number(c.text.strip())]
        if len(numeric_cells) >= 2:
            return numeric_cells[-2].text.strip()
        elif len(numeric_cells) == 1:
            return numeric_cells[0].text.strip()
    except Exception as e:
        print(f"[DOM] Value extraction error: {e}")
    return ""


def _try_dom_extraction(markdown_text: str, variable_name: str, db, template_name: str):
    """
    Tier 1 extraction: Attempts to extract a value for a variable_name using saved DOM rules.
    Steps:
      1. Check DB for a saved DomExtractionRule for this template + variable.
      2. Build DOM from OCR markdown.
      3. Use find_best_row_for_variable() to find the row.
      4. Extract the numeric value from the row.
      5. Increment success_count on the rule.
    Returns (value_str, dom_path_json) or (None, None).
    """
    try:
        # Check if we have a DOM rule for this variable
        dom_rule = db.query(models.DomExtractionRule).filter(
            models.DomExtractionRule.template_name == template_name,
            models.DomExtractionRule.variable_name.ilike(f"%{variable_name.strip()}%")
        ).order_by(models.DomExtractionRule.success_count.desc()).first()

        if not dom_rule:
            return None, None

        q = _get_dom_query_from_markdown(markdown_text)
        if q is None:
            return None, None

        best_row = _find_best_row_for_variable(q, variable_name)
        if best_row is None:
            return None, None

        value = _extract_value_from_dom_row(best_row)
        if not value:
            return None, None

        # Increment success_count on the rule
        dom_rule.success_count = (dom_rule.success_count or 0) + 1
        db.commit()

        print(f"[DOM] ✓ Extracted '{variable_name}' = '{value}' via DOM rule (success #{dom_rule.success_count})")
        return value, dom_rule.dom_path

    except Exception as e:
        print(f"[DOM] _try_dom_extraction failed for '{variable_name}': {e}")
        return None, None


def _run_triton_ocr_on_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Runs the entire PDF at once through Triton marker_model OCR and returns markdown text.
    Uses 600s network_timeout for large multi-page documents.
    """
    try:
        import tritonclient.http as httpclient
        import numpy as np

        print(f"[Triton] Sending entire PDF ({len(pdf_bytes)} bytes) to marker_model...")
        client = httpclient.InferenceServerClient(
            url="192.168.112.2:8000", network_timeout=600.0, connection_timeout=60.0
        )
        input_tensor = httpclient.InferInput("PDF_BYTES", [1], "BYTES")
        input_tensor.set_data_from_numpy(np.array([pdf_bytes], dtype=np.object_))
        output_tensor = httpclient.InferRequestedOutput("MARKDOWN")
        
        response = client.infer(model_name="marker_model", inputs=[input_tensor], outputs=[output_tensor])
        markdown = response.as_numpy("MARKDOWN")[0].decode("utf-8").strip()
        
        # Catch errors returned as plain text from the remote server
        if "CUDA out of memory" in markdown or "Traceback (most recent call last)" in markdown:
            print(f"[!] Triton OCR Remote Server Error: {markdown[:200]}...")
            raise Exception(f"Remote GPU Out of Memory or Error: {markdown[:100]}")
            
        print(f"[Triton] Entire PDF processed successfully ✓ ({len(markdown)} chars)")
        return markdown
    except Exception as e:
        print(f"[!] Triton OCR failed for full PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ==============================================================================
# NEW: POST /rules_with_dom — Smart Rule Save (Option A: replaces saveRule for Magic Pen)
# ==============================================================================

class RulesWithDomResponse(BaseModel):
    rule_id: str
    template_name: str
    form_field: str
    extracted_key: str
    dom_rule_saved: bool
    dom_path: Optional[str] = None

    class Config:
        orm_mode = True


# Global in-memory cache for pre-built DOM Query trees per uploaded document
DOCUMENT_DOM_CACHE = {}

@router.post("/process_document")
async def process_document_ocr(file: UploadFile = File(...)):
    """
    Called when a document is uploaded in IDP Studio.
    Runs Triton OCR on the entire PDF and pre-builds the DOM Tree in memory.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    pdf_bytes = await file.read()
    print(f"[IDP Studio] Processing document '{file.filename}' through Triton OCR...")

    # Run Triton OCR directly on full PDF bytes
    markdown = _run_triton_ocr_on_pdf_bytes(pdf_bytes)

    if markdown.strip():
        q = _get_dom_query_from_markdown(markdown)
        if q:
            # Memory leak fix (LRU Cap): Max 10 items in cache
            if len(DOCUMENT_DOM_CACHE) >= 10:
                oldest_key = next(iter(DOCUMENT_DOM_CACHE))
                DOCUMENT_DOM_CACHE.pop(oldest_key, None)

            DOCUMENT_DOM_CACHE[file.filename] = {
                "markdown": markdown,
                "query": q,
                "structured_document": q._root.to_dict() if hasattr(q, '_root') and q._root else None
            }
            print(f"[IDP Studio] Pre-built DOM Tree successfully for '{file.filename}'")

    return {
        "status": "success",
        "filename": file.filename,
        "chars_extracted": len(markdown),
        "dom_built": file.filename in DOCUMENT_DOM_CACHE
    }

@router.get("/structured_document/{filename}")
async def get_structured_document(filename: str):
    """
    Returns the parsed, structured JSON representation of the document for the frontend viewer.
    """
    if filename not in DOCUMENT_DOM_CACHE:
        raise HTTPException(status_code=404, detail="Document not found or not processed yet.")
    
    doc = DOCUMENT_DOM_CACHE[filename].get("structured_document")
    if not doc:
        raise HTTPException(status_code=404, detail="Structured document not available.")
    return {"structured_document": doc}
@router.post("/rules_batch_save")
async def save_rules_batch(
    template_name: str = Form(...),
    rules_json: str = Form(...),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Batch Save Endpoint: Saves all mapped form rules to DB at once when the user clicks 'Save Form Mappings'.
    Learns DOM structural paths for all mapped fields in a single transaction.
    """
    import json as python_json
    try:
        mapped_rules = python_json.loads(rules_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid rules_json: {e}")

    saved_count = 0
    dom_saved_count = 0

    # 1. Fetch pre-built DOM Query from DOCUMENT_DOM_CACHE if available
    q = None
    if file and file.filename:
        if file.filename in DOCUMENT_DOM_CACHE:
            q = DOCUMENT_DOM_CACHE[file.filename].get("query")
            print(f"[Batch Save] Using cached pre-built DOM tree for '{file.filename}'")
        else:
            for fn, cache_entry in DOCUMENT_DOM_CACHE.items():
                if file.filename in fn or fn in file.filename:
                    q = cache_entry.get("query")
                    print(f"[Batch Save] Using cached pre-built DOM tree (fuzzy match) for '{file.filename}'")
                    break

    for item in mapped_rules:
        form_field = item.get("form_field")
        extracted_key = item.get("extracted_key")
        spatial_meta = item.get("spatial_meta")

        if not form_field or not extracted_key:
            continue

        spatial_json_str = None
        if spatial_meta:
            spatial_json_str = python_json.dumps(spatial_meta) if isinstance(spatial_meta, dict) else str(spatial_meta)

        # Upsert SchemaAliasRule (spatial rule)
        existing_spatial = db.query(models.SchemaAliasRule).filter(
            models.SchemaAliasRule.template_name == template_name,
            models.SchemaAliasRule.form_field == form_field
        ).first()
        if existing_spatial:
            existing_spatial.extracted_key = extracted_key
            existing_spatial.spatial_meta_json = spatial_json_str
        else:
            db.add(models.SchemaAliasRule(
                rule_id=str(uuid.uuid4()),
                template_name=template_name,
                form_field=form_field,
                extracted_key=extracted_key,
                spatial_meta_json=spatial_json_str
            ))
        saved_count += 1

        # Learn DOM structural path
        if q and extracted_key:
            try:
                best_row = _find_best_row_for_variable(q, extracted_key)
                if best_row:
                    path = q.get_structural_path(best_row)
                    dom_path_str = python_json.dumps(path)

                    existing_dom = db.query(models.DomExtractionRule).filter(
                        models.DomExtractionRule.template_name == template_name,
                        models.DomExtractionRule.variable_name == extracted_key
                    ).first()
                    if existing_dom:
                        existing_dom.dom_path = dom_path_str
                        existing_dom.created_at = datetime.datetime.utcnow()
                    else:
                        db.add(models.DomExtractionRule(
                            rule_id=str(uuid.uuid4()),
                            template_name=template_name,
                            variable_name=extracted_key,
                            dom_path=dom_path_str,
                            success_count=0
                        ))
                    dom_saved_count += 1
            except Exception as dom_err:
                print(f"[Batch Save] Failed DOM learning for '{extracted_key}': {dom_err}")

    db.commit()
    print(f"[Batch Save] ✓ Successfully saved {saved_count} spatial rules and {dom_saved_count} DOM rules to DB for template '{template_name}'")
    return {
        "status": "success",
        "template_name": template_name,
        "saved_count": saved_count,
        "dom_saved_count": dom_saved_count
    }


@router.post("/rules_with_dom", response_model=RulesWithDomResponse)
async def save_rule_with_dom(

    template_name: str = Form(...),
    form_field: str = Form(...),
    extracted_key: str = Form(...),
    spatial_meta: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Smart rule save endpoint (replaces POST /rules for Magic Pen).
    1. Saves the legacy SchemaAliasRule (spatial rule, for backward compatibility).
    2. If a PDF file is attached, runs OCR → builds DOM → finds the structural path
       for `extracted_key` and saves a DomExtractionRule to DB.
    """
    import json as python_json

    # --- Step 1: Save legacy spatial rule (same as old /rules endpoint) ---
    existing_spatial = db.query(models.SchemaAliasRule).filter(
        models.SchemaAliasRule.template_name == template_name,
        models.SchemaAliasRule.form_field == form_field
    ).first()
    if existing_spatial:
        db.delete(existing_spatial)
        db.commit()

    spatial_json_str = None
    if spatial_meta:
        try:
            spatial_dict = python_json.loads(spatial_meta)
            spatial_json_str = python_json.dumps(spatial_dict)
        except Exception:
            spatial_json_str = spatial_meta

    db_rule = models.SchemaAliasRule(
        rule_id=str(uuid.uuid4()),
        template_name=template_name,
        form_field=form_field,
        extracted_key=extracted_key,
        spatial_meta_json=spatial_json_str
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    print(f"[IDP] Spatial rule saved: '{form_field}' → '{extracted_key}' for template '{template_name}'")

    # --- Step 2: DOM Learning (only if PDF is provided) ---
    dom_rule_saved = False
    dom_path_str = None

    if file and file.filename.endswith('.pdf'):
        try:
            q = None
            full_markdown = ""

            # Check DOCUMENT_DOM_CACHE first (instant <1ms lookup)
            if file.filename in DOCUMENT_DOM_CACHE:
                cache_entry = DOCUMENT_DOM_CACHE[file.filename]
                q = cache_entry.get("query")
                full_markdown = cache_entry.get("markdown", "")
                print(f"[DOM] Using cached pre-built DOM tree for '{file.filename}' (<1ms save)")
            else:
                for fn, cache_entry in DOCUMENT_DOM_CACHE.items():
                    if file.filename in fn or fn in file.filename:
                        q = cache_entry.get("query")
                        full_markdown = cache_entry.get("markdown", "")
                        print(f"[DOM] Using cached pre-built DOM tree (fuzzy match) for '{file.filename}'")
                        break

            if not q:
                pdf_bytes = await file.read()
                try:
                    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                        pages_text = [p.extract_text() or "" for p in pdf.pages if p.extract_text()]
                        full_markdown = "\n".join(pages_text)
                except Exception:
                    pass

                if not full_markdown.strip():
                    print(f"[DOM] No digital text found, running Triton OCR for DOM learning...")
                    full_markdown = _run_triton_ocr_on_pdf_bytes(pdf_bytes)

                if full_markdown.strip():
                    q = _get_dom_query_from_markdown(full_markdown)

            if q:
                best_row = _find_best_row_for_variable(q, extracted_key)
                if best_row:
                    path = q.get_structural_path(best_row)
                    dom_path_str = python_json.dumps(path)

                    # Upsert DomExtractionRule
                    existing_dom = db.query(models.DomExtractionRule).filter(
                        models.DomExtractionRule.template_name == template_name,
                        models.DomExtractionRule.variable_name == extracted_key
                    ).first()

                    if existing_dom:
                        existing_dom.dom_path = dom_path_str
                        existing_dom.created_at = datetime.datetime.utcnow()
                    else:
                        db.add(models.DomExtractionRule(
                            rule_id=str(uuid.uuid4()),
                            template_name=template_name,
                            variable_name=extracted_key,
                            dom_path=dom_path_str,
                            success_count=0
                        ))

                    db.commit()
                    dom_rule_saved = True
                    print(f"[DOM] ✓ Structural path learned for '{extracted_key}': {path[:2]}...")
                else:
                    print(f"[DOM] Could not find row for '{extracted_key}' in DOM tree")
            else:
                print(f"[DOM] No text content available for DOM learning")

        except Exception as e:
            print(f"[DOM] DOM learning step failed: {e}")


    return RulesWithDomResponse(
        rule_id=db_rule.rule_id,
        template_name=db_rule.template_name,
        form_field=db_rule.form_field,
        extracted_key=db_rule.extracted_key,
        dom_rule_saved=dom_rule_saved,
        dom_path=dom_path_str
    )


@router.post("/extract")
async def extract_document_llm(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for extraction")
        
    contents = await file.read()
    
    # Extract text using pdfplumber
    text_content = ""
    try:
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"
    except Exception as e:
        print(f"[!] pdfplumber text extraction error: {e}")

    # Fallback to Triton OCR if no digital text layer exists (scanned PDF)
    if not text_content.strip():
        print(f"[Batch][LLM] No digital text layer, running Triton OCR for Ollama LLM extraction...")
        text_content = _run_triton_ocr_on_pdf_bytes(contents)

    if not text_content.strip():
        raise HTTPException(status_code=400, detail="Could not extract any text from the provided PDF")


    # Call local Ollama model qwen:coder:7b
    prompt = f"""
You are an advanced Intelligent Document Processing (IDP) extractor.
Extract all relevant financial and tabular key-value pairs from the following document text.
Return ONLY a valid JSON array of objects, with each object having exactly two keys: "key" and "value".
Example: [{{"key": "Total Assets", "value": "150000"}}, {{"key": "Net Profit", "value": "2000"}}]

Document Text:
{text_content[:8000]} # Limit to avoid context window explosion
    """
    
    try:
        response = requests.post(
            "http://192.168.112.2:11434/api/generate",
            json={
                "model": "qwen2.5-coder:7b",
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        extracted_text = result.get("response", "[]")
        
        # Parse the JSON response
        import json as python_json
        extracted_data = python_json.loads(extracted_text)
        
        # Ensure it's a list
        if not isinstance(extracted_data, list):
            extracted_data = [{"key": k, "value": v} for k, v in extracted_data.items()] if isinstance(extracted_data, dict) else []
            
        return {"extracted_data": extracted_data}
        
    except requests.exceptions.RequestException as e:
        print(f"[!] Ollama Connection Error: {e}")
        # Fallback to mock data if Ollama isn't running or fails
        return {
            "error": "Failed to connect to local Ollama (qwen:coder). Showing mock data instead.",
            "extracted_data": [
                {"key": "Total Reserves & Surplus (MOCK)", "value": "3,193.00"},
                {"key": "Total Long-term borrowings (MOCK)", "value": "1,894.84"}
            ]
        }
    except Exception as e:
        print(f"[!] Parsing Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {str(e)}")

@router.post("/extract/batch")
async def extract_batch_documents(
    files: List[UploadFile] = File(...),
    template_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    DOM-First Batch Extraction Pipeline:
    Tier 1 — DOM structural navigation (saved rules, 100% deterministic).
    Tier 2 — pdfplumber digital text layer + Qwen LLM fallback.
    Tier 3 — Triton OCR + Qwen LLM fallback (scanned PDFs).
    """
    import json as python_json
    results = []

    # Load saved SchemaAliasRules for this template (maps form_field → extracted_key)
    schema_rules = []
    if template_name:
        schema_rules = db.query(models.SchemaAliasRule).filter(
            models.SchemaAliasRule.template_name == template_name
        ).all()

    for file in files:
        filename = file.filename
        try:
            pdf_bytes = await file.read()
            extracted_fields = []
            any_dom_miss = False

            # --- TIER 1: DOM-based extraction for each mapped form field ---
            if schema_rules:
                # Get full text for DOM (pdfplumber first, then OCR)
                full_text = ""
                try:
                    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                        full_text = "\n".join(
                            p.extract_text() or "" for p in pdf.pages
                        ).strip()
                except Exception:
                    pass

                # If no digital text, run Triton OCR for DOM
                if not full_text:
                    print(f"[Batch][DOM] No digital text in {filename}, running Triton OCR...")
                    full_text = _run_triton_ocr_on_pdf_bytes(pdf_bytes)

                if full_text:
                    q = _get_dom_query_from_markdown(full_text)
                else:
                    q = None

                for rule in schema_rules:
                    variable_name = rule.extracted_key
                    dom_value = None

                    # Try DOM navigation first
                    if q:
                        dom_value, _ = _try_dom_extraction(full_text, variable_name, db, template_name)

                    if dom_value:
                        extracted_fields.append({
                            "key": rule.form_field,
                            "value": dom_value,
                            "_source": "dom"
                        })
                    else:
                        # Mark as needing LLM fallback
                        any_dom_miss = True
                        extracted_fields.append({
                            "key": rule.form_field,
                            "value": None,
                            "_source": "pending_llm"
                        })

            # --- TIER 2 / 3: LLM fallback for any fields that DOM missed ---
            pending_fields = [f for f in extracted_fields if f.get("_source") == "pending_llm"]
            if pending_fields or not schema_rules:
                try:
                    # Reuse full_text already extracted from digital layer or Triton OCR (never repeat OCR!)
                    if not full_text:
                        full_text = _run_triton_ocr_on_pdf_bytes(pdf_bytes)

                    if full_text.strip():
                        # Call local Ollama model directly with cached full_text
                        prompt = f"""
You are an advanced Intelligent Document Processing (IDP) extractor.
Extract all relevant financial and tabular key-value pairs from the following document text.
Return ONLY a valid JSON array of objects, with each object having exactly two keys: "key" and "value".
Example: [{{"key": "Total Assets", "value": "150000"}}, {{"key": "Net Profit", "value": "2000"}}]

Document Text:
{full_text[:8000]}
                        """
                        try:
                            response = requests.post(
                                "http://192.168.112.2:11434/api/generate",
                                json={
                                    "model": "qwen2.5-coder:7b",
                                    "prompt": prompt,
                                    "stream": False,
                                    "format": "json"
                                },
                                timeout=60
                            )
                            response.raise_for_status()
                            result = response.json()
                            extracted_text = result.get("response", "[]")
                            
                            import json as python_json
                            llm_fields = python_json.loads(extracted_text)
                            if not isinstance(llm_fields, list):
                                llm_fields = [{"key": k, "value": v} for k, v in llm_fields.items()] if isinstance(llm_fields, dict) else []
                        except Exception as ollama_err:
                            print(f"[!] Ollama LLM call error: {ollama_err}")
                            llm_fields = []

                        if not schema_rules:
                            extracted_fields = llm_fields
                            any_dom_miss = bool(llm_fields)
                        else:
                            llm_map = {f["key"].lower(): f["value"] for f in llm_fields}
                            for field in extracted_fields:
                                if field.get("_source") == "pending_llm":
                                    key_lower = field["key"].lower()
                                    matched_val = None
                                    for llm_key, llm_val in llm_map.items():
                                        if key_lower in llm_key or llm_key in key_lower:
                                            matched_val = llm_val
                                            break
                                    field["value"] = matched_val or "Unknown"
                                    field["_source"] = "llm"
                    else:
                        print(f"[!] No text content available for LLM fallback on {filename}")
                        for field in extracted_fields:
                            if field.get("_source") == "pending_llm":
                                field["value"] = "Unknown"
                                field["_source"] = "llm"

                except Exception as llm_err:
                    print(f"[!] LLM fallback failed for {filename}: {llm_err}")
                    for field in extracted_fields:
                        if field.get("_source") == "pending_llm":
                            field["value"] = "Unknown"
                            field["_source"] = "llm"


            # Clean up internal _source metadata
            for field in extracted_fields:
                field.pop("_source", None)

            # Determine status badge
            # Green if ALL fields came from DOM, Yellow if any needed LLM
            llm_used = any_dom_miss
            status_badge = "review" if llm_used else "success"

            results.append({
                "filename": filename,
                "status": status_badge,
                "extracted_fields": extracted_fields
            })

        except Exception as e:
            print(f"[!] Batch extraction error on {filename}: {e}")
            results.append({
                "filename": filename,
                "status": "review",
                "extracted_fields": []
            })

    return {"total_files": len(files), "results": results}



@router.post("/extract_region")
async def extract_region_llm(
    file: UploadFile = File(...),
    x: float = Form(...),
    y: float = Form(...),
    width: float = Form(...),
    height: float = Form(...),
    page: int = Form(...)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for extraction")
        
    contents = await file.read()
    
    # Extract text from specific region using pdfplumber
    text_content = ""
    try:
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            if page < 1 or page > len(pdf.pages):
                raise ValueError(f"Invalid page number {page}")
                
            pdf_page = pdf.pages[page - 1]
            page_width = pdf_page.width
            page_height = pdf_page.height
            
            # Convert normalized coordinates [0, 1] to absolute PDF points and clamp them
            x0 = max(0, float(x * page_width))
            top = max(0, float(y * page_height))
            x1 = min(float(page_width), x0 + float(width * page_width))
            bottom = min(float(page_height), top + float(height * page_height))
            
            # Ensure strict inequality for bbox
            if x0 >= x1:
                x1 = x0 + 1.0
            if top >= bottom:
                bottom = top + 1.0
                
            bbox = (x0, top, x1, bottom)
            
            cropped_page = pdf_page.within_bbox(bbox)
            extracted = cropped_page.extract_text()
            
            if extracted and extracted.strip():
                text_content = extracted.strip()
            else:
                # FALLBACK: If PDF has no text layer (Scanned Document), run OCR on the cropped region via Triton
                try:
                    import tritonclient.http as httpclient
                    import numpy as np
                    
                    # Convert crop to PNG image bytes in memory
                    img = cropped_page.to_image(resolution=300).original
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    raw_bytes = img_byte_arr.getvalue()
                    
                    # Call Triton Server for marker-pdf
                    print(f"[DEBUG] Calling Triton Server OCR for cropped region...")
                    client = httpclient.InferenceServerClient(url="192.168.112.2:8000", network_timeout=600.0, connection_timeout=600.0)
                    input_tensor = httpclient.InferInput("PDF_BYTES", [1], "BYTES")
                    input_tensor.set_data_from_numpy(np.array([raw_bytes], dtype=np.object_))
                    output_tensor = httpclient.InferRequestedOutput("MARKDOWN")
                    
                    response = client.infer(model_name="marker_model", inputs=[input_tensor], outputs=[output_tensor])
                    ocr_text = response.as_numpy("MARKDOWN")[0].decode("utf-8")
                    
                    if ocr_text and ocr_text.strip():
                        print(f"[DEBUG] Extracted via Triton OCR: {len(ocr_text)} characters")
                        text_content = ocr_text.strip()
                except Exception as ocr_err:
                    print(f"[!] Triton OCR Fallback failed: {ocr_err}")
                    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to read PDF region: {str(e)}")
        
    if not text_content:
        return {
            "error": "No text found in selected region",
            "extracted_data": [
                {"key": "Status", "value": "No text detected in bounding box (even with OCR)."}
            ]
        }

    # Call local Ollama model qwen:coder:7b
    prompt = f"""
You are an advanced Intelligent Document Processing (IDP) extractor.
Extract all relevant financial and tabular key-value pairs from the following text (which was selected from a specific region of a document).
Return ONLY a valid JSON array of objects, with each object having exactly two keys: "key" and "value".
Example: [{{"key": "Total Assets", "value": "150000"}}, {{"key": "Net Profit", "value": "2000"}}]

Region Text:
{text_content[:4000]}
    """
    
    try:
        response = requests.post(
            "http://192.168.112.2:11434/api/generate",
            json={
                "model": "qwen2.5-coder:7b",
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        extracted_text = result.get("response", "[]")
        
        # Parse the JSON response
        import json as python_json
        extracted_data = python_json.loads(extracted_text)
        
        # Ensure it's a list
        if not isinstance(extracted_data, list):
            extracted_data = [{"key": k, "value": v} for k, v in extracted_data.items()] if isinstance(extracted_data, dict) else []
            
        return {"extracted_data": extracted_data}
        
    except requests.exceptions.RequestException as e:
        print(f"[!] Ollama Connection Error: {e}")
        return {
            "error": "Failed to connect to local Ollama (qwen:coder). Showing mock data instead.",
            "extracted_data": [
                {"key": "Selected Region Data (MOCK)", "value": text_content.strip()[:100]}
            ]
        }
def _extract_markdown_ast_row(cached_markdown: str, anchor_y: float, page_num: int = 1, total_pages: int = 1):
    """
    Tier 1 Extractor: Parses Triton OCR Markdown AST using page_num and relative mouse position anchor_y.
    Returns structured result dict with source="markdown_ast", confidence, page, table_id, row_index.
    """
    import re
    if not cached_markdown or not cached_markdown.strip():
        return None

    lines = [l.strip() for l in cached_markdown.split('\n') if l.strip()]
    if not lines:
        return None

    total_pages = max(1, total_pages)
    page_num = max(1, min(page_num, total_pages))

    # Calculate global document line ratio factoring in page_num and total_pages
    global_ratio = ((page_num - 1) + max(0.0, min(1.0, anchor_y))) / float(total_pages)
    line_idx = min(max(0, int(global_ratio * len(lines))), len(lines) - 1)

    
    # Search around line_idx for table rows containing '|'
    candidate_indices = []
    for offset in [0, -1, 1, -2, 2, -3, 3]:
        idx = line_idx + offset
        if 0 <= idx < len(lines):
            if '|' in lines[idx]:
                candidate_indices.append(idx)
    
    target_line_idx = candidate_indices[0] if candidate_indices else line_idx
    target_line = lines[target_line_idx]

    # Parse Markdown table row
    if '|' in target_line:
        cells = [c.strip() for c in target_line.split('|') if c.strip()]
        if len(cells) >= 1:
            key_label = cells[0]
            key_label = re.sub(r'!\[.*?\]\(.*?\)', '', key_label).strip()
            key_label = re.sub(r'[*_#`]', '', key_label).strip()

            # Find numeric currency cells (filtering out single-digit Note numbers)
            val_cells = [c for c in cells[1:] if _looks_like_number(c)]
            currency_vals = [v for v in val_cells if len(re.sub(r'[^\d]', '', v)) >= 2]
            value_text = currency_vals[0] if currency_vals else (val_cells[0] if val_cells else "")
            
            if key_label and len(key_label) >= 3:
                table_id = target_line_idx // 15
                return {
                    "key": key_label[:120],
                    "value": value_text,
                    "source": "markdown_ast",
                    "confidence": 0.98,
                    "page": page_num,
                    "table_id": table_id,
                    "row_index": target_line_idx
                }

    # Non-table line fallback
    clean_line = target_line.replace('|', ' ').strip()
    clean_line = re.sub(r'!\[.*?\]\(.*?\)', '', clean_line).strip()
    clean_line = re.sub(r'[*_#`]', '', clean_line).strip()
    if clean_line and len(clean_line) >= 3:
        return {
            "key": clean_line[:120],
            "value": "",
            "source": "markdown_ast",
            "confidence": 0.90,
            "page": page_num,
            "table_id": 0,
            "row_index": target_line_idx
        }

    return None


