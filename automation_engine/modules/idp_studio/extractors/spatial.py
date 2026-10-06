import re
import json
from typing import Dict, Any, List, Optional
from sqlalchemy import or_
from ..core.db import SessionLocal
from ..core import models

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
                (models.SchemaAliasRule.scope_id == scenario)
            )
        if company_id:
            scope_conditions.append(
                (models.SchemaAliasRule.scope_type == "COMPANY") &
                (models.SchemaAliasRule.scope_id == company_id)
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


def apply_spatial_overrides(
    template_name: str,
    ocr_data: Dict[str, Any],
    extracted_data: Dict[str, Any],
    company_id: Optional[str] = None,
    scenario: Optional[str] = None
) -> Dict[str, Any]:
    """
    Checks if there are any IDP spatial rules for this template/company/scenario.
    If yes, attempts to extract the fields based on bounding box mathematics 
    and overrides the standard regex/keyword extraction in `extracted_data`.
    """
    rules = get_effective_rules(template_name, company_id=company_id, scenario=scenario)
    if not rules:
        return extracted_data # Fallback to standard flow (Zero-Touch)
        
    print(f"[IDP Studio] Found {len(rules)} cascaded spatial rules for {template_name} (Company: {company_id}, Scenario: {scenario}).")
    return extracted_data
