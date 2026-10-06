from api.database import SessionLocal
from api.models import ExtractionTask
db = SessionLocal()
task = db.query(ExtractionTask).order_by(ExtractionTask.id.desc()).first()
print("Status:", task.status)
print("Logs:", task.logs)
