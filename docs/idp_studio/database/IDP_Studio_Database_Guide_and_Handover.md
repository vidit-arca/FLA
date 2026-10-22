# 🗄️ IDP Studio — Code-First Database Guide & Developer Handover

> **Project:** Foreign Liabilities & Assets (FLA) / IDP Studio Automation Engine  
> **Module:** `automation_engine/modules/idp_studio`  
> **Target Audience:** IDP Studio & DOM Learner Developers  

---

## 1. What Changes We Made & Why (Architectural Rationale)

We have transitioned IDP Studio from an ad-hoc SQLite setup to a professional **Code-First ORM Database Architecture**. 

### Why We Do NOT Push `.db` Files to Git
1. **Binary Merge Conflicts:** SQLite `.db` files are binary. If two developers modify tables or insert data and push their `.db` files, Git cannot merge them—resulting in database corruption or overwritten work.
2. **Repository Bloat:** Every commit containing a `.db` binary file permanently inflates the Git repository history.
3. **Local Contamination:** Staging, test, and developer databases should remain isolated and never overwrite one another.

### What We Implemented Instead
We modified three key files to automate schema synchronization through Git code:

| File Modified | What Changed | Why It Was Done |
| :--- | :--- | :--- |
| [idp_studio/db.py](file:///Users/apple/Desktop/FLA/automation_engine/modules/idp_studio/db.py) | Configured connection to `/data/idp_studio.db` and added `init_db()`. | Isolates IDP Studio tables from `fla_tasks.db` and enables automated schema creation. |
| [idp_studio/models.py](file:///Users/apple/Desktop/FLA/automation_engine/modules/idp_studio/models.py) | Standardized SQLAlchemy declarative models (`SchemaAliasRule`, `IdpTemplate`). | Serves as the **single source of truth** for database tables in Git. |
| [api/main.py](file:///Users/apple/Desktop/FLA/automation_engine/api/main.py#L30) | Invoked `idp_studio.db.init_db()` during application startup. | Ensures any developer who runs the backend server gets `/data/idp_studio.db` created automatically zero-touch. |

---

## 2. Developer Guide: How to Use `idp_studio.db`

### A. How to Create a New Table (for DOM Learner or IDP Rules)
Whenever you need a new database table, **do not create it manually in SQLite**. Define it as a Python class inside [models.py](file:///Users/apple/Desktop/FLA/automation_engine/modules/idp_studio/models.py):

```python
# In automation_engine/modules/idp_studio/models.py
from sqlalchemy import Column, String, Text, Integer
from .db import Base

class DomLearnerRule(Base):
    __tablename__ = "dom_learner_rules"

    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String(100), index=True)
    field_label = Column(String(100))
    structural_path_json = Column(Text)
```

1. Save [models.py](file:///Users/apple/Desktop/FLA/automation_engine/modules/idp_studio/models.py).
2. Start the backend server (`python -m uvicorn main:app --reload`).
3. **What happens:** `init_db()` automatically detects `DomLearnerRule` and creates the `dom_learner_rules` table inside your local `/data/idp_studio.db`!

---

### B. How to Share Your New Table with the Team
When you want to give the team access to your new table, simply commit and push your code:

```bash
git add automation_engine/modules/idp_studio/models.py
git commit -m "feat: add DomLearnerRule table to IDP Studio schema"
git push origin main
```
* **Why this works:** When another developer runs `git pull` and starts their app, `init_db()` automatically builds your new table in their local database!

---

### C. How to Query or Insert Data in Python Code

#### Option 1: Inside FastAPI Route Handlers (Recommended)
Use the `get_db` dependency to inject an auto-managed database session:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .db import get_db
from . import models

router = APIRouter()

@router.post("/dom-learner/save-rule")
def save_rule(template_name: str, path_json: str, db: Session = Depends(get_db)):
    new_rule = models.DomLearnerRule(
        template_name=template_name,
        structural_path_json=path_json
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule
```

#### Option 2: Inside Standalone Scripts or Background Tasks
If you are writing a script outside FastAPI, use `SessionLocal` directly:

```python
from automation_engine.modules.idp_studio.db import SessionLocal
from automation_engine.modules.idp_studio import models

def run_script():
    db = SessionLocal()
    try:
        rules = db.query(models.DomLearnerRule).all()
        print(f"Found {len(rules)} rules.")
    finally:
        db.close()
```

---

## 3. Operational Do's and Don'ts

| Scenario | Professional Workflow (DO) | What NOT to Do (DON'T) |
| :--- | :--- | :--- |
| **Adding a Table** | Write a class in [models.py](file:///Users/apple/Desktop/FLA/automation_engine/modules/idp_studio/models.py) and push `models.py` to Git. | Don't open DB Browser for SQLite, create a table manually, and push `.db`. |
| **Sharing Default Data** | Write an idempotent Python seed script (`seed_idp.py`) and push the script. | Don't insert rows into your local `.db` and expect others to see them. |
| **Resetting Your DB** | Delete `/data/idp_studio.db` locally and restart the app (`uvicorn main:app`). | Don't copy `.db` files from another developer's computer. |
