"""
Universal Engine-Level Fix Test Suite.

Covers:
1. FieldNormalizer unit tests (count guards, code guards, instruction header sanitization, provenance).
2. Semantic Branch Detection across branching and non-branching forms (ADT-1, DIR-12, GNL-1, MGT-14, PAS-6, GNL-2, FLA, etc.).
3. Signatory Role Semantic Isolation (Director DIN vs Manager/CS Membership, ambiguous roles preservation).
4. Unseen form dynamic validation without per-form exceptions.
5. Malformed instruction-kit schema resilience.
"""

import pytest
import copy
from automation_engine.modules.idp_studio.forms.normalizer import FieldNormalizer
from automation_engine.modules.idp_studio.forms.registry import FormRegistry
from automation_engine.modules.idp_studio.core.db import SessionLocal


# ==============================================================================
# 1. FIELD NORMALIZER UNIT TESTS
# ==============================================================================

class TestFieldNormalizer:
    def test_numeric_count_field_enforcement(self):
        """Counts like 'Number of resolution(s)' must become type 'number' and lose bleed options."""
        raw_field = {
            "id": "formnomgt14.main.field_6",
            "label": "Number of resolution(s) for which the form is being filed",
            "type": "select",
            "options": ["1", "2", "3", "4", "5", "Alteration in memorandum for change in name"]
        }
        norm_f, corrections = FieldNormalizer.normalize_field(raw_field)

        assert norm_f["type"] == "number"
        assert norm_f["options"] is None
        assert norm_f["provenance"]["original_type"] == "select"
        assert any(c["rule"] == "count_field_enforce_number" for c in corrections)
        assert any(c["rule"] == "reject_instruction_bleed_in_count_options" for c in corrections)

    def test_identifier_exclusion_from_count_guards(self):
        """Director DIN and CS Membership fields must never be misclassified as numeric counts."""
        din_field = {
            "id": "gnl2.main.field_director_identification_number_of",
            "label": "Director identification number of the director",
            "type": "text",
            "options": None
        }
        norm_din, corrections_din = FieldNormalizer.normalize_field(din_field)
        assert norm_din["type"] == "text"
        assert len(corrections_din) == 0

        cs_field = {
            "id": "field_cs_membership",
            "label": "Membership number of the company secretary",
            "type": "text",
            "options": None
        }
        norm_cs, corrections_cs = FieldNormalizer.normalize_field(cs_field)
        assert norm_cs["type"] == "text"
        assert len(corrections_cs) == 0

    def test_classification_code_pseudo_boolean_rejection(self):
        """Sub-class and NIC code fields must reject pseudo-boolean options and normalize to text."""
        raw_subclass = {
            "id": "formnomgt14.main.field_7b",
            "label": "Search and select industry sub- class",
            "type": "select",
            "options": ["Yes"]
        }
        norm_f, corrections = FieldNormalizer.normalize_field(raw_subclass)
        assert norm_f["type"] == "text"
        assert norm_f["options"] is None
        assert any(c["rule"] == "code_field_reject_spurious_boolean_options" for c in corrections)

        raw_subclass_multi = {
            "id": "formnomgt14.main.field_7c",
            "label": "Main Sub-class of industrial activity of the company",
            "type": "select",
            "options": ["Yes", "Type of Company", "IFSC Company"]
        }
        norm_f2, corrections2 = FieldNormalizer.normalize_field(raw_subclass_multi)
        assert norm_f2["type"] == "text"
        assert norm_f2["options"] is None
        assert any(c["rule"] == "code_field_reject_spurious_boolean_options" for c in corrections2)

    def test_instruction_header_row_artifact_rejection(self):
        """Instruction kit table headers like 'Resolution(s)' must be stripped from options."""
        raw_field = {
            "id": "formnomgt14.main.field_6iai",
            "label": "Purpose of passing the resolution",
            "type": "select",
            "options": ["Resolution(s)", "Alteration in memorandum for change in name", "Voluntary liquidation under section 59"]
        }
        norm_f, corrections = FieldNormalizer.normalize_field(raw_field)
        assert norm_f["type"] == "select"
        assert "Resolution(s)" not in norm_f["options"]
        assert len(norm_f["options"]) == 2
        assert any(c["rule"] == "reject_instruction_header_option" for c in corrections)

    def test_degenerate_single_option_select_converted_to_text(self):
        """A select field with only 1 option cannot function as a dropdown and must convert to text."""
        raw_field = {
            "id": "field_single_opt",
            "label": "Specific Category",
            "type": "select",
            "options": ["Only One Choice"]
        }
        norm_f, corrections = FieldNormalizer.normalize_field(raw_field)
        assert norm_f["type"] == "text"
        assert norm_f["options"] is None
        assert any(c["rule"] == "convert_insufficient_options_to_text" for c in corrections)

    def test_full_schema_normalization_and_audit(self):
        """Full schema normalization must produce an audit trail and preserve unmodified fields."""
        schema = {
            "form_id": "test_form",
            "form_name": "Test Form",
            "fields": [
                {"id": "f1", "label": "Company CIN", "type": "cin"},
                {"id": "f2", "label": "Number of directors", "type": "text"},
                {"id": "f3", "label": "Date of meeting", "type": "date"}
            ]
        }
        norm_schema, audit = FieldNormalizer.normalize_schema(schema)
        assert norm_schema["fields"][0]["type"] == "cin"
        assert norm_schema["fields"][1]["type"] == "number"
        assert norm_schema["fields"][2]["type"] == "date"
        assert len(audit) == 1
        assert audit[0]["field_id"] == "f2"


