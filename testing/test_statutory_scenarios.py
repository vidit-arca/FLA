import unittest
from automation_engine.modules.idp_studio.extractors.classifier import detect_operative_statutory_branch, classify_document
from automation_engine.modules.idp_studio.router import detect_form_branch

class TestStatutoryScenarios(unittest.TestCase):
    def test_first_auditor_board(self):
        text = """
        RESOLVED THAT pursuant to the provisions of Section 139(6) and other applicable provisions of the Companies Act, 2013, 
        M/s ABC & Co., Chartered Accountants, be and are hereby appointed as the first auditors of the company 
        to hold office until the conclusion of the first Annual General Meeting.
        """
        res = detect_operative_statutory_branch(text)
        self.assertEqual(res["recommended_branch"], "First auditor by Board of directors")
        self.assertEqual(res["scenario_key"], "first_auditor_board")
        self.assertEqual(res["section_cited"], "Section 139(6)")
        self.assertGreaterEqual(res["confidence"], 0.95)

    def test_first_auditor_members(self):
        text = """
        RESOLVED THAT pursuant to Section 139(6) of the Companies Act, 2013, the Board having failed to appoint the first auditor within thirty days of registration, 
        the members at this Extraordinary General Meeting (EGM) hereby appoint M/s DEF & Associates as the first auditors.
        """
        res = detect_operative_statutory_branch(text)
        self.assertEqual(res["recommended_branch"], "First auditor by members")
        self.assertEqual(res["scenario_key"], "first_auditor_members")
        self.assertEqual(res["section_cited"], "Section 139(6)")

    def test_cag_appointment(self):
        text = """
        RESOLVED THAT pursuant to Section 139(7) of the Companies Act, 2013, the appointment of statutory auditors 
        made by the Comptroller and Auditor General of India (C&AG) be and is hereby noted and confirmed.
        """
        res = detect_operative_statutory_branch(text)
        self.assertEqual(res["recommended_branch"], "Appointment/ Re-appointment by C&AG")
        self.assertEqual(res["scenario_key"], "cag_appointment")
        self.assertEqual(res["section_cited"], "Section 139(7)")

    def test_removal_appointment(self):
        text = """
        RESOLVED THAT pursuant to Section 140(1) and Section 140(4) of the Companies Act, 2013, 
        M/s Old Auditors be removed before expiry of their term and M/s New Auditors be appointed.
        """
        res = detect_operative_statutory_branch(text)
        self.assertEqual(res["recommended_branch"], "Auditor appointed in case of non-re-appointment/ removal")
        self.assertEqual(res["scenario_key"], "removal_appointment")
        self.assertEqual(res["section_cited"], "Section 140(1)")

    def test_casual_vacancy_resignation(self):
        text = """
        RESOLVED THAT pursuant to Section 139(8) of the Companies Act, 2013, caused due to resignation of previous auditor...
        """
        res = detect_operative_statutory_branch(text)
        self.assertEqual(res["scenario_key"], "casual_vacancy")
        self.assertEqual(res["sub_reason"], "Resignation")

    def test_agm_reappointment_with_options(self):
        text = """
        RESOLVED THAT pursuant to Section 139(1) of the Companies Act, 2013, the retiring auditors M/s ABC & Co. be re-appointed.
        """
        options = ["Appointment of Auditors in AGM", "Re-appointment of Auditors in AGM", "First auditor by Board of directors"]
        res = detect_operative_statutory_branch(text, candidate_options=options)
        self.assertEqual(res["recommended_branch"], "Re-appointment of Auditors in AGM")
        self.assertEqual(res["scenario_key"], "agm_reappointment")

    def test_dynamic_branching_non_adt_form(self):
        # MGT-6 has options Yes/No, verify ADT-1 appointment text does NOT leak
        text = "Some corporate resolution text"
        options = ["Yes", "No"]
        res = detect_operative_statutory_branch(text, candidate_options=options)
        self.assertIn(res["recommended_branch"], ["Yes", "No"])
        self.assertNotIn("Appointment", res["recommended_branch"])

    def test_no_branch_fallback(self):
        text = "Generic document"
        res = detect_operative_statutory_branch(text, candidate_options=[])
        self.assertIsNone(res["recommended_branch"])
        self.assertEqual(res["scenario_key"], "standard")

    def test_api_branch_detection_and_pdf_labels(self):
        from fastapi.testclient import TestClient
        from automation_engine.api.main import app
        import fitz

        client = TestClient(app)

        # 1. PAS-6 must report has_branches=False and zero options
        pas_res = client.post("/api/idp/forms/Form No. PAS -6/detect_branch").json()
        self.assertFalse(pas_res["has_branches"])
        self.assertEqual(pas_res["available_options"], [])

        # 2. MGT-6 must report its own branch options (Yes/No), not PAS-6 or ADT-1 options
        mgt_res = client.post("/api/idp/forms/Form MGT-6/detect_branch").json()
        self.assertTrue(mgt_res["has_branches"])
        mgt_titles = [o["title"] for o in mgt_res["available_options"]]
        self.assertEqual(mgt_titles, ["Yes", "No"])
        self.assertNotIn("Appointment of Auditors in AGM", mgt_titles)

        # 3. PDF Preview must include both field labels and values without truncation
        pdf_res = client.post("/api/idp/generate_preview_pdf", json={
            "template_name": "Form MGT-6",
            "mapped_data": {
                "cin": "U72200DL2020PTC123456",
                "company_name": "Test Company Pvt Ltd"
            }
        })
        self.assertEqual(pdf_res.status_code, 200)
        doc = fitz.open(stream=pdf_res.content, filetype="pdf")
        full_text = "\n".join([page.get_text() for page in doc])
        self.assertIn("Corporate Identity Number (CIN)", full_text)
        self.assertIn("Name of the Company", full_text)
        self.assertIn("U72200DL2020PTC123456", full_text)
        self.assertIn("Test Company Pvt Ltd", full_text)

if __name__ == "__main__":
    unittest.main()
