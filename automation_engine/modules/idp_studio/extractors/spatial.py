import re as _re
import json
import os
from typing import Dict, Any, List, Optional
from sqlalchemy import or_
from ..core.db import SessionLocal
from ..core import models

# ==============================================================================
# VALUE CAPTURE REFINEMENT (form-agnostic)
# ==============================================================================
_VALUE_LIKE_PATTERNS = [
    _re.compile(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$'),          # DD/MM/YYYY dates
    _re.compile(r'^\d{4}[/-]\d{1,2}[/-]\d{1,2}$'),          # YYYY/MM/DD dates
    _re.compile(r'^\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}$', _re.I),
    _re.compile(r'^[A-Za-z]+\s+\d{1,2},\s*\d{4}$'),         # January 1, 2025
    _re.compile(r'^[\d,]+(\.\d{1,2})?$'),                    # amounts like 5,00,00,000
    _re.compile(r'^(?:No|Yes|NA|N/A|Nil|None|True|False)$', _re.I),
]

def _is_value_like(term: str) -> bool:
    t = term.strip()
    if len(t) < 3:
        return True
    for pat in _VALUE_LIKE_PATTERNS:
        if pat.match(t):
            return True
    return False

def _capture_value_after_term(line: str, term: str) -> str:
    idx = line.lower().find(term.lower())
    if idx == -1:
        return ''
    after = line[idx + len(term):]
    colon_idx = after.rfind(':')
    if colon_idx != -1:
        after = after[colon_idx + 1:]
    after = after.strip(' :,-|•·\t').strip()
    candidate = after.split('\n')[0].strip()[:120]
    return candidate

def _is_capture_clean(candidate: str) -> bool:
    if not candidate:
        return False
    if ':' in candidate and len(candidate.split(':')) > 1:
        parts = candidate.split(':')
        if len(parts[-1].strip()) < 2:
            return False
    return True



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
    docs_paths: Optional[Dict[str, str]] = None,
    company_id: Optional[str] = None,
    scenario: Optional[str] = None
) -> Dict[str, Any]:
    """
    Applies IDP Studio spatial/alias mapping rules to extracted_data.
    Searches OCR text (from markdown files or direct PDF extraction via pdfplumber)
    for each rule's extracted_key / anchor and captures the following value.
    """
    rules = get_effective_rules(template_name, company_id=company_id, scenario=scenario)
    if not rules:
        db = SessionLocal()
        try:
            all_templates = [r[0] for r in db.query(models.SchemaAliasRule.template_name).distinct().all()]
        finally:
            db.close()
        for tn in all_templates:
            r = get_effective_rules(tn, company_id=company_id, scenario=scenario)
            if r:
                rules.update(r)
                print(f"[IDP Studio] Merged template: {tn} ({len(r)} rules)")
    if not rules:
        return extracted_data
    print(f"[IDP Studio] Found {len(rules)} cascaded spatial rules for {template_name} (Company: {company_id}, Scenario: {scenario}).")
    full_text = ""
    try:
        if isinstance(ocr_data, dict):
            for doc_key, doc_val in ocr_data.items():
                md_path = None
                if isinstance(doc_val, dict):
                    md_path = doc_val.get("md") or doc_val.get("markdown") or doc_val.get("text")
                elif isinstance(doc_val, str):
                    md_path = doc_val
                if md_path and os.path.exists(md_path):
                    try:
                        with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
                            full_text += "\n" + f.read()
                    except Exception:
                        pass
                if isinstance(doc_val, dict):
                    for k in ("text", "full_text", "content", "markdown"):
                        if doc_val.get(k) and isinstance(doc_val[k], str):
                            full_text += "\n" + doc_val[k]
        elif isinstance(ocr_data, str):
            full_text = ocr_data
        if not full_text.strip() and docs_paths:
            try:
                import pdfplumber
                for doc_key, pdf_path in docs_paths.items():
                    if isinstance(pdf_path, str) and pdf_path.lower().endswith(".pdf") and os.path.exists(pdf_path):
                        try:
                            with pdfplumber.open(pdf_path) as pdf:
                                for page in pdf.pages:
                                    t = page.extract_text()
                                    if t:
                                        full_text += "\n" + t
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        full_text = ""
    full_text = full_text or ""
    lines = full_text.splitlines()
    for field, rule in rules.items():
        try:
            val = None
            if isinstance(extracted_data, dict) and field in extracted_data and extracted_data[field] not in (None, "", "Unknown", "N/A"):
                val = extracted_data[field]
            meta = None
            sm = getattr(rule, "spatial_meta_json", None)
            if sm:
                try:
                    meta = json.loads(sm) if isinstance(sm, str) else sm
                except Exception:
                    meta = None
            anchor = None
            if meta:
                anchor = meta.get("anchor_text") or meta.get("anchor")
            search_terms = []
            if anchor and anchor.strip():
                search_terms.append(anchor.strip())
            ek = getattr(rule, "extracted_key", None)
            if ek and ek.strip():
                search_terms.append(ek.strip())
            if val is None and search_terms and lines:
                for term in search_terms:
                    # Skip terms that look like values (dates, amounts, short words)
                    if _is_value_like(term):
                        continue
                    term_l = term.lower()
                    found = False
                    for i, line in enumerate(lines):
                        if term_l in line.lower():
                            # Try same-line capture first (cleaned)
                            candidate = _capture_value_after_term(line, term)
                            if candidate and _is_capture_clean(candidate):
                                val = candidate
                                found = True
                                break
                            # Same-line not clean or empty: try next non-empty line(s)
                            for j in range(i + 1, min(i + 4, len(lines))):
                                nxt = lines[j].strip()
                                if nxt and not nxt.startswith("#"):
                                    val = nxt[:120]
                                    found = True
                                    break
                            if found:
                                break
                    if found:
                        break
            if val is None and ek and isinstance(ocr_data, dict) and ek in ocr_data:
                v = ocr_data[ek]
                if v not in (None, "", "Unknown", "N/A"):
                    val = v
            if val is not None and val not in ("", "Unknown", "N/A"):
                extracted_data[field] = val
                print(f"[IDP Spatial] {field} = {val!r} (key={ek!r})")
        except Exception as e:
            print(f"[IDP Spatial] Failed to apply rule for {field}: {e}")
    return extracted_data