# ==============================================================================
# 2. SEMANTIC BRANCH DETECTION TESTS (BRANCHING VS NON-BRANCHING)
# ==============================================================================

class TestSemanticBranchDetection:
    @staticmethod
    def _evaluate_branching(schema: dict):
        """Mirror the universal semantic branch detection algorithm."""
        fields = schema.get("fields", [])
        parent_counts = {}
        for f in fields:
            dep = f.get("depends_on")
            if dep and isinstance(dep, dict) and dep.get("field"):
                pf = dep["field"]
                parent_counts[pf] = parent_counts.get(pf, 0) + 1

        BRANCH_FIELD_SIGNALS = [
            "nature of appointment",
            "type of appointment",
            "basis of appointment",
            "purpose of filing",
            "nature of filing",
            "category of applicant",
            "purpose of application",
            "type of resolution",
            "statement of account",
        ]

        branch_field = None
        # Criterion 1: Root field with >= 2 candidate options driving >= 2 DAG dependents
        if parent_counts:
            sorted_parents = sorted(parent_counts.items(), key=lambda x: x[1], reverse=True)
            for parent_id, dep_count in sorted_parents:
                if dep_count >= 2:
                    matched_f = next(
                        (f for f in fields if f.get("id") == parent_id and f.get("options") and len(f.get("options")) >= 2),
                        None
                    )
                    if matched_f:
                        branch_field = matched_f
                        break

        # Criterion 2: Parent field matching statutory branch signals with >= 2 options and >= 1 dependent
        if not branch_field:
            for fld in fields:
                field_label_lower = fld.get("label", "").lower()
                field_options = fld.get("options") or []
                if len(field_options) >= 2 and any(sig in field_label_lower for sig in BRANCH_FIELD_SIGNALS):
                    if parent_counts.get(fld.get("id"), 0) >= 1:
                        branch_field = fld
                        break

        has_branches = branch_field is not None
        return has_branches, branch_field

    def test_branching_forms_detected(self):
        """Forms with divergent statutory pathways must be detected as branching."""
        db = SessionLocal()
        try:
            branching_templates = ["ADT-1", "DIR-12", "GNL-1", "Form No. MGT-14", "BEN-2"]
            for t_id in branching_templates:
                schema = FormRegistry.get_form_schema(t_id, db)
                assert schema is not None, f"Schema for {t_id} should exist in database"
                has_branches, b_field = self._evaluate_branching(schema)
                assert has_branches is True, f"Form {t_id} must be detected as branching"
                assert b_field is not None
                assert len(b_field.get("options", [])) >= 2
        finally:
            db.close()

    def test_non_branching_forms_flat(self):
        """Flat omnibus forms must NEVER be flagged as branching (0 false positives)."""
        db = SessionLocal()
        try:
            flat_templates = ["PAS -6", "Form MGT-6", "GNL-2", "Form No. MGT-7", "INC-20A"]
            for t_id in flat_templates:
                schema = FormRegistry.get_form_schema(t_id, db)
                if not schema:
                    continue
                has_branches, b_field = self._evaluate_branching(schema)
                assert has_branches is False, f"Flat form {t_id} must NOT be detected as branching"
                assert b_field is None
        finally:
            db.close()

    def test_unseen_form_dynamic_branch_detection(self):
        """A previously unseen form with conditional DAG gating must be recognized dynamically."""
        unseen_branching_schema = {
            "form_id": "FORM_UNSEEN_NEW",
            "form_name": "Form Unseen Dynamic",
            "fields": [
                {
                    "id": "unseen.root_selector",
                    "label": "Purpose of filing application",
                    "type": "select",
                    "options": ["Merger", "Demerger", "Capital Reduction"]
                },
                {
                    "id": "unseen.child_merger_details",
                    "label": "Details of Transferor Company",
                    "type": "text",
                    "depends_on": {"field": "unseen.root_selector", "value": "Merger"}
                },
                {
                    "id": "unseen.child_demerger_details",
                    "label": "Details of Resulting Company",
                    "type": "text",
                    "depends_on": {"field": "unseen.root_selector", "value": "Demerger"}
                }
            ]
        }
        has_branches, b_field = self._evaluate_branching(unseen_branching_schema)
        assert has_branches is True
        assert b_field["id"] == "unseen.root_selector"

    def test_unseen_form_flat_with_multi_option_dropdown(self):
        """A previously unseen flat form with a multi-option select must NOT trigger false positive."""
        unseen_flat_schema = {
            "form_id": "FORM_UNSEEN_FLAT",
            "form_name": "Flat Registration Form",
            "fields": [
                {
                    "id": "unseen.state_selector",
                    "label": "State of registered office",
                    "type": "select",
                    "options": ["Maharashtra", "Karnataka", "Delhi", "Gujarat", "Tamil Nadu"]
                },
                {
                    "id": "unseen.pincode",
                    "label": "PIN Code",
                    "type": "text"
                }
            ]
        }
        has_branches, b_field = self._evaluate_branching(unseen_flat_schema)
        assert has_branches is False
        assert b_field is None


# ==============================================================================
# 3. SIGNATORY ROLE MUTUAL EXCLUSIVITY & AMBIGUITY TESTS
# ==============================================================================

