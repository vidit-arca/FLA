"""
migrate_gnl2_schema.py
======================
ONE-SHOT migration script that repairs the GNL-2 schema stored in idp_studio.db.

Fixes applied:
  A1 - Insert missing Section 1 fields: 1(b) Name, 1(c) Address, 1(d) Email
  A2 - Fix attachment fields 7(f)-(o): type=select -> type=checkbox, clear junk options
  A3 - Split field_r label: separate "Optional attachment(s)" from the verification declaration
       Add new field_verification as a separate date field
  A4 - Fix signatory block field types:
         field_to_be_digitally_signed       -> type=dsc_block, options=[]
         field_particulars_of_the_person    -> type=signatory, options=[]
         field_director_identification_...  -> type=text,      options=[]
         field_to_be_digitally_signed_2     -> type=dsc_block, options=[]
  A5 - Fix field_4b, field_4bi, field_4bi_2, field_4bii: clear junk options
       (they are free-text section number fields, not dropdowns)

Run once:
  cd automation_engine
  python3 scripts/migrate_gnl2_schema.py
"""

import sqlite3
import json
import os
import shutil
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "modules", "idp_studio", "idp_studio.db")
DB_PATH = os.path.abspath(DB_PATH)

BACKUP_PATH = DB_PATH + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def migrate():
    # --- Backup first ---
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"[Backup] Saved to: {BACKUP_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT fields_json FROM idp_templates WHERE template_name='GNL-2'")
    row = cur.fetchone()
    if not row:
        print("[ERROR] GNL-2 not found in idp_templates!")
        conn.close()
        return

    data = json.loads(row[0])
    fields = data.get("fields", [])
    print(f"[INFO] Loaded GNL-2 with {len(fields)} fields.")

    # Build index lookup by field id for targeted edits
    idx_map = {f.get("id"): i for i, f in enumerate(fields) if isinstance(f, dict)}

    # ----------------------------------------------------------------
    # A1 — Insert 1(b), 1(c), 1(d) after field_1 (index 0)
    # ----------------------------------------------------------------
    new_sec1_fields = [
        {
            "id": "gnl2.main.field_1b",
            "label": "Name of the Company",
            "type": "text",
            "options": [],
            "canonical_no": "1(b)",
            "readonly": True,
            "is_active": True,
        },
        {
            "id": "gnl2.main.field_1c",
            "label": "Registered Office Address",
            "type": "text",
            "options": [],
            "canonical_no": "1(c)",
            "readonly": True,
            "is_active": True,
        },
        {
            "id": "gnl2.main.field_1d",
            "label": "Email ID",
            "type": "text",
            "options": [],
            "canonical_no": "1(d)",
            "readonly": True,
            "is_active": True,
        },
    ]
    # Only insert if not already present
    existing_ids = set(f.get("id") for f in fields if isinstance(f, dict))
    if "gnl2.main.field_1b" not in existing_ids:
        field_1_idx = idx_map.get("gnl2.main.field_1", 0)
        for i, nf in enumerate(new_sec1_fields):
            fields.insert(field_1_idx + 1 + i, nf)
        print("[A1] Inserted 1(b), 1(c), 1(d) fields.")
    else:
        print("[A1] 1(b)/1(c)/1(d) already present — skipping.")

    # Rebuild index map after insert
    idx_map = {f.get("id"): i for i, f in enumerate(fields) if isinstance(f, dict)}

    # ----------------------------------------------------------------
    # A2 — Fix attachment fields (f)-(o): select -> checkbox
    # ----------------------------------------------------------------
    checkbox_ids = [
        "gnl2.main.field_f",
        "gnl2.main.field_g",
        "gnl2.main.field_h",
        "gnl2.main.field_i",
        "gnl2.main.field_j",
        "gnl2.main.field_k",
        "gnl2.main.field_l",
        "gnl2.main.field_m",
        "gnl2.main.field_n",
        "gnl2.main.field_o",
        "gnl2.main.field_p",
        "gnl2.main.field_q",
    ]
    for fid in checkbox_ids:
        if fid in idx_map:
            fields[idx_map[fid]]["type"] = "checkbox"
            fields[idx_map[fid]]["options"] = []
            print(f"[A2] Fixed {fid}: type=checkbox, options=[]")

    # ----------------------------------------------------------------
    # A3 — Split field_r: attachment checkbox + separate verification
    # ----------------------------------------------------------------
    if "gnl2.main.field_r" in idx_map:
        r_idx = idx_map["gnl2.main.field_r"]
        fields[r_idx]["type"] = "checkbox"
        fields[r_idx]["options"] = []
        fields[r_idx]["label"] = "Optional attachment(s) - if any"
        print("[A3] Fixed field_r: type=checkbox, label trimmed.")

    # Insert verification field after field_r (if not exists)
    if "gnl2.main.field_verification" not in idx_map:
        r_idx = idx_map.get("gnl2.main.field_r", len(fields) - 1)
        verification_field = {
            "id": "gnl2.main.field_verification",
            "label": (
                "I have been authorised by a resolution of the Board of Directors "
                "of the company. Resolution No. and date (DD/MM/YYYY)"
            ),
            "type": "date",
            "options": [],
            "canonical_no": "verification",
            "is_active": True,
        }
        fields.insert(r_idx + 1, verification_field)
        print("[A3] Inserted field_verification (declaration block).")

    # Rebuild index map after insert
    idx_map = {f.get("id"): i for i, f in enumerate(fields) if isinstance(f, dict)}

    # ----------------------------------------------------------------
    # A4 — Fix signatory block field types
    # ----------------------------------------------------------------
    sig_fixes = {
        "gnl2.main.field_to_be_digitaly_signed":               ("dsc_block", []),
        "gnl2.main.field_particulars_of_the_person":           ("signatory", []),
        "gnl2.main.field_director_identification_number_of":   ("text",      []),
        "gnl2.main.field_to_be_digitaly_signed_2":             ("dsc_block", []),
    }
    for fid, (new_type, new_opts) in sig_fixes.items():
        if fid in idx_map:
            fields[idx_map[fid]]["type"] = new_type
            fields[idx_map[fid]]["options"] = new_opts
            print(f"[A4] Fixed {fid}: type={new_type}")

    # ----------------------------------------------------------------
    # A5 — Fix 4(b) sub-fields: these are free-text section number
    #      boxes, not dropdowns. Clear the junk options.
    # ----------------------------------------------------------------
    sec4b_ids = [
        "gnl2.main.field_4b",
        "gnl2.main.field_4bi",
        "gnl2.main.field_4bi_2",
        "gnl2.main.field_4bii",
    ]
    for fid in sec4b_ids:
        if fid in idx_map:
            fields[idx_map[fid]]["type"] = "text"
            fields[idx_map[fid]]["options"] = []
            print(f"[A5] Fixed {fid}: type=text, options=[]  (was select with junk options)")

    # ----------------------------------------------------------------
    # Write back
    # ----------------------------------------------------------------
    data["fields"] = fields
    new_json = json.dumps(data, ensure_ascii=False)
    cur.execute(
        "UPDATE idp_templates SET fields_json = ? WHERE template_name = 'GNL-2'",
        (new_json,),
    )
    conn.commit()
    conn.close()

    print(f"\n[DONE] GNL-2 schema updated. Total fields now: {len(fields)}")
    print(f"       Backup at: {BACKUP_PATH}")


if __name__ == "__main__":
    migrate()
