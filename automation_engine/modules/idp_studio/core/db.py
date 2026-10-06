import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Keep existing DB file location in idp_studio/ directory
IDP_STUDIO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(IDP_STUDIO_DIR, "idp_studio.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

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

    # Safe auto-migration: check if multi-tenant scoping and document_type columns exist
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
                    if "scope_type" not in col_names:
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN scope_type VARCHAR DEFAULT 'GLOBAL'"))
                        print(f"[IDP DB] Added 'scope_type' column to {tbl}")
                    if "scope_id" not in col_names:
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN scope_id VARCHAR DEFAULT 'default'"))
                        print(f"[IDP DB] Added 'scope_id' column to {tbl}")
                    if "priority" not in col_names:
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN priority INTEGER DEFAULT 1"))
                        print(f"[IDP DB] Added 'priority' column to {tbl}")
                except Exception as mig_err:
                    print(f"[IDP DB] Migration check on {tbl}: {mig_err}")


            # Auto-tag FORM ABT rules to their respective document types based on field names
            try:
                conn.execute(text("""
                    UPDATE idp_schema_alias_rules 
                    SET document_type = 'consent_letter' 
                    WHERE template_name = 'FORM ABT' 
                      AND (form_field LIKE '%firmregistration%' OR form_field LIKE '%categoryofauditor%')
                      AND (document_type IS NULL OR document_type = 'generic')
                """))
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

    print(f"[IDP Studio] Database and tables initialized in {DB_PATH}")
