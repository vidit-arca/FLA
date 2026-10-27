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

