#!/usr/bin/env python3
"""
Comprehensive Fix & Purge Script:
1. Purge all entity-specific data (CINs, Company names, addresses, emails, dates, personal names, account numbers, amounts)
   from `idp_schema_alias_rules` so they NEVER bleed into new company forms.
2. Fix INC-28 Field 5 template mismatch:
   - Field 5(a): Relevant act ('The Companies Act, 2013', 'The Companies Act, 1956', 'Others')
   - Field 5(b)(i): Section of the Companies Act, 2013 (clean 2013 section list, gated by 5a == 'The Companies Act, 2013')
   - Field 5(b)(ii): Section of the Companies Act, 1956 (clean 1956 section list, gated by 5a == 'The Companies Act, 1956')
3. Normalize GNL-1 template:
   - Field 3 (CIN) -> type: text, options: None
   - Field 4 (RoC) -> type: text, options: None
   - Field 1b/1c -> type: text, options: None
   - Clean up remaining identifier/declaration fields
"""

import sqlite3
import json
import re
import shutil
import time
from pathlib import Path

DB_PATH = Path("automation_engine/modules/idp_studio/idp_studio.db")
SCHEMAS_DIR = Path("automation_engine/data/form_schemas")

# Regex to detect entity-specific data that should NEVER be stored as a global alias rule
RE_ENTITY_VAL = [
    re.compile(r'\b[LUu][0-9]{5}[A-Za-z]{2}[0-9]{4}[A-Za-z]{3}[0-9]{6}\b'), # CIN
    re.compile(r'\b[A-Za-z]{3}-?[0-9]{4,7}\b'),                              # LLPIN
    re.compile(r'\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b'),                         # PAN
    re.compile(r'\b[0-9]{8}\b'),                                             # DIN
    re.compile(r'@'),                                                         # Email
    re.compile(r'\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\b'),                    # Date
    re.compile(r'(?:inr|rs\.?|₹)\s*[0-9,]+', re.IGNORECASE),                 # Monetary
    re.compile(r'\b(?:private\s+limited|pvt\s+ltd|pvt\.\s*ltd|limited|llp|ifsc)\b', re.IGNORECASE), # Company suffix
    re.compile(r'\b(?:plot\s+no|sector|flat\s+no|road|street|garden|kamothe|kanchipuram|nilgiris|ooty|raigarh)\b', re.IGNORECASE), # Address
    re.compile(r'\b(?:cp|ca|caa|nclt|slp|wp)[\s/]*\d+', re.IGNORECASE),      # Court cases
    re.compile(r'f\.no\.roc', re.IGNORECASE),                                # ROC notice
    re.compile(r'\b(?:mr\.|mrs\.|ms\.)\s+[A-Za-z]+', re.IGNORECASE),         # Personal names
    re.compile(r'^[0-9,]+(?:\.[0-9]+)?\*+$'),                                # Footnoted figures
    re.compile(r'^[0-9,]{4,}$'),                                             # Bare figures > 999
    re.compile(r'\bisin:\s*', re.IGNORECASE),                                # ISIN
]

def is_bogus_entity_rule(key: str, scope_type: str) -> bool:
    if not key:
        return True
    k = str(key).strip()
    if scope_type == "DIRECT_SELECTION":
        # Direct selections of 'Yes' or 'No' are legitimate statutory constants
        return k.lower() not in ["yes", "no"]
    
    for pat in RE_ENTITY_VAL:
        if pat.search(k):
            return True
            
    # Long text paragraphs are narrative entity facts, not field aliases
    if len(k) > 70:
        return True
    return False

