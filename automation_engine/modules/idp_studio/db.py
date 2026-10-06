import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Create isolated DB inside idp_studio/ directory (automation_engine/modules/idp_studio/idp_studio.db)
DB_DIR = os.path.dirname(os.path.abspath(__file__))
SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(DB_DIR, 'idp_studio.db')}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Automatically creates the isolated idp_studio.db file and generates all tables
    defined in models.py (zero-touch schema initialization).
    """
    from . import models
    Base.metadata.create_all(bind=engine)

    # Safe auto-migration: check if document_type column exists, if not add it
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            for tbl in ["idp_schema_alias_rules", "idp_dom_extraction_rules"]:
                try:
                    res = conn.execute(text(f"PRAGMA table_info({tbl})")).fetchall()
                    col_names = [r[1] for r in res]
                    if "document_type" not in col_names:
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN document_type VARCHAR DEFAULT 'generic'"))
                        print(f"[IDP DB] Added 'document_type' column to {tbl}")
                except Exception as mig_err:
                    print(f"[IDP DB] Migration check on {tbl}: {mig_err}")

            # Auto-tag FORM ABT rules to their respective document types based on field names
            try:
                # Consent letter / appointment letter fields: FRN and Auditor Category
                conn.execute(text("""
                    UPDATE idp_schema_alias_rules 
                    SET document_type = 'consent_letter' 
                    WHERE template_name = 'FORM ABT' 
                      AND (form_field LIKE '%firmregistration%' OR form_field LIKE '%categoryofauditor%')
                      AND (document_type IS NULL OR document_type = 'generic')
                """))
                # Board resolution fields: Firm Name, Company Name, Registered Address, CIN
                conn.execute(text("""
                    UPDATE idp_schema_alias_rules 
                    SET document_type = 'board_resolution' 
                    WHERE template_name = 'FORM ABT' 
                      AND (form_field LIKE '%nameoftheauditorsfirm%' OR form_field LIKE '%nameofthecompany%' OR form_field LIKE '%addressoftheregistered%' OR form_field LIKE '%corporateidentity%')
                      AND (document_type IS NULL OR document_type = 'generic')
                """))
            except Exception as tag_err:
                print(f"[IDP DB] Auto-tag error: {tag_err}")
    except Exception as e:
        print(f"[IDP DB] Init error: {e}")

    print(f"[IDP Studio] Database and tables initialized in {os.path.join(DB_DIR, 'idp_studio.db')}")

