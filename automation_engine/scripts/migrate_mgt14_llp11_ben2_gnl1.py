#!/usr/bin/env python3
"""
Migration: MCA Universal Form Alignment & Schema Optimization
- MGT-14:
    * Field 3 ('Registration of'): Restore 'Resolution(s)' to options:
      ['Resolution(s)', 'Postal ballot resolution(s) under Section 110', 'Agreement']
    * Fields 4(a), 4(b), 5(a), 5(b) DAG dependencies aligned to Field 3
    * Field 6: type 'number', label 'Number of resolution(s) for which the form is being filed'
    * Details of resolution fields 6(a), 6(a)(i), 6(a)(ii), 6(b)(i), 6(b)(ii), 6(c)(i-ii), 6(d)(i-ii), 6(e-h)
- LLP-11:
    * Fields 7, 8: Clean table columns and canonical references (DPIN, PAN, Name, Contributions, Resident status, LLPs/Companies count)
    * Field 9: Summary table structure with canonical categories ((a) Individuals, (b) Bodies Corporate, Total) and contribution totals
- BEN-2:
    * Field 5(a)(i): Manual input number field (type 'number', options None, readonly False)
    * Field 6B: Structured 6B(a-e) subfields for member details
    * Field 6D: Structured 6D(a-g) subfields for SBO details
- GNL-1:
    * Strict use-case isolation with prune rules
"""

import sqlite3
import json
import shutil
import time
from pathlib import Path