def clean_database_and_templates():
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} not found!")
        return

    backup_path = DB_PATH.parent / f"idp_studio_backup_{int(time.time())}.db"
    shutil.copy2(DB_PATH, backup_path)
    print(f"[Backup] Created database backup at {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Purge bogus entity rules from idp_schema_alias_rules
    cursor.execute("SELECT rule_id, template_name, form_field, extracted_key, scope_type FROM idp_schema_alias_rules")
    all_rules = cursor.fetchall()
    purged_count = 0
    kept_count = 0

    for rule_id, t_name, f_field, ex_key, s_type in all_rules:
        if is_bogus_entity_rule(ex_key, s_type):
            cursor.execute("DELETE FROM idp_schema_alias_rules WHERE rule_id = ?", (rule_id,))
            purged_count += 1
            print(f"[Purge] Deleted rule: [{t_name}] {f_field} -> '{ex_key}' ({s_type})")
        else:
            kept_count += 1

    print(f"\n[Alias Rules] Purged {purged_count} entity contaminant rules. Kept {kept_count} clean statutory aliases/constants.")

    # 2. Fix INC-28 Field 5 Template Mismatch
    cursor.execute("SELECT template_id, fields_json FROM idp_templates WHERE template_name LIKE '%INC-28%'")
    row = cursor.fetchone()
    if row:
        t_id, f_json = row
        data = json.loads(f_json)
        fields = data.get("fields", [])
        
        sections_2013 = [
            "12(6) - Change in Registered Office from one RoC to another within the same State",
            "13(7) - Change in Registered Office from one State to another",
            "48(4) - Variation of shareholders rights",
            "58(5) - Refusal of registration and appeal against refusal",
            "66(5) - Reduction of Share capital",
            "87 - Condonation of delay / rectification in register of charges",
            "111(3) - Circulation of members resolution",
            "230(8) - Compromise and arrangement",
            "232 - Amalgamation",
            "233(7) - Fast track merger or amalgamation",
            "234 - Merger involving foreign company",
            "237 - Amalgamation by Central Government",
            "252(2) - Appeal against order of ROC",
            "441 - Compounding order passed by NCLT",
            "Others"
        ]
        
        sections_1956 = [
            "17(1) - Alteration of Memorandum",
            "81(4) - Increase in subscribed capital",
            "107(3) - Rights of holders of special classes of shares",
            "167 - Power of Central Government to call general meeting",
            "186 - Power of Court to order meeting to be called",
            "391 - Compromise and arrangement",
            "394(1) - Amalgamation",
            "396 - Central Government amalgamation",
            "397 - Prevention of oppression",
            "398 - Prevention of mismanagement",
            "445 - Copy of winding up order to be filed with Registrar",
            "466 - Stay of winding up",
            "481 - Dissolution of company by Court",
            "518 - Power to apply to Court in voluntary winding up",
            "559 - Power of Court to declare dissolution of company void",
            "621A - Compounding of offences",
            "Others"
        ]

        new_fields = []
        has_5bii = False

        for f in fields:
            fid = f.get("id", "")
            cno = str(f.get("canonical_no", "")).strip()

            if fid == "formnoinc28.main.field_5a" or cno == "5(a)":
                f["canonical_no"] = "5(a)"
                f["label"] = "Relevant act under which order is passed"
                f["type"] = "radio"
                f["options"] = ["The Companies Act, 2013", "The Companies Act, 1956", "Others"]
                f["depends_on"] = None
                new_fields.append(f)
            elif fid == "formnoinc28.main.field_5bi" or cno in ["5(b)(i)", "5(b)"]:
                f["canonical_no"] = "5(b)(i)"
                f["label"] = "Section of the Companies Act, 2013 under which order passed"
                f["type"] = "select"
                f["options"] = sections_2013
                f["depends_on"] = {
                    "field": "formnoinc28.main.field_5a",
                    "operator": "equals",
                    "value": "The Companies Act, 2013"
                }
                new_fields.append(f)
            elif fid == "formnoinc28.main.field_5bii" or cno == "5(b)(ii)":
                has_5bii = True
                f["canonical_no"] = "5(b)(ii)"
                f["label"] = "Section of the Companies Act, 1956 under which order passed"
                f["type"] = "select"
                f["options"] = sections_1956
                f["depends_on"] = {
                    "field": "formnoinc28.main.field_5a",
                    "operator": "equals",
                    "value": "The Companies Act, 1956"
                }
                new_fields.append(f)
            else:
                new_fields.append(f)

        if not has_5bii:
            new_fields.append({
                "id": "formnoinc28.main.field_5bii",
                "canonical_no": "5(b)(ii)",
                "label": "Section of the Companies Act, 1956 under which order passed",
                "type": "select",
                "required": False,
                "options": sections_1956,
                "depends_on": {
                    "field": "formnoinc28.main.field_5a",
                    "operator": "equals",
                    "value": "The Companies Act, 1956"
                },
                "validation": {},
                "instructions": "Select section under Companies Act, 1956 if applicable."
            })

        data["fields"] = new_fields
        cursor.execute("UPDATE idp_templates SET fields_json = ? WHERE template_id = ?", (json.dumps(data), t_id))
        
        # Also update JSON schema file in SCHEMAS_DIR
        for p in SCHEMAS_DIR.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f_in:
                    f_content = json.load(f_in)
                if "INC-28" in f_content.get("form_name", ""):
                    f_content["fields"] = new_fields
                    with open(p, "w", encoding="utf-8") as f_out:
                        json.dump(f_content, f_out, indent=2)
                    print(f"[INC-28] Updated cached schema file: {p.name}")
            except Exception:
                pass
        print("[INC-28] Successfully updated Field 5(a), 5(b)(i) and 5(b)(ii) canonical options and DAG gating.")

    # 3. Normalize GNL-1 Template
    cursor.execute("SELECT template_id, fields_json FROM idp_templates WHERE template_name LIKE '%GNL-1%'")
    gnl_row = cursor.fetchone()
    if gnl_row:
        gt_id, gf_json = gnl_row
        g_data = json.loads(gf_json)
        g_fields = g_data.get("fields", [])

        for gf in g_fields:
            gid = gf.get("id", "")
            gcno = str(gf.get("canonical_no", "")).strip()

            # Field 3: CIN must be text
            if gid == "gnl1.main.field_3" or gcno == "3":
                gf["type"] = "text"
                gf["options"] = None
            # Field 4: RoC office must be text
            elif gid == "gnl1.main.field_4" or gcno == "4":
                gf["type"] = "text"
                gf["options"] = None
            # Field 1b: Specify purpose
            elif gid == "gnl1.main.field_1b" or gcno == "1(b)":
                gf["type"] = "text"
                gf["options"] = None
            # Field 1c: Specify section
            elif gid == "gnl1.main.field_1c" or gcno == "1(c)":
                gf["type"] = "text"
                gf["options"] = None
            # Signatory and professional fields
            elif "to_be_digitaly_signed" in gid or "certificate_by_practicing" in gid or "director_identification_number_of" in gid:
                gf["type"] = "text"
                gf["options"] = None

        g_data["fields"] = g_fields
        cursor.execute("UPDATE idp_templates SET fields_json = ? WHERE template_id = ?", (json.dumps(g_data), gt_id))
        
        # Also update JSON schema file for GNL-1
        gnl_file = SCHEMAS_DIR / "GNL-1.json"
        if gnl_file.exists():
            with open(gnl_file, "w", encoding="utf-8") as f_out:
                json.dump(g_data, f_out, indent=2)
            print("[GNL-1] Updated cached schema file: GNL-1.json")
        print("[GNL-1] Normalized template fields (CIN, RoC, Purpose, Signatories).")

    conn.commit()
    conn.close()
    print("\n[Complete] Database and schema migrations applied successfully.")

if __name__ == "__main__":
    clean_database_and_templates()