class TestSignatoryRoleResolution:
    def test_director_role_exclusivity(self):
        """If signatory designation is Director, DIN is assigned to Director slot and blocked from Manager/CS."""
        from automation_engine.modules.idp_studio.router import _find_field_value

        field_def_dir = {
            "id": "mgt14.main.field_director_din",
            "label": "Director identification number of the director",
            "canonical_no": "dir_din"
        }
        field_def_kmp = {
            "id": "mgt14.main.field_manager_or_sec",
            "label": "Manager or CEO or CFO or Membership number of the company secretary",
            "canonical_no": "kmp_id"
        }

        mapped_data = {
            "designation": "Director",
            "din": "01234567"
        }

        matched_keys = set()
        val_dir = _find_field_value(field_def_dir, mapped_data, matched_keys=matched_keys)
        assert val_dir == "01234567"

        # KMP/Secretary field must strictly return None when designation is Director
        val_kmp = _find_field_value(field_def_kmp, mapped_data, matched_keys=matched_keys)
        assert val_kmp is None

    def test_company_secretary_role_exclusivity(self):
        """If signatory designation is Company Secretary, Membership is assigned to CS slot and blocked from Director."""
        from automation_engine.modules.idp_studio.router import _find_field_value

        field_def_dir = {
            "id": "mgt14.main.field_director_din",
            "label": "Director identification number of the director",
            "canonical_no": "dir_din"
        }
        field_def_kmp = {
            "id": "mgt14.main.field_manager_or_sec",
            "label": "Manager or CEO or CFO or Membership number of the company secretary",
            "canonical_no": "kmp_id"
        }

        mapped_data = {
            "designation": "Company Secretary",
            "membership_number": "A12345"
        }

        matched_keys = set()
        val_dir = _find_field_value(field_def_dir, mapped_data, matched_keys=matched_keys)
        assert val_dir is None

        val_kmp = _find_field_value(field_def_kmp, mapped_data, matched_keys=matched_keys)
        assert val_kmp == "A12345"

    def test_ambiguous_signatory_role_no_cross_bleed(self):
        """When designation is missing, Director DIN must not bleed into Secretary slot."""
        from automation_engine.modules.idp_studio.router import _find_field_value

        field_def_kmp = {
            "id": "mgt14.main.field_manager_or_sec",
            "label": "Manager or CEO or CFO or Membership number of the company secretary",
            "canonical_no": "kmp_id"
        }

        mapped_data = {
            "din": "09876543"
        }

        matched_keys = set()
        val_kmp = _find_field_value(field_def_kmp, mapped_data, matched_keys=matched_keys)
        # DIN must NOT bleed into Manager or CS field
        assert val_kmp is None


# ==============================================================================
# 4. SUBFIELD BOUNDARY ISOLATION & STRUCTURAL HEADER SHIELDING TESTS
# ==============================================================================

class TestSubfieldBoundaryIsolationAndStructuralHeaders:
    def test_parent_subfield_token_isolation(self):
        """field_3 must NOT match field_3a data, and field_4 must NOT match field_4p/4q across ANY form."""
        from automation_engine.modules.idp_studio.router import resolve_field_value

        field_def_3 = {
            "id": "formmgt6.main.field_3",
            "label": "Particulars of shares in respect of which declaration under section 89 is filed",
            "canonical_no": "3",
            "type": "text"
        }
        field_def_3a = {
            "id": "formmgt6.main.field_3a",
            "label": "Number of shares",
            "canonical_no": "3a",
            "type": "number"
        }

        # Data contains only 3a
        mapped_data = {
            "formmgt6.main.field_3a": "25000"
        }

        matched_keys_3 = set()
        val_3 = resolve_field_value(field_def_3, mapped_data, matched_keys=matched_keys_3)
        # field_3 must NOT steal field_3a's value!
        assert val_3 is None

        matched_keys_3a = set()
        val_3a = resolve_field_value(field_def_3a, mapped_data, matched_keys=matched_keys_3a)
        assert val_3a == "25000"

    def test_structural_header_shields_scalar_numbers(self):
        """Section header rows starting with 'Particulars of...' or 'Details of...' must never absorb scalar numeric inputs."""
        from automation_engine.modules.idp_studio.router import resolve_field_value

        header_field_def = {
            "id": "formnomgt14.main.field_6",
            "label": "Particulars of resolution passed under section 179 and details of resolution passed under section 180 of the Act",
            "canonical_no": "6",
            "type": "text"
        }
        leaf_count_field = {
            "id": "formnomgt14.main.field_6_count",
            "label": "Number of resolution(s)",
            "canonical_no": "6_count",
            "type": "number"
        }

        mapped_data = {
            "field_6": "5"
        }

        matched_keys = set()
        val_header = resolve_field_value(header_field_def, mapped_data, matched_keys=matched_keys)
        # Structural header row must reject the scalar number "5"
        assert val_header is None

    def test_subfield_date_collisions_isolated(self):
        """field_4p (Date of Entry), field_4q (Date of Declaration), and field_4r (Date of Receipt) must never swap or bleed."""
        from automation_engine.modules.idp_studio.router import resolve_field_value

        f4p = {"id": "formmgt6.main.field_4p", "label": "Date of entry of name in register of members", "canonical_no": "4p", "type": "date"}
        f4q = {"id": "formmgt6.main.field_4q", "label": "Date of declaration by registered owner", "canonical_no": "4q", "type": "date"}
        f4r = {"id": "formmgt6.main.field_4r", "label": "Date of receipt of declaration by the company", "canonical_no": "4r", "type": "date"}

        mapped_data = {
            "formmgt6.main.field_4p": "10/01/2023",
            "formmgt6.main.field_4q": "15/04/2024",
            "formmgt6.main.field_4r": "20/04/2024"
        }

        m_keys = set()
        assert resolve_field_value(f4p, mapped_data, matched_keys=m_keys) == "10/01/2023"
        assert resolve_field_value(f4q, mapped_data, matched_keys=m_keys) == "15/04/2024"
        assert resolve_field_value(f4r, mapped_data, matched_keys=m_keys) == "20/04/2024"


