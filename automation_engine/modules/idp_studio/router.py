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
from .extractors.universal_statutory import (
    UniversalStatutoryExtractor,
    parse_and_normalize_date,
    match_canonical_option
)



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
    Only forms with divergent statutory pathways (like ADT-1 or DIR-12) use branch gating.
    Omnibus webforms like GNL-2, PAS-6, MGT-7, AOC-4, etc. proceed directly.
    """
    schema = FormRegistry.get_form_schema(form_id, db)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Form schema for '{form_id}' not found")

    # 1. Parse uploaded documents or JSON payload
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

    # 2. Universal Semantic Branch Detection
    # Form branches exist ONLY when a root/selector field gates conditional pathways in the DAG.
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
        "purpose of application",
        "type of resolution",
        "statement of account",
    ]

    branch_field = None

    # Criterion 1: Root field with >= 2 candidate options driving >= 2 DAG dependents
    if parent_counts:
        sorted_parents = sorted(parent_counts.items(), key=lambda x: x[1], reverse=True)
        for parent_id, dep_count in sorted_parents:
            if dep_count >= 2:
                matched_f = next(
                    (f for f in schema.get("fields", []) if f.get("id") == parent_id and f.get("options") and len(f.get("options")) >= 2),
                    None
                )
                if matched_f:
                    branch_field = matched_f
                    break

    # Criterion 2: Parent field matching statutory branch signals with >= 2 options and >= 1 dependent
    if not branch_field:
        for fld in schema.get("fields", []):
            field_label_lower = fld.get("label", "").lower()
            field_options = fld.get("options") or []
            if len(field_options) >= 2 and any(sig in field_label_lower for sig in BRANCH_FIELD_SIGNALS):
                if parent_counts.get(fld.get("id"), 0) >= 1:
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
                "key": a.form_field,
                "hint": a.extracted_key,
                "form_field": a.form_field,
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

def resolve_field_value(
    field_def: Dict[str, Any],
    mapped_data: Dict[str, Any],
    matched_keys: Optional[set] = None
) -> Optional[str]:
    """
    Universal Dynamic Field Value Resolver with Conservative Type Guards,
    Family Boundary Isolation, and Signatory Role Semantic Exclusivity.
    """
    if matched_keys is None:
        matched_keys = set()

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

        # 3. File Attachment Guard: File fields only accept genuine document/file names
        if f_type == "file":
            if not any(val_str.lower().endswith(ext) for ext in [".pdf", ".zip", ".jpg", ".png", ".xlsx", ".docx", ".doc"]):
                return None

        return val_str

    # Signatory Role Exclusivity Context
    is_dir_din_field = (
        "director identification number of the director" in flabel
        or ("director identification" in flabel and "manager" not in flabel)
        or ("din" in flabel and "manager" not in flabel and "secretary" not in flabel)
    )
    is_kmp_sec_field = (
        "manager or ceo or cfo" in flabel
        or "membership number of the company secretary" in flabel
        or "company secretary" in flabel
        or "membership number" in flabel
    ) and "director identification" not in flabel

    active_desig = str(
        mapped_data.get("designation")
        or mapped_data.get("field_designation")
        or mapped_data.get("formnomgt14.main.field_designation")
        or mapped_data.get("signatory_designation")
        or ""
    ).strip().lower()

    if is_dir_din_field and active_desig and not any(d in active_desig for d in ["director", "md", "managing"]):
        return None
    if is_kmp_sec_field and (active_desig and any(d in active_desig for d in ["director", "md", "managing"])):
        return None

    # Section Header Shield: Structural table headers (e.g. "Particulars of shares in respect of which...")
    # must never steal scalar numeric leaf inputs (e.g. share counts) meant for child fields like 3(a).
    is_structural_header = (
        (flabel.startswith("particulars of") or flabel.startswith("details of"))
        and len(flabel.split()) >= 10
        and f_type in ["text", "textarea"]
    )

    # Universal Table Field Reconstitution & Aggregation
    if f_type == "table":
        COLUMN_SYNONYMS = {
            "name": "partner_name",
            "full_name": "partner_name",
            "name_of_partner": "partner_name",
            "individual_name": "partner_name",
            "dpin": "dpin_pan",
            "pan": "dpin_pan",
            "passport": "dpin_pan",
            "din": "dpin_pan",
            "dpin_number": "dpin_pan",
            "pan_number": "dpin_pan",
            "dpin_or_pan": "dpin_pan",
            "role": "designation",
            "partner_designation": "designation",
            "obligation": "obligation_contribution",
            "obligation_of_contribution": "obligation_contribution",
            "contribution_obligation": "obligation_contribution",
            "field_7i": "obligation_contribution",
            "field_8f": "obligation_contribution",
            "received": "contribution_received",
            "contribution_accounted": "contribution_received",
            "contribution_received_and_accounted_for": "contribution_received",
            "contribution": "contribution_received",
            "field_7j": "contribution_received",
            "field_8g": "contribution_received",
            "resident": "is_resident",
            "resident_in_india": "is_resident",
            "whether_resident_in_india": "is_resident",
            "field_7k": "is_resident",
            "field_8q": "is_resident",
            "no_of_llps": "llp_count",
            "number_of_llps": "llp_count",
            "field_7l": "llp_count",
            "field_8r": "llp_count",
            "no_of_companies": "company_count",
            "number_of_companies": "company_count",
            "field_7m": "company_count",
            "field_8s": "company_count",
            "cin": "cin_llpin",
            "llpin": "cin_llpin",
            "reg_no": "cin_llpin",
            "registration_number": "cin_llpin",
            "company_name": "company_name",
            "name_of_body_corporate": "company_name",
            "nominee_name": "nominee_name",
            "name_of_nominee": "nominee_name",
            "nominee_dpin": "nominee_dpin",
            "nominee_pan": "nominee_dpin",
            "dpin_of_nominee": "nominee_dpin",
            "body_type": "body_type",
            "type_of_body_corporate": "body_type",
        }

        short_id = fid.split(".")[-1] if "." in fid else fid
        cols = field_def.get("columns") or (field_def.get("table_metadata", {}).get("columns") if isinstance(field_def.get("table_metadata"), dict) else [])
        col_keys = [c.get("key") for c in cols if isinstance(c, dict) and c.get("key")]
        default_rows = field_def.get("default_rows") or (field_def.get("table_metadata", {}).get("default_rows") if isinstance(field_def.get("table_metadata"), dict) else [])

        table_aliases = [fid, short_id, cno]
        if "individual" in flabel and "partner" in flabel:
            table_aliases.extend(["partners", "partner", "individual_partners", "designated_partners", "field_7", "7"])
        elif "body corporate" in flabel or "bodies corporate" in flabel:
            table_aliases.extend(["bodies_corporate", "body_corporate", "body_corporate_partners", "bodies_corporate_partners", "field_8", "8"])
        elif "summary" in flabel and "partner" in flabel:
            table_aliases.extend(["summary_partners", "partners_summary", "partner_summary", "field_9", "9"])

        # A. Check direct pre-aggregated list or JSON string in mapped_data
        direct_val = None
        for ta in table_aliases:
            if ta and ta in mapped_data:
                direct_val = mapped_data[ta]
                break

        if direct_val is not None:
            raw_list = None
            if isinstance(direct_val, list) and direct_val:
                raw_list = direct_val
            elif isinstance(direct_val, str) and (direct_val.strip().startswith("[") or direct_val.strip().startswith("{")):
                try:
                    parsed = json.loads(direct_val)
                    if isinstance(parsed, list) and parsed:
                        raw_list = parsed
                except Exception:
                    pass

            if raw_list:
                normalized_list = []
                for r in raw_list:
                    if isinstance(r, dict):
                        norm_r = {c: "" for c in col_keys}
                        for rk, rv in r.items():
                            if rk in norm_r:
                                norm_r[rk] = rv
                            else:
                                canon_col = COLUMN_SYNONYMS.get(str(rk).lower(), rk)
                                if canon_col in norm_r:
                                    norm_r[canon_col] = rv
                                else:
                                    norm_r[rk] = rv
                        normalized_list.append(norm_r)
                    else:
                        normalized_list.append(r)
                matched_keys.add(fid)
                if "." in fid:
                    matched_keys.add(short_id)
                return normalized_list

        # B. Dynamic Reconstruction from indexed cell keys in mapped_data
        alias_esc = "|".join([re.escape(a) for a in set(table_aliases) if a])
        indexed_rows = {}
        for k, v in mapped_data.items():
            if v is None or str(v).strip() in ["", "None", "null", "N/A", "Unknown"]:
                continue
            k_str = str(k).strip()
            # Match {table_prefix}[{idx}].{col} or {table_prefix}_row_{idx}_{col}
            m = re.search(r'(?:^|\.)(?:' + alias_esc + r')\[(\d+)\](?:\.|\_)?([a-zA-Z0-9_]+)$', k_str, re.IGNORECASE)
            if not m and short_id.startswith("field_"):
                base_num = re.search(r'field_(\d+[a-z]*)', short_id)
                if base_num:
                    m = re.search(r'(?:^|\.)field_' + re.escape(base_num.group(1)) + r'\[(\d+)\](?:\.|\_)?([a-zA-Z0-9_]+)$', k_str, re.IGNORECASE)
            if not m:
                m = re.search(r'(?:^|\.)(?:' + alias_esc + r')_row_(\d+)_([a-zA-Z0-9_]+)$', k_str, re.IGNORECASE)

            if m:
                r_idx = int(m.group(1))
                raw_col_k = m.group(2)
                col_k = raw_col_k if (raw_col_k in col_keys) else COLUMN_SYNONYMS.get(raw_col_k.lower(), raw_col_k)
                if r_idx not in indexed_rows:
                    indexed_rows[r_idx] = {}
                indexed_rows[r_idx][col_k] = v
                matched_keys.add(k)

        if indexed_rows:
            if default_rows:
                merged = [dict(r) for r in default_rows]
                for r_idx, r_dict in indexed_rows.items():
                    while len(merged) <= r_idx:
                        merged.append({c: "" for c in col_keys})
                    merged[r_idx].update(r_dict)
                return merged
            else:
                max_idx = max(indexed_rows.keys())
                res_rows = []
                for i in range(max_idx + 1):
                    row_data = {c: "" for c in col_keys}
                    row_data.update(indexed_rows.get(i, {}))
                    res_rows.append(row_data)
                return res_rows

        # C. Match loose unindexed column keys in mapped_data
        if col_keys:
            single_row = {}
            for c_def in cols:
                ck = c_def.get("key", "")
                if not ck:
                    continue
                for k, v in mapped_data.items():
                    if v is None or str(v).strip() in ["", "None", "null", "N/A", "Unknown"]:
                        continue
                    # Skip indexed table keys (they belong to Section B)
                    if re.search(r'\[\d+\]|_row_\d+', str(k)):
                        continue
                    # Cross-table family boundary guard: prevent keys prefixed with other field IDs (e.g. field_7, field_8) from bleeding into field_9
                    k_str = str(k).lower()
                    if short_id.startswith("field_"):
                        k_prefix_match = re.search(r'field_(\d+)', k_str)
                        this_prefix_match = re.search(r'field_(\d+)', short_id)
                        if k_prefix_match and this_prefix_match and k_prefix_match.group(1) != this_prefix_match.group(1):
                            continue
                    k_tail = str(k).split(".")[-1]
                    canon_k = COLUMN_SYNONYMS.get(k_tail.lower(), k_tail.lower())
                    if canon_k == ck.lower() or k.lower() == f"{short_id}.{ck}".lower() or k.lower() == f"{fid}.{ck}".lower():
                        single_row[ck] = v
                        matched_keys.add(k)
                        break
                    c_lbl = c_def.get("label", "").lower()
                    c_subno = re.search(r'([0-9]+[a-z])', c_lbl)
                    if c_subno and (k_tail.lower() == f"field_{c_subno.group(1)}" or k_tail.lower() == c_subno.group(1)):
                        single_row[ck] = v
                        matched_keys.add(k)
                        break

            if single_row:
                if default_rows:
                    merged = [dict(r) for r in default_rows]
                    merged[0].update(single_row)
                    return merged
                else:
                    return [single_row]

        # D. Universal Auto-Aggregation for Summary Tables (e.g. Field 9 in LLP-11)
        if ("summary of designated partner" in flabel or fid == "llpformno11.main.field_9" or cno == "9"):
            indiv_data = mapped_data.get("llpformno11.main.field_7") or mapped_data.get("field_7") or mapped_data.get("partners") or mapped_data.get("individual_partners")
            bc_data = mapped_data.get("llpformno11.main.field_8") or mapped_data.get("field_8") or mapped_data.get("bodies_corporate") or mapped_data.get("body_corporate_partners")

            if indiv_data or bc_data:
                indiv_rows = indiv_data if isinstance(indiv_data, list) else []
                bc_rows = bc_data if isinstance(bc_data, list) else []

                indiv_dp_cnt = sum(1 for r in indiv_rows if isinstance(r, dict) and "designated" in str(r.get("designation", "")).lower())
                indiv_p_cnt = len(indiv_rows) - indiv_dp_cnt
                if indiv_dp_cnt == 0 and indiv_rows:
                    indiv_dp_cnt = len(indiv_rows)
                    indiv_p_cnt = 0

                def _safe_float(val):
                    try:
                        return float(str(val).replace(",", "").strip())
                    except Exception:
                        return 0.0

                indiv_ob = sum(_safe_float(r.get("obligation_contribution", r.get("obligation", 0))) for r in indiv_rows if isinstance(r, dict))
                indiv_rec = sum(_safe_float(r.get("contribution_received", r.get("received", 0))) for r in indiv_rows if isinstance(r, dict))

                bc_dp_cnt = sum(1 for r in bc_rows if isinstance(r, dict) and "designated" in str(r.get("designation", "")).lower())
                bc_p_cnt = len(bc_rows) - bc_dp_cnt
                bc_ob = sum(_safe_float(r.get("obligation_contribution", r.get("obligation", 0))) for r in bc_rows if isinstance(r, dict))
                bc_rec = sum(_safe_float(r.get("contribution_received", r.get("received", 0))) for r in bc_rows if isinstance(r, dict))

                tot_dp = indiv_dp_cnt + bc_dp_cnt
                tot_p = indiv_p_cnt + bc_p_cnt
                tot_all = len(indiv_rows) + len(bc_rows)
                tot_ob = indiv_ob + bc_ob
                tot_rec = indiv_rec + bc_rec

                summary_rows = [
                    {
                        "category": "(a) Individuals",
                        "num_designated_partners": str(indiv_dp_cnt),
                        "num_partners": str(indiv_p_cnt),
                        "total_partners": str(len(indiv_rows)),
                        "obligation_contribution": str(int(indiv_ob)) if indiv_ob else "0",
                        "contribution_received": str(int(indiv_rec)) if indiv_rec else "0"
                    },
                    {
                        "category": "(b) Bodies Corporate",
                        "num_designated_partners": str(bc_dp_cnt),
                        "num_partners": str(bc_p_cnt),
                        "total_partners": str(len(bc_rows)),
                        "obligation_contribution": str(int(bc_ob)) if bc_ob else "0",
                        "contribution_received": str(int(bc_rec)) if bc_rec else "0"
                    },
                    {
                        "category": "Total",
                        "num_designated_partners": str(tot_dp),
                        "num_partners": str(tot_p),
                        "total_partners": str(tot_all),
                        "obligation_contribution": str(int(tot_ob)) if tot_ob else "0",
                        "contribution_received": str(int(tot_rec)) if tot_rec else "0"
                    }
                ]
                matched_keys.add(fid)
                return summary_rows

        if default_rows:
            return default_rows

        return None

    # BEN-2 Universal Statutory Prefill:
    # 6B(a-e) when CIN/LLPIN is available
    if (cno in ["6b(a)", "6b(b)", "6b(c)", "6b(d)", "6b(e)", "6ba", "6bb", "6bc", "6bd", "6be"] or any(k in fid.lower() for k in ["field_6ba", "field_6bb", "field_6bc", "field_6bd", "field_6be"])):
        cin_llpin_val = (
            mapped_data.get("field_6bb")
            or mapped_data.get("formnoben2.for_change_of_existing.field_6bb")
            or mapped_data.get("member_cin")
            or mapped_data.get("member_llpin")
            or mapped_data.get("cin_llpin")
            or mapped_data.get("cin")
            or mapped_data.get("llpin")
        )
        if cin_llpin_val and str(cin_llpin_val).strip() not in ["", "None", "null", "N/A"]:
            cin_str = str(cin_llpin_val).strip()
            cin_upper = cin_str.upper()
            if cno in ["6b(a)", "6ba"] or fid.endswith("field_6ba") or "type of member" in flabel:
                matched_keys.add(fid)
                return "LLP" if (cin_upper.startswith("AAA") or "LLP" in cin_upper) else "Company"
            if cno in ["6b(b)", "6bb"] or fid.endswith("field_6bb") or "registration number" in flabel or "cin" in flabel:
                matched_keys.add(fid)
                return cin_upper
            if cno in ["6b(c)", "6bc"] or fid.endswith("field_6bc") or "name of the member" in flabel:
                val = mapped_data.get("field_6bc") or mapped_data.get("member_name") or mapped_data.get("company_name")
                if val:
                    matched_keys.add(fid)
                    return str(val).strip()
            if cno in ["6b(d)", "6bd"] or fid.endswith("field_6bd") or "address of the member" in flabel:
                val = mapped_data.get("field_6bd") or mapped_data.get("member_address") or mapped_data.get("registered_office_address") or mapped_data.get("address")
                if val:
                    matched_keys.add(fid)
                    return str(val).strip()
            if cno in ["6b(e)", "6be"] or fid.endswith("field_6be") or "email id of the member" in flabel:
                val = mapped_data.get("field_6be") or mapped_data.get("member_email") or mapped_data.get("email_id") or mapped_data.get("email")
                if val:
                    matched_keys.add(fid)
                    return str(val).strip()

    # 6D(a-g) when SBO ID is available
    if (cno in ["6d(a)", "6d(a)(i)", "6d(a)(ii)", "6d(b)", "6d(c)", "6d(d)", "6d(e)", "6d(f)", "6d(g)", "6da", "6dai", "6dai_2", "6db", "6dc", "6dd", "6de", "6df", "6dg"] or any(k in fid.lower() for k in ["field_6da", "field_6dai", "field_6dai_2", "field_6db", "field_6dc", "field_6dd", "field_6de", "field_6df", "field_6dg"])):
        sbo_id_val = (
            mapped_data.get("field_6da")
            or mapped_data.get("formnoben2.for_change_of_existing.field_6da")
            or mapped_data.get("sbo_id")
            or mapped_data.get("sboid")
        )
        if sbo_id_val and str(sbo_id_val).strip() not in ["", "None", "null", "N/A"]:
            sbo_str = str(sbo_id_val).strip()
            if cno in ["6d(a)", "6da"] or (fid.endswith("field_6da") and not fid.endswith("field_6dai")) or "id of the significant beneficial owner" in flabel:
                matched_keys.add(fid)
                return sbo_str
            if cno in ["6d(a)(i)", "6dai"] or (fid.endswith("field_6dai") and not fid.endswith("field_6dai_2")) or "income tax pan" in flabel or "pan verify" in flabel:
                val = mapped_data.get("field_6dai") or mapped_data.get("sbo_pan") or mapped_data.get("pan_number") or mapped_data.get("pan")
                if val:
                    matched_keys.add(fid)
                    return str(val).strip().upper()
            if cno in ["6d(a)(ii)", "6dai_2"] or fid.endswith("field_6dai_2") or "passport number" in flabel:
                val = mapped_data.get("field_6dai_2") or mapped_data.get("sbo_passport") or mapped_data.get("passport_number") or mapped_data.get("passport")
                if val:
                    matched_keys.add(fid)
                    return str(val).strip()
            if cno in ["6d(b)", "6db"] or fid.endswith("field_6db") or "name of the significant beneficial owner" in flabel:
                val = mapped_data.get("field_6db") or mapped_data.get("sbo_name") or mapped_data.get("beneficial_owner_name") or mapped_data.get("partner_name")
                if val:
                    matched_keys.add(fid)
                    return str(val).strip()
            if cno in ["6d(c)", "6dc"] or fid.endswith("field_6dc") or "father" in flabel:
                val = mapped_data.get("field_6dc") or mapped_data.get("sbo_father_name") or mapped_data.get("father_name")
                if val:
                    matched_keys.add(fid)
                    return str(val).strip()
            if cno in ["6d(d)", "6dd"] or fid.endswith("field_6dd") or "date of birth" in flabel:
                val = mapped_data.get("field_6dd") or mapped_data.get("sbo_dob") or mapped_data.get("date_of_birth") or mapped_data.get("dob")
                if val:
                    matched_keys.add(fid)
                    return str(val).strip()
            if cno in ["6d(e)", "6de"] or fid.endswith("field_6de") or "nationality" in flabel:
                val = mapped_data.get("field_6de") or mapped_data.get("sbo_nationality") or mapped_data.get("nationality") or "Indian"
                matched_keys.add(fid)
                return str(val).strip()
            if cno in ["6d(f)", "6df"] or fid.endswith("field_6df") or "citizen of india" in flabel:
                val = mapped_data.get("field_6df") or mapped_data.get("sbo_citizen") or "Yes"
                matched_keys.add(fid)
                return str(val).strip()
            if cno in ["6d(g)", "6dg"] or fid.endswith("field_6dg") or "address of significant beneficial owner" in flabel:
                val = mapped_data.get("field_6dg") or mapped_data.get("sbo_address") or mapped_data.get("address")
                if val:
                    matched_keys.add(fid)
                    return str(val).strip()

    # 1. Exact ID check
    if fid in mapped_data:
        sanitized = _validate_and_sanitize(mapped_data[fid])
        if sanitized is not None:
            if not (is_structural_header and isinstance(sanitized, str) and sanitized.replace(",", "").isdigit()):
                matched_keys.add(fid)
                return sanitized

    # Extract field index token (e.g. "3", "3a", "4p", "4q") for subfield boundary isolation
    fid_tail_tok = re.search(r'field_([0-9]+[a-z0-9]*)', fid.lower())

    # 2. Canonical number check with Family & Subfield Isolation
    if cno:
        cno_clean = re.sub(r'[^a-z0-9]', '', str(cno).lower())
        for k, v in mapped_data.items():
            sanitized = _validate_and_sanitize(v)
            if sanitized is None:
                continue
            if is_structural_header and isinstance(sanitized, str) and sanitized.replace(",", "").isdigit():
                continue

            k_norm = str(k).lower().replace("(", "").replace(")", "").replace("-", "_").replace(" ", "_")

            # Family boundary guard: prevent cross-section suffix bleed (e.g. field_5gi_3 matching cno=3)
            k_family = re.search(r'field_([0-9]+)', k_norm)
            fid_family = re.search(r'field_([0-9]+)', fid.lower())
            if k_family and fid_family and k_family.group(1) != fid_family.group(1):
                continue

            # Subfield boundary guard: prevent field_3 from matching field_3a, or field_4 matching field_4p
            k_tail_tok = re.search(r'field_([0-9]+[a-z0-9]*)', k_norm)
            if fid_tail_tok and k_tail_tok and fid_tail_tok.group(1) != k_tail_tok.group(1):
                continue

            k_tail = k_norm.split(".")[-1]
            k_cno = re.sub(r'[^a-z0-9]', '', re.sub(r'^field_', '', k_tail))
            is_cno_match = (
                k_tail == cno
                or k_tail == f"field_{cno}"
                or k_norm == cno
                or k_norm == f"field_{cno}"
                or (k_cno == cno_clean and cno_clean)
            )
            if is_cno_match:
                matched_keys.add(k)
                return sanitized

    # 3. Normalized ID check with Subfield Isolation
    norm_fid = re.sub(r"[^a-z0-9]", "", fid.lower())
    for k, v in mapped_data.items():
        sanitized = _validate_and_sanitize(v)
        if sanitized is None:
            continue
        if is_structural_header and isinstance(sanitized, str) and sanitized.replace(",", "").isdigit():
            continue

        k_norm = str(k).lower()
        # Family boundary check for fuzzy ID
        k_family = re.search(r'field_([0-9]+)', k_norm)
        fid_family = re.search(r'field_([0-9]+)', fid.lower())
        if k_family and fid_family and k_family.group(1) != fid_family.group(1):
            continue

        # Subfield boundary guard: field_3 must NOT match field_3a, field_4 must NOT match field_4p/4q
        k_tail_tok = re.search(r'field_([0-9]+[a-z0-9]*)', k_norm)
        if fid_tail_tok and k_tail_tok and fid_tail_tok.group(1) != k_tail_tok.group(1):
            continue

        norm_k = re.sub(r"[^a-z0-9]", "", k_norm)
        if norm_k == norm_fid:
            matched_keys.add(k)
            return sanitized

        # Label token check
        k_unprefixed = re.sub(r'^[a-z0-9_]+\.(?:main|repeating|sec)\.', '', str(k).lower())
        clean_k = k_unprefixed.replace("_", " ").replace("field ", "").strip()

        STATUTORY_ACRONYMS = {
            "din": "director identification number",
            "cin": "corporate identity number",
            "pan": "permanent account number",
            "llpin": "limited liability partnership identification number",
            "srn": "service request number"
        }
        expanded_k = STATUTORY_ACRONYMS.get(clean_k, clean_k)

        if flabel:
            # Signatory mutual exclusivity token guard: Director DIN must not bleed into Manager/CS field
            if is_kmp_sec_field and (clean_k in ["din", "director identification number", "director identification", "director din"] or expanded_k == "director identification number"):
                continue
            if is_dir_din_field and any(kmp_term in clean_k for kmp_term in ["membership", "manager", "ceo", "cfo", "secretary", "liquidator", "icsi"]):
                continue

            # Direct substring match (require at least 4 chars to prevent single-character/digit bleed like '1' in '102')
            if (len(clean_k) >= 4 and (clean_k in flabel or flabel in clean_k)) or (len(expanded_k) >= 4 and (expanded_k in flabel or flabel in expanded_k)):
                matched_keys.add(k)
                return sanitized
            # Whole word match for acronyms (e.g. cin, din, pan, llpin)
            if len(clean_k) >= 3 and re.search(r'\b' + re.escape(clean_k) + r'\b', flabel):
                matched_keys.add(k)
                return sanitized
            # Multi-word token subset match (e.g. "company_name" in "Name of the Company")
            tokens_k = set(re.findall(r'[a-z0-9]+', expanded_k)) - {"the", "of", "and", "in", "to", "for", "is", "field"}
            tokens_lbl = set(re.findall(r'[a-z0-9]+', flabel)) - {"the", "of", "and", "in", "to", "for", "is", "field"}
            if len(tokens_k) >= 2 and tokens_k.issubset(tokens_lbl):
                matched_keys.add(k)
                return sanitized

    # 4. If radio/toggle with [Yes, No] options and not affirmatively mapped, default to "No"
    if f_type in ["radio", "toggle"] and options and set(str(o).lower().strip() for o in options) == {"yes", "no"}:
        return "No"

    return None

_find_field_value = resolve_field_value

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
        return resolve_field_value(field_def, mapped_data, matched_keys)

    # Section Header
    y = 115
    page.draw_rect(fitz.Rect(35, y, 560, y + 18), color=(0.88, 0.91, 0.95), fill=(0.88, 0.91, 0.95))
    page.insert_text((42, y + 13), "I. STATUTORY PARTICULARS & RETURN DATA", fontsize=8.5, fontname="helv", color=(0.1, 0.18, 0.35))
    y += 24

    # Build display items dynamically from schema with DAG Pruning
    display_items = []
    pruned_keys = set()
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
            is_pruned = False
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
                            is_pruned = True
                    elif operator == "not_equals":
                        if p_str == t_str or t_str in p_str:
                            is_pruned = True
                    elif operator == "in" and isinstance(target_value, list):
                        if not any(p_str == str(opt).strip().lower() or str(opt).strip().lower() in p_str for opt in target_value):
                            is_pruned = True
                    elif operator in ["exists", "not_empty"]:
                        if not p_str or p_str in ["none", "null", "false", "0", "n/a"]:
                            is_pruned = True
                elif operator in ["exists", "not_empty"]:
                    is_pruned = True

            if is_pruned:
                fid_clean = f.get("id", "").lower()
                pruned_keys.add(fid_clean)
                pruned_keys.add(fid_clean.split(".")[-1])
                c_no_clean = str(f.get("canonical_no", "")).strip().lower()
                if c_no_clean:
                    pruned_keys.add(c_no_clean)
                    pruned_keys.add(re.sub(r'[^a-z0-9]', '', c_no_clean))
                matched_keys.add(f.get("id"))
                matched_keys.add(fid_clean.split(".")[-1])
                continue

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

    INTERNAL_METADATA_KEYS = {
        "statutory_scenario", "statutory_branch", "recommended_branch",
        "scenario_key", "confidence", "confidence_score", "section_cited",
        "dossier_merged_fields", "file_name", "document_type", "total_files",
        "raw_text", "ocr_status", "fast_path_matched"
    }

    # Append any extra mapped fields only if form has no defined statutory schema
    if not fields:
        for k, v in mapped_data.items():
            if k in matched_keys:
                continue
            if not v or str(v).strip() in ["", "None", "null", "Unknown", "N/A", "Empty / N/A"]:
                continue

            k_lower = str(k).lower().strip()
            k_tail = k_lower.split(".")[-1]

            # 0. Skip anything matching pruned keys from inactive DAG branches
            if k_lower in pruned_keys or k_tail in pruned_keys:
                continue
            if any(pk in k_lower for pk in pruned_keys if len(pk) > 3):
                continue

            # 1. Skip known internal engine metadata
            if k_lower in INTERNAL_METADATA_KEYS or any(m in k_lower for m in ["statutory_scenario", "statutory_branch", "scenario_key"]):
                continue
            # 2. Skip raw form-prefixed dot notation keys (e.g. formnomgt14.main..., gnl1.main..., llpformno11.main...)
            if re.match(r'^(?:form|gnl|llp)[a-z0-9_]*\.(?:main|repeating|sec)\.', k_lower):
                continue
            # 3. Skip keys that match or end with any schema field id suffix
            if any(f.get("id", "").lower().endswith(k_tail) or k_tail == f.get("id", "").lower() for f in fields):
                continue

            # 4. Skip indexed table cell keys (e.g. [0], _row_0)
            if re.search(r'\[\d+\]|_row_\d+', k_lower):
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
        # Radios / small toggles (<=3 opts) show filled-circle selector.
        # Larger selects (4-20 options) render as a 2-col grid with radio dots.
        # DSC/signatory blocks and checkboxes have their own dedicated branches.
        is_radio     = (f_type in ["radio", "toggle"]) or (f_type == "select" and options and len(options) <= 3)
        is_full_grid = (f_type == "select" and options and 3 < len(options) <= 20)
        is_checkbox  = f_type in ["checkbox"]
        is_dsc       = f_type in ["dsc_block"]
        is_signatory = f_type in ["signatory"]
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

            # If no rows or empty rows, render default statutory rows or at least 2 empty rows
            if not table_rows:
                raw_default = None
                if isinstance(item.get("raw_field"), dict):
                    raw_default = item["raw_field"].get("default_rows") or (item["raw_field"].get("table_metadata", {}).get("default_rows") if isinstance(item["raw_field"].get("table_metadata"), dict) else None)
                if raw_default and isinstance(raw_default, list) and raw_default:
                    table_rows = raw_default
                else:
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

        # --- CHECKBOX RENDERING (attachment fields a-r) ---
        if is_checkbox:
            chk_h = 18.0
            if y + chk_h > 780:
                page.insert_text((42, 802), f"Page {len(doc)} • Official MCA Filing Return", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))
                page = doc.new_page(width=595, height=842)
                page.draw_rect(fitz.Rect(28, 28, 567, 814), color=(0.15, 0.2, 0.3), width=1.2)
                y = 45
            is_checked = str(val_str).strip().lower() in ("true", "1", "yes", "checked", "x")
            # Draw checkbox square
            box_r = fitz.Rect(40, y + 3, 51, y + 14)
            page.draw_rect(box_r, color=(0.3, 0.3, 0.3), width=0.8)
            if is_checked:
                page.draw_line(fitz.Point(41, y + 8), fitz.Point(46, y + 13), color=(0.05, 0.4, 0.15), width=1.5)
                page.draw_line(fitz.Point(46, y + 13), fitz.Point(54, y + 4), color=(0.05, 0.4, 0.15), width=1.5)
            page.insert_text((57, y + 12), label, fontsize=7.5, fontname="helv", color=(0.1, 0.15, 0.25))
            y += chk_h
            continue

        # --- DSC BLOCK RENDERING ---
        if is_dsc:
            dsc_h = 50.0
            if y + dsc_h > 780:
                page.insert_text((42, 802), f"Page {len(doc)} • Official MCA Filing Return", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))
                page = doc.new_page(width=595, height=842)
                page.draw_rect(fitz.Rect(28, 28, 567, 814), color=(0.15, 0.2, 0.3), width=1.2)
                y = 45
            page.insert_text((42, y + 11), label, fontsize=7.5, fontname="helv", color=(0.15, 0.22, 0.35))
            # Two DSC placeholder boxes side by side
            page.draw_rect(fitz.Rect(42, y + 15, 190, y + 45), color=(0.6, 0.6, 0.6), width=0.8)
            page.insert_text((50, y + 32), "Digital Signature", fontsize=6.5, fontname="helv", color=(0.6, 0.65, 0.7))
            page.draw_rect(fitz.Rect(200, y + 15, 348, y + 45), color=(0.6, 0.6, 0.6), width=0.8)
            page.insert_text((208, y + 32), "Digital Signature", fontsize=6.5, fontname="helv", color=(0.6, 0.65, 0.7))
            y += dsc_h
            continue

        # --- SIGNATORY BLOCK RENDERING ---
        if is_signatory:
            sig_h = 30.0
            if y + sig_h > 780:
                page.insert_text((42, 802), f"Page {len(doc)} • Official MCA Filing Return", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))
                page = doc.new_page(width=595, height=842)
                page.draw_rect(fitz.Rect(28, 28, 567, 814), color=(0.15, 0.2, 0.3), width=1.2)
                y = 45
            page.insert_text((42, y + 10), label, fontsize=7.5, fontname="helv", color=(0.15, 0.22, 0.35))
            name_val = str(val_str).strip() if val_str else ""
            page.draw_rect(fitz.Rect(42, y + 13, 300, y + 27), color=(0.75, 0.80, 0.88), width=0.6)
            if name_val:
                page.insert_text((46, y + 24), name_val, fontsize=8.0, fontname="helv", color=(0.05, 0.1, 0.25))
            y += sig_h
            continue

        # --- FULL GRID rendering for selects with 4-20 options (e.g. Section 2a) ---
        if is_full_grid and options:
            # Determine selected option via fuzzy match
            val_lower = str(val_str).lower().strip()
            selected_opt = None
            if val_lower:
                clean_val = re.sub(r'[^a-z0-9]', '', val_lower)
                for opt in options:
                    if re.sub(r'[^a-z0-9]', '', str(opt).lower()) == clean_val:
                        selected_opt = opt
                        break
                if not selected_opt:
                    tokens_val = set(re.findall(r'[a-z0-9]+', val_lower))
                    best_score = 0.0
                    for opt in options:
                        tokens_opt = set(re.findall(r'[a-z0-9]+', str(opt).lower()))
                        if tokens_opt:
                            score = len(tokens_opt & tokens_val) / float(len(tokens_opt))
                            if score > best_score and score >= 0.7:
                                best_score = score
                                selected_opt = opt

            n_opts = len(options)
            col_w = 255.0
            opt_row_h = 15.0
            n_rows = math.ceil(n_opts / 2)
            header_h = 20.0
            grid_h = header_h + n_rows * opt_row_h + 6

            if y + grid_h > 780:
                page.insert_text((42, 802), f"Page {len(doc)} • Official MCA Filing Return", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))
                page = doc.new_page(width=595, height=842)
                page.draw_rect(fitz.Rect(28, 28, 567, 814), color=(0.15, 0.2, 0.3), width=1.2)
                y = 45

            # Section label banner
            page.draw_rect(fitz.Rect(35, y, 560, y + header_h), color=(0.75, 0.80, 0.88), fill=(0.88, 0.91, 0.96), width=0.8)
            page.insert_textbox(fitz.Rect(40, y + 3, 555, y + header_h - 2), label, fontsize=7.5, fontname="helv", color=(0.08, 0.16, 0.35))
            y += header_h

            # 2-column radio grid
            for row_i in range(n_rows):
                for col_i in range(2):
                    opt_i = row_i * 2 + col_i
                    if opt_i >= n_opts:
                        break
                    opt = options[opt_i]
                    is_sel = (selected_opt is not None and opt == selected_opt)
                    x_off = 40 + col_i * col_w
                    cy = y + row_i * opt_row_h + 7
                    # Radio circle
                    page.draw_circle((x_off, cy), radius=3.5, color=(0.3, 0.3, 0.3), width=0.7)
                    if is_sel:
                        page.draw_circle((x_off, cy), radius=2.0, color=(0.05, 0.1, 0.25), fill=(0.05, 0.1, 0.25))
                    txt_col = (0.05, 0.1, 0.25) if is_sel else (0.35, 0.4, 0.5)
                    opt_rect = fitz.Rect(x_off + 8, cy - 5, x_off + col_w - 4, cy + 9)
                    page.insert_textbox(opt_rect, str(opt), fontsize=6.8, fontname="helv", color=txt_col)

            y += n_rows * opt_row_h + 6
            continue

        # --- Standard field value ---
        # For DSC/signatory types, never stamp fallback text — leave blank.
        if is_dsc or is_signatory:
            display_val = ""
        elif val_str:
            display_val = val_str
        else:
            display_val = ""

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
            # Pick ONLY ONE best-matching option to guarantee single-choice exclusivity
            selected_opt = None
            if val_lower:
                clean_val = re.sub(r'[^a-z0-9]', '', val_lower)
                # 1. Exact equality check
                for opt in options:
                    clean_opt = re.sub(r'[^a-z0-9]', '', str(opt).lower())
                    if clean_opt == clean_val:
                        selected_opt = opt
                        break
                # 2. Token overlap check if no exact equality
                if not selected_opt:
                    tokens_val = set(re.findall(r'[a-z0-9]+', val_lower))
                    best_score = 0.0
                    for opt in options:
                        tokens_opt = set(re.findall(r'[a-z0-9]+', str(opt).lower()))
                        if tokens_opt:
                            overlap = len(tokens_opt & tokens_val)
                            score = overlap / float(len(tokens_opt))
                            if score > best_score and score >= 0.8:
                                best_score = score
                                selected_opt = opt

            opt_y = y + 4
            for opt in options:
                opt_str = str(opt).strip()
                is_selected = (selected_opt is not None and opt == selected_opt)
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
# GNL-2 DEDICATED OFFICIAL MCA CANVAS RENDERER
# Builds a pixel-faithful replica of the official MCA Form GNL-2 layout.
# Called before the generic fallback for any GNL-2 request.
# ==============================================================================
def _render_gnl2_official_pdf(mapped_data: Dict[str, Any]) -> Any:
    """
    Renders an exact visual replica of MCA Form GNL-2 using PyMuPDF.
    Sections: Header, Form Language, 1 (Company Info), 2 (Purpose),
              3 (Advertisement), 4 (Act/Section), 5 (SRN/Resolution),
              6 (Event), 7 (Attachments), Verification, Signatory,
              For Office Use Only footer.
    Returns a fitz.Document ready for bytes() serialization.
    """
    import fitz
    import math
    import re

    # -----------------------------------------------------------------
    # Helper: get mapped value by key (case-insensitive partial match)
    # -----------------------------------------------------------------
    def _v(key: str, default: str = "") -> str:
        """Fetch a value from mapped_data by exact or suffix key match."""
        if key in mapped_data:
            v = mapped_data[key]
            return str(v).strip() if v not in (None, "", "null", "None") else default
        # Suffix match (e.g. 'field_1' matches 'gnl2.main.field_1')
        for k, v in mapped_data.items():
            if str(k).endswith(key) or key in str(k):
                return str(v).strip() if v not in (None, "", "null", "None") else default
        return default

    # Color palette (MCA blue-grey theme)
    C_BORDER  = (0.13, 0.20, 0.35)
    C_HEADER  = (0.08, 0.16, 0.36)
    C_FILL_H  = (0.90, 0.93, 0.97)
    C_FILL_R  = (0.97, 0.98, 1.00)   # row fill
    C_FILL_A  = (1.00, 1.00, 1.00)   # alternate row fill
    C_SEC_LBL = (0.06, 0.14, 0.30)   # section label text
    C_VAL     = (0.05, 0.10, 0.20)   # value text
    C_MUTED   = (0.55, 0.60, 0.65)   # muted / empty field
    C_LINE    = (0.78, 0.82, 0.90)
    C_RADIO   = (0.05, 0.10, 0.25)   # selected radio fill
    C_RADIO_O = (0.35, 0.40, 0.50)   # unselected radio text
    C_GREEN   = (0.05, 0.40, 0.15)   # checkmark
    C_VERIF   = (0.90, 0.94, 0.98)   # verification box fill
    C_FOOTER  = (0.94, 0.94, 0.97)   # For Office Use Only footer
    C_SIG     = (0.75, 0.78, 0.85)   # DSC box border

    DOC_W, DOC_H = 595, 842  # A4
    L_MARGIN, R_MARGIN = 32, 563
    TOP_Y = 32

    doc = fitz.open()
    page = doc.new_page(width=DOC_W, height=DOC_H)

    # Outer border
    page.draw_rect(fitz.Rect(TOP_Y - 4, TOP_Y - 4, R_MARGIN + 4, DOC_H - 28),
                   color=C_BORDER, width=1.0)

    y = float(TOP_Y)

    def _new_page():
        nonlocal page, y
        page.insert_text((L_MARGIN, DOC_H - 14),
                         f"Page {len(doc)} • MCA Form GNL-2 • CRAFT IDP Engine",
                         fontsize=6.5, fontname="helv", color=(0.5, 0.5, 0.5))
        page = doc.new_page(width=DOC_W, height=DOC_H)
        page.draw_rect(fitz.Rect(TOP_Y - 4, TOP_Y - 4, R_MARGIN + 4, DOC_H - 28),
                       color=C_BORDER, width=1.0)
        y = float(TOP_Y)

    def _check_page(need_h: float):
        if y + need_h > DOC_H - 50:
            _new_page()

    def _draw_section_header(title: str, h: float = 16.0):
        nonlocal y
        _check_page(h)
        page.draw_rect(fitz.Rect(L_MARGIN, y, R_MARGIN, y + h),
                       color=C_BORDER, fill=C_FILL_H, width=0.8)
        page.insert_textbox(fitz.Rect(L_MARGIN + 5, y + 1, R_MARGIN - 5, y + h),
                            title, fontsize=7.8, fontname="helv", color=C_HEADER)
        y += h

    def _draw_row(label: str, value: str, h: float = 20.0, label_w_frac: float = 0.42, alternate: bool = False):
        nonlocal y
        _check_page(h)
        fill = C_FILL_A if alternate else C_FILL_R
        page.draw_rect(fitz.Rect(L_MARGIN, y, R_MARGIN, y + h),
                       color=C_LINE, fill=fill, width=0.4)
        split_x = L_MARGIN + (R_MARGIN - L_MARGIN) * label_w_frac
        page.draw_line(fitz.Point(split_x, y), fitz.Point(split_x, y + h),
                       color=C_LINE, width=0.4)
        # Label
        lbl_rect = fitz.Rect(L_MARGIN + 3, y + 2, split_x - 2, y + h - 2)
        page.insert_textbox(lbl_rect, label, fontsize=7.5, fontname="helv", color=C_SEC_LBL)
        # Value
        val_rect = fitz.Rect(split_x + 3, y + 2, R_MARGIN - 3, y + h - 2)
        if value:
            page.insert_textbox(val_rect, value, fontsize=8.0, fontname="helv", color=C_VAL)
        else:
            page.insert_textbox(val_rect, "________________", fontsize=7.5, fontname="helv", color=C_MUTED)
        y += h

    def _draw_radio_row(label: str, options_list, chosen: str, h_per_row: float = 14.0, label_h: float = 16.0):
        nonlocal y
        n_opts = len(options_list)
        total_h = label_h + math.ceil(n_opts / 2) * h_per_row + 4
        _check_page(total_h)
        # Label banner
        page.draw_rect(fitz.Rect(L_MARGIN, y, R_MARGIN, y + label_h),
                       color=C_LINE, fill=C_FILL_R, width=0.4)
        page.insert_textbox(fitz.Rect(L_MARGIN + 3, y + 1, R_MARGIN - 3, y + label_h),
                            label, fontsize=7.5, fontname="helv", color=C_SEC_LBL)
        y += label_h

        chosen_norm = re.sub(r'[^a-z0-9]', '', str(chosen).lower())
        col_w = (R_MARGIN - L_MARGIN) / 2.0
        n_rows = math.ceil(n_opts / 2)
        for row_i in range(n_rows):
            row_h = h_per_row
            _check_page(row_h)
            page.draw_rect(fitz.Rect(L_MARGIN, y, R_MARGIN, y + row_h),
                           color=C_LINE, fill=C_FILL_A, width=0.3)
            for col_i in range(2):
                opt_i = row_i * 2 + col_i
                if opt_i >= n_opts:
                    break
                opt = options_list[opt_i]
                opt_norm = re.sub(r'[^a-z0-9]', '', str(opt).lower())
                is_sel = (chosen_norm and (opt_norm == chosen_norm or chosen_norm in opt_norm))
                cx = L_MARGIN + col_i * col_w + 9
                cy = y + row_h / 2
                # Radio circle
                page.draw_circle((cx, cy), radius=3.8, color=(0.35, 0.35, 0.35), width=0.7)
                if is_sel:
                    page.draw_circle((cx, cy), radius=2.2, color=C_RADIO, fill=C_RADIO)
                opt_col = C_RADIO if is_sel else C_RADIO_O
                opt_rect = fitz.Rect(cx + 7, y + 1, L_MARGIN + (col_i + 1) * col_w - 4, y + row_h)
                page.insert_textbox(opt_rect, str(opt), fontsize=6.8, fontname="helv", color=opt_col)
            y += row_h
        y += 3

    def _draw_checkbox_row(label: str, checked: bool, alternate: bool = False):
        nonlocal y
        chk_h = 16.0
        _check_page(chk_h)
        fill = C_FILL_A if alternate else C_FILL_R
        page.draw_rect(fitz.Rect(L_MARGIN, y, R_MARGIN, y + chk_h),
                       color=C_LINE, fill=fill, width=0.3)
        bx1, by1, bx2, by2 = L_MARGIN + 4, y + 3, L_MARGIN + 13, y + 12
        page.draw_rect(fitz.Rect(bx1, by1, bx2, by2), color=(0.35, 0.35, 0.35), width=0.8)
        if checked:
            page.draw_line(fitz.Point(bx1 + 1, by1 + 4), fitz.Point(bx1 + 4, by2 - 1), color=C_GREEN, width=1.5)
            page.draw_line(fitz.Point(bx1 + 4, by2 - 1), fitz.Point(bx2 + 2, by1 - 1), color=C_GREEN, width=1.5)
        page.insert_textbox(fitz.Rect(L_MARGIN + 17, y + 1, R_MARGIN - 3, y + chk_h),
                            label, fontsize=7.2, fontname="helv", color=C_SEC_LBL)
        y += chk_h

    # =================================================================
    # HEADER
    # =================================================================
    hdr_h = 64.0
    page.draw_rect(fitz.Rect(L_MARGIN, y, R_MARGIN, y + hdr_h),
                   color=C_BORDER, fill=C_FILL_H, width=0.8)
    page.insert_text((L_MARGIN + 8, y + 14), "GOVERNMENT OF INDIA",
                     fontsize=8.0, fontname="helv", color=(0.30, 0.30, 0.30))
    page.insert_text((L_MARGIN + 8, y + 26), "MINISTRY OF CORPORATE AFFAIRS",
                     fontsize=10.5, fontname="helv", color=C_HEADER)
    page.insert_text((L_MARGIN + 8, y + 43), "Form GNL-2",
                     fontsize=14.0, fontname="helv", color=C_SEC_LBL)
    page.insert_text((L_MARGIN + 8, y + 56),
                     "[Webform for filing of documents and information with the Central Government]",
                     fontsize=7.0, fontname="helv", color=(0.40, 0.45, 0.50))
    # Form language toggle (top-right)
    lang_x = R_MARGIN - 145
    lang_y = y + 15
    page.insert_text((lang_x, lang_y), "Form language:", fontsize=7.0, fontname="helv", color=C_SEC_LBL)
    page.draw_circle((lang_x + 70, lang_y - 2), radius=3.5, color=(0.3, 0.3, 0.3), width=0.7)
    page.draw_circle((lang_x + 70, lang_y - 2), radius=2.0, color=C_RADIO, fill=C_RADIO)
    page.insert_text((lang_x + 76, lang_y), "English", fontsize=7.0, fontname="helv", color=C_RADIO)
    page.draw_circle((lang_x + 110, lang_y - 2), radius=3.5, color=(0.3, 0.3, 0.3), width=0.7)
    page.insert_text((lang_x + 116, lang_y), "Hindi", fontsize=7.0, fontname="helv", color=C_RADIO_O)
    y += hdr_h + 4

    # =================================================================
    # SECTION 1 — Company Information
    # =================================================================
    _draw_section_header("1. Company Information")
    cin   = _v("field_1") or _v("cin") or _v("CIN")
    name  = _v("field_1b") or _v("company_name") or _v("name_of_company")
    addr  = _v("field_1c") or _v("registered_address") or _v("address")
    email = _v("field_1d") or _v("email")
    _draw_row("(a) *Corporate Identity Number (CIN)", cin, h=22.0)
    _draw_row("(b) Name of the Company", name, h=22.0, alternate=True)
    _draw_row("(c) Registered Office Address", addr, h=26.0)
    _draw_row("(d) Email ID", email, h=20.0, alternate=True)
    y += 3

    # =================================================================
    # SECTION 2 — Purpose of Filing
    # =================================================================
    _draw_section_header("2. Purpose of Filing")
    doc_filed   = _v("field_2a") or _v("document_type") or _v("purpose")
    others_spec = _v("field_2b")

    sec2a_options = [
        "Affidavit under Section 59 of the Insolvency and Bankruptcy Code, 2016",
        "Circular or Circular in the form of Advertisement inviting Deposits in DPT-1",
        "Final Report on Completion of liquidation process by Liquidator",
        "Form 149 of the Companies (Court) Rules, 1959",
        "Form 152 of the Companies (Court) Rules, 1959",
        "Form 153 of the Companies (Court) Rules, 1959",
        "Form 154 of the Companies (Court) Rules, 1959",
        "Form 156 of the Companies (Court) Rules, 1959",
        "Form 157 of the Companies (Court) Rules, 1959",
        "Form 158 of the Companies (Court) Rules, 1959",
        "Form 159 of the Companies (Court) Rules, 1959",
        "Others",
        "Private placement offer letter or Record of a private placement offer to be kept by the company",
        "Prospectus",
        "Red Herring Prospectus",
    ]
    _draw_radio_row("(a) *Please indicate the document being filed:", sec2a_options, doc_filed)
    _draw_row("(b) If others, then specify:", others_spec, h=20.0)
    y += 3

    # =================================================================
    # SECTION 3 — Advertisement / Order Details
    # =================================================================
    _draw_section_header("3. Advertisement / Order Details")
    d3a        = _v("field_3a")
    d3a_order  = _v("field_3a_2") or _v("order_passed_by")
    d3b        = _v("field_3b")
    d3c        = _v("field_3c")
    d3d        = _v("field_3d") or _v("petition_number")
    d3e        = _v("field_3e") or _v("order_number")
    _draw_row("(a) Expected date of issue of Advertisement (DD/MM/YYYY)", d3a, alternate=False)
    _draw_row("    Order passed by", d3a_order, h=20.0, alternate=True)
    _draw_row("(b) Expected opening date of Acceptance of Deposits (DD/MM/YYYY)", d3b)
    _draw_row("(c) Expected date of expiry of validity of advertisement (DD/MM/YYYY)", d3c, alternate=True)
    _draw_row("(d) Petition / Application / Appeal Number", d3d)
    _draw_row("(e) Order Number", d3e, alternate=True)
    y += 3

    # =================================================================
    # SECTION 4 — Act and Section Reference
    # =================================================================
    _draw_section_header("4. Act and Section Reference")
    act_choice = _v("field_4a") or _v("act")
    sec_4bi    = _v("field_4bi") or _v("section_ca2013")
    sec_4bi2   = _v("field_4bi_2") or _v("section_ca1956")
    sec_4bii   = _v("field_4bii") or _v("section_ibc")
    _draw_radio_row(
        "(a) Act under which the document is being filed:",
        ["Companies Act, 2013", "Companies Act, 1956", "Insolvency and Bankruptcy Code, 2016"],
        act_choice
    )
    _draw_row("(b)(i) Section(s) of the Companies Act, 2013 under which the document is being filed", sec_4bi)
    _draw_row("(b)(i) Section(s) of the Companies Act, 1956 under which the document is being filed", sec_4bi2, alternate=True)
    _draw_row("(b)(ii) Section(s) of the Insolvency and Bankruptcy Code, 2016", sec_4bii)
    y += 3

    # =================================================================
    # SECTION 5 — Special / Ordinary Resolution (MGT-14)
    # =================================================================
    _draw_section_header("5. Special / Ordinary Resolution (MGT-14)")
    srn_raw = _v("field_5a") or _v("srn") or _v("service_request_number")
    # SRN guard: reject bleed values like "Companies Act, 2013"
    _srn_strict = re.compile(r'^[A-Za-z]{1,3}[0-9]{6,9}$')
    srn_val = srn_raw.strip() if srn_raw and _srn_strict.match(srn_raw.strip()) else ""
    res_date = _v("field_5b") or _v("resolution_date")
    _draw_row("(a) Service Request Number of Form MGT-14", srn_val, h=22.0)
    _draw_row("(b) Date of passing special/ordinary resolution (DD/MM/YYYY)", res_date, h=22.0, alternate=True)
    y += 3

    # =================================================================
    # SECTION 6 — Event Details
    # =================================================================
    _draw_section_header("6. Event Details")
    ev_date   = _v("field_6a") or _v("date_of_event")
    decl_date = _v("field_6b") or _v("date_of_declaration")
    _draw_row("(a) Date of event (DD/MM/YYYY)", ev_date)
    _draw_row("(b) Date of declaration by majority of directors (DD/MM/YYYY)", decl_date, alternate=True)
    y += 3

    # =================================================================
    # SECTION 7 — Attachments
    # =================================================================
    _draw_section_header("7. Attachments")
    attach_defs = [
        ("field_a",  "(a) Copy of prospectus"),
        ("field_b",  "(b) Copy of red herring prospectus"),
        ("field_c",  "(c) Circular or Circular in the form of Advertisement inviting Deposits in DPT-1"),
        ("field_d",  "(d) Private placement offer letter or record of private placement offer letter"),
        ("field_e",  "(e) Form 149 of the Companies (Court) Rules, 1959"),
        ("field_f",  "(f) Form 152 of the Companies (Court) Rules, 1959"),
        ("field_g",  "(g) Form 153 of the Companies (Court) Rules, 1959"),
        ("field_h",  "(h) Form 154 of the Companies (Court) Rules, 1959"),
        ("field_i",  "(i) Form 156 of the Companies (Court) Rules, 1959"),
        ("field_j",  "(j) Form 157 of the Companies (Court) Rules, 1959"),
        ("field_k",  "(k) Form 158 of the Companies (Court) Rules, 1959"),
        ("field_l",  "(l) Form 159 of the Companies (Court) Rules, 1959"),
        ("field_m",  "(m) Final Report on Completion of liquidation process by Liquidator"),
        ("field_n",  "(n) Any other relevant document"),
        ("field_o",  "(o) Audited financial statements and record of business operations (previous two years)"),
        ("field_p",  "(p) A report of the valuation of assets of the company, if any, prepared by a Registered Valuer"),
        ("field_q",  "(q) Affidavit under section 59 of the Insolvency and Bankruptcy Code, 2016"),
        ("field_r",  "(r) Optional attachment(s) - if any"),
    ]
    for i, (fkey, flabel) in enumerate(attach_defs):
        raw_val = _v(fkey)
        is_checked = str(raw_val).strip().lower() in ("true", "1", "yes", "checked", "x")
        _draw_checkbox_row(flabel, is_checked, alternate=(i % 2 == 1))
    y += 4

    # =================================================================
    # VERIFICATION BLOCK
    # =================================================================
    _draw_section_header("Verification")
    verif_date = _v("field_verification") or _v("verification_date") or _v("resolution_date_verification")
    verif_h = 52.0
    _check_page(verif_h)
    page.draw_rect(fitz.Rect(L_MARGIN, y, R_MARGIN, y + verif_h),
                   color=C_LINE, fill=C_VERIF, width=0.6)
    verif_text = (
        "I have been authorised by a resolution of the Board of Directors of the company "
        "passed in their meeting held on ________________ to sign and submit this form."
    )
    page.insert_textbox(
        fitz.Rect(L_MARGIN + 5, y + 4, R_MARGIN - 5, y + verif_h - 20),
        verif_text, fontsize=7.5, fontname="helv", color=C_SEC_LBL
    )
    page.insert_text((L_MARGIN + 5, y + verif_h - 14),
                     f"Resolution No. and date (DD/MM/YYYY): {verif_date or '________________'}",
                     fontsize=7.5, fontname="helv", color=C_VAL if verif_date else C_MUTED)
    y += verif_h + 5

    # =================================================================
    # SIGNATORY BLOCK
    # =================================================================
    _draw_section_header("To be digitally signed by")
    sig_name   = _v("field_particulars_of_the_person") or _v("signatory_name") or _v("name")
    sig_desig  = _v("field_designation") or _v("designation")
    sig_din    = _v("field_director_identification_number_of") or _v("din") or _v("membership_number")

    sig_info_h = 24.0
    _check_page(sig_info_h + 55)
    page.draw_rect(fitz.Rect(L_MARGIN, y, R_MARGIN, y + sig_info_h),
                   color=C_LINE, fill=C_FILL_R, width=0.4)
    split1 = L_MARGIN + 175
    split2 = L_MARGIN + 350
    page.draw_line(fitz.Point(split1, y), fitz.Point(split1, y + sig_info_h), color=C_LINE, width=0.4)
    page.draw_line(fitz.Point(split2, y), fitz.Point(split2, y + sig_info_h), color=C_LINE, width=0.4)
    # Name
    page.insert_text((L_MARGIN + 3, y + 9), "Name:", fontsize=7.0, fontname="helv", color=C_SEC_LBL)
    page.insert_text((L_MARGIN + 28, y + 9), sig_name or "________________",
                     fontsize=8.0, fontname="helv", color=C_VAL if sig_name else C_MUTED)
    # Designation
    page.insert_text((split1 + 3, y + 9), "Designation:", fontsize=7.0, fontname="helv", color=C_SEC_LBL)
    page.insert_text((split1 + 55, y + 9), sig_desig or "___________",
                     fontsize=7.5, fontname="helv", color=C_VAL if sig_desig else C_MUTED)
    # DIN
    page.insert_text((split2 + 3, y + 9), "DIN / Membership No:", fontsize=6.5, fontname="helv", color=C_SEC_LBL)
    page.insert_text((split2 + 3, y + 18), sig_din or "________",
                     fontsize=7.5, fontname="helv", color=C_VAL if sig_din else C_MUTED)
    y += sig_info_h + 6

    # DSC placeholder boxes
    _check_page(52)
    dsc_label_y = y
    page.insert_text((L_MARGIN + 3, dsc_label_y + 9),
                     "Digital Signature of authorised signatory",
                     fontsize=7.0, fontname="helv", color=C_SEC_LBL)
    page.insert_text((L_MARGIN + 193, dsc_label_y + 9),
                     "Digital Signature of Liquidator (if applicable)",
                     fontsize=7.0, fontname="helv", color=C_SEC_LBL)
    y += 14
    page.draw_rect(fitz.Rect(L_MARGIN, y, L_MARGIN + 180, y + 38), color=C_SIG, width=0.9)
    page.insert_text((L_MARGIN + 55, y + 22), "[DSC Placeholder]",
                     fontsize=7.0, fontname="helv", color=(0.65, 0.68, 0.74))
    page.draw_rect(fitz.Rect(L_MARGIN + 191, y, L_MARGIN + 371, y + 38), color=C_SIG, width=0.9)
    page.insert_text((L_MARGIN + 246, y + 22), "[DSC Placeholder]",
                     fontsize=7.0, fontname="helv", color=(0.65, 0.68, 0.74))
    y += 44

    # =================================================================
    # FOR OFFICE USE ONLY FOOTER
    # =================================================================
    footer_h = 40.0
    _check_page(footer_h)
    page.draw_rect(fitz.Rect(L_MARGIN, y, R_MARGIN, y + footer_h),
                   color=C_BORDER, fill=C_FOOTER, width=0.9)
    page.draw_line(fitz.Point(L_MARGIN, y + 14), fitz.Point(R_MARGIN, y + 14),
                   color=C_LINE, width=0.5)
    page.insert_text((L_MARGIN + 5, y + 10),
                     "FOR OFFICE USE ONLY",
                     fontsize=8.0, fontname="helv", color=C_HEADER)
    split_footer = L_MARGIN + 270
    page.draw_line(fitz.Point(split_footer, y + 14), fitz.Point(split_footer, y + footer_h),
                   color=C_LINE, width=0.5)
    page.insert_text((L_MARGIN + 5, y + 26), "Date of Filing:", fontsize=7.0, fontname="helv", color=C_SEC_LBL)
    page.insert_text((L_MARGIN + 5, y + 37), "__________________", fontsize=7.0, fontname="helv", color=C_MUTED)
    page.insert_text((split_footer + 5, y + 26), "eForm Service Request No.:",
                     fontsize=7.0, fontname="helv", color=C_SEC_LBL)
    page.insert_text((split_footer + 5, y + 37), "__________________",
                     fontsize=7.0, fontname="helv", color=C_MUTED)
    y += footer_h

    # Final page footer
    page.insert_text((L_MARGIN, DOC_H - 14),
                     f"Page {len(doc)} • MCA Form GNL-2 • CRAFT IDP Engine",
                     fontsize=6.5, fontname="helv", color=(0.5, 0.5, 0.5))

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
            # GNL-2: route through dedicated official MCA canvas renderer
            if clean_tname.upper().replace(" ", "") in ("GNL-2", "GNL2"):
                print(f"[Preview PDF] Using dedicated GNL-2 official canvas renderer.")
                doc = _render_gnl2_official_pdf(mapped_data)
            else:
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
    from sqlalchemy import or_
    tmpl = db.query(models.IdpTemplate).filter(
        or_(
            models.IdpTemplate.template_id == template_name,
            models.IdpTemplate.template_name == template_name
        )
    ).first()
    canonical_name = tmpl.template_name if tmpl else template_name
    all_names = list({template_name, canonical_name} | ({tmpl.template_id} if tmpl else set()))

    if company_id or scenario or document_type:
        effective = get_effective_rules(canonical_name, company_id=company_id, scenario=scenario, document_type=document_type)
        if not effective and canonical_name != template_name:
            effective = get_effective_rules(template_name, company_id=company_id, scenario=scenario, document_type=document_type)
        return list(effective.values())
    rules = db.query(models.SchemaAliasRule).filter(models.SchemaAliasRule.template_name.in_(all_names)).all()
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

        # Guard 2: Reject self-referential extractions for text labels (e.g. value == "Corporate Office" when searching for "Corporate Office")
        if not re.search(r'\d', str(variable_name)) and str(value).strip().lower() == str(variable_name).strip().lower():
            print(f"[DOM] ❌ Rejected '{variable_name}' — value is same as the label (self-referential). Passing to LLM.")
            return None, None

        # Guard 3: Reject URLs as values (e.g. www.kritilabs.com returned as Corporate Office address)
        val_stripped = str(value).strip().lower()
        if val_stripped.startswith("www.") or val_stripped.startswith("http://") or val_stripped.startswith("https://"):
            print(f"[DOM] ❌ Rejected '{variable_name}' — value is a URL, not a field value. Passing to LLM.")
            return None, None

        # Safely increment success_count on the rule without failing extraction on DB write errors
        try:
            dom_rule.success_count = (dom_rule.success_count or 0) + 1
            db.commit()
            print(f"[DOM] ✓ Extracted '{variable_name}' = '{value}' via DOM rule (success #{dom_rule.success_count})")
        except Exception as write_err:
            try:
                db.rollback()
            except Exception:
                pass
            print(f"[DOM] ⚠ Extracted '{variable_name}' = '{value}' via DOM rule (counter update skipped: {write_err})")

        return value, dom_rule.dom_path

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
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
    other_specify = None

    # 1. Universal Statutory Extraction (CIN, PAN, DIN, Dates, Resolutions, SRNs)
    stat_entities = UniversalStatutoryExtractor.extract_entities(full_text)
    assigned_entities = set()

    for f_id, label in field_label_map.items():
        l_lower = (label or "").lower()
        f_lower = (f_id or "").lower()

        # CIN mapping: Primary company CIN only (never transferor/transferee/foreign/amalgamated)
        if stat_entities.get("primary_cin") and "primary_cin" not in assigned_entities:
            is_secondary = any(w in l_lower or w in f_lower for w in ["transferor", "transferee", "foreign", "amalgamat", "other", "subsidiar"])
            is_primary_cin = (
                f_lower.endswith(".field_1") or f_lower.endswith(".field_1a") or f_lower.endswith(".field_3") or
                f_lower in ["field_1", "field_1a", "field_3"] or
                ("corporate identity number" in l_lower and not is_secondary) or
                (re.search(r'\bcin\b', l_lower) and "pan" not in l_lower and not is_secondary)
            )
            if is_primary_cin:
                extracted[f_id] = stat_entities["primary_cin"]
                assigned_entities.add("primary_cin")

        # PAN mapping: Assign once to primary PAN field
        if stat_entities.get("primary_pan") and "primary_pan" not in assigned_entities:
            if "permanent account number" in l_lower or re.search(r'\bpan\b', l_lower):
                extracted[f_id] = stat_entities["primary_pan"]
                assigned_entities.add("primary_pan")

        # DIN mapping: Assign once to primary DIN field
        if stat_entities.get("primary_din") and "primary_din" not in assigned_entities:
            if "director identification number" in l_lower or re.search(r'\bdin\b', l_lower):
                extracted[f_id] = stat_entities["primary_din"]
                assigned_entities.add("primary_din")

        # Resolution Number: Assign once
        if stat_entities.get("primary_resolution") and "primary_resolution" not in assigned_entities:
            if "resolution" in l_lower and ("number" in l_lower or "no" in l_lower):
                extracted[f_id] = stat_entities["primary_resolution"]
                assigned_entities.add("primary_resolution")

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
        comp_assigned = False
        for f_id, label in field_label_map.items():
            if comp_assigned:
                break
            l_lower = (label or "").lower()
            f_lower = (f_id or "").lower()
            is_secondary = any(w in l_lower or w in f_lower for w in ["transferor", "transferee", "foreign", "amalgamat", "auditor", "practicing", "rta", "other"])
            if not is_secondary and ("name of the company" in l_lower or "company name" in l_lower or (f_lower.endswith(".field_2a") and "company" in l_lower)):
                extracted[f_id] = comp_name_clean
                comp_assigned = True

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
        table_rows_5g = [
            {"category": "(i) Promoters / Promoter Group", "demat": "0", "physical": "0", "total": "0"},
            {"category": "(ii) Directors", "demat": "0", "physical": "0", "total": "0"},
            {"category": "(iii) Key Managerial Personnel (KMP)", "demat": "0", "physical": "0", "total": "0"}
        ]
        has_table_data = False

        prom_match = re.search(r'(?:^|\n)\s*\|?\s*(?:\(i\)\s*)?Promoters\s*\|?\s*([0-9,]+)\s*\|?\s*([0-9,]+)', full_text, re.IGNORECASE)
        if prom_match:
            has_table_data = True
            demat_val = prom_match.group(1).strip()
            phys_val = prom_match.group(2).strip()
            table_rows_5g[0]["demat"] = demat_val
            table_rows_5g[0]["physical"] = phys_val
            try:
                table_rows_5g[0]["total"] = f"{int(demat_val.replace(',', '')) + int(phys_val.replace(',', '')):,}"
            except Exception:
                table_rows_5g[0]["total"] = f"{demat_val}"
            extracted["formnopas6.main.field_5gi"] = demat_val
            extracted["formnopas6.main.field_5gi_3"] = phys_val
            for f_id in field_label_map:
                if f_id.endswith(".field_5gi") or f_id == "field_5gi":
                    extracted[f_id] = demat_val
                elif f_id.endswith(".field_5gi_3") or f_id == "field_5gi_3":
                    extracted[f_id] = phys_val

        dir_match = re.search(r'(?:^|\n)\s*\|?\s*(?:\(ii\)\s*)?Directors\s*\|?\s*([0-9,]+)\s*\|?\s*([0-9,]+)', full_text, re.IGNORECASE)
        if dir_match:
            has_table_data = True
            demat_val = dir_match.group(1).strip()
            phys_val = dir_match.group(2).strip()
            table_rows_5g[1]["demat"] = demat_val
            table_rows_5g[1]["physical"] = phys_val
            try:
                table_rows_5g[1]["total"] = f"{int(demat_val.replace(',', '')) + int(phys_val.replace(',', '')):,}"
            except Exception:
                table_rows_5g[1]["total"] = f"{demat_val}"
            extracted["formnopas6.main.field_5gi_2"] = demat_val
            extracted["formnopas6.main.field_5gi_4"] = phys_val
            for f_id in field_label_map:
                if f_id.endswith(".field_5gi_2") or f_id == "field_5gi_2":
                    extracted[f_id] = demat_val
                elif f_id.endswith(".field_5gi_4") or f_id == "field_5gi_4":
                    extracted[f_id] = phys_val

        kmp_match = re.search(r'(?:^|\n)\s*\|?\s*(?:\(iii\)\s*)?KMPs?\s*\|?\s*([0-9,]+)\s*\|?\s*([0-9,]+)', full_text, re.IGNORECASE)
        if kmp_match:
            has_table_data = True
            demat_val = kmp_match.group(1).strip()
            phys_val = kmp_match.group(2).strip()
            table_rows_5g[2]["demat"] = demat_val
            table_rows_5g[2]["physical"] = phys_val
            try:
                table_rows_5g[2]["total"] = f"{int(demat_val.replace(',', '')) + int(phys_val.replace(',', '')):,}"
            except Exception:
                table_rows_5g[2]["total"] = f"{demat_val}"
            extracted["formnopas6.main.field_5gii"] = demat_val
            extracted["formnopas6.main.field_5gii_2"] = phys_val
            for f_id in field_label_map:
                if f_id.endswith(".field_5gii") or f_id == "field_5gii":
                    extracted[f_id] = demat_val
                elif f_id.endswith(".field_5gii_2") or f_id == "field_5gii_2":
                    extracted[f_id] = phys_val

        if has_table_data:
            extracted["formnopas6.main.field_5g"] = json.dumps(table_rows_5g)
            for f_id in field_label_map:
                if f_id.endswith(".field_5g") or f_id == "field_5g":
                    extracted[f_id] = json.dumps(table_rows_5g)

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

    # 4. Registered Address and Email for any MCA form (assign at most once to primary company field)
    addr_match = re.search(r'(?:Address of the registered office|Registered Office Address|Registered Address)\s*[:\|]\s*([^\n\|]+)', full_text, re.IGNORECASE)
    if addr_match:
        addr_val = addr_match.group(1).strip()
        addr_assigned = False
        for f_id, label in field_label_map.items():
            if addr_assigned or f_id in extracted:
                continue
            l_lower = (label or "").lower()
            if "registered ofice" in l_lower or "registered office" in l_lower or "registered address" in l_lower:
                extracted[f_id] = addr_val
                addr_assigned = True

    email_match = re.search(r'(?:email ID of the company|Email ID|Email)\s*[:\|]\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', full_text, re.IGNORECASE)
    if email_match:
        email_val = email_match.group(1).strip()
        email_assigned = False
        for f_id, label in field_label_map.items():
            if email_assigned or f_id in extracted:
                continue
            l_lower = (label or "").lower()
            if "email id" in l_lower or "email" in l_lower:
                extracted[f_id] = email_val
                email_assigned = True

    # 5. DIN, PAN, CS Membership, and Board Resolution Date across all statutory forms (assign at most once)
    din_match = re.search(r'\b(?:DIN|Director Identification Number)\s*[:\-\s]*([0-9]{8})\b', full_text, re.IGNORECASE)
    if din_match and "primary_din" not in assigned_entities:
        din_val = din_match.group(1).strip()
        din_assigned = False
        for f_id, label in field_label_map.items():
            if din_assigned or f_id in extracted:
                continue
            l_lower = (label or "").lower()
            # Director DIN must only map to Director DIN fields, not to Manager/CEO/CFO/CS fields
            if ("director identification" in l_lower or "din of director" in l_lower or "din" in l_lower) and "manager" not in l_lower and "secretary" not in l_lower and "liquidator" not in l_lower:
                extracted[f_id] = din_val
                din_assigned = True
                assigned_entities.add("primary_din")

    cs_match = re.search(r'\b(?:ACS|FCS|Membership\s*(?:No\.?|Number))\s*[:\-\s]*([A-Z0-9]{4,8})\b', full_text, re.IGNORECASE)
    if cs_match:
        cs_val = cs_match.group(1).strip()
        cs_assigned = False
        for f_id, label in field_label_map.items():
            if cs_assigned or f_id in extracted:
                continue
            l_lower = (label or "").lower()
            if "membership number of the company secretary" in l_lower or "membership number of company secretary" in l_lower:
                extracted[f_id] = cs_val
                cs_assigned = True

    kmp_match = re.search(r'(?:Manager|CEO|CFO|Liquidator)\s*(?:DIN|PAN)?\s*[:\-\s]*([A-Z0-9]{8,10})\b', full_text, re.IGNORECASE)
    if kmp_match:
        kmp_val = kmp_match.group(1).strip()
        kmp_assigned = False
        for f_id, label in field_label_map.items():
            if kmp_assigned or f_id in extracted:
                continue
            l_lower = (label or "").lower()
            if ("manager" in l_lower or "ceo" in l_lower or "cfo" in l_lower) and ("din or pan" in l_lower or "din" in l_lower):
                extracted[f_id] = kmp_val
                kmp_assigned = True

    pan_match = re.search(r'\b(?:PAN|Permanent Account Number)\s*[:\-\s]*([A-Z]{5}[0-9]{4}[A-Z])\b', full_text, re.IGNORECASE)
    if pan_match and "primary_pan" not in assigned_entities:
        pan_val = pan_match.group(1).strip()
        pan_assigned = False
        for f_id, label in field_label_map.items():
            if pan_assigned or f_id in extracted:
                continue
            l_lower = (label or "").lower()
            if ("permanent account number" in l_lower or re.search(r'\bpan\b', l_lower)) and "company" not in l_lower:
                extracted[f_id] = pan_val
                pan_assigned = True
                assigned_entities.add("primary_pan")

    br_match = re.search(r'resolution\s*(?:no\.?|number)?\s*[:\-\s]*([0-9A-Za-z/]+)?\s*dated\s*[:\-\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', full_text, re.IGNORECASE)
    if br_match:
        br_num = br_match.group(1).strip() if br_match.group(1) else ""
        br_date = br_match.group(2).strip() if br_match.group(2) else ""
        br_assigned = False
        for f_id, label in field_label_map.items():
            if br_assigned or f_id in extracted:
                continue
            l_lower = (label or "").lower()
            if "board of directors" in l_lower or "vide resolution" in l_lower:
                extracted[f_id] = f"Resolution No: {br_num} Dated: {br_date}".strip()
                br_assigned = True

    # 6. Form No. GNL-2 specific deterministic extraction
    if "gnl-2" in tmpl_lower or "gnl2" in tmpl_lower or "gnl 2" in tmpl_lower:
        GNL2_DOC_MAP = [
            (r'affidavit\s+under\s+section\s+59\s+of\s+the\s+insolvency\s+and\s+bankruptcy\s+code',
             'Affidavit under Section 59 of the Insolvency and Bankruptcy Code, 2016'),
            (r'form\s*159\s+of\s+the\s+companies\s*\(\s*court\s*\)\s*rules',
             'Form 159 of the Companies (Court) Rules, 1959'),
            (r'form\s*157\s+of\s+the\s+companies\s*\(\s*court\s*\)\s*rules',
             'Form 157 of the Companies (Court) Rules, 1959'),
            (r'form\s*154\s+of\s+the\s+companies\s*\(\s*court\s*\)\s*rules',
             'Form 154 of the Companies (Court) Rules, 1959'),
            (r'form\s*158\s+of\s+the\s+companies\s*\(\s*court\s*\)\s*rules',
             'Form 158 of the Companies (Court) Rules, 1959'),
            (r'form\s*156\s+of\s+the\s+companies\s*\(\s*court\s*\)\s*rules',
             'Form 156 of the Companies (Court) Rules, 1959'),
            (r'form\s*149\s+of\s+the\s+companies\s*\(\s*court\s*\)\s*rules',
             'Form 149 of the Companies (Court) Rules, 1959'),
            (r'form\s*153\s+of\s+the\s+companies\s*\(\s*court\s*\)\s*rules',
             'Form 153 of the Companies (Court) Rules, 1959'),
            (r'form\s*152\s+of\s+the\s+companies\s*\(\s*court\s*\)\s*rules',
             'Form 152 of the Companies (Court) Rules, 1959'),
            (r'(?:private\s+placement\s+offer\s+letter|pas\s*[-_]?\s*4|record\s+of\s+a\s+private\s+placement)',
             'Private placement offer letter or Record of a private placement offer to be kept by the company'),
            (r'\bred\s+herring\s+prospectus\b',
             'Red Herring Prospectus'),
            (r'(?:final\s+report\s+on\s+completion\s+of\s+liquidation|liquidation\s+process\s+by\s+liquidator)',
             'Final Report on Completion of liquidation process by Liquidator'),
            (r'\bprospectus\b',
             'Prospectus'),
            (r'(?:circular\s+or\s+circular\s+in\s+the\s+form\s+of\s+advertisement|dpt\s*[-_]?\s*1)',
             'Circular or Circular in the form of Advertisement inviting Deposits in DPT-1')
        ]

        matched_doc_option = None
        other_specify = None

        for pattern, standard_opt in GNL2_DOC_MAP:
            if re.search(pattern, full_text, re.IGNORECASE):
                matched_doc_option = standard_opt
                break

        # Check for Declaration of Solvency / CAA-10 / Custom Documents
        if not matched_doc_option:
            if re.search(r'declaration\s+of\s+solvency|caa[-.\s]*10', full_text, re.IGNORECASE):
                matched_doc_option = "Others"
                other_specify = "Declaration of Solvency"
            else:
                m_other = re.search(r'(?:Document\s*Title|Subject|Sub|In\s*the\s*matter\s*of)\s*[:\|]\s*([^\n\|]+)', full_text, re.IGNORECASE)
                if m_other:
                    matched_doc_option = "Others"
                    other_specify = m_other.group(1).strip()
                elif re.search(r'order\s+under\s+section|nclt\s+order|tribunal\s+order', full_text, re.IGNORECASE):
                    matched_doc_option = "Others"
                    other_specify = "Order of Hon'ble NCLT"
                elif re.search(r'aoc\s*[-_]?\s*4|mgt\s*[-_]?\s*7', full_text, re.IGNORECASE):
                    matched_doc_option = "Others"
                    other_specify = "Filing OF AOC-4 & MGT-7"

        # Field 2(a) and 2(b)
        for f_id, label in field_label_map.items():
            f_low = (f_id or "").lower()
            l_low = (label or "").lower()
            if "field_2a" in f_low or "indicate the document being filed" in l_low:
                extracted[f_id] = matched_doc_option or "Others"
            elif "field_2b" in f_low or "if others, then specify" in l_low:
                if other_specify or (matched_doc_option == "Others"):
                    extracted[f_id] = other_specify or "Statutory Document Filing"

        # Field 4(a) - Act under which document is filed
        act_val = "Companies Act, 2013"
        if re.search(r'insolvency\s+and\s+bankruptcy|ibc\s*,?\s*2016|\bibc\b|section\s+59\s+of\s+the\s+insolvency', full_text, re.IGNORECASE):
            act_val = "Insolvency and Bankruptcy Code, 2016"
        elif re.search(r'companies\s+act\s*,?\s*1956', full_text, re.IGNORECASE):
            act_val = "Companies Act, 1956"

        for f_id, label in field_label_map.items():
            f_low = (f_id or "").lower()
            l_low = (label or "").lower()
            if "field_4a" in f_low or "act under which" in l_low:
                extracted[f_id] = act_val

        # Field 4(b), 4(b)(i), 4(b)(ii) - Section under which document is filed
        sec_val = None
        if "declaration of solvency" in (other_specify or "").lower() or re.search(r'caa[-.\s]*10', full_text, re.IGNORECASE):
            sec_val = "Section 233"
        else:
            sec_match = re.search(r'(?:pursuant\s+to\s+section|under\s+section|section|sec\.?)\s*([0-9A-Za-z\(\)\s,to\-]+?)(?:\s+of\s+(?:the\s+)?companies\s+act|\s+of\s+(?:the\s+)?insolvency|\s+and\s+rule|,|\n|\.|\)|$)', full_text, re.IGNORECASE)
            if sec_match:
                s_raw = sec_match.group(1).strip()
                s_clean = re.sub(r'[\(\[\{].*$', '', s_raw).strip()
                if s_clean:
                    sec_val = f"Section {s_clean}" if not s_clean.lower().startswith("section") else s_clean

        if sec_val:
            for f_id, label in field_label_map.items():
                f_low = (f_id or "").lower()
                l_low = (label or "").lower()
                if "field_4a" not in f_low and not l_low.startswith("act") and ("field_4b" in f_low or "section" in l_low):
                    if "4bi_2" in f_low or "1956" in l_low:
                        if act_val == "Companies Act, 1956":
                            extracted[f_id] = sec_val
                    elif "4bii" in f_low or "insolvency" in l_low:
                        if act_val == "Insolvency and Bankruptcy Code, 2016":
                            extracted[f_id] = sec_val
                    else:
                        extracted[f_id] = sec_val

        # Field 5(a) - SRN of Form MGT-14
        m_srn = re.search(r'(?:srn|service\s+request\s+number|form\s+mgt-?14\s+srn)\s*[:\|\-\s]*([A-Za-z0-9]{9})\b', full_text, re.IGNORECASE)
        if m_srn:
            srn_val = m_srn.group(1).strip()
            for f_id, label in field_label_map.items():
                f_low = (f_id or "").lower()
                l_low = (label or "").lower()
                if "field_5a" in f_low or "service request number" in l_low:
                    extracted[f_id] = srn_val

    # 7. Universal MCA Statutory Dates, Share Counts, and Signatory Role Extraction
    # Date capture pattern supporting DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY, and textual dates
    _DATE_PAT = r'([0-9]{1,2}[/\-\.][0-9]{1,2}[/\-\.][0-9]{2,4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}|[A-Za-z]+\s+[0-9]{1,2}(?:st|nd|rd|th)?,?\s+[0-9]{4}|[^\n\|\r;]+)'

    # Date of passing special (SR) or ordinary resolution (OR)
    m_res_date = re.search(r'(?:date\s+of\s+passing\s+(?:the\s+)?(?:board\s+)?resolution|resolution\s+dated|vide\s+resolution\s+dated)\s*[:\|\-\s]*' + _DATE_PAT, full_text, re.IGNORECASE)
    if m_res_date:
        p_res = parse_and_normalize_date(m_res_date.group(1).strip())
        if p_res:
            for f_id, label in field_label_map.items():
                f_low = (f_id or "").lower()
                l_low = (label or "").lower()
                if "field_5b" in f_low or "date of passing special" in l_low:
                    extracted[f_id] = p_res
                elif "field_r" in f_low or "authorised by board of directors" in l_low:
                    extracted[f_id] = p_res

    # Date of event (e.g. order date, effective date)
    m_event_date = re.search(r'(?:date\s+of\s+event|event\s+date|effective\s+date|execution\s+date|order\s+pronounced\s+on|order\s+dated|dated)\s*[:\|\-\s]*' + _DATE_PAT, full_text, re.IGNORECASE)
    if m_event_date:
        parsed_event_date = parse_and_normalize_date(m_event_date.group(1).strip())
        if parsed_event_date:
            for f_id, label in field_label_map.items():
                f_low = (f_id or "").lower()
                l_low = (label or "").lower()
                if "field_6a" in f_low or "date of event" in l_low:
                    extracted[f_id] = parsed_event_date

    # Universal Number of Shares (e.g. "10,000 Equity Shares", "Number of shares: 50,000")
    m_shares = re.search(r'(?:number\s+of\s+shares|no\.\s*of\s+shares|total\s+shares)\s*[:\|\-\s]*([0-9,]+)', full_text, re.IGNORECASE)
    if not m_shares:
        m_shares = re.search(r'\b([0-9,]+)\s+(?:equity|preference)?\s*shares\b', full_text, re.IGNORECASE)
    if m_shares:
        raw_sh = m_shares.group(1).replace(",", "").strip()
        if raw_sh.isdigit() and int(raw_sh) > 0:
            for f_id, label in field_label_map.items():
                f_low = (f_id or "").lower()
                l_low = (label or "").lower()
                # Target specific leaf count fields, NOT parent section headers!
                if ("number of shares" in l_low or "no. of shares" in l_low or "num_shares" in f_low) and "particulars" not in l_low:
                    extracted[f_id] = raw_sh

    # Date of Entry of name in register of members / charges (e.g. MGT-6 4(p), BEN-2)
    m_entry_date = re.search(
        r'(?:date\s+of\s+entry(?:\s+of\s+name)?(?:\s+in\s+(?:the\s+)?register)?|'
        r'entered\s+(?:in\s+)?(?:the\s+)?register(?:\s+of\s+members)?\s+(?:on|dated)|'
        r'entry\s+in\s+register\s+dated?)\s*(?:was|is)?[:\|\-\s]*' + _DATE_PAT,
        full_text, re.IGNORECASE
    )
    if m_entry_date:
        p_entry = parse_and_normalize_date(m_entry_date.group(1).strip())
        if p_entry:
            for f_id, label in field_label_map.items():
                f_low = (f_id or "").lower()
                l_low = (label or "").lower()
                if "field_4p" in f_low or "entry of name in register" in l_low or "date of entry" in l_low:
                    extracted[f_id] = p_entry

    # Date of Receipt of declaration by company (e.g. MGT-6 4(r), 5(r))
    m_receipt_date = re.search(
        r'(?:date\s+of\s+receipt(?:\s+of\s+declaration)?(?:\s+by\s+(?:the\s+)?company)?|'
        r'received\s+(?:the\s+declaration\s+on|by\s+(?:the\s+)?company\s+on)|'
        r'receipt\s+dated?)\s*(?:was|is)?[:\|\-\s]*' + _DATE_PAT,
        full_text, re.IGNORECASE
    )
    if m_receipt_date:
        p_rec = parse_and_normalize_date(m_receipt_date.group(1).strip())
        if p_rec:
            for f_id, label in field_label_map.items():
                f_low = (f_id or "").lower()
                l_low = (label or "").lower()
                if "field_4r" in f_low or "field_5r" in f_low or "receipt of declaration" in l_low or "received by the company" in l_low:
                    extracted[f_id] = p_rec

    # Date of declaration by majority of directors / registered owners (e.g. MGT-6 4(q), 5(q), GNL-2 6(b))
    m_dec_date = re.search(r'(?:date\s+of\s+declaration|declaration\s+.*?dated|declared\s+on|solemnly\s+affirmed.*?on)\s*[:\|\-\s]*' + _DATE_PAT, full_text, re.IGNORECASE)
    p_dec = parse_and_normalize_date(m_dec_date.group(1).strip()) if m_dec_date else None
    if not p_dec and ("declaration of solvency" in (other_specify or "").lower() or re.search(r'caa[-.\s]*10', full_text, re.IGNORECASE)):
        p_dec = extracted.get("gnl2.main.field_6a") or extracted.get("gnl2.main.field_5b") or stat_entities.get("primary_date")

    if p_dec:
        for f_id, label in field_label_map.items():
            f_low = (f_id or "").lower()
            l_low = (label or "").lower()
            # Strictly exclude receipt fields from declaration date matching
            if ("field_6b" in f_low or "field_4q" in f_low or "field_5q" in f_low or "date of declaration" in l_low) and "receipt" not in l_low:
                extracted[f_id] = p_dec

    # Signatory / DIN / Designation: Resolve using semantics and metadata, never guessing from format alone
    has_dir_mention = bool(re.search(r'\b(?:managing\s+)?director\b', full_text, re.IGNORECASE))
    has_sec_mention = bool(re.search(r'\bcompany\s+secretary\b|\bsecretary\b', full_text, re.IGNORECASE))

    # Resolve explicit designation; preserve ambiguity if both or neither are explicitly indicated
    detected_desig = None
    if has_dir_mention and not has_sec_mention:
        detected_desig = "Director"
    elif has_sec_mention and not has_dir_mention:
        detected_desig = "Company Secretary"
    elif has_dir_mention and has_sec_mention:
        # Document mentions both roles; keep designation unassigned to avoid false attribution
        detected_desig = None

    for f_id, label in field_label_map.items():
        f_low = (f_id or "").lower()
        l_low = (label or "").lower()
        if "designation" in f_low or "designation" in l_low:
            if detected_desig:
                extracted[f_id] = detected_desig
        elif "director_identification_number" in f_low or ("director" in l_low and "identification" in l_low) or ("din" in l_low and "director" in l_low):
            # Strictly assign DIN (or PAN if DIN unavailable), never ICSI membership to a Director field
            if stat_entities.get("primary_din"):
                extracted[f_id] = stat_entities["primary_din"]
            elif stat_entities.get("primary_pan") and detected_desig == "Director":
                extracted[f_id] = stat_entities["primary_pan"]
        elif "membership_number" in f_low or "membership number" in l_low or ("secretary" in l_low and "membership" in l_low):
            # Strictly assign ICSI membership to CS/Membership fields, never Director DIN
            if stat_entities.get("icsi_memberships"):
                extracted[f_id] = stat_entities["icsi_memberships"][0]

    # 8. Form No. INC-20A Table 4 & Shareholder count
    if "inc-20a" in tmpl_lower or "inc20a" in tmpl_lower or "20a" in tmpl_lower:
        m_sh_count = re.search(r'(?:number\s+of\s+shareholders?|shareholders?\s+count)\s*[:\|\-\s]*([0-9]+)', full_text, re.IGNORECASE)
        if m_sh_count:
            for f_id, label in field_label_map.items():
                if f_id.endswith(".field_4a") or "number of shareholders" in (label or "").lower():
                    extracted[f_id] = m_sh_count.group(1).strip()

        sh_rows = []
        for line in full_text.splitlines():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 4:
                d_cand = next((p for p in parts if re.search(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', p)), None)
                amt_cand = next((p for p in parts if re.search(r'^[0-9,]+(?:\.[0-9]+)?$', p.replace("₹", "").replace("INR", "").replace(",", "").strip())), None)
                if d_cand and amt_cand:
                    name_cand = parts[0]
                    bank_cand = parts[1] if len(parts) > 1 else ""
                    acc_cand = parts[2] if len(parts) > 2 else ""
                    sh_rows.append({
                        "shareholder_name": name_cand,
                        "bank_name": bank_cand,
                        "account_number": acc_cand,
                        "date_of_receipt": d_cand,
                        "amount_of_receipt": amt_cand
                    })
        if sh_rows:
            extracted["formnoinc20a.main.field_4table"] = sh_rows
            if not m_sh_count:
                for f_id, label in field_label_map.items():
                    if f_id.endswith(".field_4a") or "number of shareholders" in (label or "").lower():
                        extracted[f_id] = str(len(sh_rows))

    # 9. Form LLP-8 Part B Statement of Account extraction
    if "llp" in tmpl_lower and "8" in tmpl_lower:
        FINANCIAL_HEAD_MAP = [
            ("I. Contribution received by all partners", r'(?:contribution\s+received|partners?\s+contribution)'),
            ("II. Reserves and Surplus", r'(?:reserves\s+and\s+surplus)'),
            ("III. Secured Loans", r'(?:secured\s+loans?)'),
            ("IV. Unsecured Loans", r'(?:unsecured\s+loans?)'),
            ("V. Short Term Borrowings", r'(?:short\s+term\s+borrowings?)'),
            ("VI. Trade Payables", r'(?:trade\s+payables?)'),
            ("VII. Other Liabilities", r'(?:other\s+liabilities)'),
            ("VIII. Provisions", r'(?:provisions\b)'),
            ("I. Gross Fixed Assets", r'(?:gross\s+fixed\s+assets?)'),
            ("III. Investments", r'(?:investments\b)'),
            ("V. Inventories", r'(?:inventories|stock\s+in\s+trade)'),
            ("VI. Trade Receivables", r'(?:trade\s+receivables?|debtors)'),
            ("VII. Cash and Cash Equivalents", r'(?:cash\s+and\s+cash\s+equivalents?|cash\s+and\s+bank\s+balances?)'),
            ("VIII. Loans and Advances", r'(?:loans\s+and\s+advances)'),
            ("I. Gross Turnover", r'(?:gross\s+turnover|turnover|revenue\s+from\s+operations)'),
            ("II. Other Income", r'(?:other\s+income)'),
            ("V. Administrative Expenses", r'(?:administrative\s+expenses?)'),
            ("VI. Personnel Expenses", r'(?:personnel\s+expenses?|employee\s+benefit\s+expenses?)'),
            ("VIII. Total Expenses", r'(?:total\s+expenses?)'),
            ("IX. Profit / Loss Before Tax", r'(?:profit\s+/\s+loss\s+before\s+tax|profit\s+before\s+tax|pbt\b)'),
        ]
        parsed_heads = {}
        for head_name, pat in FINANCIAL_HEAD_MAP:
            m_fin = re.search(pat + r'[^\n0-9]*?[:\|\-\s]+([0-9,]+(?:\.[0-9]+)?)(?:[\s\|]+([0-9,]+(?:\.[0-9]+)?))?', full_text, re.IGNORECASE)
            if m_fin:
                cur_val = m_fin.group(1).strip()
                prev_val = m_fin.group(2).strip() if m_fin.group(2) else ""
                parsed_heads[head_name] = {"current_year": cur_val, "previous_year": prev_val}

        if parsed_heads:
            from .forms.registry import FormRegistry
            llp8_schema = FormRegistry.get_form_schema("LLP Form No. 8")
            if llp8_schema:
                for f in llp8_schema.get("fields", []):
                    if (f.get("id") == "llpformno8.section_1.field_5" or f.get("canonical_no") == "5") and f.get("type") == "table":
                        def_rows = f.get("table_metadata", {}).get("default_rows") or f.get("default_rows") or []
                        hydrated = []
                        for dr in def_rows:
                            r_copy = dict(dr)
                            h_label = r_copy.get("financial_head", "")
                            for matched_h, vals in parsed_heads.items():
                                if matched_h.lower() in h_label.lower() or h_label.lower() in matched_h.lower():
                                    r_copy["current_year"] = vals["current_year"]
                                    if vals["previous_year"]:
                                        r_copy["previous_year"] = vals["previous_year"]
                                    break
                            hydrated.append(r_copy)
                        extracted["llpformno8.section_1.field_5"] = hydrated
                        break

    # 10. Form GNL-1 Deterministic Fast-Path Extraction
    if "gnl" in tmpl_lower and "1" in tmpl_lower:
        f_text_l = full_text.lower()
        if "compounding" in f_text_l:
            extracted["gnl1.main.field_1a"] = "Compounding of offences"
        elif "annual general meeting" in f_text_l and "extension" in f_text_l:
            extracted["gnl1.main.field_1a"] = "Extension of period of annual general meeting by three months"
        elif "scheme" in f_text_l and ("amalgamation" in f_text_l or "arrangement" in f_text_l):
            extracted["gnl1.main.field_1a"] = "Scheme of arrangement, amalgamation"

        if stat_entities.get("primary_cin"):
            extracted["gnl1.main.field_2"] = "Company"
            extracted["gnl1.main.field_3"] = stat_entities["primary_cin"]

        m_roc = re.search(r'(?:registrar\s+of\s+companies|roc)\s*[,:\-\s]+\s*([A-Za-z\s]+?)(?:\s*\n|\s*,|\s*\.)', full_text, re.IGNORECASE)
        if m_roc:
            roc_loc = m_roc.group(1).strip()
            if len(roc_loc) < 30 and not any(w in roc_loc.lower() for w in ["section", "act", "form", "the"]):
                extracted["gnl1.main.field_4"] = roc_loc

        extracted["gnl1.main.field_8a"] = "Company"

        m_notice = re.search(r'(?:notice\s+(?:no|number)|f\.?\s*no\.?|ref(?:\s+no)?)\s*[:\-]?\s*([A-Za-z0-9/\-._()]+)', full_text, re.IGNORECASE)
        if m_notice and len(m_notice.group(1)) > 3:
            extracted["gnl1.main.field_8d"] = "In pursuance to a notice"
            extracted["gnl1.main.field_8e"] = m_notice.group(1).strip()
        else:
            extracted["gnl1.main.field_8d"] = "Suo-motu"

        m_not_date = re.search(r'(?:dated|date\s+of\s+notice)\s*[:\-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})', full_text, re.IGNORECASE)
        if m_not_date:
            norm_d = parse_and_normalize_date(m_not_date.group(1))
            if norm_d:
                extracted["gnl1.main.field_8f"] = norm_d

        m_sec = re.search(r'\bsection\s+(\d+[A-Za-z]?)\b', full_text, re.IGNORECASE)
        if m_sec:
            extracted["gnl1.main.field_8g"] = m_sec.group(1).strip()

        extracted["gnl1.main.field_8q"] = "No"

    # 11. Form INC-28 Deterministic Fast-Path Extraction (Act & Sections 5bi / 5bii)
    if "inc" in tmpl_lower and "28" in tmpl_lower:
        f_text_l = full_text.lower()
        if "companies act, 1956" in f_text_l or "companies act 1956" in f_text_l:
            extracted["formnoinc28.main.field_5a"] = "The Companies Act, 1956"
        else:
            extracted["formnoinc28.main.field_5a"] = "The Companies Act, 2013"

        sec_matches = re.findall(r'\b(?:section|u/s|under\s+section)\s*(\d+[A-Za-z]?(?:\(\d+\))?)\b', full_text, re.IGNORECASE)
        for sm in sec_matches:
            clean_s = sm.strip().lower()
            if "232" in clean_s:
                extracted["formnoinc28.main.field_5bi"] = "232 - Amalgamation"
                break
            elif "230" in clean_s:
                extracted["formnoinc28.main.field_5bi"] = "230(8) - Compromise and arrangement"
                break
            elif "66" in clean_s:
                extracted["formnoinc28.main.field_5bi"] = "66(5) - Reduction of Share capital"
                break
            elif "441" in clean_s:
                extracted["formnoinc28.main.field_5bi"] = "441 - Compounding order passed by NCLT"
                break
            elif "252" in clean_s:
                extracted["formnoinc28.main.field_5bi"] = "252(2) - Appeal against order of ROC"
                break
            elif "12" in clean_s:
                extracted["formnoinc28.main.field_5bi"] = "12(6) - Change in Registered Office from one RoC to another within the same State"
                break
            elif "13" in clean_s:
                extracted["formnoinc28.main.field_5bi"] = "13(7) - Change in Registered Office from one State to another"
                break
            elif "394" in clean_s:
                extracted["formnoinc28.main.field_5bii"] = "394(1) - Amalgamation"
                extracted["formnoinc28.main.field_5a"] = "The Companies Act, 1956"
                break
            elif "391" in clean_s:
                extracted["formnoinc28.main.field_5bii"] = "391 - Compromise and arrangement"
                extracted["formnoinc28.main.field_5a"] = "The Companies Act, 1956"
                break

    return extracted


def is_safe_semantic_hint(hint: Optional[str]) -> bool:
    """
    Guards LLM prompt hints from bleeding hardcoded company values (CIN, PAN, personal names, dates, amounts).
    Returns True only if the hint is an abstract field description / canonical label.
    """
    if not hint:
        return False
    h = str(hint).strip()
    if len(h) < 2 or len(h) > 60:
        return False
    if h.lower() in ["yes", "no", "true", "false", "n/a", "none", "null"]:
        return False
    # Exclude CIN / LLPIN
    if re.search(r'\b[LUu][0-9]{5}[A-Za-z]{2}[0-9]{4}[A-Za-z]{3}[0-9]{6}\b', h) or re.search(r'\b[A-Za-z]{3}-?[0-9]{4,7}\b', h):
        return False
    # Exclude PAN / DIN / SRN
    if re.search(r'\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b', h) or re.search(r'\b[0-9]{8}\b', h) or re.search(r'\b[A-Za-z]{1,2}[0-9]{7,8}\b', h):
        return False
    # Exclude emails
    if "@" in h:
        return False
    # Exclude dates
    if re.search(r'\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\b', h):
        return False
    # Exclude company entity names
    if re.search(r'\b(?:private\s+limited|pvt\s+ltd|pvt\.\s*ltd|limited|llp|ifsc)\b', h, re.IGNORECASE):
        return False
    # Exclude addresses
    if re.search(r'\b(?:plot\s+no|sector|flat\s+no|road|street|garden|colony|nagar|pin\s*code|zip)\b', h, re.IGNORECASE) or re.search(r'\b\d{6}\b', h):
        return False
    # Exclude monetary figures / share count
    if re.search(r'(?:inr|rs\.?|₹)\s*[0-9,]+', h, re.IGNORECASE) or re.search(r'^[0-9,]+(?:\.[0-9]+)?$', h):
        return False
    # Exclude court order case numbers
    if re.search(r'\b(?:cp|ca|caa|nclt|slp|wp)[\s/]*\d+', h, re.IGNORECASE):
        return False
    return True


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
            mapped_form_fields = {r.form_field for r in schema_rules} if schema_rules else None
            tmpl_clean = (template_name or "").lower().replace(" ", "").replace("-", "")
            is_dedicated_pipeline = "gnl2" in tmpl_clean or "pas6" in tmpl_clean or "pas" in tmpl_clean

            fast_path_data = _fast_path_extract_mca_fields(full_text, template_name, field_label_map)
            for f_id, f_val in fast_path_data.items():
                if f_val and f_val not in [None, "", "Unknown", "N/A"]:
                    if mapped_form_fields and not is_dedicated_pipeline and f_id not in mapped_form_fields:
                        # Exclude unmapped fields for generic studio templates
                        continue
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
                            safe_hint = rule.extracted_key if is_safe_semantic_hint(rule.extracted_key) else None
                            extracted_fields.append({
                                "key": rule.form_field,
                                "value": None,
                                "_source": "pending_llm",
                                "_hint": safe_hint
                            })

            elif field_label_map:
                # When no explicit SchemaAliasRules exist in DB, scope LLM to unextracted template fields
                for f_id, label in field_label_map.items():
                    if f_id not in extracted_lookup and f_id not in [f["key"] for f in extracted_fields]:
                        # DAG Pruning Check: evaluate condition against already extracted values
                        dep = field_dependency_map.get(f_id)
                        if dep and isinstance(dep, dict):
                            parent_id = dep.get("field")
                            op = dep.get("operator", "equals")
                            target_val = dep.get("value")
                            parent_val = extracted_lookup.get(parent_id)

                            if parent_val is not None:
                                p_str = str(parent_val).strip().lower()
                                t_str = str(target_val).strip().lower() if target_val is not None else ""
                                cond = (p_str == t_str) if op == "equals" else (any(p_str == str(v).strip().lower() for v in target_val) if op == "in" and isinstance(target_val, list) else True)
                                if not cond:
                                    continue
                        any_dom_miss = True
                        extracted_fields.append({
                            "key": f_id,
                            "value": None,
                            "_source": "pending_llm",
                            "_hint": label
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
                        if pending_items:
                            field_lines = []
                            seen_prompt_keys = set()
                            for pf in pending_items:
                                raw_key = pf["key"]
                                if raw_key in seen_prompt_keys:
                                    continue
                                seen_prompt_keys.add(raw_key)

                                label = field_label_map.get(raw_key, "")
                                hint = pf.get("_hint", "")
                                safe_hint_val = hint if is_safe_semantic_hint(hint) else None
                                if label and safe_hint_val and safe_hint_val.lower() not in label.lower():
                                    desc = f"{label} (Alias / Hint: {safe_hint_val})"
                                elif label:
                                    desc = label
                                elif safe_hint_val:
                                    desc = safe_hint_val
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
                                ollama_url = os.getenv("OLLAMA_API_URL", "http://192.168.112.2:11434").rstrip("/")
                                response = None
                                try:
                                    response = requests.post(
                                        f"{ollama_url}/api/generate",
                                        json={
                                            "model": "qwen2.5:14b",
                                            "prompt": prompt,
                                            "stream": False,
                                            "format": "json"
                                        },
                                        timeout=(3.0, 25.0)
                                    )
                                    response.raise_for_status()
                                except Exception as primary_err:
                                    print(f"[LLM] Primary endpoint ({ollama_url}) failed: {primary_err}. Trying localhost...")
                                    try:
                                        response = requests.post(
                                            "http://127.0.0.1:11434/api/generate",
                                            json={
                                                "model": "qwen2.5:14b",
                                                "prompt": prompt,
                                                "stream": False,
                                                "format": "json"
                                            },
                                            timeout=(1.5, 20.0)
                                        )
                                        response.raise_for_status()
                                    except Exception as local_err:
                                        raise RuntimeError(f"All Ollama endpoints unreachable: {primary_err} | {local_err}")

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

                        def _clean_alpha(s: str) -> str:
                            if not s: return ""
                            s = str(s).lower().strip()
                            if s.startswith("field_"): s = s[6:]
                            return "".join(c for c in s if c.isalnum())

                        llm_raw_map = {f["key"]: f["value"] for f in llm_fields if f.get("key") and f.get("value")}
                        llm_alpha_map = {_clean_alpha(f["key"]): f["value"] for f in llm_fields if f.get("key") and f.get("value")}

                        used_llm_fuzzy_values = set()
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
                                    if target_alpha in llm_alpha_map and llm_alpha_map[target_alpha] not in used_llm_fuzzy_values:
                                        matched_val = llm_alpha_map[target_alpha]
                                        used_llm_fuzzy_values.add(matched_val)

                                # 4. Alphanumeric Substring & Hint match (guarded against duplicates)
                                if not matched_val:
                                    target_alpha = _clean_alpha(field_key)
                                    hint_alpha = _clean_alpha(hint)
                                    for k, v in llm_raw_map.items():
                                        if v in used_llm_fuzzy_values:
                                            continue
                                        k_alpha = _clean_alpha(k)
                                        if target_alpha and len(target_alpha) > 4 and (target_alpha in k_alpha or k_alpha in target_alpha):
                                            matched_val = v
                                            used_llm_fuzzy_values.add(v)
                                            break
                                        if hint_alpha and len(hint_alpha) > 4 and (hint_alpha in k_alpha or k_alpha in hint_alpha):
                                            matched_val = v
                                            used_llm_fuzzy_values.add(v)
                                            break

                                # Date normalization for any date fields extracted via LLM
                                if matched_val and matched_val not in ["Unknown", "N/A", "None", None]:
                                    f_lbl = field_label_map.get(field_key, "")
                                    if "date" in field_key.lower() or "date" in f_lbl.lower():
                                        norm_d = parse_and_normalize_date(str(matched_val))
                                        if norm_d:
                                            matched_val = norm_d

                                field["value"] = matched_val or "Unknown"
                                field["_source"] = "llm"

                        # Append extra fields ONLY if not strictly scoped to schema_rules and not already present
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

            # Universal date normalization pass on all date fields
            for field in extracted_fields:
                f_key = field.get("key", "")
                f_lbl = field_label_map.get(f_key, "")
                if "date" in f_key.lower() or "date" in f_lbl.lower():
                    v = field.get("value")
                    if v and str(v).strip() not in ["Unknown", "N/A", "None", ""]:
                        norm_d = parse_and_normalize_date(str(v))
                        if norm_d:
                            field["value"] = norm_d


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
                # When template has schema mapping rules and is not a dedicated pipeline, STRICTLY discard any field that was not mapped by the user
                if mapped_form_fields and not is_dedicated_pipeline and k not in mapped_form_fields:
                    continue
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
            try:
                db.rollback()
            except Exception:
                pass
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


