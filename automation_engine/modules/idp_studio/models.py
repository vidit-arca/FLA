# ==============================================================================
# IDP Studio ORM Models (Code-First Database Schema)
# ==============================================================================
# All models defined here are automatically created inside `/data/idp_studio.db`
# when the application starts via `idp_studio.db.init_db()`.
#
# HOW TO ADD A NEW TABLE (for DOM Learner or IDP Studio):
# 1. Define a new class inheriting from `Base`:
#      class MyNewTable(Base):
#          __tablename__ = "my_new_table"
#          id = Column(String, primary_key=True, index=True)
#          ...
# 2. Push this file (`models.py`) to Git.
# 3. Anyone running the server will automatically get your table in their local DB!
# ==============================================================================

from sqlalchemy import Column, String, Text, Integer, DateTime
import datetime
from .db import Base

class SchemaAliasRule(Base):
    __tablename__ = "idp_schema_alias_rules"

    rule_id = Column(String, primary_key=True, index=True)
    template_name = Column(String, index=True) # e.g. "FLA"
    form_field = Column(String, index=True)    # e.g. "net_worth" (The target field in the UI Form)
    extracted_key = Column(String)             # e.g. "Total Reserves and Surplus" (The key found by the PDF OCR engine)
    spatial_meta_json = Column(Text, nullable=True) # JSON containing anchor_text, dx, dy, width, height

class IdpTemplate(Base):
    __tablename__ = "idp_templates"

    template_id = Column(String, primary_key=True, index=True)
    template_name = Column(String)
    fields_json = Column(Text) # JSON serialized list of {id, label} objects


class DomExtractionRule(Base):
    __tablename__ = "idp_dom_extraction_rules"

    rule_id = Column(String, primary_key=True, index=True)
    
    # Context
    template_name = Column(String, index=True)      # e.g., "FLA"
    variable_name = Column(String, index=True)      # e.g., "Trade payables"
    
    # The actual rule
    dom_path = Column(String)                       # e.g., "section(...) → table(...) → row(...)"
    
    # Metrics for ordering/prioritizing rules
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    success_count = Column(Integer, default=0)      # To prioritize most successful paths