# ==============================================================================
# 5. MULTI-DATE STATUTORY EXTRACTION DISAMBIGUATION TESTS
# ==============================================================================

class TestMultiDateDisambiguation:
    def test_section_89_and_statutory_multi_date_extraction(self):
        """Disambiguate Date of Entry, Date of Declaration, and Date of Receipt without string prefix collision."""
        from automation_engine.modules.idp_studio.router import _fast_path_extract_mca_fields

        synthetic_ocr_text = """
        FORM MGT-6
        DECLARATION OF BENEFICIAL INTEREST IN SHARES
        [Pursuant to section 89 of Companies Act, 2013]

        The name of the holder was entered in the register of members on 05/01/2022.
        Declaration dated 12/03/2024 was solemnly affirmed and declared by the registered owner.
        The date of receipt of declaration by the company was 18/03/2024.
        Total number of shares: 15,000 Equity Shares.
        """

        field_label_map = {
            "formmgt6.main.field_3a": "Number of shares",
            "formmgt6.main.field_4p": "Date of entry of name in register of members",
            "formmgt6.main.field_4q": "Date of declaration",
            "formmgt6.main.field_4r": "Date of receipt of declaration by the company",
        }

        extracted = _fast_path_extract_mca_fields(synthetic_ocr_text, "Form MGT-6", field_label_map)

        assert extracted.get("formmgt6.main.field_3a") == "15000"
        assert extracted.get("formmgt6.main.field_4p") == "05/01/2022"
        assert extracted.get("formmgt6.main.field_4q") == "12/03/2024"
        assert extracted.get("formmgt6.main.field_4r") == "18/03/2024"


class TestTableReconstructionAndPdfPlacement:
    """
    Validates universal table reconstruction and ensures no constituent table keys
    leak into the end of generated statutory PDFs.
    """

    def test_inc20a_table_reconstruction_and_no_trailing_values(self):
        from automation_engine.modules.idp_studio.router import resolve_field_value, _create_dynamic_statutory_form_pdf
        from automation_engine.modules.idp_studio.forms.registry import FormRegistry

        schema = FormRegistry.get_form_schema("Form INC-20A")
        assert schema is not None, "Form INC-20A schema must be registered"

        table_field = next(f for f in schema["fields"] if f.get("type") == "table" or "4table" in f.get("id", ""))
        assert table_field is not None

        # Scenario 1: Mapped data contains indexed cells
        mapped_data = {
            "formnoinc20a.main.field_1": "U72900KA2024PTC123456",
            "formnoinc20a.main.field_4table[0].shareholder_name": "Ramesh Kumar",
            "formnoinc20a.main.field_4table[0].bank_name": "State Bank of India",
            "formnoinc20a.main.field_4table[0].account_number": "1234567890",
            "formnoinc20a.main.field_4table[0].date_of_receipt": "15/04/2024",
            "formnoinc20a.main.field_4table[0].amount_of_receipt": "500000",
        }
        matched_keys = set()
        resolved_rows = resolve_field_value(table_field, mapped_data, matched_keys)

        assert isinstance(resolved_rows, list)
        assert len(resolved_rows) >= 1
        assert resolved_rows[0]["shareholder_name"] == "Ramesh Kumar"
        assert resolved_rows[0]["bank_name"] == "State Bank of India"
        assert "formnoinc20a.main.field_4table[0].shareholder_name" in matched_keys
        assert "formnoinc20a.main.field_4table[0].bank_name" in matched_keys

        # Generate PDF and ensure no trailing dump of table cells
        doc = _create_dynamic_statutory_form_pdf("Form INC-20A", mapped_data)
        assert doc is not None

        full_pdf_text = "".join(page.get_text() for page in doc)

        # Table values appear in table, not as '*Field 4Table[0].Shareholder Name' at the end
        assert "*Field 4Table[0].Shareholder Name" not in full_pdf_text
        assert "*Formnoinc20A.Main.Field 4Table[0]" not in full_pdf_text

    def test_inc28_field_13_table_reconstruction(self):
        from automation_engine.modules.idp_studio.router import resolve_field_value, _create_dynamic_statutory_form_pdf
        from automation_engine.modules.idp_studio.forms.registry import FormRegistry

        schema = FormRegistry.get_form_schema("Form No. INC-28")
        assert schema is not None

        table_13a = next(f for f in schema["fields"] if f.get("id") == "formnoinc28.main.field_13a" or f.get("canonical_no") == "13A")

        mapped_data = {
            "formnoinc28.main.field_1": "L24220MH1945PLC004598",
            "formnoinc28.main.field_13a[0].share_type": "Equity",
            "formnoinc28.main.field_13a[0].class_of_share": "Equity Shares",
            "formnoinc28.main.field_13a[0].nominal_value": "10",
            "formnoinc28.main.field_13a[0].num_shares": "1000000",
            "formnoinc28.main.field_13a[0].total_amount": "10000000",
        }
        matched_keys = set()
        resolved_rows = resolve_field_value(table_13a, mapped_data, matched_keys)

        assert isinstance(resolved_rows, list)
        assert len(resolved_rows) >= 1
        assert resolved_rows[0]["share_type"] == "Equity"
        assert resolved_rows[0]["total_amount"] == "10000000"

        # Verify PDF shields constituent keys
        doc = _create_dynamic_statutory_form_pdf("Form No. INC-28", mapped_data)
        pdf_text = "".join(p.get_text() for p in doc)
        assert "*Field 13A[0]" not in pdf_text


