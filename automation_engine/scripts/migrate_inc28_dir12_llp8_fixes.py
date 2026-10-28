#!/usr/bin/env python3
"""
Migration: Statutory MCA Form Alignment & Schema Cleanups
- INC-28: Field 12(e) -> number, Field 17 DAG cleanup (17a date, 17b radio Yes/No, 17b(i) cin, 17b(ii) date).
- DIR-12: Field 3 -> text header (reject options bleed), Field 3(r) -> dynamic table gated by 3(a) appointment.
- LLP-8: Purge hardcoded entity financial figures leaking as extracted_key in alias rules.
"""

import sqlite3
import json
import shutil
import time
from pathlib import Path

DB_PATH = Path("automation_engine/modules/idp_studio/idp_studio.db")

def run_migration():
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} not found!")
        return

    # 1. Backup DB
    backup_path = DB_PATH.parent / f"idp_studio_backup_{int(time.time())}.db"
    shutil.copy2(DB_PATH, backup_path)
    print(f"[Backup] Created database backup at {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Fix INC-28
    cursor.execute("SELECT template_id, fields_json FROM idp_templates WHERE template_name LIKE '%INC%28%'")
    row = cursor.fetchone()
    if row:
        t_id, f_json = row[0], row[1]
        data = json.loads(f_json)
        fields = data.get("fields", [])
        new_fields = []
        found_17b_i = False
        found_17b_ii = False

        for f in fields:
            fid = f.get("id", "")
            cno = str(f.get("canonical_no", "")).strip()

            if fid == "formnoinc28.main.field_12e" or cno == "12(e)":
                f["type"] = "number"
                f["options"] = None
                new_fields.append(f)
            elif fid == "formnoinc28.main.field_17a" or cno == "17(a)":
                f["canonical_no"] = "17(a)"
                f["label"] = "Date with effect from which dissolution has been declared as void under section 559 of The Companies Act, 1956"
                f["type"] = "date"
                f["options"] = None
                f["depends_on"] = None
                new_fields.append(f)
            elif fid == "formnoinc28.main.field_17b_2":
                # Obsolete spurious field - drop it
                continue
            elif fid == "formnoinc28.main.field_17b" or cno == "17(b)":
                f["canonical_no"] = "17(b)"
                f["label"] = "Whether the order is in respect of company dissolved under section 394 of The Companies Act, 1956"
                f["type"] = "radio"
                f["options"] = ["Yes", "No"]
                f["depends_on"] = None
                new_fields.append(f)
            elif fid == "formnoinc28.main.field_17b_i" or cno == "17(b)(i)":
                found_17b_i = True
                f["canonical_no"] = "17(b)(i)"
                f["label"] = "CIN or FCRN"
                f["type"] = "cin"
                f["options"] = None
                f["depends_on"] = {
                    "field": "formnoinc28.main.field_17b",
                    "operator": "equals",
                    "value": "Yes"
                }
                new_fields.append(f)
            elif fid == "formnoinc28.main.field_17b_ii" or cno == "17(b)(ii)":
                found_17b_ii = True
                f["canonical_no"] = "17(b)(ii)"
                f["label"] = "Date of amalgamation"
                f["type"] = "date"
                f["options"] = None
                f["depends_on"] = {
                    "field": "formnoinc28.main.field_17b",
                    "operator": "equals",
                    "value": "Yes"
                }
                new_fields.append(f)
            else:
                new_fields.append(f)

        if not found_17b_i:
            new_fields.append({
                "id": "formnoinc28.main.field_17b_i",
                "canonical_no": "17(b)(i)",
                "label": "CIN or FCRN",
                "type": "cin",
                "options": None,
                "required": True,
                "section": "main",
                "depends_on": {
                    "field": "formnoinc28.main.field_17b",
                    "operator": "equals",
                    "value": "Yes"
                },
                "validation_rules": [],
                "is_prefilled": False,
                "prefill_source": None
            })
        if not found_17b_ii:
            new_fields.append({
                "id": "formnoinc28.main.field_17b_ii",
                "canonical_no": "17(b)(ii)",
                "label": "Date of amalgamation",
                "type": "date",
                "options": None,
                "required": True,
                "section": "main",
                "depends_on": {
                    "field": "formnoinc28.main.field_17b",
                    "operator": "equals",
                    "value": "Yes"
                },
                "validation_rules": [],
                "is_prefilled": False,
                "prefill_source": None
            })

        data["fields"] = new_fields
        cursor.execute("UPDATE idp_templates SET fields_json = ? WHERE template_id = ?", (json.dumps(data), t_id))
        print(f"[INC-28] Updated schema: 12(e) -> number, 17(a)/(b) statutory DAG aligned.")

    # 3. Fix DIR-12
    cursor.execute("SELECT template_id, fields_json FROM idp_templates WHERE template_name LIKE '%DIR%12%'")
    row = cursor.fetchone()
    if row:
        t_id, f_json = row[0], row[1]
        data = json.loads(f_json)
        fields = data.get("fields", [])
        new_fields = []
        found_3r = False

        table_3r_cols = [
            {"key": "cin_llpin", "label": "CIN / LLPIN / FCRN / Registration No", "type": "text", "required": True},
            {"key": "name", "label": "Name of Entity", "type": "text", "required": True},
            {"key": "address", "label": "Address", "type": "text", "required": True},
            {"key": "designation", "label": "Designation", "type": "text", "required": True},
            {"key": "percentage_share", "label": "% Share / Amount of Contribution", "type": "number", "required": True}
        ]

        table_3r_depends = {
            "field": "formnodir12.main.field_3a",
            "operator": "in",
            "value": [
                "Appointment",
                "Appointment due to disqualification of all the existing directors",
                "Appointment by liquidator"
            ]
        }

        for f in fields:
            fid = f.get("id", "")
            cno = str(f.get("canonical_no", "")).strip()

            if fid == "formnodir12.main.field_3" or cno == "3":
                f["label"] = "Details of the Managing Director or Director of the company"
                f["type"] = "text"
                f["options"] = None
                new_fields.append(f)
            elif fid == "formnodir12.main.field_3r" or cno in ["3(r)", "3r"]:
                found_3r = True
                f["label"] = "Interest in other entities"
                f["type"] = "table"
                f["table_archetype"] = "web_dynamic_grid"
                f["options"] = None
                f["repeat_count_field"] = None
                f["min_rows"] = 1
                f["max_rows"] = 50
                f["columns"] = table_3r_cols
                f["table_metadata"] = {
                    "table_archetype": "web_dynamic_grid",
                    "columns": table_3r_cols,
                    "default_rows": []
                }
                f["depends_on"] = table_3r_depends
                new_fields.append(f)
            else:
                new_fields.append(f)

        if not found_3r:
            new_fields.append({
                "id": "formnodir12.main.field_3r",
                "canonical_no": "3(r)",
                "label": "Interest in other entities",
                "type": "table",
                "table_archetype": "web_dynamic_grid",
                "required": False,
                "section": "main",
                "options": None,
                "columns": table_3r_cols,
                "table_metadata": {
                    "table_archetype": "web_dynamic_grid",
                    "columns": table_3r_cols,
                    "default_rows": []
                },
                "depends_on": table_3r_depends,
                "validation_rules": []
            })

        data["fields"] = new_fields
        cursor.execute("UPDATE idp_templates SET fields_json = ? WHERE template_id = ?", (json.dumps(data), t_id))
        print(f"[DIR-12] Updated schema: 3 -> text header (options cleared), 3(r) -> dynamic table gated by 3(a) appointment.")

    # 4. Clean up bogus LLP-8 rules holding hardcoded values as extracted_key
    bogus_keys = [
        '1,42,46,303', '22.09.99.672', '3,05,53,654', '41,96,20,818',
        '6,06,10,272', '16,18,87,529', '10,46,28,834', '11,03,73,152',
        '92,69,33,736', '41,92,498', '1,22,15,91,745', '5,91,79,213',
        'AAP-3112'
    ]
    cursor.execute("""
        DELETE FROM idp_schema_alias_rules
        WHERE template_name LIKE '%LLP Form No. 8%'
          AND extracted_key IN ({})
    """.format(','.join(['?']*len(bogus_keys))), bogus_keys)
    deleted_count = cursor.rowcount
    print(f"[LLP-8] Purged {deleted_count} bogus hardcoded financial alias rules.")

    conn.commit()
    conn.close()
    print("[Migration] Success: Database updated idempotently.")

if __name__ == "__main__":
    run_migration()
