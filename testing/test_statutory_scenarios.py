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

if __name__ == "__main__":
    unittest.main()
