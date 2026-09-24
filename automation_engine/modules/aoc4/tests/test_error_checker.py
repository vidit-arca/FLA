import unittest
import os
import sys

# Ensure module path is accessible
current_dir = os.path.dirname(os.path.abspath(__file__))
module_dir = os.path.abspath(os.path.join(current_dir, ".."))
if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

from aoc4_error_checker import AOC4CommonErrorEngine

class TestAOC4CommonErrorRow1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.excel_path = os.path.join(module_dir, 'excel', 'ANNFIL COMMONERROR .xlsx')
        if not os.path.exists(cls.excel_path):
            cls.excel_path = os.path.join(module_dir, 'excel', 'ANNFIL COMMONERROR.xlsx')
        cls.engine = AOC4CommonErrorEngine(cls.excel_path)

    def test_clean_private_company_audit_report(self):
        """Clean unlisted private company report with all 5 mandatory sections present, conditional absent."""
        mock_audit_text = """
        INDEPENDENT AUDITOR'S REPORT
        To the Members of ABC Private Limited
        
        Report on the Audit of the Standalone Financial Statements
        
        Opinion
        We have audited the accompanying standalone financial statements of ABC Private Limited.
        In our opinion and to the best of our information, the aforesaid financial statements give a true and fair view.
        
        Basis for Opinion
        We conducted our audit in accordance with the Standards on Auditing (SAs) specified under section 143(10).
        
        Responsibilities of Management and Those Charged with Governance for the Standalone Financial Statements
        The Company's Board of Directors is responsible for the matters stated in section 134(5).
        
        Auditor’s Responsibilities for the Audit of the Financial Statements
        Our objectives are to obtain reasonable assurance about whether the financial statements are free from material misstatement.
        
        Report on Other Legal and Regulatory Requirements
        As required by Section 143(3) of the Act, we report that:
        a) We have sought and obtained all the information and explanations.
        """
        
        input_data = {
            "full_text": mock_audit_text,
            "is_listed": "no",
            "turnover": 1000.0,  # 10 Cr (in Lakhs) -> < 50 Cr
            "borrowings": 200.0   # 2 Cr (in Lakhs) -> < 25 Cr
        }
        
        flags = self.engine.execute(input_data)
        row1_flag = next(f for f in flags if "whether audit report has the following fields" in f["particulars"].lower())
        
        self.assertEqual(row1_flag["user_value"], "Yes")
        self.assertIn("a: Yes, b: Yes, c: No (Clean/NA), d: No (Unlisted - NA), e: No (NA), f: Yes, g: Yes, h: No (NA), i: Yes, j: No (Exempt under GSR 583(E))", row1_flag["reason"])
        self.assertIn("All mandatory audit report sections verified", row1_flag["reason"])

    def test_missing_mandatory_basis_of_opinion(self):
        """Audit report missing Basis of Opinion should yield 'No' and itemized missing mandatory."""
        mock_audit_text = """
        Opinion
        We have audited the financial statements.
        
        Responsibilities of Management for the Financial Statements
        Management is responsible.
        
        Auditor's Responsibility for Audit of the Financial Statements
        Our responsibility is to express an opinion.
        
        Report on Other Legal and Regulatory Requirements
        We report that all info was obtained.
        """
        
        input_data = {
            "full_text": mock_audit_text,
            "is_listed": "no"
        }
        
        flags = self.engine.execute(input_data)
        row1_flag = next(f for f in flags if "whether audit report has the following fields" in f["particulars"].lower())
        
        self.assertEqual(row1_flag["user_value"], "No")
        self.assertIn("b: No", row1_flag["reason"])
        self.assertIn("Missing mandatory sections: Basis of Opinion", row1_flag["reason"])

    def test_listed_company_missing_kam(self):
        """Listed company missing Key Audit Matters should fail."""
        mock_audit_text = """
        Opinion
        We have audited the financial statements.
        
        Basis for Opinion
        We conducted our audit in accordance with SAs.
        
        Responsibilities of Management for the Financial Statements
        Management is responsible.
        
        Auditor's Responsibility for Audit of the Financial Statements
        Our responsibility is to express an opinion.
        
        Report on Other Legal and Regulatory Requirements
        We report that all info was obtained.
        
        Internal Financial Controls
        The company has adequate internal financial controls.
        """
        
        input_data = {
            "full_text": mock_audit_text,
            "is_listed": "yes"  # Listed -> KAM is mandatory
        }
        
        flags = self.engine.execute(input_data)
        row1_flag = next(f for f in flags if "whether audit report has the following fields" in f["particulars"].lower())
        
        self.assertEqual(row1_flag["user_value"], "No")
        self.assertIn("d: No", row1_flag["reason"])
        self.assertIn("Missing mandatory sections: Key Audit Matters", row1_flag["reason"])

    def test_all_10_sections_present(self):
        """Report with all 10 sections present should have all Yes and overall 'Yes'."""
        mock_audit_text = """
        Opinion
        We have audited the financial statements.
        
        Basis for Opinion
        We conducted our audit.
        
        Emphasis of Matter
        We draw attention to Note 5 regarding litigation.
        
        Key Audit Matters
        Key audit matters are those matters that...
        
        Other Information
        The directors are responsible for the other information.
        
        Responsibilities of Management for the Financial Statements
        Management is responsible.
        
        Auditor's Responsibility for the Audit of the Financial Statements
        Our responsibility.
        
        Other Matters
        The previous year financial statements were audited by another auditor.
        
        Report on Other Legal and Regulatory Requirements
        We report under 143(3).
        
        Report on Internal Financial Controls
        In our opinion, the Company has adequate internal financial controls.
        """
        
        input_data = {
            "full_text": mock_audit_text,
            "is_listed": "yes"
        }
        
        flags = self.engine.execute(input_data)
        row1_flag = next(f for f in flags if "whether audit report has the following fields" in f["particulars"].lower())
        
        self.assertEqual(row1_flag["user_value"], "Yes")
        self.assertIn("a: Yes, b: Yes, c: Yes, d: Yes, e: Yes, f: Yes, g: Yes, h: Yes, i: Yes, j: Yes", row1_flag["reason"])

if __name__ == "__main__":
    unittest.main()
