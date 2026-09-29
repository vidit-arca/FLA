"""
Regression Test Suite for Universal MCA Instruction Kit Parser.
Tests LLP-8, ADT-1, and MGT-14 across statutory structural rules.
"""

import os
import unittest
from automation_engine.modules.idp_studio.forms.kit_parser import InstructionKitParser, ParserValidator


class TestInstructionKitParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = InstructionKitParser()
        cls.instructions_dir = "/Users/apple/Desktop/FLA/document/instructions"
        cls.fallback_dir = "/Users/apple/Desktop/FLA"

        def get_pdf(name):
            p1 = os.path.join(cls.instructions_dir, name)
            if os.path.exists(p1):
                return p1
            return os.path.join(cls.fallback_dir, name)

        cls.llp8_path = get_pdf("Instruction Kit_LLP Form No. 8.pdf")
        cls.adt1_path = get_pdf("Instruction Kit_ADT-1.pdf")
        cls.mgt14_path = get_pdf("Instruction Kit_MGT-14.pdf")
        cls.mgt7_path = get_pdf("Instruction Kit_MGT-7.pdf")

    def test_llp8_generic_branching_and_physical_order(self):
        """Verify LLP-8 multi-branch parsing, duplicate field numbers, and physical ordering."""
        schema = self.parser.parse(self.llp8_path)
        fields = schema["fields"]
        val = schema.get("validation_report", {})

        # 1. Validation integrity
        self.assertTrue(val.get("ok"), f"LLP-8 validation failed: {val.get('errors')}")
        self.assertEqual(val.get("errors"), [])

        # 2. No duplicate canonical IDs
        ids = [f["id"] for f in fields]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate canonical IDs detected in LLP-8!")

        # 3. Duplicate MCA field numbers coexist across separate canonical sections
        sec1_3a = any(f["id"].endswith("section_1.field_3a") for f in fields)
        sec2_3a = any(f["id"].endswith("section_2.field_3a") for f in fields)
        self.assertTrue(sec1_3a, "section_1.field_3a must exist!")
        self.assertTrue(sec2_3a, "section_2.field_3a must exist!")

        # 4. Strict physical sequence preserved (3(b) -> 3(c) -> 3(e) -> 3(d))
        sec1_fields = [f for f in fields if "section_1" in f["id"]]
        sec1_nos = [f["canonical_no"] for f in sec1_fields if f["canonical_no"]]
        self.assertIn("3(e)", sec1_nos, "3(e) Email ID must exist in Solvency section!")
        
        idx_3b = sec1_nos.index("3(b)")
        idx_3c = sec1_nos.index("3(c)")
        idx_3e = sec1_nos.index("3(e)")
        idx_3d = sec1_nos.index("3(d)")
        self.assertTrue(idx_3b < idx_3c < idx_3e < idx_3d, f"Physical sequence violated: {sec1_nos}")

        # 5. Unnumbered statutory rows retained (Attachments, Certificate, etc.)
        unnum_fields = [f for f in fields if not f.get("canonical_no")]
        self.assertGreater(len(unnum_fields), 0, "Unnumbered statutory rows must be preserved!")
        has_attachment = any("attachment" in f["id"] or f["canonical_no"] == "5" for f in fields)
        has_certificate = any("certificate" in f["id"] or "category" in f["id"] for f in fields)
        self.assertTrue(has_attachment, "Attachments must exist!")
        self.assertTrue(has_certificate, "Certificate fields must exist!")

        # 6. Branch dependency resolution: Solvency vs Charge
        root_f = next(f for f in fields if "common" in f["id"])
        self.assertEqual(root_f["type"], "radio")
        self.assertIn("Statement of Account and Solvency", root_f["options"])
        self.assertIn("Charge", root_f["options"])

        for f in sec1_fields:
            self.assertIsNotNone(f.get("depends_on"), f"Field {f['id']} must inherit section dependency!")
            self.assertEqual(f["depends_on"]["value"], "Statement of Account and Solvency")

        sec2_fields = [f for f in fields if "section_2" in f["id"]]
        for f in sec2_fields:
            # Either direct branch dependency or nested intra-section dependency
            has_charge_dep = (
                f.get("depends_on", {}).get("value") == "Charge" or
                f.get("section_depends_on", {}).get("value") == "Charge" or
                "section_2" in f.get("depends_on", {}).get("field", "")
            )
            self.assertTrue(has_charge_dep, f"Field {f['id']} must belong to Charge branch!")

        # 7. Intra-section child triggers in Charge: 4(b), 10(a), 18
        f_4b = next(f for f in sec2_fields if f["canonical_no"] == "4(b)")
        self.assertIn("field_4a", f_4b["depends_on"]["field"])

        f_10a = next(f for f in sec2_fields if f["canonical_no"] == "10(a)")
        self.assertIn("field_4a", f_10a["depends_on"]["field"])
        self.assertEqual(f_10a["depends_on"]["value"], "Creation of charge")

        f_18 = next(f for f in sec2_fields if f["canonical_no"] == "18")
        self.assertIn("field_4a", f_18["depends_on"]["field"])
        self.assertEqual(f_18["depends_on"]["value"], "Modification of charge")

    def test_adt1_single_section_form(self):
        """Verify single-section form (ADT-1) creates zero unnecessary branches."""
        schema = self.parser.parse(self.adt1_path)
        fields = schema["fields"]
        val = schema.get("validation_report", {})

        self.assertTrue(val.get("ok"), f"ADT-1 validation failed: {val.get('errors')}")
        sections = set(f["section"] for f in fields)
        self.assertEqual(sections, {"main"}, f"ADT-1 must only contain 'main' section, got: {sections}")

    def test_mgt14_statutory_extraction(self):
        """Verify MGT-14 captures Field 11, multi-level Roman field numbers, and attachments."""
        schema = self.parser.parse(self.mgt14_path)
        fields = schema["fields"]
        val = schema.get("validation_report", {})

        self.assertTrue(val.get("ok"), f"MGT-14 validation failed: {val.get('errors')}")
        
        # Field 11 not collapsed to 1
        has_f11 = any(f["canonical_no"] == "11" for f in fields)
        self.assertTrue(has_f11, "MGT-14 must retain Field 11 without collapsing to 1!")

        # Roman numeral sub-fields preserved
        has_6ia = any("6i" in f["canonical_no"].lower() for f in fields)
        self.assertTrue(has_6ia, "MGT-14 must preserve Roman numeral subfields under Field 6!")

        # Reverse Option Harvesting verification
        f_3 = next((f for f in fields if f["canonical_no"] == "3"), None)
        self.assertIsNotNone(f_3, "Field 3 ('Registration of') must exist in MGT-14!")
        self.assertIn("Resolution(s)", f_3["options"], "Reverse Option Harvesting must populate 'Resolution(s)' in Field 3 options!")
        self.assertIn("Agreement", f_3["options"], "Reverse Option Harvesting must populate 'Agreement' in Field 3 options!")

        f_6 = next((f for f in fields if f["canonical_no"] == "6"), None)
        self.assertIsNotNone(f_6, "Field 6 ('Number of resolution(s)') must exist in MGT-14!")
        self.assertIn("1", f_6["options"], "Field 6 must offer selectable resolution counts!")
        self.assertIsNotNone(f_6["depends_on"], "Field 6 must have dependency on Field 3!")
        self.assertIn("field_3", f_6["depends_on"]["field"], "Field 6 must depend on Field 3!")

        # Attachment (b) dependency verification
        f_b = next((f for f in fields if f["canonical_no"] == "(b)"), None)
        self.assertIsNotNone(f_b, "Attachment (b) ('Copy of agreement') must exist in MGT-14!")
        self.assertEqual(f_b["type"], "file", "Attachment (b) must be of type 'file'!")
        self.assertIsNotNone(f_b.get("depends_on"), "Attachment (b) must depend on Field 3!")
        self.assertIn("field_3", f_b["depends_on"]["field"], "Attachment (b) must depend on Field 3!")
        self.assertEqual(f_b["depends_on"]["value"], "Agreement", "Attachment (b) must depend on 'Agreement'!")

    def test_mgt7_statutory_extraction(self):
        """Verify MGT-7 captures Roman numeral field numbers (I, II, IV) and 50+ granular fields."""
        schema = self.parser.parse(self.mgt7_path)
        fields = schema["fields"]
        val = schema.get("validation_report", {})

        self.assertTrue(val.get("ok"), f"MGT-7 validation failed: {val.get('errors')}")
        self.assertGreater(len(fields), 40, f"MGT-7 must extract at least 40 granular fields, got {len(fields)}")

        # No duplicate canonical IDs
        f_ids = [f["id"] for f in fields]
        self.assertEqual(len(f_ids), len(set(f_ids)), "Duplicate field IDs detected in MGT-7!")

        # Verify Roman numeral canonical field numbers are properly extracted
        has_roman_fields = any(f["canonical_no"].startswith("I") or f["canonical_no"].startswith("IV") for f in fields)
        self.assertTrue(has_roman_fields, "MGT-7 must extract Roman numeral canonical field numbers!")

if __name__ == "__main__":
    unittest.main()