class TestINC28StatutorySchemaAndDAG:
    """
    Validates INC-28 Field 12(e) count enforcement and statutory Field 17 DAG branch alignment.
    """

    def test_inc28_field_12e_numeric_manual_input(self):
        from automation_engine.modules.idp_studio.forms.normalizer import FieldNormalizer

        raw_field = {
            "id": "formnoinc28.main.field_12e",
            "canonical_no": "12(e)",
            "label": "Number of transferor company(s)",
            "type": "select",
            "options": ["Transferee company", "Category of transferor company", "SRN of Form INC-28"],
            "required": True
        }

        normalized, corrections = FieldNormalizer.normalize_field(raw_field)
        assert normalized["type"] == "number"
        assert normalized["options"] is None, "Options bleed must be purged from count fields"
        assert any(c["rule"] == "count_field_enforce_number" for c in corrections)

    def test_inc28_field_17_dag_alignment(self):
        from automation_engine.modules.idp_studio.forms.registry import FormRegistry

        schema = FormRegistry.get_form_schema("Form No. INC-28")
        fields_by_id = {f["id"]: f for f in schema["fields"]}

        f_17a = fields_by_id.get("formnoinc28.main.field_17a")
        f_17b = fields_by_id.get("formnoinc28.main.field_17b")
        f_17b_i = fields_by_id.get("formnoinc28.main.field_17b_i")
        f_17b_ii = fields_by_id.get("formnoinc28.main.field_17b_ii")

        assert f_17a is not None and f_17a["type"] == "date"
        assert f_17b is not None and f_17b["type"] == "radio"
        assert f_17b.get("options") == ["Yes", "No"]
        assert f_17b_i is not None and f_17b_i["type"] == "cin"
        assert f_17b_i.get("depends_on") == {
            "field": "formnoinc28.main.field_17b",
            "operator": "equals",
            "value": "Yes"
        }
        assert f_17b_ii is not None and f_17b_ii["type"] == "date"
        assert f_17b_ii.get("depends_on") == {
            "field": "formnoinc28.main.field_17b",
            "operator": "equals",
            "value": "Yes"
        }
        # Spurious 17b_2 must not exist
        assert "formnoinc28.main.field_17b_2" not in fields_by_id


class TestDIR12StatutorySchemaAndDAG:
    """
    Validates DIR-12 Field 3 section header and Field 3(r) dynamic table conditional presence.
    """

    def test_dir12_field_3_and_3r_schema(self):
        from automation_engine.modules.idp_studio.forms.registry import FormRegistry

        schema = FormRegistry.get_form_schema("Form No. DIR-12")
        fields_by_id = {f["id"]: f for f in schema["fields"]}

        f_3 = fields_by_id.get("formnodir12.main.field_3")
        f_3a = fields_by_id.get("formnodir12.main.field_3a")
        f_3r = fields_by_id.get("formnodir12.main.field_3r")

        assert f_3 is not None
        assert f_3["type"] == "text"
        assert f_3.get("options") is None

        assert f_3r is not None
        assert f_3r["type"] == "table"
        assert len(f_3r.get("columns", [])) == 5
        col_keys = [c["key"] for c in f_3r["columns"]]
        assert "cin_llpin" in col_keys
        assert "name" in col_keys
        assert "percentage_share" in col_keys

        # Check DAG condition: 3(r) depends on 3(a) being Appointment
        dep = f_3r.get("depends_on")
        assert dep is not None
        assert dep["field"] == "formnodir12.main.field_3a"
        assert dep["operator"] == "in"
        assert "Appointment" in dep["value"]

    def test_dir12_table_3r_conditional_rendering(self):
        from automation_engine.modules.idp_studio.router import _create_dynamic_statutory_form_pdf

        # Case 1: Purpose is Cessation -> 3(r) should be DAG-pruned
        cessation_data = {
            "formnodir12.main.field_1": "U72900MH2020PTC345678",
            "formnodir12.main.field_3a": "Cessation",
        }
        doc_cess = _create_dynamic_statutory_form_pdf("Form No. DIR-12", cessation_data)
        text_cess = "".join(p.get_text() for p in doc_cess)
        assert "Interest in other entities" not in text_cess

        # Case 2: Purpose is Appointment -> 3(r) dynamic grid must appear
        appointment_data = {
            "formnodir12.main.field_1": "U72900MH2020PTC345678",
            "formnodir12.main.field_3a": "Appointment",
            "formnodir12.main.field_3r[0].cin_llpin": "U12345DL2010PTC111111",
            "formnodir12.main.field_3r[0].name": "Alpha Solutions Pvt Ltd",
            "formnodir12.main.field_3r[0].percentage_share": "25",
        }
        doc_app = _create_dynamic_statutory_form_pdf("Form No. DIR-12", appointment_data)
        text_app = "".join(p.get_text() for p in doc_app)
        assert "Interest in other entities" in text_app
        assert "Alpha Solutions Pvt Ltd" in text_app