DB_PATH = Path("automation_engine/modules/idp_studio/idp_studio.db")
SCHEMAS_DIR = Path("automation_engine/data/form_schemas")

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

    # =========================================================================
    # 1. FIX MGT-14
    # =========================================================================
    cursor.execute("SELECT template_id, fields_json FROM idp_templates WHERE template_name LIKE '%MGT-14%'")
    mgt_row = cursor.fetchone()
    if mgt_row:
        t_id, f_json = mgt_row[0], mgt_row[1]
        data = json.loads(f_json)
        fields = data.get("fields", [])
        
        # Build new MGT-14 fields adhering to official MCA V3 format
        mgt14_aligned_fields = [
            {
                "id": "formnomgt14.main.field_1",
                "canonical_no": "1",
                "canonical_field_no": "1",
                "label": "Corporate Identity Number (CIN)",
                "type": "text",
                "required": True,
                "options": None,
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_2a",
                "canonical_no": "2(a)",
                "canonical_field_no": "2(a)",
                "label": "Name of the Company",
                "type": "text",
                "required": True,
                "options": None,
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_2b",
                "canonical_no": "2(b)",
                "canonical_field_no": "2(b)",
                "label": "Address of the registered office of the company",
                "type": "textarea",
                "required": True,
                "options": None,
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_2c",
                "canonical_no": "2(c)",
                "canonical_field_no": "2(c)",
                "label": "Email ID of the company",
                "type": "text",
                "required": True,
                "options": None,
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_3",
                "canonical_no": "3",
                "canonical_field_no": "3",
                "label": "Registration of",
                "type": "select",
                "required": True,
                "options": [
                    "Resolution(s)",
                    "Postal ballot resolution(s) under Section 110",
                    "Agreement"
                ],
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_4a",
                "canonical_no": "4(a)",
                "canonical_field_no": "4(a)",
                "label": "Date of dispatch of notice for passing of resolution(s) (DD/MM/YYYY)",
                "type": "date",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)"]
                }
            },
            {
                "id": "formnomgt14.main.field_4b",
                "canonical_no": "4(b)",
                "canonical_field_no": "4(b)",
                "label": "Date of passing of resolution(s) (DD/MM/YYYY)",
                "type": "date",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)"]
                }
            },
            {
                "id": "formnomgt14.main.field_5a",
                "canonical_no": "5(a)",
                "canonical_field_no": "5(a)",
                "label": "Date of dispatch of notice for passing of postal ballot resolution(s) (DD/MM/YYYY)",
                "type": "date",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_5b",
                "canonical_no": "5(b)",
                "canonical_field_no": "5(b)",
                "label": "Date of passing of postal ballot resolution(s)",
                "type": "date",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6",
                "canonical_no": "6",
                "canonical_field_no": "6",
                "label": "Number of resolution(s) for which the form is being filed",
                "type": "number",
                "required": True,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6a",
                "canonical_no": "6(a)",
                "canonical_field_no": "6(a)",
                "label": "Details of the resolution",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6iai",
                "canonical_no": "6(a)(i)",
                "canonical_field_no": "6(a)(i)",
                "label": "Purpose of passing the resolution",
                "type": "select",
                "required": True,
                "options": [
                    "Alteration of Articles",
                    "Alteration in memorandum for change in name",
                    "Alteration in object clause",
                    "Issue of sweat equity shares",
                    "Issue of further shares to employees under scheme of employees stock option",
                    "Preferential or Private allotment",
                    "Voluntary liquidation under section 59",
                    "Others under Companies Act, 2013",
                    "Others under Insolvency and Bankruptcy Code, 2016"
                ],
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6iaii",
                "canonical_no": "6(a)(ii)",
                "canonical_field_no": "6(a)(ii)",
                "label": "Type of allotment of securities",
                "type": "select",
                "required": False,
                "options": [
                    "Issue of sweat equity shares",
                    "Issue of further shares to employees under scheme of employees stock option",
                    "Preferential or Private allotment",
                    "Issue of debentures with an option to convert such debentures into shares",
                    "Issue of bonus shares",
                    "Issue of preference shares",
                    "Others"
                ],
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6ibi",
                "canonical_no": "6(b)(i)",
                "canonical_field_no": "6(b)(i)",
                "label": "Section of the Companies Act, 2013 under which passed",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6ibii",
                "canonical_no": "6(b)(ii)",
                "canonical_field_no": "6(b)(ii)",
                "label": "Section of the Insolvency and Bankruptcy Code, 2016 under which passed",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6ici",
                "canonical_no": "6(c)(i)",
                "canonical_field_no": "6(c)(i)",
                "label": "If others, Mention the section of the Companies Act, 2013 under which passed",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_6iai",
                    "operator": "equals",
                    "value": "Others under Companies Act, 2013"
                }
            },
            {
                "id": "formnomgt14.main.field_6icii",
                "canonical_no": "6(c)(ii)",
                "canonical_field_no": "6(c)(ii)",
                "label": "If others, Mention the purpose of passing the resolution",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_6iai",
                    "operator": "equals",
                    "value": "Others under Companies Act, 2013"
                }
            },
            {
                "id": "formnomgt14.main.field_6idi",
                "canonical_no": "6(d)(i)",
                "canonical_field_no": "6(d)(i)",
                "label": "If others, Mention the section of the Insolvency and Bankruptcy Code, 2016 under which passed",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_6iai",
                    "operator": "equals",
                    "value": "Others under Insolvency and Bankruptcy Code, 2016"
                }
            },
            {
                "id": "formnomgt14.main.field_6idii",
                "canonical_no": "6(d)(ii)",
                "canonical_field_no": "6(d)(ii)",
                "label": "If others, Mention the purpose of passing the special resolution",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_6iai",
                    "operator": "equals",
                    "value": "Others under Insolvency and Bankruptcy Code, 2016"
                }
            },
            {
                "id": "formnomgt14.main.field_6ie",
                "canonical_no": "6(e)",
                "canonical_field_no": "6(e)",
                "label": "Subject matter of the resolution",
                "type": "textarea",
                "required": True,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6if",
                "canonical_no": "6(f)",
                "canonical_field_no": "6(f)",
                "label": "Mention whether resolution passed by postal ballot",
                "type": "radio",
                "required": True,
                "options": ["Yes", "No"],
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6ig",
                "canonical_no": "6(g)",
                "canonical_field_no": "6(g)",
                "label": "Indicate the authority passing or agreeing to the resolution",
                "type": "select",
                "required": True,
                "options": [
                    "Board of directors",
                    "Shareholders",
                    "Class of shareholders",
                    "Creditors"
                ],
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_6ih",
                "canonical_no": "6(h)",
                "canonical_field_no": "6(h)",
                "label": "Whether ordinary or special resolution or with requisite majority",
                "type": "select",
                "required": True,
                "options": [
                    "Ordinary resolution",
                    "Special resolution",
                    "Requisite majority"
                ],
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "in",
                    "value": ["Resolution(s)", "Postal ballot resolution(s) under Section 110"]
                }
            },
            {
                "id": "formnomgt14.main.field_7a",
                "canonical_no": "7(a)",
                "canonical_field_no": "7(a)",
                "label": "Is there any change in the industrial activity of the company",
                "type": "radio",
                "required": False,
                "options": ["Yes", "No"],
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_7b",
                "canonical_no": "7(b)",
                "canonical_field_no": "7(b)",
                "label": "Search and select industry sub- class",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_7a",
                    "operator": "equals",
                    "value": "Yes"
                }
            },
            {
                "id": "formnomgt14.main.field_7c",
                "canonical_no": "7(c)",
                "canonical_field_no": "7(c)",
                "label": "Main Sub-class of industrial activity of the company",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_7a",
                    "operator": "equals",
                    "value": "Yes"
                }
            },
            {
                "id": "formnomgt14.main.field_11",
                "canonical_no": "11",
                "canonical_field_no": "11",
                "label": "Service request number(SRN) of RUN Form",
                "type": "text",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_6iai",
                    "operator": "equals",
                    "value": "Alteration in memorandum for change in name"
                }
            },
            {
                "id": "formnomgt14.main.field_a",
                "canonical_no": "1",
                "canonical_field_no": "1",
                "label": "Copy(s) of resolution(s) along with copy of explanatory statement under section 102",
                "type": "file",
                "required": True,
                "options": None,
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_b",
                "canonical_no": "2",
                "canonical_field_no": "2",
                "label": "Copy of agreement",
                "type": "file",
                "required": False,
                "options": None,
                "depends_on": {
                    "field": "formnomgt14.main.field_3",
                    "operator": "equals",
                    "value": "Agreement"
                }
            },
            {
                "id": "formnomgt14.main.field_c",
                "canonical_no": "3",
                "canonical_field_no": "3",
                "label": "Optional attachment(s) - if any",
                "type": "file",
                "required": False,
                "options": None,
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_declaration_i_am_authorised",
                "canonical_no": "declaration",
                "canonical_field_no": "declaration",
                "label": "Declaration: I am authorised by the Board of Directors of the company vide resolution no and date to sign this form",
                "type": "text",
                "required": True,
                "options": None,
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_designation",
                "canonical_no": "designation",
                "canonical_field_no": "designation",
                "label": "Designation",
                "type": "select",
                "required": True,
                "options": [
                    "Director",
                    "Manager",
                    "Company Secretary",
                    "CEO",
                    "CFO",
                    "Insolvency Resolution professional (IRP)",
                    "Resolution professional (RP)",
                    "Liquidator"
                ],
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_director_identification_number_of",
                "canonical_no": "din_pan",
                "canonical_field_no": "din_pan",
                "label": "Director identification number of the director; or DIN or PAN of manager or CEO or CFO or IRP/RP/Liquidator; or Membership number of Company Secretary",
                "type": "text",
                "required": True,
                "options": None,
                "depends_on": None
            },
            {
                "id": "formnomgt14.main.field_certificate_by_practicing_professional",
                "canonical_no": "certification",
                "canonical_field_no": "certification",
                "label": "Certificate by Practicing Professional (Associate / Fellow)",
                "type": "select",
                "required": True,
                "options": ["Associate", "Fellow"],
                "depends_on": None
            }
        ]

        data["fields"] = mgt14_aligned_fields
        updated_json = json.dumps(data, indent=2)
        cursor.execute("UPDATE idp_templates SET fields_json = ? WHERE template_id = ?", (updated_json, t_id))
        
        # Also update json files on disk
        for p in [SCHEMAS_DIR / "Form_No__MGT-14.json", SCHEMAS_DIR / "formnomgt14.json", SCHEMAS_DIR / f"{t_id}.json"]:
            if p.exists() or p.name == "Form_No__MGT-14.json":
                with open(p, "w", encoding="utf-8") as f:
                    f.write(updated_json)
        print("[MGT-14] Updated schema with Field 3 'Resolution(s)' and aligned Field 6(a-h) block.")

    # =========================================================================
    # 2. FIX LLP-11
    # =========================================================================
    cursor.execute("SELECT template_id, fields_json FROM idp_templates WHERE template_name LIKE '%LLP%11%'")
    llp_row = cursor.fetchone()
    if llp_row:
        t_id, f_json = llp_row[0], llp_row[1]
        data = json.loads(f_json)
        fields = data.get("fields", [])

        # Standardized column definitions
        field_7_cols = [
            {"key": "designation", "label": "Designation", "type": "select", "options": ["Designated Partner", "Partner"], "required": True},
            {"key": "dpin_pan", "label": "DPIN / PAN / Passport", "type": "text", "required": True},
            {"key": "partner_name", "label": "Name of Partner", "type": "text", "required": True},
            {"key": "obligation_contribution", "label": "Obligation of Contribution (in ₹)", "type": "number", "required": True},
            {"key": "contribution_received", "label": "Contribution Received & Accounted for (in ₹)", "type": "number", "required": True},
            {"key": "is_resident", "label": "Resident in India", "type": "select", "options": ["Yes", "No"], "required": True},
            {"key": "llp_count", "label": "No. of LLPs as partner", "type": "number", "required": False},
            {"key": "company_count", "label": "No. of Companies as director", "type": "number", "required": False}
        ]

        field_8_cols = [
            {"key": "body_type", "label": "Type of Body Corporate", "type": "select", "options": ["LLP", "Company", "Foreign Body Corporate", "Others"], "required": True},
            {"key": "cin_llpin", "label": "CIN / LLPIN / Reg No.", "type": "text", "required": True},
            {"key": "company_name", "label": "Name of Body Corporate", "type": "text", "required": True},
            {"key": "obligation_contribution", "label": "Obligation of Contribution (in ₹)", "type": "number", "required": True},
            {"key": "contribution_received", "label": "Contribution Received & Accounted for (in ₹)", "type": "number", "required": True},
            {"key": "nominee_name", "label": "Name of Nominee", "type": "text", "required": True},
            {"key": "nominee_dpin", "label": "DPIN / PAN of Nominee", "type": "text", "required": True},
            {"key": "is_resident", "label": "Resident in India", "type": "select", "options": ["Yes", "No"], "required": True}
        ]

        field_9_cols = [
            {"key": "category", "label": "Category of Partner", "type": "text", "readonly": True, "required": True},
            {"key": "num_designated_partners", "label": "Number of Designated Partners", "type": "number", "required": True},
            {"key": "num_partners", "label": "Number of Partners", "type": "number", "required": True},
            {"key": "total_partners", "label": "Total Number of Partners", "type": "number", "required": True},
            {"key": "obligation_contribution", "label": "Obligation of Contribution (in ₹)", "type": "number", "required": True},
            {"key": "contribution_received", "label": "Contribution Received & Accounted for (in ₹)", "type": "number", "required": True}
        ]

        field_9_default_rows = [
            {"category": "(a) Individuals", "num_designated_partners": "", "num_partners": "", "total_partners": "", "obligation_contribution": "", "contribution_received": ""},
            {"category": "(b) Bodies Corporate", "num_designated_partners": "", "num_partners": "", "total_partners": "", "obligation_contribution": "", "contribution_received": ""},
            {"category": "Total", "num_designated_partners": "", "num_partners": "", "total_partners": "", "obligation_contribution": "", "contribution_received": ""}
        ]

        for f in fields:
            fid = f.get("id", "")
            if fid == "llpformno11.main.field_7":
                f["canonical_no"] = "7"
                f["canonical_field_no"] = "7"
                f["type"] = "table"
                f["label"] = "Detail of individual(s) as partners"
                f["columns"] = field_7_cols
            elif fid == "llpformno11.main.field_8":
                f["canonical_no"] = "8"
                f["canonical_field_no"] = "8"
                f["type"] = "table"
                f["label"] = "Details of bodies corporate as partners"
                f["columns"] = field_8_cols
            elif fid == "llpformno11.main.field_9":
                f["canonical_no"] = "9"
                f["canonical_field_no"] = "9"
                f["type"] = "table"
                f["label"] = "Summary of Designated Partner(s)/partner(s) as on 31st March of the period for which annual return is being filed"
                f["columns"] = field_9_cols
                f["default_rows"] = field_9_default_rows

        data["fields"] = fields
        updated_json = json.dumps(data, indent=2)
        cursor.execute("UPDATE idp_templates SET fields_json = ? WHERE template_id = ?", (updated_json, t_id))

        for p in [SCHEMAS_DIR / "LLP_Form_No__11.json", SCHEMAS_DIR / "llp_form_no_11.json", SCHEMAS_DIR / "llpformno11.json", SCHEMAS_DIR / f"{t_id}.json"]:
            if p.exists() or p.name == "LLP_Form_No__11.json":
                with open(p, "w", encoding="utf-8") as f:
                    f.write(updated_json)
        print("[LLP-11] Aligned Fields 7, 8, 9 columns and summary defaults.")

    # =========================================================================
    # 3. FIX BEN-2
    # =========================================================================
    cursor.execute("SELECT template_id, fields_json FROM idp_templates WHERE template_name LIKE '%BEN-2%'")
    ben_row = cursor.fetchone()
    if ben_row:
        t_id, f_json = ben_row[0], ben_row[1]
        data = json.loads(f_json)
        fields = data.get("fields", [])

        new_ben_fields = []
        for f in fields:
            fid = f.get("id", "")
            lbl = f.get("label", "")
            cno = str(f.get("canonical_no") or f.get("canonical_field_no") or "")

            # Field 5(a)(i): Manual input number
            if "field_5ai" in fid or cno == "5(a)(i)" or "number of significant beneficial owners for whom the form is being filed" in lbl.lower():
                f["canonical_no"] = "5(a)(i)"
                f["canonical_field_no"] = "5(a)(i)"
                f["type"] = "number"
                f["options"] = None
                f["readonly"] = False
                f["required"] = True
                new_ben_fields.append(f)
                continue

            # Field 6B: Expand collapsed 6B text into structured 6B(a-e) subfields
            if fid.endswith("field_6b") and not fid.endswith("field_6bf"):
                # Replace monolithic 6B field with structured subfields
                new_ben_fields.append({
                    "id": f"{fid}a",
                    "canonical_no": "6B(a)",
                    "canonical_field_no": "6B(a)",
                    "label": "Type of Member",
                    "type": "select",
                    "options": ["Company", "LLP", "Body Corporate", "Others"],
                    "required": True,
                    "depends_on": f.get("depends_on")
                })
                new_ben_fields.append({
                    "id": f"{fid}b",
                    "canonical_no": "6B(b)",
                    "canonical_field_no": "6B(b)",
                    "label": "CIN/ FCRN/ LLPIN or any other registration number",
                    "type": "text",
                    "required": True,
                    "options": None,
                    "depends_on": f.get("depends_on")
                })
                new_ben_fields.append({
                    "id": f"{fid}c",
                    "canonical_no": "6B(c)",
                    "canonical_field_no": "6B(c)",
                    "label": "Name of the Member",
                    "type": "text",
                    "required": True,
                    "options": None,
                    "depends_on": f.get("depends_on")
                })
                new_ben_fields.append({
                    "id": f"{fid}d",
                    "canonical_no": "6B(d)",
                    "canonical_field_no": "6B(d)",
                    "label": "Address of the Member",
                    "type": "textarea",
                    "required": True,
                    "options": None,
                    "depends_on": f.get("depends_on")
                })
                new_ben_fields.append({
                    "id": f"{fid}e",
                    "canonical_no": "6B(e)",
                    "canonical_field_no": "6B(e)",
                    "label": "Email ID of the Member",
                    "type": "text",
                    "required": True,
                    "options": None,
                    "depends_on": f.get("depends_on")
                })
                continue

            # Ensure canonical numbers on 6D fields
            if "field_6da" in fid and not "field_6dai" in fid:
                f["canonical_no"] = "6D(a)"
                f["canonical_field_no"] = "6D(a)"
            elif "field_6dai" in fid and not "field_6dai_2" in fid:
                f["canonical_no"] = "6D(a)(i)"
                f["canonical_field_no"] = "6D(a)(i)"
                f["type"] = "text"
            elif "field_6dai_2" in fid:
                f["canonical_no"] = "6D(a)(ii)"
                f["canonical_field_no"] = "6D(a)(ii)"
                f["type"] = "text"
            elif "field_6db" in fid:
                f["canonical_no"] = "6D(b)"
                f["canonical_field_no"] = "6D(b)"
            elif "field_6dc" in fid:
                f["canonical_no"] = "6D(c)"
                f["canonical_field_no"] = "6D(c)"
            elif "field_6dd" in fid:
                f["canonical_no"] = "6D(d)"
                f["canonical_field_no"] = "6D(d)"
            elif "field_6de" in fid:
                f["canonical_no"] = "6D(e)"
                f["canonical_field_no"] = "6D(e)"
            elif "field_6df" in fid:
                f["canonical_no"] = "6D(f)"
                f["canonical_field_no"] = "6D(f)"
            elif "field_6dg" in fid:
                f["canonical_no"] = "6D(g)"
                f["canonical_field_no"] = "6D(g)"

            new_ben_fields.append(f)

        data["fields"] = new_ben_fields
        updated_json = json.dumps(data, indent=2)
        cursor.execute("UPDATE idp_templates SET fields_json = ? WHERE template_id = ?", (updated_json, t_id))

        for p in [SCHEMAS_DIR / "Form_No__BEN-2.json", SCHEMAS_DIR / "formnoben2.json", SCHEMAS_DIR / f"{t_id}.json"]:
            if p.exists() or p.name == "Form_No__BEN-2.json":
                with open(p, "w", encoding="utf-8") as f:
                    f.write(updated_json)
        print("[BEN-2] Field 5(a)(i) set to manual input; expanded 6B(a-e) and aligned 6D(a-g).")

    # =========================================================================
    # 4. FIX GNL-1 (Schema DAG alignment)
    # =========================================================================
    cursor.execute("SELECT template_id, fields_json FROM idp_templates WHERE template_name LIKE '%GNL-1%'")
    gnl_row = cursor.fetchone()
    if gnl_row:
        t_id, f_json = gnl_row[0], gnl_row[1]
        data = json.loads(f_json)
        fields = data.get("fields", [])
        
        for f in fields:
            fid = f.get("id", "")
            if fid == "gnl1.main.field_1a":
                f["options"] = [
                    "Compounding of offences",
                    "Extension of period of annual general meeting by three months",
                    "Scheme of arrangement, amalgamation",
                    "Others"
                ]
            elif any(k in fid for k in ["field_8d", "field_8e", "field_8f", "field_8g", "field_8h", "field_8i", "field_8j", "field_8k", "field_8l", "field_8m", "field_8p", "field_8q"]):
                if not f.get("depends_on"):
                    f["depends_on"] = {
                        "field": "gnl1.main.field_1a",
                        "operator": "equals",
                        "value": "Compounding of offences"
                    }
            elif any(k in fid for k in ["field_9a", "field_9b", "field_9c"]):
                f["depends_on"] = {
                    "field": "gnl1.main.field_1a",
                    "operator": "equals",
                    "value": "Extension of period of annual general meeting by three months"
                }
            elif any(k in fid for k in ["field_10", "field_b"]):
                f["depends_on"] = {
                    "field": "gnl1.main.field_1a",
                    "operator": "equals",
                    "value": "Scheme of arrangement, amalgamation"
                }

        data["fields"] = fields
        updated_json = json.dumps(data, indent=2)
        cursor.execute("UPDATE idp_templates SET fields_json = ? WHERE template_id = ?", (updated_json, t_id))

        for p in [SCHEMAS_DIR / "GNL-1.json", SCHEMAS_DIR / f"{t_id}.json"]:
            if p.exists() or p.name == "GNL-1.json":
                with open(p, "w", encoding="utf-8") as f:
                    f.write(updated_json)
        print("[GNL-1] Verified and refreshed strict DAG dependencies on use cases.")

    conn.commit()
    conn.close()
    print("[Migration] All 4 forms migrated successfully.")

if __name__ == "__main__":
    run_migration()
