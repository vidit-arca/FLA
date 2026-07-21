from sqlalchemy import Column, String, Text
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