class TestLLP8FinancialDataIsolation:
    """
    Validates that LLP Form No. 8 Statement of Account financial figures are
    dynamically extracted from the document and completely isolated without static rule bleed.
    """

    def test_llp8_part_b_statement_of_account_hydration(self):
        from automation_engine.modules.idp_studio.router import _fast_path_extract_mca_fields, resolve_field_value
        from automation_engine.modules.idp_studio.forms.registry import FormRegistry

        full_doc_text = """
        LLP FORM NO. 8
        STATEMENT OF ACCOUNT & SOLVENCY
        LLPIN: AAB-1234
        Name of LLP: TEST TECH VENTURES LLP

        Statement of Assets and Liabilities as at 31st March 2024:
        Contribution received by all partners : 50,00,000 | 40,00,000
        Reserves and Surplus : 85,50,000 | 60,00,000
        Secured Loans : 12,00,000 | 10,00,000
        Gross Fixed Assets : 1,10,00,000 | 90,00,000
        Gross Turnover : 4,50,00,000 | 3,20,00,000
        Administrative Expenses : 35,00,000 | 25,00,000
        Profit / Loss Before Tax : 95,00,000 | 70,00,000
        """

        field_map = {
            "llpformno8.section_1.field_2": "LLPIN",
            "llpformno8.section_1.field_5": "Part B: Statement of Account",
        }

        extracted = _fast_path_extract_mca_fields(full_doc_text, "LLP Form No. 8", field_map)
        assert "llpformno8.section_1.field_5" in extracted
        rows = extracted["llpformno8.section_1.field_5"]
        assert isinstance(rows, list)

        # Verify extracted amounts match document, not old hardcoded figures
        contrib_row = next(r for r in rows if "Contribution received" in r.get("financial_head", ""))
        assert contrib_row["current_year"] == "50,00,000"
        assert contrib_row["previous_year"] == "40,00,000"
        # Old bleed was '1,42,46,303'
        assert contrib_row["current_year"] != "1,42,46,303"

        reserves_row = next(r for r in rows if "Reserves and Surplus" in r.get("financial_head", ""))
        assert reserves_row["current_year"] == "85,50,000"
        # Old bleed was '22.09.99.672'
        assert reserves_row["current_year"] != "22.09.99.672"

    def test_llp8_alias_rule_isolation(self):
        import sqlite3
        conn = sqlite3.connect("automation_engine/modules/idp_studio/idp_studio.db")
        c = conn.cursor()
        c.execute("""
            SELECT extracted_key FROM idp_schema_alias_rules
            WHERE template_name LIKE '%LLP Form No. 8%'
              AND extracted_key IN ('1,42,46,303', '22.09.99.672', '3,05,53,654', '41,96,20,818', 'AAP-3112')
        """)
        bad_rules = c.fetchall()
        conn.close()
        assert len(bad_rules) == 0, f"No literal financial values must exist in schema alias rules: {bad_rules}"


# ==============================================================================
# 6. UNIVERSAL ENGINE REGRESSION TESTS: MGT-14, LLP-11, BEN-2, GNL-1
# ==============================================================================

class TestMGT14UniversalAlignment:
    """Regression tests for MGT-14 Use-Case selection and Field 6 structure."""

    def test_mgt14_field_3_has_resolution_option(self):
        db = SessionLocal()
        schema = FormRegistry.get_form_schema("Form No. MGT-14", db)
        db.close()

        assert schema is not None
        fields = schema.get("fields", [])
        f3 = next((f for f in fields if f.get("id") == "formnomgt14.main.field_3"), None)
        assert f3 is not None, "Field 3 ('Registration of') must exist"
        assert f3.get("type") in ["select", "radio"]
        opts = f3.get("options", [])
        assert "Resolution(s)" in opts, f"Field 3 must include 'Resolution(s)', got {opts}"
        assert "Postal ballot resolution(s) under Section 110" in opts
        assert "Agreement" in opts

    def test_mgt14_field_6_structure_and_dependencies(self):
        db = SessionLocal()
        schema = FormRegistry.get_form_schema("Form No. MGT-14", db)
        db.close()

        fields = {f["id"]: f for f in schema.get("fields", [])}
        f6 = fields.get("formnomgt14.main.field_6")
        assert f6 is not None
        assert f6.get("type") == "number", "Field 6 must be numeric count"
        assert f6.get("canonical_no") == "6"
        assert f6.get("depends_on") is not None

        # Check subfields 6(a), 6(a)(i), 6(a)(ii), 6(b)(i), 6(b)(ii)
        assert "formnomgt14.main.field_6a" in fields
        assert fields["formnomgt14.main.field_6a"].get("canonical_no") == "6(a)"

        assert "formnomgt14.main.field_6iai" in fields
        f6iai = fields["formnomgt14.main.field_6iai"]
        assert f6iai.get("canonical_no") == "6(a)(i)"
        assert f6iai.get("type") == "select"
        assert "Alteration of Articles" in f6iai.get("options", [])

        assert "formnomgt14.main.field_6iaii" in fields
        f6iaii = fields["formnomgt14.main.field_6iaii"]
        assert f6iaii.get("canonical_no") == "6(a)(ii)"
        assert f6iaii.get("type") == "select"

        assert "formnomgt14.main.field_6ibi" in fields
        assert fields["formnomgt14.main.field_6ibi"].get("canonical_no") == "6(b)(i)"

        assert "formnomgt14.main.field_6ibii" in fields
        assert fields["formnomgt14.main.field_6ibii"].get("canonical_no") == "6(b)(ii)"
        assert "Insolvency and Bankruptcy Code" in fields["formnomgt14.main.field_6ibii"].get("label")

    def test_mgt14_pdf_rendering_resolution_scenario(self):
        from automation_engine.modules.idp_studio.router import _create_dynamic_statutory_form_pdf

        data = {
            "formnomgt14.main.field_1": "U62099MH2003PTC142119",
            "formnomgt14.main.field_2a": "POINTER8 TECHNOLOGIES PRIVATE LIMITED",
            "formnomgt14.main.field_3": "Resolution(s)",
            "formnomgt14.main.field_4a": "02/06/2026",
            "formnomgt14.main.field_4b": "24/06/2026",
            "formnomgt14.main.field_6": "1",
            "formnomgt14.main.field_6iai": "Alteration of Articles",
            "formnomgt14.main.field_6ibi": "Sec 14(1)",
            "formnomgt14.main.field_6ibii": "N/A",
            "formnomgt14.main.field_6ie": "Approval for alteration of Articles of Association in line with Shareholders Agreement",
            "formnomgt14.main.field_6if": "No",
            "formnomgt14.main.field_6ig": "Shareholders",
            "formnomgt14.main.field_6ih": "Special resolution"
        }

        doc = _create_dynamic_statutory_form_pdf("Form No. MGT-14", data)
        pdf_text = "".join(p.get_text() for p in doc)

        assert "FORM NO. MGT-14" in pdf_text
        assert "POINTER8 TECHNOLOGIES PRIVATE LIMITED" in pdf_text
        assert "Resolution(s)" in pdf_text
        assert "Alteration of Articles" in pdf_text
        assert "Sec 14(1)" in pdf_text
        assert "Insolvency and Bankruptcy Code" in pdf_text


