from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid
import datetime
import pandas as pd
import json
import json as python_json
import io
import os
import sys
import re

from .core.db import get_db, engine, init_db
from .core import models
from .extractors.classifier import classify_document, detect_operative_statutory_branch
from .extractors.spatial import get_effective_rules, get_scenario_lexicon
from .forms.kit_parser import InstructionKitParser
from .forms.registry import FormRegistry
from .forms.filler import DynamicFormFiller



# Ensure tables and migrations are initialized
init_db()

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
    templates = [t for t in templates if t.template_name != "FLA Return (Standard Form)"]
    existing_names = {t.template_name for t in templates}
    
    saved_rules = db.query(models.SchemaAliasRule.template_name).distinct().all()
    for (t_name,) in saved_rules:
        if t_name and t_name not in existing_names and t_name != "FLA Return (Standard Form)":
            templates.append(
                models.IdpTemplate(
                    template_id=t_name,
                    template_name=t_name,
                    fields_json="[]"
                )
            )
            existing_names.add(t_name)
            
    return templates


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    """Deletes a template from the database by template_id or template_name."""
    tmpl = db.query(models.IdpTemplate).filter(
        (models.IdpTemplate.template_id == template_id) | (models.IdpTemplate.template_name == template_id)
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(tmpl)
    db.commit()
    return {"message": f"Template '{tmpl.template_name}' successfully deleted"}


@router.post("/templates/upload")
async def upload_pdf_template(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Template Ingestion Endpoint.
    Parses the uploaded Instruction Kit PDF using InstructionKitParser, generating a clean,
    type-safe, conditional form schema (with radio/select options, validations, depends_on).
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for template upload")
        
    contents = await file.read()
    try:
        # Parse Instruction Kit into structured schema
        parser = InstructionKitParser()
        schema = parser.parse(contents)
        fields = schema.get("fields", [])
        
        template_name = schema.get("template_name") or schema.get("form_name") or file.filename.replace(".pdf", "").replace(".PDF", "")
        # Clean up form name
        if not template_name or template_name == "Form Template":
            template_name = file.filename.replace(".pdf", "").replace(".PDF", "").replace("_", " ")

        template_id = str(uuid.uuid4())
        schema["template_name"] = template_name
        schema["form_name"] = template_name
        schema["form_id"] = template_id
        
        # Save the template PDF to the data/templates folder for reference and PDF previews
        template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "templates"))
        os.makedirs(template_dir, exist_ok=True)
        template_path = os.path.join(template_dir, f"{template_name}.pdf")
        with open(template_path, "wb") as out_f:
            out_f.write(contents)
        
        # Persist to FormRegistry (which synchronizes DB IdpTemplate and filesystem cache)
        try:
            template_id = FormRegistry.save_form_schema(schema, db)
        except Exception as reg_err:
            print(f"[!] FormRegistry sync notice: {reg_err}")
            # Fallback direct DB save
            existing_tmpl = db.query(models.IdpTemplate).filter(models.IdpTemplate.template_name == template_name).first()
            if existing_tmpl:
                existing_tmpl.fields_json = json.dumps(schema)
                db.commit()
                db.refresh(existing_tmpl)
                template_id = existing_tmpl.template_id
            else:
                db_template = models.IdpTemplate(
                    template_id=template_id,
                    template_name=template_name,
                    fields_json=json.dumps(schema)
                )
                db.add(db_template)
                db.commit()
                db.refresh(db_template)

        print(f"[IDP Studio] Successfully parsed and saved template '{template_name}' with {len(fields)} fields from Instruction Kit.")
        return {
            "message": f"Template created from Instruction Kit ({len(fields)} fields)",
            "template_id": template_id,
            "template_name": template_name,
            "fields": fields,
            "schema": schema
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error parsing Instruction Kit template: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# Generic Schema-Driven MCA Dynamic Form Endpoints (Supporting 54+ Forms)
# ─────────────────────────────────────────────────────────────────────────────

class FormAutofillRequest(BaseModel):
    evidence: Optional[List[Dict[str, Any]]] = None

class FormValidateRequest(BaseModel):
    values: Dict[str, Any]


@router.get("/forms")
def list_available_forms(db: Session = Depends(get_db)):
    """
    Lists all available MCA forms (out of 54) dynamically from DB and schema registry.
    Returns lightweight summaries with field counts and conditional indicators.
    """
    forms = FormRegistry.list_forms(db)
    return {"total_forms": len(forms), "forms": forms}


@router.get("/forms/{form_id}")
def get_form_definition(form_id: str, db: Session = Depends(get_db)):
    """
    Retrieves the complete standardized schema for a specific MCA form.
    Decoupled: includes canonical numbers, labels, types, options, validations, depends_on.
    """
    schema = FormRegistry.get_form_schema(form_id, db)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Form schema for '{form_id}' not found")
    return schema


@router.post("/forms/{form_id}/detect_branch")
async def detect_form_branch(
    form_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Scans uploaded documents (or document text) and runs the Operative Clause Detector
    to recommend the statutory branch for the Upfront HITL Decision Gate.
    """
    schema = FormRegistry.get_form_schema(form_id, db)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Form schema for '{form_id}' not found")

    content_type = request.headers.get("content-type", "")
    full_text = ""
    filename = ""

    import pdfplumber
    if "application/json" in content_type:
        try:
            body = await request.json()
            full_text = body.get("text", "")
            filename = body.get("filename", "")
        except Exception:
            pass
    elif "multipart/form-data" in content_type:
        try:
            form = await request.form()
            uploaded_files = form.getlist("files")
            single_file = form.get("file")
            if single_file and single_file not in uploaded_files:
                uploaded_files.append(single_file)
            for uf in uploaded_files:
                if hasattr(uf, "read") and hasattr(uf, "filename") and uf.filename.lower().endswith(".pdf"):
                    contents = await uf.read()
                    filename = uf.filename
                    with pdfplumber.open(io.BytesIO(contents)) as pdf:
                        for page in pdf.pages:
                            t = page.extract_text()
                            if t:
                                full_text += t + "\n"
        except Exception as e:
            print(f"[!] Error in detect_form_branch: {e}")

    # Dynamically locate the branching field from the schema (the field that drives DAG pruning)
    parent_counts = {}
    for f in schema.get("fields", []):
        dep = f.get("depends_on")
        if dep and isinstance(dep, dict) and dep.get("field"):
            pf = dep["field"]
            parent_counts[pf] = parent_counts.get(pf, 0) + 1

    BRANCH_FIELD_SIGNALS = [
        "nature of appointment",
        "type of appointment",
        "basis of appointment",
        "purpose of filing",
        "nature of filing",
        "category of applicant",
        "type of company",
        "statement of account",
    ]

    branch_field = None

    # Priority 1: Field with the most DAG dependents that has >= 2 options
    if parent_counts:
        sorted_parents = sorted(parent_counts.items(), key=lambda x: x[1], reverse=True)
        for parent_id, _ in sorted_parents:
            matched_f = next((f for f in schema.get("fields", []) if f.get("id") == parent_id and f.get("options") and len(f.get("options")) >= 2), None)
            if matched_f:
                branch_field = matched_f
                break

    # Priority 2: Match by branch keyword signals
    if not branch_field:
        for fld in schema.get("fields", []):
            field_label_lower = fld.get("label", "").lower()
            field_options = fld.get("options") or []
            if len(field_options) >= 2 and any(sig in field_label_lower for sig in BRANCH_FIELD_SIGNALS):
                branch_field = fld
                break

    # Priority 3: Multi-option select/radio field (with at least 3 options)
    if not branch_field:
        for fld in schema.get("fields", []):
            field_type = fld.get("type", "")
            field_options = fld.get("options") or []
            if field_type in ["radio", "select"] and len(field_options) >= 3:
                branch_field = fld
                break

    if branch_field:
        candidate_options = branch_field.get("options", [])
        branch_field_id = branch_field.get("id")
        branch_field_label = branch_field.get("label")
        branch_field_canonical = branch_field.get("canonical_no")
    else:
        candidate_options = []
        branch_field_id = None
        branch_field_label = None
        branch_field_canonical = None

    # Build structured option objects for the frontend UI
    available_options = []
    for opt in candidate_options:
        if isinstance(opt, dict):
            available_options.append(opt)
        elif isinstance(opt, str):
            available_options.append({
                "id": opt,
                "title": opt,
                "description": "",
                "section": ""
            })

    has_branches = len(available_options) >= 2
    result = detect_operative_statutory_branch(full_text, filename=filename, candidate_options=candidate_options) if has_branches else None

    return {
        "status": "success",
        "form_id": form_id,
        "form_name": schema.get("form_name"),
        "has_branches": has_branches,
        "branch_field_id": branch_field_id,
        "branch_field_label": branch_field_label,
        "branch_field_canonical": branch_field_canonical,
        "available_options": available_options,
        "detected": result
    }


@router.post("/forms/{form_id}/autofill")
async def autofill_mca_form(
    form_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Autonomous Dynamic Form-Filling Endpoint:
    1. Loads target Form Schema from FormRegistry (no hardcoding).
    2. Gathers evidence from either JSON body or multipart uploaded documents.
    3. Injects confirmed branch and harvested scenario lexicon from database.
    4. Runs qwen2.5:14b semantic mapper to match document evidence to target schema fields.
    5. Enforces deterministic guardrails: Type checks, Regex, Canonical Options, and DAG pruning.
    6. Returns audited FormFillExecutionPayload with populated values and missing field flags.
    """
    schema = FormRegistry.get_form_schema(form_id, db)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Form schema for '{form_id}' not found")

    context = {}
    evidence_items = []
    content_type = request.headers.get("content-type", "")

    # 1. Parse JSON body
    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                if body.get("evidence"):
                    evidence_items.extend(body["evidence"])
                if body.get("company_id") or body.get("scenario") or body.get("confirmed_branch"):
                    context = {
                        "company_id": body.get("company_id"),
                        "scenario": body.get("scenario"),
                        "confirmed_branch": body.get("confirmed_branch"),
                        "casual_vacancy_reason": body.get("casual_vacancy_reason"),
                    }
        except Exception as je:
            print(f"[!] Error parsing JSON body in autofill: {je}")

    # 2. Parse multipart form data (files and/or evidence JSON string)
    elif "multipart/form-data" in content_type:
        try:
            form = await request.form()
            ev_str = form.get("evidence")
            if ev_str:
                try:
                    parsed_ev = json.loads(ev_str)
                    if isinstance(parsed_ev, list):
                        evidence_items.extend(parsed_ev)
                except Exception:
                    pass

            if form.get("company_id") or form.get("scenario") or form.get("confirmed_branch"):
                context = {
                    "company_id": form.get("company_id"),
                    "scenario": form.get("scenario"),
                    "confirmed_branch": form.get("confirmed_branch"),
                    "casual_vacancy_reason": form.get("casual_vacancy_reason"),
                }

            import pdfplumber
            uploaded_files = form.getlist("files")
            single_file = form.get("file")
            if single_file and single_file not in uploaded_files:
                uploaded_files.append(single_file)

            for uf in uploaded_files:
                if hasattr(uf, "read") and hasattr(uf, "filename") and uf.filename.lower().endswith(".pdf"):
                    contents = await uf.read()
                    file_text = ""
                    with pdfplumber.open(io.BytesIO(contents)) as pdf:
                        for page in pdf.pages:
                            t = page.extract_text()
                            if t:
                                file_text += t + "\n"
                    lines = [l.strip() for l in file_text.splitlines() if l.strip()]
                    for l in lines[:80]:
                        if ":" in l:
                            parts = l.split(":", 1)
                            evidence_items.append({
                                "key": parts[0].strip(),
                                "value": parts[1].strip(),
                                "source_doc": uf.filename
                            })
                        else:
                            evidence_items.append({
                                "key": l[:40],
                                "value": l,
                                "source_doc": uf.filename
                            })
        except Exception as fe:
            print(f"[!] Error parsing multipart form in autofill: {fe}")

    # Harvest dynamic scenario lexicon from database if scenario provided
    scenario_key = context.get("scenario")
    if not scenario_key and context.get("confirmed_branch"):
        cb = str(context["confirmed_branch"]).lower()
        if "first auditor" in cb:
            if "member" in cb or "egm" in cb:
                scenario_key = "first_auditor_members"
            else:
                scenario_key = "first_auditor_board"
        elif "c&ag" in cb or "cag" in cb:
            scenario_key = "cag_appointment"
        elif "casual" in cb:
            scenario_key = "casual_vacancy"
        elif "re-appointment" in cb and "agm" in cb:
            scenario_key = "agm_reappointment"
        elif "agm" in cb:
            scenario_key = "agm_appointment"
        elif "tribunal" in cb:
            scenario_key = "tribunal_order"
        elif "central" in cb:
            scenario_key = "central_gov"
        elif "removal" in cb or "non-re-appointment" in cb:
            scenario_key = "removal_appointment"
        elif "appointment" in cb:
            scenario_key = "appointment"
        elif "cessation" in cb:
            scenario_key = "cessation"
        elif "change in designation" in cb:
            scenario_key = "change_in_designation"
        else:
            scenario_key = re.sub(r'[^a-z0-9]+', '_', cb).strip('_')
        context["scenario"] = scenario_key

    if scenario_key:
        t_name = schema.get("form_name", form_id)
        lexicon = get_scenario_lexicon(t_name, scenario=scenario_key)
        context["lexicon"] = lexicon

    # Fallback to saved SchemaAliasRules for this form template if no direct evidence was supplied
    if not evidence_items:
        t_name = schema.get("form_name")
        effective_rules = get_effective_rules(
            t_name,
            company_id=context.get("company_id"),
            scenario=context.get("scenario")
        )
        for a in effective_rules.values():
            evidence_items.append({
                "key": a.extracted_key,
                "value": a.extracted_key,
                "source_doc": f"Rule Memory ({a.scope_type})"
            })

    # Execute dynamic form filling with context and dynamic lexicon
    filler = DynamicFormFiller()
    execution_result = filler.fill_form(schema, evidence_items, context=context if context else None)
    return execution_result



@router.post("/forms/{form_id}/validate")
def validate_mca_form(
    form_id: str,
    request: FormValidateRequest,
    db: Session = Depends(get_db)
):
    """
    Deterministic Live Validation Endpoint for UI form edits:
    Evaluates types, regexes, canonical option constraints, and DAG dependency pruning.
    Does NOT call the LLM — runs 100% deterministically in <5ms.
    """
    schema = FormRegistry.get_form_schema(form_id, db)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Form schema for '{form_id}' not found")

    fields = schema.get("fields", [])
    raw_mappings = {}
    for f in fields:
        f_id = f["id"]
        val = request.values.get(f_id)
        raw_mappings[f_id] = {
            "status": "populated" if val is not None and str(val).strip() != "" else "missing",
            "value": val,
            "confidence": 1.0 if val is not None else 0.0,
            "reasoning": "User input / validated edit"
        }

    filler = DynamicFormFiller()
    validated_fields = filler._validate_and_normalize_values(fields, raw_mappings, [])
    active_fields = filler._resolve_dag_dependencies(fields, validated_fields)
    payload = filler._compile_execution_payload(schema["form_id"], schema["form_name"], fields, active_fields, 0.001)
    return payload


from typing import Optional, Dict, Any

class SchemaAliasCreate(BaseModel):
    template_name: str
    form_field: str
    extracted_key: str
    spatial_meta: Optional[Dict[str, Any]] = None
    document_type: Optional[str] = "generic"
    scope_type: Optional[str] = "GLOBAL"
    scope_id: Optional[str] = "default"
    priority: Optional[int] = 1

class SchemaAliasResponse(SchemaAliasCreate):
    rule_id: str
    scope_type: Optional[str] = "GLOBAL"
    scope_id: Optional[str] = "default"
    priority: Optional[int] = 1
    
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
    Takes the mapped dictionary from IDP Studio, feeds it into the FLABridgeAdapter
    (which executes untouched FLA RuleEngine math + direct mapping guarantee),
    and returns the computed cell state.
    """
    try:
        print("INCOMING IDP PAYLOAD:", payload)
        from .extractors.fla_bridge import FLABridgeAdapter
        bridge = FLABridgeAdapter()

        computed_state = bridge.adapt_and_evaluate(payload)
        cell_labels = bridge.get_all_cell_labels()
        
        return {
            "status": "success",
            "computed_state": computed_state,
            "cell_labels": cell_labels
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
    Takes the mapped dictionary from IDP Studio, evaluates it via FLABridgeAdapter,
    populates the skeletal Excel template, and returns the physical .xlsx file.
    """
    try:
        from .extractors.fla_bridge import FLABridgeAdapter
        from automation_engine.core.excel_writer import ExcelWriter

        
        # 1. Compute target cells via 3-Phase FLABridgeAdapter
        bridge = FLABridgeAdapter()
        target_cells = bridge.adapt_and_evaluate(payload)
        
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

# ==============================================================================
def _create_dynamic_statutory_form_pdf(template_name: str, mapped_data: Dict[str, Any], db: Any = None) -> Any:
    """
    Universal Dynamic Statutory PDF Template Generator for all 54+ MCA Forms.
    ZERO HARDCODING: Dynamically reads field definitions, canonical numbers,
    statutory labels, radio/toggle options, and DAG pruning conditions directly from FormRegistry.
    Guarantees every field has its field name/label clearly rendered without text truncation or overflow.
    """
    import fitz
    import math
    import re
    from .forms.registry import FormRegistry

    schema = FormRegistry.get_form_schema(template_name, db) if template_name else None
    form_title = (schema.get("form_name") if schema else None) or template_name or "MCA Statutory Form"
    governing_law = (schema.get("governing_law") if schema else None) or "Companies Act, 2013 / Applicable Statutory Rules"
    fields = schema.get("fields", []) if schema else []

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # Standard A4

    # Outer statutory border
    page.draw_rect(fitz.Rect(28, 28, 567, 814), color=(0.15, 0.2, 0.3), width=1.2)

    # Header Banner
    page.draw_rect(fitz.Rect(28, 28, 567, 102), color=(0.94, 0.96, 0.98), fill=(0.94, 0.96, 0.98))
    page.draw_line(fitz.Point(28, 102), fitz.Point(567, 102), color=(0.15, 0.2, 0.3), width=1.0)

    page.insert_text((42, 48), "GOVERNMENT OF INDIA", fontsize=9.5, fontname="helv", color=(0.25, 0.25, 0.25))
    page.insert_text((42, 63), "MINISTRY OF CORPORATE AFFAIRS", fontsize=12, fontname="helv", color=(0.08, 0.16, 0.36))
    page.insert_text((42, 82), str(form_title).upper(), fontsize=13.5, fontname="helv", color=(0.05, 0.1, 0.25))
    page.insert_text((42, 95), f"Statutory Return Pursuant to {governing_law}", fontsize=7.5, fontname="helv", color=(0.4, 0.45, 0.5))

    # Verification seal / badge
    badge_rect = fitz.Rect(430, 42, 552, 68)
    page.draw_rect(badge_rect, color=(0.1, 0.6, 0.3), fill=(0.92, 0.98, 0.94), width=1.0)
    page.insert_text((440, 58), "STATUS: READY TO FILE", fontsize=7.5, fontname="helv", color=(0.05, 0.5, 0.25))

    matched_keys = set()

    # Dynamic Field Value Resolver with Type Guards & Family Boundary Isolation
    def _find_field_value(field_def: Dict[str, Any]) -> Optional[str]:
        fid = field_def.get("id", "")
        flabel = field_def.get("label", "").lower()
        cno = str(field_def.get("canonical_no", "")).lower().replace("(", "").replace(")", "").strip()
        f_type = str(field_def.get("type", "text")).lower()
        options = field_def.get("options") or []

        # Universal Data-Type Sanity Validator & Sanitizer
        def _validate_and_sanitize(val: Any) -> Optional[str]:
            if val is None:
                return None
            if isinstance(val, (list, dict)):
                return val
            val_str = str(val).strip()
            if val_str in ["", "None", "null", "Unknown", "N/A", "Empty / N/A"]:
                return None

            # 1. Date Type Guard: Strictly enforce date format and reject comma-separated share numbers
            is_date_field = (
                f_type == "date"
                or "(dd/mm/yyyy)" in flabel
                or "from (dd/mm/yyyy)" in flabel
                or "to (dd/mm/yyyy)" in flabel
                or "period of filing" in flabel
            )
            if is_date_field:
                if "," in val_str:
                    return None  # Reject share numbers like 2,99,025
                if not re.search(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', val_str):
                    return None  # Must match date pattern

            # 2. Numeric / Share count Guard: Sanitize non-numeric status strings to clean 0
            is_numeric_field = (
                f_type in ["number", "currency"]
                or "number of shares" in flabel
                or "held in" in flabel
                or "total shares" in flabel
            )
            if is_numeric_field:
                upper = val_str.upper()
                if upper in ["NOT ADMITTED", "N/A", "NIL", "NONE", "UNKNOWN"]:
                    return "0"

            return val_str

        # 1. Exact ID check
        if fid in mapped_data:
            sanitized = _validate_and_sanitize(mapped_data[fid])
            if sanitized is not None:
                matched_keys.add(fid)
                return sanitized

        # 2. Canonical number check with Family Isolation
        if cno:
            for k, v in mapped_data.items():
                sanitized = _validate_and_sanitize(v)
                if sanitized is None:
                    continue

                k_norm = str(k).lower().replace("(", "").replace(")", "").replace("-", "_").replace(" ", "_")
                
                # Family boundary guard: prevent cross-section suffix bleed (e.g. field_5gi_3 matching cno=3)
                k_family = re.search(r'field_([0-9]+)', k_norm)
                fid_family = re.search(r'field_([0-9]+)', fid.lower())
                if k_family and fid_family and k_family.group(1) != fid_family.group(1):
                    continue

                k_tail = k_norm.split(".")[-1]
                is_cno_match = (
                    k_tail == cno
                    or k_tail == f"field_{cno}"
                    or k_tail.startswith(f"field_{cno}_")
                    or k_norm == cno
                    or k_norm == f"field_{cno}"
                    or k_norm.startswith(f"{cno}_")
                )
                if is_cno_match:
                    matched_keys.add(k)
                    return sanitized

        # 3. Normalized ID fuzzy check
        norm_fid = re.sub(r"[^a-z0-9]", "", fid.lower())
        for k, v in mapped_data.items():
            sanitized = _validate_and_sanitize(v)
            if sanitized is None:
                continue

            k_norm = str(k).lower()
            # Family boundary check for fuzzy ID
            k_family = re.search(r'field_([0-9]+)', k_norm)
            fid_family = re.search(r'field_([0-9]+)', fid.lower())
            if k_family and fid_family and k_family.group(1) != fid_family.group(1):
                continue

            norm_k = re.sub(r"[^a-z0-9]", "", k_norm)
            if norm_k == norm_fid or (len(norm_fid) > 4 and norm_fid in norm_k) or (len(norm_k) > 4 and norm_k in norm_fid):
                matched_keys.add(k)
                return sanitized

            # Label token check
            clean_k = str(k).lower().replace("_", " ").replace("field ", "").strip()
            if flabel:
                # Direct substring match
                if clean_k in flabel or flabel in clean_k:
                    matched_keys.add(k)
                    return sanitized
                # Whole word match for acronyms (e.g. cin, din, pan, llpin)
                if len(clean_k) >= 3 and re.search(r'\b' + re.escape(clean_k) + r'\b', flabel):
                    matched_keys.add(k)
                    return sanitized
                # Multi-word token subset match (e.g. "company_name" in "Name of the Company")
                tokens_k = set(re.findall(r'[a-z0-9]+', clean_k)) - {"the", "of", "and", "in", "to", "for", "is", "field"}
                tokens_lbl = set(re.findall(r'[a-z0-9]+', flabel)) - {"the", "of", "and", "in", "to", "for", "is", "field"}
                if len(tokens_k) >= 2 and tokens_k.issubset(tokens_lbl):
                    matched_keys.add(k)
                    return sanitized

        # 4. If radio/toggle with [Yes, No] options and not affirmatively mapped, default to "No"
        if f_type in ["radio", "toggle"] and options and set(str(o).lower().strip() for o in options) == {"yes", "no"}:
            return "No"

        return None

    # Section Header
    y = 115
    page.draw_rect(fitz.Rect(35, y, 560, y + 18), color=(0.88, 0.91, 0.95), fill=(0.88, 0.91, 0.95))
    page.insert_text((42, y + 13), "I. STATUTORY PARTICULARS & RETURN DATA", fontsize=8.5, fontname="helv", color=(0.1, 0.18, 0.35))
    y += 24

    # Build display items dynamically from schema with DAG Pruning
    display_items = []
    if fields:
        # Build context map for DAG dependency evaluation
        extracted_context = {}
        for f in fields:
            v = _find_field_value(f)
            if v:
                extracted_context[f["id"]] = v

        for f in fields:
            # Dynamic DAG Pruning Check
            dep = f.get("depends_on")
            if dep and isinstance(dep, dict):
                parent_field = dep.get("field")
                target_value = dep.get("value")
                operator = dep.get("operator", "equals")

                parent_val = extracted_context.get(parent_field)
                if not parent_val and parent_field:
                    norm_pf = re.sub(r"[^a-z0-9]", "", str(parent_field).lower())
                    for ek, ev in extracted_context.items():
                        norm_ek = re.sub(r"[^a-z0-9]", "", str(ek).lower())
                        if norm_pf == norm_ek or norm_pf in norm_ek or norm_ek in norm_pf:
                            parent_val = ev
                            break

                if parent_val:
                    p_str = str(parent_val).strip().lower()
                    t_str = str(target_value).strip().lower() if target_value else ""
                    if operator == "equals":
                        if p_str != t_str and t_str not in p_str and p_str not in t_str:
                            continue
                    elif operator == "in" and isinstance(target_value, list):
                        if not any(p_str == str(opt).strip().lower() or str(opt).strip().lower() in p_str for opt in target_value):
                            continue
                # If parent value not available, keep field visible so form is complete

            val = _find_field_value(f)
            c_no = str(f.get("canonical_no", "")).strip()
            raw_lbl = str(f.get("label", f["id"])).strip()
            full_label = f"{c_no}. {raw_lbl}" if c_no else raw_lbl
            if not full_label.startswith("*") and f.get("required", True):
                full_label = f"*{full_label}"

            display_items.append({
                "id": f.get("id"),
                "label": full_label,
                "value": val or "",
                "type": f.get("type", "text"),
                "options": f.get("options"),
                "columns": f.get("columns") or (f.get("table_metadata", {}).get("columns") if isinstance(f.get("table_metadata"), dict) else None) or [],
                "archetype": f.get("table_archetype") or (f.get("table_metadata", {}).get("table_archetype") if isinstance(f.get("table_metadata"), dict) else "web_dynamic_grid"),
                "raw_field": f
            })

    # Append any extra mapped fields that were not covered by schema
    for k, v in mapped_data.items():
        if k in matched_keys:
            continue
        if not v or str(v).strip() in ["", "None", "null", "Unknown", "N/A", "Empty / N/A"]:
            continue
        clean_lbl = k.replace("_", " ").replace("field ", "").title()
        display_items.append({
            "label": f"*{clean_lbl}",
            "value": str(v).strip(),
            "type": "text",
            "options": None,
            "columns": [],
            "archetype": None,
            "raw_field": None
        })

    # Render each statutory item dynamically
    for idx, item in enumerate(display_items):
        label = item["label"]
        val_str = item["value"]
        f_type = item.get("type", "text")
        options = item.get("options")
        is_radio = f_type in ["radio", "select", "toggle"] and options and len(options) > 0

        # --- STATUTORY TABLE / GRID RENDERING ---
        if f_type == "table":
            table_cols = item.get("columns") or []
            if not table_cols and isinstance(item.get("raw_field"), dict):
                table_cols = item["raw_field"].get("columns", [])

            # Check if value is list of rows or JSON string
            table_rows = []
            if isinstance(val_str, list):
                table_rows = val_str
            elif isinstance(val_str, str) and (val_str.startswith("[") or val_str.startswith("{")):
                try:
                    parsed_rows = json.loads(val_str)
                    table_rows = parsed_rows if isinstance(parsed_rows, list) else [parsed_rows]
                except Exception:
                    table_rows = []
            elif isinstance(val_str, dict):
                table_rows = [val_str]

            # If no rows or empty rows, render at least 2 default statutory rows so grid is clearly visible
            if not table_rows:
                table_rows = [{c.get("key", ""): "" for c in table_cols}, {c.get("key", ""): "" for c in table_cols}]

            header_h = 22.0
            col_header_h = 20.0
            row_h = 20.0
            total_table_min_h = header_h + col_header_h + row_h

            if y + total_table_min_h > 780:
                page.insert_text((42, 802), f"Page {len(doc)} • Official MCA Filing Return", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))
                page = doc.new_page(width=595, height=842)
                page.draw_rect(fitz.Rect(28, 28, 567, 814), color=(0.15, 0.2, 0.3), width=1.2)
                y = 45

            # 1. Table Title Banner across full width (x=35 to 560)
            page.draw_rect(fitz.Rect(35, y, 560, y + header_h), color=(0.75, 0.80, 0.88), fill=(0.88, 0.91, 0.96), width=0.8)
            lbl_text_rect = fitz.Rect(42, y + 2, 430, y + header_h - 2)
            page.insert_textbox(lbl_text_rect, label, fontsize=8.0, fontname="helv", color=(0.08, 0.16, 0.35))
            page.insert_text((440, y + 14), "[STATUTORY DYNAMIC GRID]", fontsize=6.5, fontname="helv", color=(0.25, 0.35, 0.45))
            y += header_h

            # 2. Column Headers
            num_cols = len(table_cols) if table_cols else 1
            sno_w = 26.0
            avail_w = 525.0 - sno_w
            col_w = avail_w / max(1, num_cols)

            page.draw_rect(fitz.Rect(35, y, 560, y + col_header_h), color=(0.75, 0.80, 0.88), fill=(0.93, 0.95, 0.98), width=0.5)
            page.insert_text((43, y + 13), "#", fontsize=7.5, fontname="helv", color=(0.12, 0.2, 0.3))

            for c_i, c in enumerate(table_cols):
                cx = 35 + sno_w + c_i * col_w
                page.draw_line(fitz.Point(cx, y), fitz.Point(cx, y + col_header_h), color=(0.75, 0.80, 0.88), width=0.5)
                c_lbl = c.get("label") or c.get("key", f"Col {c_i+1}")
                c_rect = fitz.Rect(cx + 2, y + 2, cx + col_w - 2, y + col_header_h - 2)
                page.insert_textbox(c_rect, c_lbl, fontsize=6.8, fontname="helv", color=(0.12, 0.2, 0.3))
            y += col_header_h

            # 3. Data Rows
            for r_idx, r_dict in enumerate(table_rows):
                if y + row_h > 780:
                    page.insert_text((42, 802), f"Page {len(doc)} • Official MCA Filing Return", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))
                    page = doc.new_page(width=595, height=842)
                    page.draw_rect(fitz.Rect(28, 28, 567, 814), color=(0.15, 0.2, 0.3), width=1.2)
                    y = 45
                    page.draw_rect(fitz.Rect(35, y, 560, y + col_header_h), color=(0.75, 0.80, 0.88), fill=(0.93, 0.95, 0.98), width=0.5)
                    page.insert_text((43, y + 13), "#", fontsize=7.5, fontname="helv", color=(0.12, 0.2, 0.3))
                    for c_i, c in enumerate(table_cols):
                        cx = 35 + sno_w + c_i * col_w
                        page.draw_line(fitz.Point(cx, y), fitz.Point(cx, y + col_header_h), color=(0.75, 0.80, 0.88), width=0.5)
                        c_lbl = c.get("label") or c.get("key", f"Col {c_i+1}")
                        c_rect = fitz.Rect(cx + 2, y + 2, cx + col_w - 2, y + col_header_h - 2)
                        page.insert_textbox(c_rect, c_lbl, fontsize=6.8, fontname="helv", color=(0.12, 0.2, 0.3))
                    y += col_header_h

                r_bg = (0.98, 0.99, 1.0) if r_idx % 2 == 0 else (1.0, 1.0, 1.0)
                page.draw_rect(fitz.Rect(35, y, 560, y + row_h), color=(0.85, 0.88, 0.92), fill=r_bg, width=0.5)
                page.draw_line(fitz.Point(35 + sno_w, y), fitz.Point(35 + sno_w, y + row_h), color=(0.85, 0.88, 0.92), width=0.5)
                page.insert_text((43, y + 13), str(r_idx + 1), fontsize=7.5, fontname="helv", color=(0.4, 0.45, 0.5))

                for c_i, c in enumerate(table_cols):
                    cx = 35 + sno_w + c_i * col_w
                    page.draw_line(fitz.Point(cx, y), fitz.Point(cx, y + row_h), color=(0.85, 0.88, 0.92), width=0.5)
                    cell_val = str(r_dict.get(c.get("key", ""), "") if isinstance(r_dict, dict) else "").strip()
                    cell_rect = fitz.Rect(cx + 3, y + 2, cx + col_w - 3, y + row_h - 2)
                    if cell_val:
                        page.insert_textbox(cell_rect, cell_val, fontsize=7.5, fontname="helv", color=(0.05, 0.1, 0.2))
                    else:
                        page.insert_textbox(cell_rect, "—", fontsize=7.0, fontname="helv", color=(0.6, 0.65, 0.7))
                y += row_h

            y += 6
            continue

        display_val = val_str if val_str else "(Not Applicable / Not Filled)"

        # Accurate Dynamic Row Height Calculation: accounts for BOTH label and value length
        lbl_lines = max(1, math.ceil(len(label) / 36.0))
        val_lines = max(1, math.ceil(len(display_val) / 44.0))
        radio_lines = len(options) if (is_radio and options) else 1
        total_lines = max(lbl_lines, val_lines, radio_lines)
        row_h = max(26.0, total_lines * 13.0 + 8.0)

        # Dynamic page break handling
        if y + row_h > 780:
            page.insert_text((42, 802), f"Page {len(doc)} • Official MCA Filing Return", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))
            page = doc.new_page(width=595, height=842)
            page.draw_rect(fitz.Rect(28, 28, 567, 814), color=(0.15, 0.2, 0.3), width=1.2)
            y = 45

        bg = (0.98, 0.99, 1.0) if idx % 2 == 0 else (1.0, 1.0, 1.0)
        page.draw_rect(fitz.Rect(35, y, 560, y + row_h), color=(0.85, 0.88, 0.92), fill=bg, width=0.5)
        # Column divider at x = 265 (gives 225pt width to label column, 285pt to value column)
        page.draw_line(fitz.Point(265, y), fitz.Point(265, y + row_h), color=(0.85, 0.88, 0.92), width=0.5)

        # Label cell: Guaranteed visibility with font size fallback
        lbl_rect = fitz.Rect(40, y + 3, 260, y + row_h - 2)
        res_lbl = page.insert_textbox(lbl_rect, label, fontsize=8.0, fontname="helv", color=(0.15, 0.22, 0.35))
        if res_lbl < 0:
            page.insert_textbox(lbl_rect, label, fontsize=7.0, fontname="helv", color=(0.15, 0.22, 0.35))

        # Value cell: Render dynamic radio/select options with filled dots or formatted text
        if is_radio and options:
            val_lower = val_str.lower().strip()
            opt_y = y + 4
            for opt in options:
                opt_str = str(opt).strip()
                is_selected = (opt_str.lower() in val_lower) or (val_lower and val_lower in opt_str.lower())
                page.draw_circle((280, opt_y + 5), radius=3.2, color=(0.3, 0.3, 0.3), width=0.75)
                if is_selected:
                    page.draw_circle((280, opt_y + 5), radius=1.8, color=(0.05, 0.1, 0.25), fill=(0.05, 0.1, 0.25))
                text_col = (0.05, 0.1, 0.25) if is_selected else (0.4, 0.45, 0.5)
                page.insert_text((290, opt_y + 8), opt_str, fontsize=7.5, fontname="helv", color=text_col)
                opt_y += 14
        else:
            val_rect = fitz.Rect(275, y + 3, 555, y + row_h - 2)
            val_col = (0.05, 0.1, 0.2) if val_str else (0.55, 0.6, 0.65)
            res_val = page.insert_textbox(val_rect, display_val, fontsize=8.5, fontname="helv", color=val_col)
            if res_val < 0:
                page.insert_textbox(val_rect, display_val, fontsize=7.5, fontname="helv", color=val_col)

        y += row_h + 2

    page.insert_text((42, 802), f"Page {len(doc)} of {len(doc)} • Official MCA Filing Return (Autonomous IDP Engine)", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))
    return doc


