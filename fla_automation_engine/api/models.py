from sqlalchemy import Column, String, DateTime, JSON, Text
from .database import Base
from datetime import datetime
import uuid

class ExtractionTask(Base):
    __tablename__ = "extraction_tasks"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    company_name = Column(String, index=True)
    status = Column(String, default="pending") # pending, processing, review_needed, completed, error
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    input_dir = Column(String)
    extracted_data = Column(JSON, nullable=True)
    logs = Column(Text, default="")
    output_excel = Column(String, nullable=True)