class TestLLP11UniversalAlignment:
    """Regression tests for LLP-11 Fields 7, 8, 9 template alignment and auto-aggregation."""

    def test_llp11_schema_columns(self):
        db = SessionLocal()
        schema = FormRegistry.get_form_schema("LLP Form No. 11", db)
        db.close()

        fields = {f["id"]: f for f in schema.get("fields", [])}
        assert "llpformno11.main.field_7" in fields
        f7 = fields["llpformno11.main.field_7"]
        f7_col_keys = [c["key"] for c in f7.get("columns", [])]
        assert "dpin_pan" in f7_col_keys
        assert "partner_name" in f7_col_keys
        assert "obligation_contribution" in f7_col_keys
        assert "contribution_received" in f7_col_keys

        assert "llpformno11.main.field_9" in fields
        f9 = fields["llpformno11.main.field_9"]
        f9_col_keys = [c["key"] for c in f9.get("columns", [])]
        assert "category" in f9_col_keys
        assert "num_designated_partners" in f9_col_keys
        assert "total_partners" in f9_col_keys

    def test_llp11_partner_table_reconstitution_and_field_9_auto_aggregation(self):
        from automation_engine.modules.idp_studio.router import resolve_field_value, _create_dynamic_statutory_form_pdf

        partner_data = {
            "llpformno11.main.field_1": "AAA-1234",
            "field_7[0].designation": "Designated Partner",
            "field_7[0].dpin": "01234567",
            "field_7[0].name": "Rajesh Kumar",
            "field_7[0].obligation": "100000",
            "field_7[0].received": "100000",
            "field_7[0].resident": "Yes",
            "field_7[1].designation": "Partner",
            "field_7[1].dpin": "09876543",
            "field_7[1].name": "Pooja Sharma",
            "field_7[1].obligation": "50000",
            "field_7[1].received": "50000",
            "field_7[1].resident": "Yes",
        }

        db = SessionLocal()
        schema = FormRegistry.get_form_schema("LLP Form No. 11", db)
        db.close()

        f7_def = next(f for f in schema["fields"] if f["id"] == "llpformno11.main.field_7")
        f9_def = next(f for f in schema["fields"] if f["id"] == "llpformno11.main.field_9")

        matched = set()
        f7_val = resolve_field_value(f7_def, partner_data, matched)
        assert isinstance(f7_val, list)
        assert len(f7_val) == 2
        assert f7_val[0]["partner_name"] == "Rajesh Kumar"
        assert f7_val[0]["dpin_pan"] == "01234567"
        assert f7_val[1]["partner_name"] == "Pooja Sharma"

        # Field 9 auto-aggregation from partner rows
        partner_data["llpformno11.main.field_7"] = f7_val
        f9_val = resolve_field_value(f9_def, partner_data, matched)
        assert isinstance(f9_val, list)
        assert len(f9_val) == 3
        indiv_row = f9_val[0]
        assert indiv_row["category"] == "(a) Individuals"
        assert indiv_row["num_designated_partners"] == "1"
        assert indiv_row["num_partners"] == "1"
        assert indiv_row["total_partners"] == "2"
        assert indiv_row["obligation_contribution"] == "150000"
        assert indiv_row["contribution_received"] == "150000"

        # Verify PDF rendering contains reconstituted partner names and aggregated numbers
        doc = _create_dynamic_statutory_form_pdf("LLP Form No. 11", partner_data)
        pdf_text = "".join(p.get_text() for p in doc)
        assert "Rajesh Kumar" in pdf_text
        assert "Pooja Sharma" in pdf_text
        assert "150000" in pdf_text


