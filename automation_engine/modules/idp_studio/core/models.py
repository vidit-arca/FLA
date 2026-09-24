# ==============================================================================
# IDP Studio ORM Models (Code-First Database Schema)
# ==============================================================================

from sqlalchemy import Column, String, Text, Integer, DateTime
import datetime
from .db import Base

class SchemaAliasRule(Base):
    __tablename__ = "idp_schema_alias_rules"

    rule_id = Column(String, primary_key=True, index=True)
    template_name = Column(String, index=True) # e.g. "ADT-1", "FLA"
    
    # Hierarchical Scoping Columns
    scope_type = Column(String, index=True, default="GLOBAL")   # "GLOBAL" | "SCENARIO" | "COMPANY"
    scope_id = Column(String, index=True, default="default")     # "default" | scenario_name | company_cin
    priority = Column(Integer, default=1)                       # 1 = Global, 2 = Scenario, 3 = Company
    
    document_type = Column(String, index=True, default="generic", nullable=True) # e.g. "board_resolution", "consent_letter"
    form_field = Column(String, index=True)    # e.g. "net_worth" (The target field in the UI Form)
    extracted_key = Column(String)             # e.g. "Total Reserves and Surplus" (The key found by the PDF OCR engine)
    spatial_meta_json = Column(Text, nullable=True) # JSON containing anchor_text, dx, dy, width, height

# Backward compatibility alias
SpatialRule = SchemaAliasRule


class IdpTemplate(Base):
    __tablename__ = "idp_templates"

    template_id = Column(String, primary_key=True, index=True)
    template_name = Column(String)
    fields_json = Column(Text) # JSON serialized list of {id, label} objects


class DomExtractionRule(Base):
    __tablename__ = "idp_dom_extraction_rules"

    rule_id = Column(String, primary_key=True, index=True)
    
    # Context & Scoping
    template_name = Column(String, index=True)      # e.g., "FLA", "ADT-1"
    scope_type = Column(String, index=True, default="GLOBAL")   # "GLOBAL" | "SCENARIO" | "COMPANY"
    scope_id = Column(String, index=True, default="default")     # "default" | scenario_name | company_cin
    priority = Column(Integer, default=1)                       # 1 = Global, 2 = Scenario, 3 = Company
    
    document_type = Column(String, index=True, default="generic", nullable=True) # e.g., "board_resolution", "consent_letter"
    variable_name = Column(String, index=True)      # e.g., "Trade payables"
    
    # The actual rule
    dom_path = Column(String)                       # e.g., "section(...) → table(...) → row(...)"
    
    # Metrics for ordering/prioritizing rules
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    success_count = Column(Integer, default=0)      # To prioritize most successful paths
