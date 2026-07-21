from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import uuid
import pandas as pd
import json
import io

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

@router.get("/templates", response_model=List[IdpTemplateResponse])
def get_all_templates(db: Session = Depends(get_db)):
    return db.query(models.IdpTemplate).all()

@router.post("/templates/upload")
async def upload_excel_template(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files are supported")
        
    contents = await file.read()
    try:
        # Read the first sheet of the excel file
        # Read without headers to analyze raw grid
        df = pd.read_excel(io.BytesIO(contents), header=None)
        
        # We will extract all distinct, reasonable-length string cells from the first 50 rows 
        # as potential "fields" they might want to map to (since Excel forms can be very unstructured).
        fields = []
        seen_labels = set()
        
        for r_idx, row in df.head(100).iterrows():
            for c_idx, val in enumerate(row):
                val_str = str(val).strip()
                # If it's a valid string (not empty, not NaN, not a massive paragraph)
                if val_str and val_str.lower() != 'nan' and 3 <= len(val_str) <= 150:
                    # Clean it up to avoid exact duplicates (e.g., removing newlines)
                    clean_label = val_str.replace('\n', ' ').strip()
                    if clean_label not in seen_labels:
                        seen_labels.add(clean_label)
                        # Create a safe ID
                        field_id = ''.join(e for e in clean_label.lower() if e.isalnum())[:40]
                        fields.append({
                            "id": f"cell_{r_idx}_{c_idx}_{field_id}",
                            "label": clean_label
                        })
                    
        template_name = file.filename.replace(".xlsx", "").replace(".xls", "")
        template_id = str(uuid.uuid4())
        
        db_template = models.IdpTemplate(
            template_id=template_id,
            template_name=template_name,
            fields_json=json.dumps(fields)
        )
        db.add(db_template)
        db.commit()
        db.refresh(db_template)
        
        return {"message": "Template created", "template_id": template_id, "fields": fields}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing Excel: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Failed to read PDF: {str(e)}")
        
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

from fastapi import Form

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
    except Exception as e:
        print(f"[!] Parsing Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {str(e)}")

@router.post("/extract_spatial_rule")
async def extract_spatial_rule(
    file: UploadFile = File(...),
    anchor_x: float = Form(...),
    anchor_y: float = Form(...),
    anchor_w: float = Form(...),
    anchor_h: float = Form(...),
    value_x: float = Form(...),
    value_y: float = Form(...),
    value_w: float = Form(...),
    value_h: float = Form(...),
    page: int = Form(...)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    contents = await file.read()
    
    def _extract_rect(pdf_page, x, y, width, height):
        page_width = pdf_page.width
        page_height = pdf_page.height
        
        x0 = max(0, float(x * page_width))
        top = max(0, float(y * page_height))
        x1 = min(float(page_width), x0 + float(width * page_width))
        bottom = min(float(page_height), top + float(height * page_height))
        
        if x0 >= x1: x1 = x0 + 1.0
        if top >= bottom: bottom = top + 1.0
            
        bbox = (x0, top, x1, bottom)
        cropped_page = pdf_page.within_bbox(bbox)
        extracted = cropped_page.extract_text()
        
        if extracted and extracted.strip():
            return extracted.strip()
            
        # Triton Fallback
        try:
            import tritonclient.http as httpclient
            import numpy as np
            import io
            
            img = cropped_page.to_image(resolution=300).original
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            raw_bytes = img_byte_arr.getvalue()
            
            client = httpclient.InferenceServerClient(url="192.168.112.2:8000", network_timeout=600.0, connection_timeout=600.0)
            input_tensor = httpclient.InferInput("PDF_BYTES", [1], "BYTES")
            input_tensor.set_data_from_numpy(np.array([raw_bytes], dtype=np.object_))
            output_tensor = httpclient.InferRequestedOutput("MARKDOWN")
            
            response = client.infer(model_name="marker_model", inputs=[input_tensor], outputs=[output_tensor])
            ocr_text = response.as_numpy("MARKDOWN")[0].decode("utf-8")
            if ocr_text and ocr_text.strip():
                return ocr_text.strip()
        except Exception as e:
            print(f"[!] OCR Fallback failed in spatial rule: {e}")
            
        return "Unknown"

    try:
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            if page < 1 or page > len(pdf.pages):
                raise ValueError(f"Invalid page number {page}")
                
            pdf_page = pdf.pages[page - 1]
            
            # Extract anchor text
            anchor_text = _extract_rect(pdf_page, anchor_x, anchor_y, anchor_w, anchor_h)
            
            # Extract value text
            value_text = _extract_rect(pdf_page, value_x, value_y, value_w, value_h)
            
            # Clean up the texts (e.g. LLM might have returned markdown or newlines)
            anchor_text = anchor_text.replace('\n', ' ').strip()
            value_text = value_text.replace('\n', ' ').strip()
            
            # Calculate relative offset
            dx = value_x - anchor_x
            dy = value_y - anchor_y
            
            return {
                "extracted_data": [
                    {
                        "key": anchor_text,
                        "value": value_text,
                        "_spatial_meta": {
                            "anchor_text": anchor_text,
                            "dx": dx,
                            "dy": dy,
                            "width": value_w,
                            "height": value_h
                        }
                    }
                ]
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to extract spatial rule: {str(e)}")