# ==============================================================================
# NEW: POST /generate_preview_pdf — Generic PDF Preview Generation
# ==============================================================================
@router.post("/generate_preview_pdf")
async def generate_preview_pdf(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    """
    Takes the mapped dictionary, fetches spatial metadata for the template,
    and stamps the text onto the official PDF template (with dynamic template generation fallback).
    """
    try:
        import fitz  # PyMuPDF
        import json as python_json
        import re
        import os
        import uuid
        
        template_name = payload.get("template_name")
        mapped_data = payload.get("mapped_data", {})
        
        if not template_name:
            raise HTTPException(status_code=400, detail="Missing template_name in payload")
            
        # 1. Fetch schema alias rules for spatial metadata
        rules = db.query(models.SchemaAliasRule).filter(models.SchemaAliasRule.template_name == template_name).all()
        spatial_map = {}
        for r in rules:
            if r.spatial_meta_json:
                spatial_map[r.form_field] = python_json.loads(r.spatial_meta_json)
                
        # 2. Locate blank template with case-insensitive fallback
        clean_tname = template_name.replace(".pdf", "").replace(".PDF", "").strip()
        template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "templates"))
        template_path = os.path.join(template_dir, f"{clean_tname}.pdf")
        
        if not os.path.exists(template_path) and os.path.exists(template_dir):
            for fname in os.listdir(template_dir):
                if fname.lower() == f"{clean_tname.lower()}.pdf" or clean_tname.lower() in fname.lower():
                    template_path = os.path.join(template_dir, fname)
                    break
                    
        # 3. Open PDF or dynamically generate statutory template on-the-fly
        doc = None
        is_dynamic_generated = False
        if os.path.exists(template_path):
            try:
                doc = fitz.open(template_path)
                # Verify whether this is an instruction kit or a genuine blank form
                first_page_text = doc[0].get_text().lower() if len(doc) > 0 else ""
                if "instruction kit" in first_page_text or "table of contents" in first_page_text or "about this document" in first_page_text or len(doc) > 6:
                    # It's an instruction kit booklet, not a blank form template!
                    doc.close()
                    doc = None
            except Exception as open_err:
                print(f"[Preview PDF] Could not open static template '{template_path}': {open_err}")
                doc = None

        if doc is None:
            print(f"[Preview PDF] Generating dynamic statutory output template on-the-fly for '{template_name}'...")
            doc = _create_dynamic_statutory_form_pdf(template_name, mapped_data, db=db)
            is_dynamic_generated = True

        # 4. If using static PDF template, stamp extracted data onto coordinates
        if not is_dynamic_generated:
            # Helper: Stamp Radio Button / Toggle Option Dot
            def stamp_radio_button(doc_ref, label_targets, chosen_val, possible_options=["Yes", "No"]):
                if not chosen_val:
                    return False
                val_norm = str(chosen_val).strip()
                
                for p in doc_ref:
                    for target in label_targets:
                        lbl_rects = p.search_for(target)
                        if lbl_rects:
                            lr = lbl_rects[0]
                            # 1. Clear existing marks from all options on this line
                            for opt in possible_options:
                                for mr in p.search_for(opt):
                                    if abs(mr.y0 - lr.y0) < 18:
                                        cx = mr.x0 - 8.5
                                        cy = (mr.y0 + mr.y1) / 2.0
                                        p.draw_circle((cx, cy), radius=3.2, color=(1, 1, 1), fill=(1, 1, 1))
                                        p.draw_circle((cx, cy), radius=4.5, color=(0.2, 0.2, 0.2), fill=None, width=0.75)
                            
                            # 2. Find selected option and stamp filled dot
                            target_opt = None
                            for opt in possible_options:
                                if opt.lower() == val_norm.lower() or val_norm.lower() in opt.lower() or opt.lower() in val_norm.lower():
                                    target_opt = opt
                                    break
                            
                            if target_opt:
                                for mr in p.search_for(target_opt):
                                    if abs(mr.y0 - lr.y0) < 18:
                                        cx = mr.x0 - 8.5
                                        cy = (mr.y0 + mr.y1) / 2.0
                                        p.draw_circle((cx, cy), radius=2.5, color=(0, 0, 0), fill=(0, 0, 0))
                                        return True
                return False

            # 5. STEP 2: STAMP newly extracted data (text boxes & radio buttons)
            for key, value in mapped_data.items():
                if not value or str(value).strip() in ["", "None", "null", "N/A", "Unknown", "Empty / N/A"]:
                    continue
                    
                val_str = str(value).strip()
                meta = spatial_map.get(key)
                stamped = False
                lower_key = key.lower()

                # Radio & Toggle Check
                if any(k in lower_key for k in ["class_of_companies", "139_2", "139(2)", "falling under"]):
                    stamped = stamp_radio_button(doc, ["falling under any class of companies", "section 139(2)"], val_str, ["Yes", "No"])
                elif any(k in lower_key for k in ["nature_of_appointment", "nature of appointment", "appointment_type"]):
                    stamped = stamp_radio_button(doc, ["*Nature of appointment", "Nature of appointment"], val_str, [
                        "First auditor by Board of directors", "Appointment of Auditors in AGM", "Re-appointment of Auditors in AGM",
                        "Appointment/ Re-appointment by C&AG", "Auditor appointed in case of casual vacancy",
                        "Auditor appointed in case of non-re-appointment/ removal", "Auditor appointed by Central Government",
                        "Auditor appointed by the Tribunal", "Others"
                    ])
                elif any(k in lower_key for k in ["purpose_of_filing", "purpose of filing", "field_3a", "field_5a", "field_5c_2"]) or (("3a" in lower_key or "5a" in lower_key) and "purpose" in lower_key):
                    stamped = stamp_radio_button(doc, ["Purpose of filing the form", "Purpose of filing"], val_str, [
                        "Appointment", "Cessation", "Change in designation",
                        "Appointment due to disqualification of all the existing directors",
                        "Appointment by liquidator"
                    ])
                elif any(k in lower_key for k in ["appointed_in_agm", "annual general meeting", "agm"]):
                    stamped = stamp_radio_button(doc, ["annual general meeting (AGM)", "appointed in the annual general meeting"], val_str, ["Yes", "No"])
                elif any(k in lower_key for k in ["joint_auditor", "joint auditors"]):
                    stamped = stamp_radio_button(doc, ["joint auditors have been appointed"], val_str, ["Yes", "No"])
                elif any(k in lower_key for k in ["audit_committee", "recommendation of the audit"]):
                    stamped = stamp_radio_button(doc, ["recommendation of the Audit Committee constituted", "Audit Committee constituted"], val_str, ["Yes", "No", "Not Applicable"])
                elif any(k in lower_key for k in ["whether_chairman", "chairman", "executive_director", "field_3m"]):
                    stamped = stamp_radio_button(doc, ["Whether Chairman, Executive Director, Non-Executive Director"], val_str, ["Yes", "No"])
                elif lower_key in ["language", "form_language"]:
                    stamped = stamp_radio_button(doc, ["English", "Hindi"], val_str, ["English", "Hindi"])

                if stamped:
                    continue
                
                # Method A: Use exact spatial metadata if present
                if meta:
                    polygon = None
                    if meta.get("bounding_regions") and len(meta["bounding_regions"]) > 0:
                        polygon = meta["bounding_regions"][0].get("polygon")
                    elif meta.get("polygon"):
                        polygon = meta["polygon"]
                    
                    if polygon and len(polygon) >= 8:
                        x0 = min(polygon[0], polygon[2], polygon[4], polygon[6]) * 72
                        y0 = min(polygon[1], polygon[3], polygon[5], polygon[7]) * 72
                        x1 = max(polygon[0], polygon[2], polygon[4], polygon[6]) * 72
                        y1 = max(polygon[1], polygon[3], polygon[5], polygon[7]) * 72
                        
                        erase_rect = fitz.Rect(max(392.5, x0 + 1), y0 + 1, min(573.5, x1 - 1), y1 - 1)
                        write_rect = fitz.Rect(max(395.0, x0 + 3), y0 + 2, min(571.0, x1 - 2), y1 - 1)
                        
                        page_num = 0
                        if meta.get("bounding_regions") and len(meta["bounding_regions"]) > 0:
                            page_num = meta["bounding_regions"][0].get("pageNumber", 1) - 1
                            
                        if 0 <= page_num < len(doc):
                            page = doc[page_num]
                            page.draw_rect(erase_rect, color=(1, 1, 1), fill=(1, 1, 1))
                            page.insert_textbox(write_rect, val_str, fontsize=9.0, color=(0, 0, 0.75), fontname="helv")
                            stamped = True
                            
                # Method B: Smart targeted search for official form field labels
                if not stamped:
                    targets = []
                    is_address = 'address' in lower_key
                    
                    if 'cin' in lower_key or 'identity' in lower_key:
                        targets = ['Corporate Identity Number', 'CIN', 'identity number']
                    elif 'company' in lower_key and 'name' in lower_key:
                        targets = ['Name of the company', 'Name of the Company']
                    elif is_address:
                        targets = ['Address of the registered office of the company', 'Address of the registered office', 'Address Line 1', 'Address Line 2']
                    elif 'email' in lower_key:
                        targets = ['Email ID of the company', 'Email ID', '*Email ID']
                    elif 'date' in lower_key and 'appointment' in lower_key:
                        targets = ['Date of appointment', 'appointment (DD/MM/YYYY)', 'appointment']
                    elif 'auditor' in lower_key and ('firm' in lower_key or 'name' in lower_key):
                        targets = ["Name of the Auditor's Firm", "Name of the auditor", "Name of the Auditor", "Auditor's Firm"]
                    elif 'membership' in lower_key:
                        targets = ['*Membership Number of Auditor', 'Membership Number']
                    elif 'firm registration' in lower_key or 'frn' in lower_key:
                        targets = ['Firm Registration Number']
                    elif 'financial year' in lower_key and 'number' in lower_key:
                        targets = ['*Number of financial year(s)', 'Number of financial year']
                    elif 's. no' in lower_key or 's.no' in lower_key:
                        targets = ['*S. no.', 'S. no.']
                    elif 'financial year start' in lower_key:
                        targets = ['*Financial Year Start Date', 'Financial Year Start Date (DD/MM/YYYY)']
                    elif 'financial year end' in lower_key:
                        targets = ['*Financial Year End Date', 'Financial Year End Date (DD/MM/YYYY)']
                    elif 'pan' in lower_key:
                        targets = ['permanent account number', 'Income Tax permanent account number', 'PAN']
                    else:
                        clean_search = re.sub(r"^field_", "", key).lower()
                        clean_search = re.sub(r"^[0-9]+[a-z]?\s*", "", clean_search)
                        kws = [w for w in re.split(r"[_\s]+", clean_search) if len(w) >= 3 and w not in ["the", "and", "for", "with", "from"]]
                        targets = [" ".join(kws[:3]), " ".join(kws[:2]), kws[0] if kws else ""]

                    for page in doc:
                        if stamped:
                            break
                        for phrase in targets:
                            if not phrase or len(phrase) < 3:
                                continue
                            rects = page.search_for(phrase)
                            if rects:
                                r = rects[0]
                                box_h = 42.0 if is_address else 16.0
                                font_sz = 8.0 if is_address else 9.0
                                
                                # Place text precisely within the black box margins (x=395 to 571)
                                erase_box = fitz.Rect(392.5, r.y0 - 2, 573.5, r.y0 + box_h)
                                text_box = fitz.Rect(395.0, r.y0, 571.0, r.y0 + box_h)
                                
                                page.draw_rect(erase_box, color=(1, 1, 1), fill=(1, 1, 1))
                                page.insert_textbox(text_box, val_str, fontsize=font_sz, color=(0, 0, 0.75), fontname="helv")
                                stamped = True
                                break
                    
        # 6. Save output
        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "output", "previews"))
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"{template_name}_Preview_{uuid.uuid4().hex[:8]}.pdf"
        output_path = os.path.join(output_dir, output_filename)
        
        doc.save(output_path)
        doc.close()
        
        return FileResponse(
            path=output_path,
            filename=f"{template_name}_Preview.pdf",
            media_type="application/pdf"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF Generation Error: {str(e)}")

@router.get("/rules/{template_name}", response_model=List[SchemaAliasResponse])
def get_rules_for_template(
    template_name: str,
    company_id: Optional[str] = None,
    scenario: Optional[str] = None,
    document_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if company_id or scenario or document_type:
        effective = get_effective_rules(template_name, company_id=company_id, scenario=scenario, document_type=document_type)
        return list(effective.values())
    rules = db.query(models.SchemaAliasRule).filter(models.SchemaAliasRule.template_name == template_name).all()
    return rules

@router.post("/rules", response_model=SchemaAliasResponse)
def create_schema_alias_rule(rule: SchemaAliasCreate, db: Session = Depends(get_db)):
    scope_t = rule.scope_type or "GLOBAL"
    scope_i = rule.scope_id or "default"
    pri = rule.priority or (3 if scope_t == "COMPANY" else (2 if scope_t == "SCENARIO" else 1))

    # Delete existing rule for this template + form_field + scope combination if it exists
    existing = db.query(models.SchemaAliasRule).filter(
        models.SchemaAliasRule.template_name == rule.template_name,
        models.SchemaAliasRule.form_field == rule.form_field,
        models.SchemaAliasRule.scope_type == scope_t,
        models.SchemaAliasRule.scope_id == scope_i
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
        document_type=rule.document_type or "generic",
        scope_type=scope_t,
        scope_id=scope_i,
        priority=pri,
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

def get_custom_temp_dir():
    candidates = [
        os.getenv("CUSTOM_TEMP_DIR"),
        "/data/arcaai/vidit",
        "/data/aracaai/vidit",
        os.path.expanduser("~/tmp")
    ]
    for target in candidates:
        if not target:
            continue
        try:
            os.makedirs(target, exist_ok=True)
            return target
        except Exception:
            pass
    return tempfile.gettempdir()

try:
    tempfile.tempdir = get_custom_temp_dir()
except Exception:
    pass

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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', dir=get_custom_temp_dir(), delete=False, encoding='utf-8') as tmp:
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


def _extract_value_from_dom_node(node, target_col_index: Optional[int] = None) -> str:
    """
    Extracts value from a matched DOM node (supports table rows and text/paragraph lines with colons).
    If target_col_index is specified, extracts the cell at that exact column index.
    """
    if not node:
        return ""
    
    text = (getattr(node, 'text', '') or '').strip()
    
    # 1. If line contains colon or hyphen delimiter (e.g. "PAN Number : AALCB0387K" or "CIN Number : U85100TN2022PTC154992")
    if ':' in text or ' - ' in text:
        delimiter = ':' if ':' in text else ' - '
        parts = text.split(delimiter)
        if len(parts) >= 2:
            val = parts[-1].strip()
            if val:
                return val

    # 2. If it's a table row with cells
    if hasattr(node, 'children') and node.children:
        from dom_learner.models import NodeType
        cells = [c for c in node.children if hasattr(c, 'node_type') and str(c.node_type).endswith('CELL')]
        if cells:
            if target_col_index is not None and 0 <= target_col_index < len(cells):
                return cells[target_col_index].text.strip()

            numeric_cells = [c for c in cells if _looks_like_number(c.text.strip())]
            if len(numeric_cells) >= 2:
                return numeric_cells[-2].text.strip()
            elif len(numeric_cells) == 1:
                return numeric_cells[0].text.strip()
            elif len(cells) >= 2:
                return cells[-1].text.strip()

    # 3. Fallback to text (handles flattened text lines without cell children)
    tokens = text.split()
    numeric_tokens = []
    # Find contiguous numeric tokens at the end of the line
    for token in reversed(tokens):
        if _looks_like_number(token):
            numeric_tokens.insert(0, token)
        else:
            break
            
    if numeric_tokens:
        # Simulate table cells: Col 0 = Text Label, Col 1+ = Numbers
        label_len = len(tokens) - len(numeric_tokens)
        label = " ".join(tokens[:label_len])
        simulated_cells = [label] + numeric_tokens if label else numeric_tokens
        
        if target_col_index is not None and 0 <= target_col_index < len(simulated_cells):
            return simulated_cells[target_col_index]
            
        if len(numeric_tokens) >= 2:
            return numeric_tokens[-2]
        elif len(numeric_tokens) == 1:
            return numeric_tokens[0]

    # If it's a raw unstructured paragraph without colons or trailing numbers, 
    # we MUST return empty to let the LLM extract the exact substring.
    return ""


def _try_dom_extraction(markdown_text: str, variable_name: str, db, template_name: str):
    """
    Tier 1 extraction: Attempts to extract a value for a variable_name using saved DOM rules.
    Navigates via saved dom_path JSON and handles both table cells and text sentences.
    Returns (value_str, dom_path_json) or (None, None).
    """
    try:
        clean_var = variable_name.strip().lower()
        import json as python_json

        # Check if we have a DOM rule for this variable
        dom_rule = db.query(models.DomExtractionRule).filter(
            models.DomExtractionRule.template_name == template_name,
            models.DomExtractionRule.variable_name.ilike(f"%{clean_var}%")
        ).order_by(models.DomExtractionRule.success_count.desc()).first()

        if not dom_rule:
            return None, None

        q = _get_dom_query_from_markdown(markdown_text)
        if q is None:
            return None, None

        matched_node = None
        target_col_index = None

        # Tier A: Try navigating via saved dom_path JSON if present
        if dom_rule.dom_path:
            try:
                path_list = python_json.loads(dom_rule.dom_path)
                if path_list and isinstance(path_list, list) and len(path_list) > 0:
                    last_path_item = path_list[-1]
                    target_col_index = last_path_item.get("col_index")

                    if hasattr(q, '_root') and q._root:
                        current_node = q._root
                        # True structural traversal: Walk down the tree following the path steps
                        for step_idx, step in enumerate(path_list):
                            step_type = (step.get("type") or "").lower()
                            
                            # Skip the Document node step if we are already at it
                            if step_idx == 0 and step_type == "document":
                                continue
                                
                            best_child = None
                            if hasattr(current_node, 'children') and current_node.children:
                                for child in current_node.children:
                                    child_type_str = str(getattr(child, 'node_type', '')).lower()
                                    if step_type in child_type_str or child_type_str.endswith(step_type):
                                        step_label = (step.get("label") or "").strip().lower()
                                        step_text = (step.get("text") or "").strip().lower()
                                        
                                        child_label = (child.metadata.get("row_label") or "").strip().lower() if hasattr(child, 'metadata') and child.metadata else ""
                                        child_text = (getattr(child, 'text', '') or "").strip().lower()
                                        
                                        # Prefer exact label/text match
                                        if step_label and (step_label in child_label or step_label in child_text):
                                            best_child = child
                                            break
                                        if step_text and step_text in child_text:
                                            best_child = child
                                            break
                                            
                                        # Fallback: if no specific label/text to match, just take the first matching type
                                        if not best_child and not step_label and not step_text:
                                            best_child = child
                            
                            if best_child:
                                current_node = best_child
                            else:
                                # Path broke, we can't find the next child
                                current_node = None
                                break
                                
                        if current_node and current_node != q._root:
                            matched_node = current_node
            except Exception as path_err:
                print(f"[DOM] Path navigation error: {path_err}")



        # Tier B: Fallback if structural path broke or did not match: find row/text directly via DOMQuery
        if not matched_node and q:
            matches = q.find_row(clean_var) or q.find_by_text(clean_var)
            if matches:
                matched_node = matches[0]

        if not matched_node:
            return None, None

        # If matched node is a cell directly, return its text
        if hasattr(matched_node, 'node_type') and str(matched_node.node_type).endswith('CELL'):
            value = (getattr(matched_node, 'text', '') or '').strip()
        else:
            value = _extract_value_from_dom_node(matched_node, target_col_index=target_col_index)

        if not value:
            return None, None

        # Guard 1: Reject large paragraph blocks — pass to LLM instead
        if len(str(value)) > len(str(variable_name)) + 20 and len(str(value).split()) > 5:
            print(f"[DOM] ❌ Rejected '{variable_name}' — grabbed large paragraph ({len(str(value))} chars). Passing to LLM.")
            return None, None

        # Guard 2: Reject self-referential extractions (e.g. value == "Corporate Office" when searching for "Corporate Office")
        if str(value).strip().lower() == str(variable_name).strip().lower():
            print(f"[DOM] ❌ Rejected '{variable_name}' — value is same as the label (self-referential). Passing to LLM.")
            return None, None

        # Guard 3: Reject URLs as values (e.g. www.kritilabs.com returned as Corporate Office address)
        val_stripped = str(value).strip().lower()
        if val_stripped.startswith("www.") or val_stripped.startswith("http://") or val_stripped.startswith("https://"):
            print(f"[DOM] ❌ Rejected '{variable_name}' — value is a URL, not a field value. Passing to LLM.")
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

    # 1. Fetch pre-built DOM Query from DOCUMENT_DOM_CACHE if available, or build on-the-fly
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

        # Fallback: If cache missed (e.g. server restarted), build DOM on-the-fly via Triton OCR!
        if not q:
            try:
                pdf_bytes = await file.read()
                full_text = _run_triton_ocr_on_pdf_bytes(pdf_bytes)
                if not full_text:
                    try:
                        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                            full_text = "\n".join(p.extract_text() or "" for p in pdf.pages if p.extract_text()).strip()
                    except Exception:
                        pass
                if full_text:
                    q = _get_dom_query_from_markdown(full_text)
                    DOCUMENT_DOM_CACHE[file.filename] = {"markdown": full_text, "query": q}
                    print(f"[Batch Save] Built DOM tree on-the-fly via Triton OCR for '{file.filename}'")
            except Exception as e:
                print(f"[Batch Save] Error building DOM tree on-the-fly: {e}")

    # Detect document type from file
    detected_doc_type = "generic"
    if file and file.filename:
        detected_doc_type = classify_document(file.filename, "")

    for item in mapped_rules:
        form_field = item.get("form_field")
        extracted_key = item.get("extracted_key")
        spatial_meta = item.get("spatial_meta")

        if not form_field or not extracted_key:
            continue

        spatial_json_str = None
        if spatial_meta:
            spatial_json_str = python_json.dumps(spatial_meta) if isinstance(spatial_meta, dict) else str(spatial_meta)

        item_scope_type = item.get("scope_type", "GLOBAL")
        item_scope_id = item.get("scope_id", "default")
        item_priority = item.get("priority", 3 if item_scope_type == "COMPANY" else (2 if item_scope_type == "SCENARIO" else 1))

        # Upsert SchemaAliasRule (spatial rule) with detected_doc_type and multi-tenant scoping
        existing_spatial = db.query(models.SchemaAliasRule).filter(
            models.SchemaAliasRule.template_name == template_name,
            models.SchemaAliasRule.form_field == form_field,
            models.SchemaAliasRule.scope_type == item_scope_type,
            models.SchemaAliasRule.scope_id == item_scope_id
        ).first()
        if existing_spatial:
            existing_spatial.document_type = detected_doc_type
            existing_spatial.extracted_key = extracted_key
            existing_spatial.spatial_meta_json = spatial_json_str
            existing_spatial.priority = item_priority
        else:
            db.add(models.SchemaAliasRule(
                rule_id=str(uuid.uuid4()),
                template_name=template_name,
                document_type=detected_doc_type,
                scope_type=item_scope_type,
                scope_id=item_scope_id,
                priority=item_priority,
                form_field=form_field,
                extracted_key=extracted_key,
                spatial_meta_json=spatial_json_str
            ))
        saved_count += 1

        # Learn DOM structural path using dom_learner down to Cell level when value is present
        extracted_val = item.get("extracted_value") or item.get("mapped_value")
        if q and extracted_key:
            try:
                best_target_node = None
                # Try exact row match first
                _matches = q.find_row(extracted_key) if hasattr(q, 'find_row') else []
                if _matches:
                    best_target_node = _matches[0]
                else:
                    clean_key = extracted_key.strip().lower()
                    if hasattr(q, '_root') and q._root and hasattr(q._root, 'get_all_nodes'):
                        for n in q._root.get_all_nodes():
                            if hasattr(n, 'text') and n.text and clean_key in n.text.lower():
                                best_target_node = n
                                break
                    if not best_target_node and hasattr(q, 'find_all'):
                        from dom_learner.models import NodeType
                        for n_type in [NodeType.ROW, NodeType.CELL, NodeType.PARAGRAPH, NodeType.HEADING]:
                            nodes = q.find_all(n_type)
                            for n in nodes:
                                if clean_key in (n.text or '').lower():
                                    best_target_node = n
                                    break
                            if best_target_node:
                                break

                # If extracted_val is present and best_target_node is a table row, find exact matching CellNode or col_index
                matched_cell_col_idx = None
                if best_target_node and extracted_val and hasattr(best_target_node, 'children'):
                    clean_val = str(extracted_val).strip()
                    cells = [c for c in best_target_node.children if hasattr(c, 'node_type') and str(c.node_type).endswith('CELL')]
                    for idx, cell in enumerate(cells):
                        if cell.text.strip() == clean_val:
                            best_target_node = cell
                            matched_cell_col_idx = idx
                            break

                if best_target_node:
                    path = q.get_structural_path(best_target_node) if hasattr(q, 'get_structural_path') else None
                    if path:
                        if matched_cell_col_idx is not None and isinstance(path, list) and len(path) > 0:
                            path[-1]["col_index"] = matched_cell_col_idx

                        dom_path_str = python_json.dumps(path)

                        existing_dom = db.query(models.DomExtractionRule).filter(
                            models.DomExtractionRule.template_name == template_name,
                            models.DomExtractionRule.variable_name == extracted_key,
                            models.DomExtractionRule.scope_type == item_scope_type,
                            models.DomExtractionRule.scope_id == item_scope_id
                        ).first()
                        if existing_dom:
                            existing_dom.dom_path = dom_path_str
                            existing_dom.document_type = detected_doc_type
                            existing_dom.priority = item_priority
                            existing_dom.created_at = datetime.datetime.utcnow()
                        else:
                            db.add(models.DomExtractionRule(
                                rule_id=str(uuid.uuid4()),
                                template_name=template_name,
                                document_type=detected_doc_type,
                                scope_type=item_scope_type,
                                scope_id=item_scope_id,
                                priority=item_priority,
                                variable_name=extracted_key,
                                dom_path=dom_path_str,
                                success_count=0
                            ))
                        db.commit()
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

    detected_doc_type = classify_document(file.filename if file else "", "")

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
        document_type=detected_doc_type,
        form_field=form_field,
        extracted_key=extracted_key,
        spatial_meta_json=spatial_json_str
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    print(f"[IDP] Spatial rule saved: '{form_field}' → '{extracted_key}' (DocType: {detected_doc_type}) for template '{template_name}'")

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

            # Refine doc type from full OCR text if available
            if full_markdown:
                refined_type = classify_document(file.filename, full_markdown)
                if refined_type != "generic":
                    detected_doc_type = refined_type
                    db_rule.document_type = detected_doc_type
                    db.commit()

            if q:
                _matches = q.find_row(extracted_key)
                best_row = _matches[0] if _matches else None
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
                        existing_dom.document_type = detected_doc_type
                        existing_dom.created_at = datetime.datetime.utcnow()
                    else:
                        db.add(models.DomExtractionRule(
                            rule_id=str(uuid.uuid4()),
                            template_name=template_name,
                            document_type=detected_doc_type,
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


def _normalize_llm_fields(raw_json):
    """Unwraps LLM response wrappers and ensures key-value pairs are flat primitive strings."""
    if isinstance(raw_json, dict):
        for wrapper_key in ["data", "extracted_data", "fields", "items", "results", "financials"]:
            if wrapper_key in raw_json and isinstance(raw_json[wrapper_key], list):
                raw_json = raw_json[wrapper_key]
                break
    
    items = []
    if isinstance(raw_json, dict):
        # Fix: Check if the dict itself is a single item like {"key": "...", "value": "..."}
        if ("key" in raw_json or "field" in raw_json or "label" in raw_json) and ("value" in raw_json or "val" in raw_json):
            k = raw_json.get("key") or raw_json.get("field") or raw_json.get("label") or raw_json.get("name")
            v = raw_json.get("value") or raw_json.get("val") or raw_json.get("amount")
            if k is not None and v is not None and not isinstance(v, (dict, list)):
                return [{"key": str(k), "value": str(v)}]

        for k, v in raw_json.items():
            if isinstance(v, (dict, list)):
                continue
            items.append({"key": str(k), "value": str(v)})
    elif isinstance(raw_json, list):
        for item in raw_json:
            if isinstance(item, dict):
                k = item.get("key") or item.get("field") or item.get("label") or item.get("name")
                v = item.get("value") or item.get("val") or item.get("amount")
                if k is not None and v is not None and not isinstance(v, (dict, list)):
                    items.append({"key": str(k), "value": str(v)})
                else:
                    for fk, fv in item.items():
                        if not isinstance(fv, (dict, list)):
                            items.append({"key": str(fk), "value": str(fv)})
    return items


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
CRITICAL INSTRUCTION: When you see tables with two years of data (e.g., 2023 and 2024), you MUST distinguish them.
Append "PY" to the key for the Previous Year and "FY" to the key for the Current/Financial Year.
Return ONLY a valid JSON array of objects, with each object having exactly two keys: "key" and "value".
Example: [{{"key": "Total Assets PY", "value": "120000"}}, {{"key": "Total Assets FY", "value": "150000"}}]

Document Text:
{text_content[:8000]}
    """
    
    try:
        response = requests.post(
            "http://192.168.112.2:11434/api/generate",
            json={
                "model": "qwen2.5:14b",
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
        raw_data = python_json.loads(extracted_text)
        extracted_data = _normalize_llm_fields(raw_data)
            
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

def _fast_path_extract_mca_fields(full_text: str, template_name: str, field_label_map: dict) -> dict:
    """
    Tier 0.5 — Fast-path deterministic regex and structured table matchers for standard MCA fields.
    Extracts high-confidence statutory fields (CIN, Company Name, Total Shares, 5(g) Demat/Physical tables)
    directly before DOM/LLM to guarantee instant, deterministic results.
    Returns {form_field: value} mapping.
    """
    if not full_text:
        return {}

    import re
    extracted = {}
    tmpl_lower = (template_name or "").lower()

    # 1. Corporate Identity Number (CIN) - 21 characters: [LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}
    cin_match = re.search(r'\b([LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b', full_text)
    if cin_match:
        cin_val = cin_match.group(1).strip()
        for f_id, label in field_label_map.items():
            l_lower = (label or "").lower()
            f_lower = (f_id or "").lower()
            if f_lower.endswith(".field_1") or f_lower == "field_1" or f_lower == "cin" or re.search(r'\bcin\b|\bcorporate identity number\b', l_lower):
                extracted[f_id] = cin_val

    # 2. Company Name
    comp_name = None
    # Pattern A: Subject: PAS 6 for <Company Name> (CIN: ... or \n)
    m = re.search(r'Subject:\s*(?:PAS\s*6\s*for|DIR-12\s*for|ADT-1\s*for|[A-Za-z0-9\-]+\s*for)\s+([A-Za-z0-9\s,\.\(\)]+?)(?:\s*\(CIN|\s*CIN[:\s]|\s*\n)', full_text, re.IGNORECASE)
    if m:
        comp_name = m.group(1).strip()
    # Pattern B: Markdown header ## **<Company Name>**
    if not comp_name:
        m = re.search(r'##\s*\*\*([A-Za-z0-9\s\.,\(\)]+?(?:Limited|Private Limited|Pvt Ltd|LLP))\*\*', full_text)
        if m:
            comp_name = m.group(1).strip()
    # Pattern C: Company Name followed by Date
    if not comp_name:
        m = re.search(r'\n([A-Za-z0-9\s,\.]+?(?:Limited|Private Limited|Pvt Ltd|LLP))\s*\nDate:', full_text)
        if m:
            comp_name = m.group(1).strip()
    # Pattern D: Key-Value line "Company Name: ..." or "Name of the Company: ..."
    if not comp_name:
        m = re.search(r'(?:Name of the company|Company Name)\s*[:\|]\s*([^\n\|]+)', full_text, re.IGNORECASE)
        if m:
            comp_name = m.group(1).strip()
    # Pattern E: Date followed by Company Name in RTA Certificate
    if not comp_name:
        m = re.search(r'Date:\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*\n([A-Za-z0-9\s,\.]+?(?:LIMITED|PVT LTD|PRIVATE LIMITED))', full_text, re.IGNORECASE)
        if m:
            comp_name = m.group(1).strip()
    if not comp_name:
        m = re.search(r'ISIN Description:\s*([A-Za-z0-9\s,\.]+?)\s+(?:EQ|EQUITY|PREF)', full_text, re.IGNORECASE)
        if m:
            comp_name = m.group(1).strip()

    if comp_name:
        comp_name_clean = comp_name.strip('*').strip()
        for f_id, label in field_label_map.items():
            l_lower = (label or "").lower()
            f_lower = (f_id or "").lower()
            if "name of the company" in l_lower or "company name" in l_lower or (f_lower.endswith(".field_2a") and "company" in l_lower):
                extracted[f_id] = comp_name_clean

    # 3. Form No. PAS-6 specific deterministic extraction
    if "pas" in tmpl_lower or "pas6" in tmpl_lower or "pas-6" in tmpl_lower:
        # Field 5(d): Total number of issued shares
        shares_match = re.search(r'(?:out of|total of)\s+([0-9,]+)\s+shares', full_text, re.IGNORECASE)
        if not shares_match:
            shares_match = re.search(r'(?:Total number of issued shares|Number of issued shares)\s*[:\|]\s*([0-9,]+)', full_text, re.IGNORECASE)
        if shares_match:
            shares_val = shares_match.group(1).strip()
            for f_id, label in field_label_map.items():
                if f_id.endswith(".field_5d") or f_id == "field_5d" or ("total" in (label or "").lower() and "shares" in (label or "").lower()):
                    extracted[f_id] = shares_val

        # Field 5(g): Promoters, Directors, KMP shares breakdown (Demat & Physical)
        prom_match = re.search(r'(?:^|\n)\s*\|?\s*(?:\(i\)\s*)?Promoters\s*\|?\s*([0-9,]+)\s*\|?\s*([0-9,]+)', full_text, re.IGNORECASE)
        if prom_match:
            demat_val = prom_match.group(1).strip()
            phys_val = prom_match.group(2).strip()
            for f_id in field_label_map:
                if f_id.endswith(".field_5gi") or f_id == "field_5gi":
                    extracted[f_id] = demat_val
                elif f_id.endswith(".field_5gi_3") or f_id == "field_5gi_3":
                    extracted[f_id] = phys_val

        dir_match = re.search(r'(?:^|\n)\s*\|?\s*(?:\(ii\)\s*)?Directors\s*\|?\s*([0-9,]+)\s*\|?\s*([0-9,]+)', full_text, re.IGNORECASE)
        if dir_match:
            demat_val = dir_match.group(1).strip()
            phys_val = dir_match.group(2).strip()
            for f_id in field_label_map:
                if f_id.endswith(".field_5gi_2") or f_id == "field_5gi_2":
                    extracted[f_id] = demat_val
                elif f_id.endswith(".field_5gi_4") or f_id == "field_5gi_4":
                    extracted[f_id] = phys_val

        kmp_match = re.search(r'(?:^|\n)\s*\|?\s*(?:\(iii\)\s*)?KMPs?\s*\|?\s*([0-9,]+)\s*\|?\s*([0-9,]+)', full_text, re.IGNORECASE)
        if kmp_match:
            demat_val = kmp_match.group(1).strip()
            phys_val = kmp_match.group(2).strip()
            for f_id in field_label_map:
                if f_id.endswith(".field_5gii") or f_id == "field_5gii":
                    extracted[f_id] = demat_val
                elif f_id.endswith(".field_5gii_2") or f_id == "field_5gii_2":
                    extracted[f_id] = phys_val

        # RTA Certificate & ISIN Pattern Matching
        m_isin = re.search(r'\b([A-Z]{2}[A-Z0-9]{9}\d)\b', full_text)
        if m_isin:
            isin_val = m_isin.group(1).strip()
            for f_id, label in field_label_map.items():
                if f_id.endswith(".field_5b") or f_id == "field_5b" or "isin" in (label or "").lower():
                    extracted[f_id] = isin_val

        # Half-year filing period from RTA certificate or audit text
        m_half = re.search(r'half year(?:ly)?\s*(?:audit|ended|end)?[-\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})', full_text, re.IGNORECASE)
        if m_half:
            end_date = m_half.group(1).strip()
            try:
                parts = end_date.split('/') if '/' in end_date else end_date.split('-')
                if len(parts) == 3:
                    d, m_part, y = parts[0], parts[1], parts[2]
                    from_date = f"01/10/{int(y)-1}" if m_part == "03" else f"01/04/{y}"
                    for f_id, label in field_label_map.items():
                        l_low = (label or "").lower()
                        if f_id.endswith(".field_3") or (f_id.endswith("field_3") and not f_id.endswith("field_3_2")) or "from (dd/mm/yyyy)" in l_low:
                            extracted[f_id] = from_date
                        elif f_id.endswith(".field_3_2") or f_id.endswith("field_3_2") or "to (dd/mm/yyyy)" in l_low:
                            extracted[f_id] = end_date
            except Exception:
                pass

        # Depository shares held through NSDL / CDSL (mapping NOT ADMITTED / NIL -> 0)
        m_nsdl = re.search(r'Electronic Form through NSDL\s*([0-9,]+|NOT ADMITTED|NIL)', full_text, re.IGNORECASE)
        if m_nsdl:
            raw_nsdl = m_nsdl.group(1).strip().upper()
            nsdl_val = "0" if raw_nsdl in ["NOT ADMITTED", "NIL", "N/A"] else m_nsdl.group(1).strip()
            for f_id, label in field_label_map.items():
                if f_id.endswith(".field_5di_2") or "nsdl" in (label or "").lower():
                    extracted[f_id] = nsdl_val

        m_cdsl = re.search(r'Electronic Form through CDSL\s*([0-9,]+|NOT ADMITTED|NIL)', full_text, re.IGNORECASE)
        if m_cdsl:
            raw_cdsl = m_cdsl.group(1).strip().upper()
            cdsl_val = "0" if raw_cdsl in ["NOT ADMITTED", "NIL", "N/A"] else m_cdsl.group(1).strip()
            for f_id, label in field_label_map.items():
                if f_id.endswith(".field_5di") or ("cdsl" in (label or "").lower() and "nsdl" not in (label or "").lower()):
                    extracted[f_id] = cdsl_val

        # Security type
        if "equity" in full_text.lower():
            for f_id, label in field_label_map.items():
                if f_id.endswith(".field_5a") or "type of security" in (label or "").lower():
                    extracted[f_id] = "Equity"

    # 4. Registered Address and Email for any MCA form
    addr_match = re.search(r'(?:Address of the registered office|Registered Office Address|Registered Address)\s*[:\|]\s*([^\n\|]+)', full_text, re.IGNORECASE)
    if addr_match:
        addr_val = addr_match.group(1).strip()
        for f_id, label in field_label_map.items():
            l_lower = (label or "").lower()
            if "registered ofice" in l_lower or "registered office" in l_lower or "registered address" in l_lower:
                extracted[f_id] = addr_val

    email_match = re.search(r'(?:email ID of the company|Email ID|Email)\s*[:\|]\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', full_text, re.IGNORECASE)
    if email_match:
        email_val = email_match.group(1).strip()
        for f_id, label in field_label_map.items():
            l_lower = (label or "").lower()
            if "email id" in l_lower or "email" in l_lower:
                extracted[f_id] = email_val

    # 5. DIN, PAN, and Board Resolution Date across all statutory forms
    din_match = re.search(r'\b(?:DIN|Director Identification Number)\s*[:\-\s]*([0-9]{8})\b', full_text, re.IGNORECASE)
    if din_match:
        din_val = din_match.group(1).strip()
        for f_id, label in field_label_map.items():
            l_lower = (label or "").lower()
            if "din" in l_lower or "director identification" in l_lower:
                extracted[f_id] = din_val

    pan_match = re.search(r'\b(?:PAN|Permanent Account Number)\s*[:\-\s]*([A-Z]{5}[0-9]{4}[A-Z])\b', full_text, re.IGNORECASE)
    if pan_match:
        pan_val = pan_match.group(1).strip()
        for f_id, label in field_label_map.items():
            l_lower = (label or "").lower()
            if "pan" in l_lower:
                extracted[f_id] = pan_val

    br_match = re.search(r'resolution\s*(?:no\.?|number)?\s*[:\-\s]*([0-9A-Za-z/]+)?\s*dated\s*[:\-\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', full_text, re.IGNORECASE)
    if br_match:
        br_num = br_match.group(1).strip() if br_match.group(1) else ""
        br_date = br_match.group(2).strip() if br_match.group(2) else ""
        for f_id, label in field_label_map.items():
            l_lower = (label or "").lower()
            if "board of directors" in l_lower or "vide resolution" in l_lower:
                extracted[f_id] = f"Resolution No: {br_num} Dated: {br_date}".strip()

    return extracted


@router.post("/extract/batch")
async def extract_batch_documents(
    files: List[UploadFile] = File(...),
    template_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    DOM-First Batch Extraction Pipeline:
    Tier 0 — Direct Excel (.xlsx / .xls) and Raw Markdown (.md / .txt) parsing.
    Tier 0.5 — Fast-Path deterministic regex and structured table matchers for standard MCA fields.
    Tier 1 — DOM structural navigation (saved rules, 100% deterministic).
    Tier 2 — pdfplumber digital text layer + Qwen LLM fallback.
    Tier 3 — Triton OCR + Qwen LLM fallback (scanned PDFs).
    """
    import json as python_json
    import re
    results = []

    # Load saved SchemaAliasRules for this template (maps form_field → extracted_key)
    schema_rules = []
    if template_name:
        schema_rules = db.query(models.SchemaAliasRule).filter(
            models.SchemaAliasRule.template_name == template_name
        ).all()

    # Build field_label_map and field_dependency_map from IdpTemplate schema
    field_label_map = {}
    field_dependency_map = {}
    if template_name:
        tmpl = db.query(models.IdpTemplate).filter(models.IdpTemplate.template_name == template_name).first()
        if tmpl and tmpl.fields_json:
            try:
                parsed_tmpl = python_json.loads(tmpl.fields_json)
                fields_list = parsed_tmpl.get("fields", parsed_tmpl) if isinstance(parsed_tmpl, dict) else parsed_tmpl
                if isinstance(fields_list, list):
                    for f in fields_list:
                        if isinstance(f, dict) and f.get("id"):
                            field_label_map[f["id"]] = f.get("label", f["id"])
                            if f.get("depends_on"):
                                field_dependency_map[f["id"]] = f["depends_on"]
            except Exception as tmpl_err:
                print(f"[Batch] Error loading template fields: {tmpl_err}")

    for file in files:
        filename = file.filename
        try:
            pdf_bytes = await file.read()
            extracted_fields = []
            extracted_lookup = {}
            any_dom_miss = False
            full_text = ""
            q = None
            doc_type = "generic"

            # --- TIER 0: Direct Excel (.xlsx / .xls) and Markdown (.md) Parsing ---
            fname_lower = filename.lower()
            if fname_lower.endswith(('.xlsx', '.xls', '.md', '.txt')):
                is_fla_template = "fla" in (template_name or "").lower()
                if is_fla_template:
                    try:
                        from modules.fla.comparison_platform.modules.legacy_parser import LegacyFLAParser
                        parser = LegacyFLAParser()
                        if fname_lower.endswith(('.xlsx', '.xls')):
                            import pandas as pd
                            excel_dfs = pd.read_excel(io.BytesIO(pdf_bytes), sheet_name=None)
                            parsed_dict = parser.parse_previous_fla(excel_dfs)
                        else:
                            text_str = pdf_bytes.decode('utf-8', errors='ignore')
                            parsed_dict = parser.parse_md(text_str)

                        extracted_fields = [{"key": k, "value": str(v)} for k, v in parsed_dict.items() if v not in [None, "", "Unknown", "N/A"]]
                        results.append({
                            "filename": filename,
                            "status": "success",
                            "extracted_fields": extracted_fields
                        })
                        continue
                    except Exception as excel_err:
                        print(f"[Batch] Direct Excel/MD parsing error on {filename}: {excel_err}")
                elif fname_lower.endswith(('.md', '.txt')):
                    full_text = pdf_bytes.decode('utf-8', errors='ignore')

            # Digital text extraction for PDFs via pdfplumber
            if fname_lower.endswith('.pdf'):
                pdf_digital_text = ""
                try:
                    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                        pages_text = [p.extract_text() or "" for p in pdf.pages if p.extract_text()]
                        pdf_digital_text = "\n".join(pages_text).strip()
                except Exception as pdf_err:
                    print(f"[Batch] pdfplumber digital text extraction error: {pdf_err}")

                # Run Full OCR (Triton) if possible to get structured tables for DOM
                try:
                    print(f"[Batch][DOM] Running Full Triton OCR on {filename}...")
                    full_text = _run_triton_ocr_on_pdf_bytes(pdf_bytes)
                except Exception as ocr_err:
                    print(f"[Batch][DOM] Triton OCR failed: {ocr_err}")

                if not full_text.strip() and pdf_digital_text:
                    full_text = pdf_digital_text

            if full_text:
                try:
                    q = _get_dom_query_from_markdown(full_text)
                except Exception as q_err:
                    print(f"[Batch][DOM] Error building DOM query from markdown: {q_err}")

            # Classify document into its specific document type
            doc_type = classify_document(filename, full_text)
            print(f"[Batch] Document '{filename}' classified as: '{doc_type}'")

            # --- TIER 0.5: Fast-Path Deterministic MCA Extraction ---
            fast_path_data = _fast_path_extract_mca_fields(full_text, template_name, field_label_map)
            for f_id, f_val in fast_path_data.items():
                if f_val and f_val not in [None, "", "Unknown", "N/A"]:
                    extracted_lookup[f_id] = f_val
                    extracted_fields.append({
                        "key": f_id,
                        "value": f_val,
                        "_source": "fast_path"
                    })
            if fast_path_data:
                print(f"[Batch] Fast-path extracted {len(fast_path_data)} fields deterministically: {list(fast_path_data.keys())}")

            # --- TIER 1: DOM-based extraction for each mapped form field ---
            if schema_rules:
                # Filter rules strictly for this document type
                scoped_rules = [r for r in schema_rules if getattr(r, 'document_type', 'generic') == doc_type]
                if not scoped_rules:
                    scoped_rules = [r for r in schema_rules if getattr(r, 'document_type', 'generic') in [None, 'generic', '']] or schema_rules

                print(f"[Batch] Scoped {len(scoped_rules)} of {len(schema_rules)} total rules for '{filename}' ({doc_type})")

                # Sort rules topologically: rules without dependencies evaluated first
                root_rules = [r for r in scoped_rules if r.form_field not in field_dependency_map]
                dependent_rules = [r for r in scoped_rules if r.form_field in field_dependency_map]
                ordered_rules = root_rules + dependent_rules

                seen_rule_fields = set()
                for rule in ordered_rules:
                    # If this field has already been extracted with a valid value (e.g. from Fast-Path), skip DOM/LLM
                    if rule.form_field in extracted_lookup and extracted_lookup[rule.form_field] not in [None, "", "Unknown", "N/A"]:
                        continue

                    # DAG Pruning Check: evaluate condition against already extracted values
                    dep = field_dependency_map.get(rule.form_field)
                    if dep and isinstance(dep, dict):
                        parent_id = dep.get("field")
                        op = dep.get("operator", "equals")
                        target_val = dep.get("value")
                        parent_val = extracted_lookup.get(parent_id)

                        if parent_val is not None:
                            p_str = str(parent_val).strip().lower()
                            t_str = str(target_val).strip().lower() if target_val is not None else ""
                            condition_met = True
                            if op == "equals":
                                condition_met = (p_str == t_str)
                            elif op == "in" and isinstance(target_val, list):
                                condition_met = any(p_str == str(v).strip().lower() for v in target_val)
                            
                            if not condition_met:
                                print(f"[Batch] ✂️ Pruning branch '{rule.form_field}': condition not met ({parent_id}='{parent_val}' vs target='{target_val}')")
                                continue

                    variable_name = rule.extracted_key
                    dom_value = None

                    # Try DOM navigation first
                    if full_text:
                        dom_value, _ = _try_dom_extraction(full_text, variable_name, db, template_name)

                    if dom_value:
                        extracted_lookup[rule.form_field] = dom_value
                        extracted_fields.append({
                            "key": rule.form_field,
                            "value": dom_value,
                            "_source": "dom"
                        })
                    else:
                        # Mark as needing LLM fallback only if not already marked for this field
                        if rule.form_field not in seen_rule_fields and rule.form_field not in extracted_lookup:
                            seen_rule_fields.add(rule.form_field)
                            any_dom_miss = True
                            extracted_fields.append({
                                "key": rule.form_field,
                                "value": None,
                                "_source": "pending_llm",
                                "_hint": rule.extracted_key
                            })

            # --- TIER 2 / 3: LLM fallback for any fields that DOM missed ---
            if True:
                try:
                    # Ensure we have text
                    if not full_text and fname_lower.endswith('.pdf'):
                        print(f"[LLM] No text yet for {filename}, running Triton OCR now...")
                        full_text = _run_triton_ocr_on_pdf_bytes(pdf_bytes)
                        if doc_type == "generic":
                            doc_type = classify_document(filename, full_text)

                    pending_items = [f for f in extracted_fields if f.get("_source") == "pending_llm"]
                    print(f"[LLM] Tier 2 starting for '{filename}' ({doc_type}) — {len(pending_items)} fields need LLM, text length={len(full_text)}")

                    if full_text.strip():
                        if not schema_rules:
                            targeted_fields_instruction = "Extract all relevant key-value pairs from the document."
                        elif pending_items:
                            field_lines = []
                            seen_prompt_keys = set()
                            for pf in pending_items:
                                raw_key = pf["key"]
                                if raw_key in seen_prompt_keys:
                                    continue
                                seen_prompt_keys.add(raw_key)

                                label = field_label_map.get(raw_key, "")
                                hint = pf.get("_hint", "")
                                if label and hint and hint.lower() not in label.lower():
                                    desc = f"{label} (Alias / Hint: {hint})"
                                elif label:
                                    desc = label
                                elif hint:
                                    desc = hint
                                else:
                                    clean_name = raw_key.replace("field_", "")
                                    clean_name = re.sub(r'^[0-9]+[a-z]?\s*', '', clean_name)
                                    clean_name = clean_name.replace("_", " ").title()
                                    desc = clean_name
                                field_lines.append(f'- Key: "{raw_key}" (Description: {desc})')
                            field_list = "\n".join(field_lines)
                            targeted_fields_instruction = f"""You MUST extract the following specific fields from the document text:
{field_list}

CRITICAL RULES:
1. Return ONLY a valid JSON array of objects.
2. In each object, the "key" property MUST BE THE EXACT Key string provided above (e.g. "{pending_items[0]['key']}"). Do NOT use the Description as the key.
3. Extract the actual value from the document text. Be strict: for "Address of Registered Office of the Company", extract ONLY the target Company's address. Do NOT extract an auditor's or service provider's letterhead address. If a field is not present in the document, return "Unknown" as the value."""
                        else:
                            targeted_fields_instruction = "Extract all relevant key-value pairs from the document."

                        if pending_items or not schema_rules:
                            prompt = f"""You are an advanced Intelligent Document Processing (IDP) extractor.
{targeted_fields_instruction}

Document Text:
{full_text[:8000]}
                            """
                            try:
                                response = requests.post(
                                    "http://192.168.112.2:11434/api/generate",
                                    json={
                                        "model": "qwen2.5:14b",
                                        "prompt": prompt,
                                        "stream": False,
                                        "format": "json"
                                    },
                                    timeout=60
                                )
                                response.raise_for_status()
                                result = response.json()
                                extracted_text = result.get("response", "[]")
                                print(f"[LLM] Raw response for '{filename}': {extracted_text[:300]}")
                                
                                raw_data = python_json.loads(extracted_text)
                                llm_fields = _normalize_llm_fields(raw_data)
                            except Exception as ollama_err:
                                print(f"[!] Ollama LLM call error for {filename}: {ollama_err}")
                                llm_fields = []
                        else:
                            llm_fields = []

                        if not schema_rules:
                            extracted_fields = llm_fields
                            any_dom_miss = bool(llm_fields)
                        else:
                            def _clean_alpha(s: str) -> str:
                                if not s: return ""
                                s = str(s).lower().strip()
                                if s.startswith("field_"): s = s[6:]
                                return "".join(c for c in s if c.isalnum())

                            llm_raw_map = {f["key"]: f["value"] for f in llm_fields if f.get("key") and f.get("value")}
                            llm_alpha_map = {_clean_alpha(f["key"]): f["value"] for f in llm_fields if f.get("key") and f.get("value")}

                            for field in extracted_fields:
                                if field.get("_source") == "pending_llm":
                                    field_key = field["key"]
                                    hint = field.get("_hint", "")
                                    matched_val = None

                                    # 1. Exact key match
                                    if field_key in llm_raw_map:
                                        matched_val = llm_raw_map[field_key]

                                    # 2. Case-insensitive key match
                                    if not matched_val:
                                        for k, v in llm_raw_map.items():
                                            if k.lower().strip() == field_key.lower().strip():
                                                matched_val = v
                                                break

                                    # 3. Clean Alphanumeric match (ignores field_, underscores, spaces, punctuation)
                                    if not matched_val:
                                        target_alpha = _clean_alpha(field_key)
                                        if target_alpha in llm_alpha_map:
                                            matched_val = llm_alpha_map[target_alpha]

                                    # 4. Alphanumeric Substring & Hint match
                                    if not matched_val:
                                        target_alpha = _clean_alpha(field_key)
                                        hint_alpha = _clean_alpha(hint)
                                        for k, v in llm_raw_map.items():
                                            k_alpha = _clean_alpha(k)
                                            if target_alpha and (target_alpha in k_alpha or k_alpha in target_alpha):
                                                matched_val = v
                                                break
                                            if hint_alpha and len(hint_alpha) > 3 and (hint_alpha in k_alpha or k_alpha in hint_alpha):
                                                matched_val = v
                                                break

                                    field["value"] = matched_val or "Unknown"
                                    field["_source"] = "llm"

                            # Append extra fields ONLY if not strictly scoped to schema_rules
                            if not schema_rules:
                                existing_keys = {f["key"].lower() for f in extracted_fields}
                                for item in llm_fields:
                                    k = item.get("key", "")
                                    v = item.get("value", "")
                                    if k and k.lower() not in existing_keys and v not in [None, "", "Unknown", "N/A"]:
                                        extracted_fields.append({"key": k, "value": v, "_source": "llm"})
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


            # Clean up internal metadata (_source, _hint) and remove any fields with no real value
            # Deduplicate by key keeping the first valid extracted value
            BAD_VALUES = {None, "", "Unknown", "N/A", "Empty / N/A", "None", "null"}
            cleaned_fields = []
            seen_clean_keys = set()
            for field in extracted_fields:
                field.pop("_source", None)
                field.pop("_hint", None)
                val = field.get("value")
                k = field.get("key")
                if str(val).strip() not in BAD_VALUES and val is not None and k not in seen_clean_keys:
                    seen_clean_keys.add(k)
                    cleaned_fields.append(field)

            # Determine status badge
            llm_used = any_dom_miss
            status_badge = "review" if llm_used else "success"

            results.append({
                "filename": filename,
                "document_type": doc_type,
                "status": status_badge,
                "extracted_fields": cleaned_fields
            })

        except Exception as e:
            print(f"[!] Batch extraction error on {filename}: {e}")
            results.append({
                "filename": filename,
                "status": "review",
                "extracted_fields": []
            })

    # Build unified dossier return across all uploaded files for the session
    dossier_map = {}
    for r in results:
        for f in r.get("extracted_fields", []):
            k = f.get("key")
            v = f.get("value")
            if k and v not in [None, "", "Unknown", "N/A", "Empty / N/A"]:
                # High-confidence precedence: if not yet present or previously "0", take non-empty value
                if k not in dossier_map or dossier_map[k] in ["0", "Unknown", None]:
                    dossier_map[k] = v

    dossier_merged_fields = [{"key": k, "value": v} for k, v in dossier_map.items()]

    return {
        "total_files": len(files),
        "results": results,
        "dossier_merged_fields": dossier_merged_fields
    }



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
                "model": "qwen2.5:14b",
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


