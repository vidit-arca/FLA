"""
Unit tests for Universal MCA Dynamic Tables & Repeating Groups Parsing.
Validates extraction of Archetype 1 (Web Dynamic Grid) and Archetype 2 (Excel Utility Bridge).
"""

import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from automation_engine.modules.idp_studio.forms.pipeline import StatutoryFormPipeline
from automation_engine.modules.idp_studio.forms.registry import FormRegistry


class TestDynamicTableParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = StatutoryFormPipeline()
        cls.pipeline.stage3.use_llm_fallback = False

    def test_ben2_dynamic_sbo_tables(self):
        pdf_path = os.path.join(REPO_ROOT, "document", "instructions", "Instruction_Kit_BEN-2.pdf")
        self.assertTrue(os.path.exists(pdf_path), f"BEN-2 PDF not found: {pdf_path}")

        schema = self.pipeline.run(pdf_path)
        self.assertEqual(schema["template_name"], "Form No. BEN-2")

        table_fields = [f for f in schema["fields"] if f.get("type") == "table"]
        self.assertGreaterEqual(len(table_fields), 2, "Expected at least 2 table fields in BEN-2 (5a and 5b)")

        # 1. Test 5(a)_table
        t_5a = next((f for f in table_fields if f.get("canonical_no") == "5(a)_table"), None)
        self.assertIsNotNone(t_5a, "Missing 5(a)_table in BEN-2")
        self.assertEqual(t_5a.get("table_archetype"), "web_dynamic_grid")
        self.assertIn("field_5ai", t_5a.get("repeat_count_field", ""))
        self.assertEqual(t_5a.get("min_rows"), 1)
        self.assertEqual(t_5a.get("max_rows"), 10)

        cols_5a = t_5a.get("columns", [])
        self.assertEqual(len(cols_5a), 2, "Expected 2 columns in 5(a)_table")
        col_sbo = cols_5a[0]
        self.assertEqual(col_sbo["key"], "significant_beneficial_owner")
        self.assertTrue(col_sbo.get("readonly"))
        self.assertEqual(col_sbo.get("default_pattern"), "SBO{index}")

        col_mem = cols_5a[1]
        self.assertEqual(col_mem["type"], "number")
        self.assertTrue(col_mem.get("required"))

        # 2. Test 5(b)_table
        t_5b = next((f for f in table_fields if f.get("canonical_no") == "5(b)_table"), None)
        self.assertIsNotNone(t_5b, "Missing 5(b)_table in BEN-2")
        self.assertEqual(t_5b.get("table_archetype"), "web_dynamic_grid")
        self.assertIn("field_5bi", t_5b.get("repeat_count_field", ""))
        self.assertEqual(len(t_5b.get("columns", [])), 2)

    def test_llp8_excel_utility_bridge(self):
        pdf_path = os.path.join(REPO_ROOT, "document", "instructions", "Instruction Kit_LLP Form No. 8.pdf")
        self.assertTrue(os.path.exists(pdf_path), f"LLP-8 PDF not found: {pdf_path}")

        schema = self.pipeline.run(pdf_path)
        self.assertEqual(schema["template_name"], "LLP Form No. 8")

        table_fields = [f for f in schema["fields"] if f.get("type") == "table"]
        self.assertGreaterEqual(len(table_fields), 1, "Expected at least 1 table field in LLP-8 (Field 7 Download Excel)")

        t_7 = next((f for f in table_fields if f.get("canonical_no") == "7" or "excel" in f.get("label", "").lower()), None)
        self.assertIsNotNone(t_7, "Missing Field 7 table in LLP-8")
        self.assertEqual(t_7.get("table_archetype"), "excel_utility_bridge")
        self.assertIn("field_7a", t_7.get("repeat_count_field", ""))

        cols_7 = t_7.get("columns", [])
        self.assertGreaterEqual(len(cols_7), 4, "Expected charge holder detail columns in LLP-8")
        col_keys = [c["canonical_no"] for c in cols_7]
        self.assertIn("8(b)", col_keys, "Expected 8(b) Category column in LLP-8")
        self.assertIn("8(e)", col_keys, "Expected 8(e) Name column in LLP-8")
        self.assertIn("8(f)", col_keys, "Expected 8(f) Address column in LLP-8")
        self.assertIn("8(g)", col_keys, "Expected 8(g) Email column in LLP-8")

    def test_registry_persistence_and_retrieval(self):
        # Verify BEN-2 retrieval from registry
        ben2_schema = FormRegistry.get_form_schema("Form No. BEN-2")
        self.assertIsNotNone(ben2_schema)
        table_fields = [f for f in ben2_schema["fields"] if f.get("type") == "table"]
        self.assertGreaterEqual(len(table_fields), 2)
        for tf in table_fields:
            self.assertEqual(tf["type"], "table")
            self.assertIn("repeat_count_field", tf)
            self.assertGreater(len(tf["columns"]), 0)


if __name__ == "__main__":
    unittest.main()
