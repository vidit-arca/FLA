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
    print(f"[IDP Studio] Database and tables initialized in {os.path.join(DB_DIR, 'idp_studio.db')}")
