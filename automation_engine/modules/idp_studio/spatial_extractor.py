import re
from typing import Dict, Any
from .db import SessionLocal
from . import models

def get_spatial_rules(template_name: str) -> Dict[str, models.SpatialRule]:
    """Fetches all spatial rules for a given template as a dictionary keyed by field_name."""
    db = SessionLocal()
    try:
        rules = db.query(models.SpatialRule).filter(models.SpatialRule.template_name == template_name).all()
        return {r.field_name: r for r in rules}
    except Exception as e:
        print(f"[IDP Studio] Error fetching rules: {e}")
        return {}
    finally:
        db.close()

def apply_spatial_overrides(template_name: str, ocr_data: Dict[str, Any], extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Checks if there are any IDP spatial rules for this template.
    If yes, attempts to extract the fields based on bounding box mathematics 
    and overrides the standard regex/keyword extraction in `extracted_data`.
    """
    rules = get_spatial_rules(template_name)
    if not rules:
        return extracted_data # Fallback to standard flow (Zero-Touch)
        
    print(f"[IDP Studio] Found {len(rules)} spatial rules for {template_name}. Attempting overrides...")
    
    # In a full implementation, this is where we would:
    # 1. Search the PDF/OCR Bounding Box data for the `anchor_text`.
    # 2. Get the (X, Y) coordinates of the anchor.
    # 3. Apply the rule's `x_offset` and `y_offset` to find the target Region of Interest (ROI).
    # 4. Extract text from the ROI and update `extracted_data[field_name] = value`.
    
    # For now, this serves as the injection point stub.
    # We will expand this logic in Phase 3 once the OCR payload format is integrated.
    
    return extracted_data
