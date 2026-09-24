"""
Universal Form Registry for MCA Dynamic Forms (Supporting 54+ Forms).

Decouples form definitions from application code.
Loads, validates, and manages MCA Form Schemas from SQLite (IdpTemplate)
and filesystem JSON files (/data/form_schemas/).
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ..core.models import IdpTemplate
from ..core.db import SessionLocal

logger = logging.getLogger(__name__)

# Base directory for pre-bundled or cached form schemas
SCHEMAS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "form_schemas"))
os.makedirs(SCHEMAS_DIR, exist_ok=True)



class FormRegistry:
    """
    Manages the lifecycle, loading, and dependency indexing of all 54+ MCA Form Schemas.
    """

    @classmethod
    def list_forms(cls, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Lists all registered MCA forms across DB and local schema cache.
        Returns lightweight summaries: [{form_id, form_name, governing_law, total_fields, has_conditionals}]
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        forms_map = {}

        try:
            # 1. Load from DB
            db_templates = db.query(IdpTemplate).all()
            for t in db_templates:
                if t.template_name == "FLA Return (Standard Form)":
                    continue
                schema = cls._parse_raw_schema(t.fields_json)
                fields = schema.get("fields", [])
                form_id = t.template_id or schema.get("form_id") or t.template_name.lower().replace(" ", "_")
                forms_map[form_id] = {
                    "form_id": form_id,
                    "form_name": t.template_name,
                    "governing_law": schema.get("governing_law", ""),
                    "total_fields": len(fields),
                    "conditional_fields": sum(1 for f in fields if f.get("depends_on")),
                    "source": "database"
                }

            # 2. Load from JSON files in SCHEMAS_DIR (if not already present)
            for fname in os.listdir(SCHEMAS_DIR):
                if fname.endswith(".json"):
                    fpath = os.path.join(SCHEMAS_DIR, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            file_schema = json.load(f)
                            f_id = file_schema.get("form_id") or fname.replace(".json", "")
                            if f_id not in forms_map:
                                fields = file_schema.get("fields", [])
                                forms_map[f_id] = {
                                    "form_id": f_id,
                                    "form_name": file_schema.get("form_name", f_id),
                                    "governing_law": file_schema.get("governing_law", ""),
                                    "total_fields": len(fields),
                                    "conditional_fields": sum(1 for f in fields if f.get("depends_on")),
                                    "source": "filesystem"
                                }
                    except Exception as e:
                        logger.warning(f"[FormRegistry] Error loading schema file {fname}: {e}")

        finally:
            if close_db:
                db.close()

        return sorted(list(forms_map.values()), key=lambda x: x["form_name"])

    @classmethod
    def get_form_schema(cls, form_identifier: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves the complete standardized schema for a given form_id or template_name.
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            # 1. Search DB by template_id or template_name
            db_t = db.query(IdpTemplate).filter(
                (IdpTemplate.template_id == form_identifier) | 
                (IdpTemplate.template_name == form_identifier)
            ).first()

            if db_t:
                schema = cls._parse_raw_schema(db_t.fields_json)
                schema["form_id"] = db_t.template_id
                schema["form_name"] = db_t.template_name
                return cls._standardize_schema(schema)

            # 2. Search filesystem cache
            for fname in os.listdir(SCHEMAS_DIR):
                if fname.endswith(".json"):
                    if fname == f"{form_identifier}.json" or fname.replace(".json", "").lower() == form_identifier.lower():
                        fpath = os.path.join(SCHEMAS_DIR, fname)
                        with open(fpath, "r", encoding="utf-8") as f:
                            file_schema = json.load(f)
                            return cls._standardize_schema(file_schema)

        finally:
            if close_db:
                db.close()

        return None

    @classmethod
    def save_form_schema(cls, schema: Dict[str, Any], db: Optional[Session] = None) -> str:
        """
        Persists a newly ingested or edited form schema to both DB and local filesystem.
        Returns form_id.
        """
        standardized = cls._standardize_schema(schema)
        form_id = standardized["form_id"]
        form_name = standardized["form_name"]

        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            # Save to DB
            existing = db.query(IdpTemplate).filter(
                (IdpTemplate.template_id == form_id) | (IdpTemplate.template_name == form_name)
            ).first()

            schema_json_str = json.dumps(standardized)
            if existing:
                existing.fields_json = schema_json_str
                existing.template_name = form_name
                db.commit()
            else:
                new_row = IdpTemplate(
                    template_id=form_id,
                    template_name=form_name,
                    fields_json=schema_json_str
                )
                db.add(new_row)
                db.commit()

            # Save to filesystem
            clean_filename = f"{form_id}.json"
            fpath = os.path.join(SCHEMAS_DIR, clean_filename)
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(standardized, f, indent=2)

            logger.info(f"[FormRegistry] Successfully saved schema for '{form_name}' (ID: {form_id})")
            return form_id

        finally:
            if close_db:
                db.close()

    @staticmethod
    def _parse_raw_schema(raw_json: Any) -> Dict[str, Any]:
        """Safely unpacks fields_json whether stored as string or pre-parsed dict/list."""
        if isinstance(raw_json, dict):
            return raw_json
        if isinstance(raw_json, str):
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    return parsed
                elif isinstance(parsed, list):
                    return {"fields": parsed}
            except Exception:
                pass
        return {"fields": []}

    @classmethod
    def _standardize_schema(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures the schema strictly conforms to the MCAFormDefinition specification."""
        form_name = raw.get("form_name") or raw.get("template_name") or "Form Template"
        form_id = raw.get("form_id") or raw.get("template_id") or form_name.lower().replace(" ", "_").replace(".", "")
        
        fields = raw.get("fields", [])
        standardized_fields = []

        for f in fields:
            f_id = f.get("id") or f"field_{f.get('canonical_no', 'unassigned').replace('(', '_').replace(')', '')}"
            c_no = str(f.get("canonical_no") or "")
            label = str(f.get("label") or f"Field {c_no}")
            f_type = str(f.get("type") or "text").lower()

            # Standardize type enum
            if f_type not in ["text", "number", "date", "select", "radio", "textarea", "file", "email", "cin", "pan", "din"]:
                if "date" in f_type:
                    f_type = "date"
                elif "select" in f_type or "dropdown" in f_type:
                    f_type = "select"
                elif "radio" in f_type:
                    f_type = "radio"
                else:
                    f_type = "text"

            options = f.get("options")
            if options and not isinstance(options, list):
                options = [str(options)]

            # Clean depends_on
            dep = f.get("depends_on")
            if dep and isinstance(dep, dict) and dep.get("field"):
                dep_cleaned = {
                    "field": dep.get("field"),
                    "operator": dep.get("operator", "equals"),
                    "value": dep.get("value")
                }
            else:
                dep_cleaned = None

            standardized_fields.append({
                "id": f_id,
                "canonical_no": c_no,
                "label": label,
                "type": f_type,
                "required": bool(f.get("required", False)),
                "options": options,
                "depends_on": dep_cleaned,
                "validation": f.get("validation", {}),
                "instructions": f.get("instructions", "")
            })

        return {
            "form_id": form_id,
            "form_name": form_name,
            "governing_law": raw.get("governing_law", ""),
            "version": raw.get("version", "1.0.0"),
            "fields": standardized_fields
        }