class TestBEN2UniversalAlignment:
    """Regression tests for BEN-2 Field 5(a)(i) manual input and 6B/6D conditional prefill."""

    def test_ben2_field_5ai_supports_manual_input(self):
        db = SessionLocal()
        schema = FormRegistry.get_form_schema("Form No. BEN-2", db)
        db.close()

        fields = {f["id"]: f for f in schema.get("fields", [])}
        f5ai = next((f for f in schema.get("fields", []) if f.get("canonical_no") == "5(a)(i)"), None)
        assert f5ai is not None, "Field 5(a)(i) must exist"
        assert f5ai.get("type") == "number"
        assert f5ai.get("readonly") is not True

    def test_ben2_6b_prefill_when_cin_llpin_present(self):
        from automation_engine.modules.idp_studio.router import resolve_field_value

        data = {
            "member_cin": "U72900DL2021PTC123456",
            "member_name": "Nexus Holdings Private Limited",
            "member_address": "Plot 10, Connaught Place, New Delhi",
            "member_email": "compliance@nexusholdings.com"
        }

        matched = set()
        f6ba = {"id": "field_6ba", "canonical_no": "6B(a)", "label": "Type of Member", "type": "select"}
        f6bb = {"id": "field_6bb", "canonical_no": "6B(b)", "label": "CIN/ FCRN/ LLPIN", "type": "text"}
        f6bc = {"id": "field_6bc", "canonical_no": "6B(c)", "label": "Name of the Member", "type": "text"}
        f6bd = {"id": "field_6bd", "canonical_no": "6B(d)", "label": "Address of the Member", "type": "textarea"}
        f6be = {"id": "field_6be", "canonical_no": "6B(e)", "label": "Email ID of the Member", "type": "text"}

        assert resolve_field_value(f6ba, data, matched) == "Company"
        assert resolve_field_value(f6bb, data, matched) == "U72900DL2021PTC123456"
        assert resolve_field_value(f6bc, data, matched) == "Nexus Holdings Private Limited"
        assert resolve_field_value(f6bd, data, matched) == "Plot 10, Connaught Place, New Delhi"
        assert resolve_field_value(f6be, data, matched) == "compliance@nexusholdings.com"

    def test_ben2_6d_prefill_when_sbo_id_present(self):
        from automation_engine.modules.idp_studio.router import resolve_field_value

        data = {
            "sbo_id": "SBO87654321",
            "sbo_pan": "ABCDE1234F",
            "sbo_name": "Vikramaditya Singhania",
            "sbo_father_name": "Aditya Singhania",
            "sbo_dob": "15/08/1982",
            "sbo_address": "14 Marine Drive, Mumbai"
        }

        matched = set()
        f6da = {"id": "field_6da", "canonical_no": "6D(a)", "label": "ID of the Significant Beneficial Owner"}
        f6dai = {"id": "field_6dai", "canonical_no": "6D(a)(i)", "label": "Income Tax PAN"}
        f6db = {"id": "field_6db", "canonical_no": "6D(b)", "label": "Name of the Significant Beneficial Owner"}
        f6dc = {"id": "field_6dc", "canonical_no": "6D(c)", "label": "Father's Name"}
        f6dd = {"id": "field_6dd", "canonical_no": "6D(d)", "label": "Date of Birth"}
        f6dg = {"id": "field_6dg", "canonical_no": "6D(g)", "label": "Address of Significant Beneficial Owner"}

        assert resolve_field_value(f6da, data, matched) == "SBO87654321"
        assert resolve_field_value(f6dai, data, matched) == "ABCDE1234F"
        assert resolve_field_value(f6db, data, matched) == "Vikramaditya Singhania"
        assert resolve_field_value(f6dc, data, matched) == "Aditya Singhania"
        assert resolve_field_value(f6dd, data, matched) == "15/08/1982"
        assert resolve_field_value(f6dg, data, matched) == "14 Marine Drive, Mumbai"


class TestGNL1UniversalUseCaseIsolation:
    """Regression tests ensuring unselected use-case database mappings never populate the output."""

    def test_gnl1_agm_extension_shields_compounding_db_values(self):
        from automation_engine.modules.idp_studio.router import _create_dynamic_statutory_form_pdf

        # User selected AGM Extension, but database contains mapped values for Compounding of offences
        mapped_data_with_bleed = {
            "gnl1.main.field_1a": "Extension of period of annual general meeting by three months",
            "gnl1.main.field_3": "U12345MH2020PTC000000",
            "gnl1.main.field_5": "Acme Ventures Private Limited",
            "gnl1.main.field_9a": "Financial year end 31/03/2026",
            # Spurious DB bleed from Compounding use-case
            "gnl1.main.field_8d": "Suo-motu",
            "gnl1.main.field_8m": "Yes",
            "field_8d": "Suo-motu",
            "offence_details": "Failure to hold AGM within due date",
            "compounding_authority": "Regional Director"
        }

        doc = _create_dynamic_statutory_form_pdf("GNL-1", mapped_data_with_bleed)
        pdf_text = "".join(p.get_text() for p in doc)

        assert "Extension of period of annual general meeting by three months" in pdf_text
        assert "Financial year end 31/03/2026" in pdf_text
        # Compounding data fields must NOT appear in output
        assert "Suo-motu" not in pdf_text
        assert "Suo motu" not in pdf_text
        assert "Failure to hold AGM within due date" not in pdf_text
        assert "Regional Director" not in pdf_text

    def test_gnl1_compounding_shields_agm_extension_values(self):
        from automation_engine.modules.idp_studio.router import _create_dynamic_statutory_form_pdf

        mapped_data_compounding = {
            "gnl1.main.field_1a": "Compounding of offences",
            "gnl1.main.field_3": "U12345MH2020PTC000000",
            "gnl1.main.field_5": "Acme Ventures Private Limited",
            "gnl1.main.field_8d": "Suo-motu",
            # Spurious DB bleed from AGM Extension
            "gnl1.main.field_9a": "Extension up to 30/12/2026",
            "field_9a": "Extension up to 30/12/2026"
        }

        doc = _create_dynamic_statutory_form_pdf("GNL-1", mapped_data_compounding)
        pdf_text = "".join(p.get_text() for p in doc)

        assert "Compounding of offences" in pdf_text
        assert "Suo-motu" in pdf_text
        assert "Extension up to 30/12/2026" not in pdf_text



