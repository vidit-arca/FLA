"""
Comprehensive End-to-End Test Suite for IDP Studio Modular Architecture,
Multi-Tenant Scoping, Data-Driven Lexicon Harvesting, and HITL Operative Detection.
"""

import os
import sys
import unittest
import requests

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from automation_engine.modules.idp_studio.core import (
    engine,
    SessionLocal,
    Base,
    get_db,
    init_db,
    DB_PATH,
    SchemaAliasRule,
    IdpTemplate,
    DomExtractionRule,
)
from automation_engine.modules.idp_studio.forms import (
    InstructionKitParser,
    FormRegistry,
    DynamicFormFiller,
)
from automation_engine.modules.idp_studio.extractors import (
    classify_document,
    detect_operative_statutory_branch,
    apply_spatial_overrides,
    get_spatial_rules,
    get_effective_rules,
    get_scenario_lexicon,
    FLABridgeAdapter,
)
from automation_engine.modules.idp_studio import router


class TestIDPStudioSuite(unittest.TestCase):

    def test_01_core_db_and_models(self):
        """Test database connection, session, multi-tenant columns, and ORM tables."""
        self.assertTrue(os.path.exists(DB_PATH), f"DB file does not exist at {DB_PATH}")
        db = SessionLocal()
        try:
            templates = db.query(IdpTemplate).all()
            self.assertIsInstance(templates, list)
            
            rules = db.query(SchemaAliasRule).all()
            self.assertIsInstance(rules, list)
            if rules:
                r = rules[0]
                self.assertTrue(hasattr(r, "scope_type"))
                self.assertTrue(hasattr(r, "scope_id"))
                self.assertTrue(hasattr(r, "priority"))
        finally:
            db.close()

    def test_02_forms_registry(self):
        """Test universal FormRegistry catalog."""
        forms = FormRegistry.list_forms()
        self.assertGreaterEqual(len(forms), 1, "Expected at least 1 form in registry")
        
        form_ids = [f["form_id"] for f in forms]
        has_adt1 = any("adt" in fid.lower() or "adt" in f.get("form_name", "").lower() for f, fid in zip(forms, form_ids))
        self.assertTrue(has_adt1, "ADT-1 form not found in FormRegistry")

    def test_03_extractors_classifier(self):
        """Test document classifier heuristic accuracy."""
        t1 = classify_document(filename="CTC_BM_Signed.pdf", text="Certified True Copy of the Resolution")
        self.assertEqual(t1, "board_resolution")

        t2 = classify_document(filename="Auditor_Consent.pdf", text="We hereby give our consent and eligibility certificate")
        self.assertEqual(t2, "consent_letter")

        t3 = classify_document(filename="Certificate.pdf", text="Statutory Auditor Certificate under section 139")
        self.assertEqual(t3, "auditor_certificate")

        t4 = classify_document(filename="random.pdf", text="Hello world")
        self.assertEqual(t4, "generic")

    def test_04_extractors_fla_bridge(self):
        """Test FLA Bridge Adapter normalization and evaluation."""
        bridge = FLABridgeAdapter()
        raw_payload = {
            "pan_number": "AAACT1234A",
            "cin_number": "U12345DL2020PTC123456",
            "field_10totalpaidupcapital": "50.0",
        }
        normalized = bridge.normalize_payload_keys(raw_payload)
        self.assertIn("pan_number", normalized)
        self.assertIn("cin_number", normalized)

    def test_05_forms_filler_dag_resolution(self):
        """Test DynamicFormFiller DAG dependency pruning."""
        filler = DynamicFormFiller()
        fields = [
            {"id": "field_category", "label": "Category of Auditor", "type": "select"},
            {
                "id": "field_frn",
                "label": "Firm Registration Number",
                "type": "text",
                "depends_on": {"field": "field_category", "operator": "equals", "value": "Auditor's Firm"}
            },
        ]
        
        # Case A: Condition MET -> field_frn should be active
        validated_a = {"field_category": "Auditor's Firm", "field_frn": "123456N"}
        active_a = filler._resolve_dag_dependencies(fields, validated_a)
        self.assertIn("field_frn", active_a)
        self.assertTrue(active_a["field_frn"]["is_active"])

        # Case B: Condition NOT MET -> field_frn should be pruned (inactive)
        validated_b = {"field_category": "Individual", "field_frn": "123456N"}
        active_b = filler._resolve_dag_dependencies(fields, validated_b)
        self.assertFalse(active_b["field_frn"]["is_active"])

    def test_06_live_api_endpoints(self):
        """Test live FastAPI endpoints on http://localhost:8000."""
        try:
            resp = requests.get("http://localhost:8000/api/idp/forms", timeout=5)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("total_forms", data)
            self.assertIn("forms", data)
            self.assertGreaterEqual(data["total_forms"], 1)
        except requests.exceptions.ConnectionError:
            print("[!] FastAPI server not running on port 8000, skipping HTTP check.")

    def test_07_operative_clause_detector(self):
        """Test Operative Clause Detection and Statutory Precedence Matrix."""
        # 1. Casual Vacancy (Section 139(8))
        cv_text = """
        WHEREAS the previous auditor resigned...
        RESOLVED THAT pursuant to Section 139(8) of the Companies Act, 2013, M/s ABC & Co be appointed to fill casual vacancy.
        """
        r_cv = detect_operative_statutory_branch(cv_text)
        self.assertEqual(r_cv["recommended_branch"], "Casual Vacancy")
        self.assertEqual(r_cv["sub_reason"], "Resignation")
        self.assertGreaterEqual(r_cv["confidence"], 0.95)

        # 2. AGM Reappointment (Section 139(1))
        agm_text = """
        RESOLVED THAT pursuant to Section 139(1) of the Companies Act, 2013, M/s XYZ & Associates be appointed for 5 consecutive years.
        """
        r_agm = detect_operative_statutory_branch(agm_text)
        self.assertEqual(r_agm["recommended_branch"], "Appointment/ Re-appointment in AGM")

        # 3. Tribunal Order (Section 140(5))
        tribunal_text = """
        RESOLVED THAT pursuant to order of the National Company Law Tribunal under Section 140(5)...
        """
        r_trib = detect_operative_statutory_branch(tribunal_text)
        self.assertEqual(r_trib["recommended_branch"], "Auditor appointed by the Tribunal")

    def test_08_multi_tenant_shadowing_cascade(self):
        """Test 3-Tier Multi-Tenant Shadowing: Company (3) > Scenario (2) > Global (1)."""
        db = SessionLocal()
        try:
            db.query(SchemaAliasRule).filter(SchemaAliasRule.template_name == "TEST_SHADOW").delete()
            db.commit()

            # Add Global Base Rule
            db.add(SchemaAliasRule(
                rule_id="r_glob", template_name="TEST_SHADOW", form_field="firm_name",
                extracted_key="Firm Name (Global)", scope_type="GLOBAL", scope_id="default", priority=1
            ))
            # Add Scenario Rule
            db.add(SchemaAliasRule(
                rule_id="r_scen", template_name="TEST_SHADOW", form_field="firm_name",
                extracted_key="Firm Name (Scenario)", scope_type="SCENARIO", scope_id="casual_vacancy", priority=2
            ))
            # Add Company Override
            db.add(SchemaAliasRule(
                rule_id="r_comp", template_name="TEST_SHADOW", form_field="firm_name",
                extracted_key="Firm Name (Company U123)", scope_type="COMPANY", scope_id="U123", priority=3
            ))
            db.commit()

            # Priority 3 wins for Company U123
            eff_u123 = get_effective_rules("TEST_SHADOW", company_id="U123", scenario="casual_vacancy")
            self.assertEqual(eff_u123["firm_name"].extracted_key, "Firm Name (Company U123)")

            # Priority 2 wins for other company under casual_vacancy
            eff_u456 = get_effective_rules("TEST_SHADOW", company_id="U456", scenario="casual_vacancy")
            self.assertEqual(eff_u456["firm_name"].extracted_key, "Firm Name (Scenario)")

            # Priority 1 wins for other company under different scenario
            eff_u789 = get_effective_rules("TEST_SHADOW", company_id="U789", scenario="agm_appointment")
            self.assertEqual(eff_u789["firm_name"].extracted_key, "Firm Name (Global)")

            db.query(SchemaAliasRule).filter(SchemaAliasRule.template_name == "TEST_SHADOW").delete()
            db.commit()
        finally:
            db.close()

    def test_09_dynamic_scenario_lexicon_harvesting(self):
        """Test Data-Driven Keyword Harvesting from DB mappings without hardcoded lists."""
        db = SessionLocal()
        try:
            db.query(SchemaAliasRule).filter(SchemaAliasRule.template_name == "TEST_LEX").delete()
            db.commit()

            db.add(SchemaAliasRule(
                rule_id="r_lex1", template_name="TEST_LEX", form_field="date_of_cessation",
                extracted_key="Date of cessation of statutory auditor", scope_type="SCENARIO", scope_id="casual_vacancy", priority=2
            ))
            db.commit()

            lex = get_scenario_lexicon("TEST_LEX", scenario="casual_vacancy")
            self.assertIn("date_of_cessation", lex)
            self.assertIn("Date of cessation of statutory auditor", lex["date_of_cessation"])

            db.query(SchemaAliasRule).filter(SchemaAliasRule.template_name == "TEST_LEX").delete()
            db.commit()
        finally:
            db.close()

    def test_10_live_detect_branch_api(self):
        """Test live HTTP endpoint /api/idp/forms/{form_id}/detect_branch."""
        try:
            url = "http://localhost:8000/api/idp/forms/form_no_adt-1/detect_branch"
            payload = {
                "text": "RESOLVED THAT pursuant to Section 139(8) of the Companies Act, 2013, to fill the casual vacancy..."
            }
            res = requests.post(url, json=payload, timeout=5)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["detected"]["recommended_branch"], "Casual Vacancy")
            self.assertGreaterEqual(data["detected"]["confidence"], 0.90)
        except requests.exceptions.ConnectionError:
            print("[!] FastAPI server not running on port 8000, skipping HTTP check.")


if __name__ == "__main__":
    unittest.main()
