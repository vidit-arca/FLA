"""
Regression Test Suite for MCA Form GNL-2 Batch Extractor.
Validates:
1. Regex compilation safety (absence of variable-width lookbehinds, precedence order).
2. Statutory field mappings across all MCA GNL-2 document types.
3. Ollama timeout resilience and non-destructive fallback.
4. Backward compatibility: other forms (PAS-6, ADT-1, etc.) remain unaffected.
5. End-to-end batch extraction endpoint (/api/idp/extract/batch).
"""

import re
import sys
import os
import unittest

# Ensure project and module paths are in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.idp_studio.router import _fast_path_extract_mca_fields


class TestGnl2BatchExtractor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Canonical GNL-2 field label map mimicking DB template schema
        cls.gnl2_field_label_map = {
            "gnl2.main.field_1": "Corporate Identity Number (CIN)",
            "gnl2.main.field_2a": "Please indicate the document being filed",
            "gnl2.main.field_2b": "If others, then specify",
            "gnl2.main.field_3a": "Expected date of issue of Advertisement (DD/MM/YYYY)",
            "gnl2.main.field_3b": "Expected opening date of Acceptance of Deposits (DD/MM/YYYY)",
            "gnl2.main.field_3c": "Expected date of expiry of validity of advertisement or circular (DD/MM/YYYY)",
            "gnl2.main.field_4a": "Act under which the document is being filed",
            "gnl2.main.field_4b": "Section(s) of the Companies Act, 2013 or the Companies Act, 1956 or Insolvency and Bankruptcy Code 2016, under which the document is being filed",
            "gnl2.main.field_4bi": "Section(s) of the Companies Act, 2013 under which the document is being filed",
            "gnl2.main.field_4bi_2": "Section(s) of the Companies Act, 1956 under which the document is being filed",
            "gnl2.main.field_4bii": "Section(s) of the Insolvency and Bankruptcy Code, 2016 under which the document is being filed",
            "gnl2.main.field_5a": "Service request number of Form MGT-14",
            "gnl2.main.field_5b": "Date of passing special (SR) or ordinary resolution (OR) (DD/MM/YYYY)",
            "gnl2.main.field_6a": "Date of event (DD/MM/YYYY)",
            "gnl2.main.field_6b": "Date of declaration by majority of directors (DD/MM/YYYY)",
            "gnl2.main.field_r": "Optional atachment(s) - if any I have been authorised by board of directors’ resolution dated (DD/MM/YYYY) to sign and submit this form.",
            "gnl2.main.field_designation": "Designation",
            "gnl2.main.field_director_identification_number_of": "Director identification number of the director or membership number of the secretary or DIN/PAN of the Manager/CEO/CFO/IRP/RP/Liquidator",
        }

    # =========================================================================
    # 1. Regex Compilation Safety & Precedence
    # =========================================================================
    def test_no_variable_width_lookbehind_in_router(self):
        """Verify router.py does not contain illegal variable-width lookbehinds."""
        router_path = os.path.join(BASE_DIR, "modules", "idp_studio", "router.py")
        with open(router_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Variable-width lookbehind pattern: (?<!...\s+...) or (?<=...\s+...)
        illegal_patterns = re.findall(r"\(\?<(?:!|=)[^)]*(?:\+|\*|\{[0-9]+,[0-9]*\})[^)]*\)", code)
        self.assertEqual(
            illegal_patterns, [],
            f"Found illegal variable-width lookbehind in router.py: {illegal_patterns}"
        )

    def test_prospectus_precedence(self):
        """Red Herring Prospectus must match 'Red Herring Prospectus', not plain 'Prospectus'."""
        text_rh = "RED HERRING PROSPECTUS for issue of shares by ABC Ltd"
        res = _fast_path_extract_mca_fields(text_rh, "GNL-2", self.gnl2_field_label_map)
        self.assertEqual(res.get("gnl2.main.field_2a"), "Red Herring Prospectus")

        text_plain = "PROSPECTUS for public issue of shares by XYZ Ltd"
        res_plain = _fast_path_extract_mca_fields(text_plain, "GNL-2", self.gnl2_field_label_map)
        self.assertEqual(res_plain.get("gnl2.main.field_2a"), "Prospectus")

    # =========================================================================
    # 2. Statutory Field Mappings for GNL-2 Document Types
    # =========================================================================
    def test_declaration_of_solvency_caa10(self):
        """CAA-10 Declaration of Solvency extracts all statutory fields deterministically."""
        text = """
        FORM NO. CAA.10
        [Pursuant to Section 233(1)(c) of Companies Act, 2013 and Rule 25(2) of the Companies Rules, 2016]
        DECLARATION OF SOLVENCY
        1. (a) Corporate Identification Number of the Company: U72200TN2004PTC052429
           (b) Name of the Company: SAKSOFT SOLUTIONS PRIVATE LIMITED
        2. Date of passing the Board Resolution: 06/05/2024
        3. In the matter of Scheme of Amalgamation under Section 233.
        4. Date of event: 06/05/2024
        5. Date of declaration: 06/05/2024
        """
        extracted = _fast_path_extract_mca_fields(text, "GNL-2", self.gnl2_field_label_map)

        self.assertEqual(extracted.get("gnl2.main.field_1"), "U72200TN2004PTC052429")
        self.assertEqual(extracted.get("gnl2.main.field_2a"), "Others")
        self.assertEqual(extracted.get("gnl2.main.field_2b"), "Declaration of Solvency")
        self.assertEqual(extracted.get("gnl2.main.field_4a"), "Companies Act, 2013")
        self.assertEqual(extracted.get("gnl2.main.field_4bi"), "Section 233")
        self.assertEqual(extracted.get("gnl2.main.field_5b"), "06/05/2024")
        self.assertEqual(extracted.get("gnl2.main.field_6a"), "06/05/2024")
        self.assertEqual(extracted.get("gnl2.main.field_6b"), "06/05/2024")
        self.assertEqual(extracted.get("gnl2.main.field_r"), "06/05/2024")

    def test_dpt1_circular(self):
        """Circular in form of Advertisement (DPT-1) mapping."""
        text = """
        Circular or Circular in the form of Advertisement inviting Deposits in DPT-1
        ABC Power Limited (CIN: U40101TN2000PTC045283)
        Pursuant to Section 73 of Companies Act, 2013
        Resolution dated: 20/05/2024
        Date of event: 20/05/2024
        """
        extracted = _fast_path_extract_mca_fields(text, "GNL-2", self.gnl2_field_label_map)

        self.assertEqual(extracted.get("gnl2.main.field_1"), "U40101TN2000PTC045283")
        self.assertEqual(
            extracted.get("gnl2.main.field_2a"),
            "Circular or Circular in the form of Advertisement inviting Deposits in DPT-1"
        )
        self.assertEqual(extracted.get("gnl2.main.field_4a"), "Companies Act, 2013")
        self.assertEqual(extracted.get("gnl2.main.field_4bi"), "Section 73")
        self.assertEqual(extracted.get("gnl2.main.field_5b"), "20/05/2024")
        self.assertEqual(extracted.get("gnl2.main.field_6a"), "20/05/2024")

    def test_court_rules_form_159_companies_act_1956(self):
        """Form 159 Court Rules under Companies Act, 1956 mapping."""
        text = """
        Form 159 of the Companies (Court) Rules, 1959
        High Court of Judicature at Madras
        In the matter of Companies Act, 1956
        Kaveri Gas Power Limited (CIN: U40101TN2000PTC045283)
        Order dated: 26/04/2024
        """
        extracted = _fast_path_extract_mca_fields(text, "GNL-2", self.gnl2_field_label_map)

        self.assertEqual(extracted.get("gnl2.main.field_1"), "U40101TN2000PTC045283")
        self.assertEqual(
            extracted.get("gnl2.main.field_2a"),
            "Form 159 of the Companies (Court) Rules, 1959"
        )
        self.assertEqual(extracted.get("gnl2.main.field_4a"), "Companies Act, 1956")
        self.assertEqual(extracted.get("gnl2.main.field_6a"), "26/04/2024")

    def test_nclt_order_and_resubmission(self):
        """NCLT Order reply extraction for GNL-2."""
        text = """
        Subject: Request for Approval of Form GNL 2 – SRN AB4008531 – Reply to Resubmission
        Saksoft Limited (CIN: L72200TN1999PLC054429)
        Pursuant to the order dated 08.05.2025 by the Hon'ble NCLT Chennai Bench.
        Order under section 230 to 232 of the Companies Act, 2013.
        Date of Event: 08/05/2025
        Resolution dated: 26th April 2024
        """
        extracted = _fast_path_extract_mca_fields(text, "GNL-2", self.gnl2_field_label_map)

        self.assertEqual(extracted.get("gnl2.main.field_1"), "L72200TN1999PLC054429")
        self.assertEqual(extracted.get("gnl2.main.field_2a"), "Others")
        self.assertIn("Request for Approval of Form GNL 2", extracted.get("gnl2.main.field_2b", ""))
        self.assertEqual(extracted.get("gnl2.main.field_4a"), "Companies Act, 2013")
        self.assertEqual(extracted.get("gnl2.main.field_4bi"), "Section 230 to 232")
        self.assertEqual(extracted.get("gnl2.main.field_5a"), "AB4008531")
        self.assertEqual(extracted.get("gnl2.main.field_5b"), "26/04/2024")
        self.assertEqual(extracted.get("gnl2.main.field_6a"), "08/05/2025")

    def test_ibc_section_59_affidavit(self):
        """Affidavit under Section 59 of IBC 2016."""
        text = """
        Affidavit under Section 59 of the Insolvency and Bankruptcy Code, 2016
        Company: XYZ Liquidation Corp (CIN: U12345DL2015PTC123456)
        Insolvency and Bankruptcy Code, 2016
        Date of declaration: 15/07/2024
        Director DIN: 01234567
        """
        extracted = _fast_path_extract_mca_fields(text, "GNL-2", self.gnl2_field_label_map)

        self.assertEqual(extracted.get("gnl2.main.field_1"), "U12345DL2015PTC123456")
        self.assertEqual(
            extracted.get("gnl2.main.field_2a"),
            "Affidavit under Section 59 of the Insolvency and Bankruptcy Code, 2016"
        )
        self.assertEqual(extracted.get("gnl2.main.field_4a"), "Insolvency and Bankruptcy Code, 2016")
        self.assertEqual(extracted.get("gnl2.main.field_4bii"), "Section 59")
        self.assertEqual(extracted.get("gnl2.main.field_6b"), "15/07/2024")
        self.assertEqual(extracted.get("gnl2.main.field_director_identification_number_of"), "01234567")

    # =========================================================================
    # 3. Verification of Other Forms (PAS-6, ADT-1, Generic)
    # =========================================================================
    def test_pas6_remains_fully_functional(self):
        """Verify PAS-6 deterministic extraction remains 100% intact."""
        pas6_labels = {
            "formnopas6.main.field_1": "Corporate Identity Number (CIN)",
            "formnopas6.main.field_2a": "Name of the Company",
            "formnopas6.main.field_5a": "Type of security",
            "formnopas6.main.field_5b": "ISIN",
            "formnopas6.main.field_5d": "Total number of issued shares",
            "formnopas6.main.field_5di": "Electronic Form through CDSL",
            "formnopas6.main.field_5di_2": "Electronic Form through NSDL",
            "formnopas6.main.field_5g": "Promoters and Directors breakdown"
        }
        text = """
        Subject: PAS 6 for Kritilabs Technologies Private Limited (CIN: U72200TN2004PTC052429)
        ISIN: INE012345678
        Type of security: Equity
        Total number of issued shares: 1,500,000 shares
        Electronic Form through NSDL 1,000,000
        Electronic Form through CDSL 500,000
        | (i) Promoters | 800,000 | 0 |
        | (ii) Directors | 200,000 | 0 |
        | (iii) KMPs | 0 | 0 |
        """
        extracted = _fast_path_extract_mca_fields(text, "Form No. PAS -6", pas6_labels)

        self.assertEqual(extracted.get("formnopas6.main.field_1"), "U72200TN2004PTC052429")
        self.assertIn("Kritilabs Technologies", extracted.get("formnopas6.main.field_2a", ""))
        self.assertEqual(extracted.get("formnopas6.main.field_5b"), "INE012345678")
        self.assertEqual(extracted.get("formnopas6.main.field_5d"), "1,500,000")
        self.assertEqual(extracted.get("formnopas6.main.field_5a"), "Equity")
        self.assertEqual(extracted.get("formnopas6.main.field_5di_2"), "1,000,000")
        self.assertEqual(extracted.get("formnopas6.main.field_5di"), "500,000")
        self.assertIn("Promoters", extracted.get("formnopas6.main.field_5g", ""))

    def test_adt1_auditor_resolution_date_intact(self):
        """Verify ADT-1 / DIR-12 Board Resolution mapping remains intact."""
        adt1_labels = {
            "formnoadt1.main.field_1": "Corporate Identity Number (CIN)",
            "formnoadt1.main.field_br": "Board of Directors vide resolution dated"
        }
        text = """
        Saksoft Limited CIN: L72200TN1999PLC054429
        vide resolution dated 14/08/2024 passed by the Board of Directors
        """
        extracted = _fast_path_extract_mca_fields(text, "Form No. ADT-1", adt1_labels)
        self.assertEqual(extracted.get("formnoadt1.main.field_1"), "L72200TN1999PLC054429")
        self.assertIn("14/08/2024", extracted.get("formnoadt1.main.field_br", ""))

    # =========================================================================
    # 4. Ollama Fallback & Timeout Resilience Tests
    # =========================================================================
    def test_ollama_fallback_resilience_when_offline(self):
        """Simulate Ollama offline / connect timeout; verify fast-path fields are preserved."""
        from unittest.mock import patch
        import requests

        doc_text = """
        FORM NO. CAA.10
        DECLARATION OF SOLVENCY
        CIN: U72200TN2004PTC052429
        Saksoft Solutions Private Limited
        Pursuant to Section 233 of Companies Act, 2013
        Date of passing the Board Resolution: 06/05/2024
        Date of event: 06/05/2024
        """

        # Mock requests.post to simulate connection failure on both primary and localhost Ollama
        with patch("requests.post", side_effect=requests.exceptions.ConnectTimeout("Connection timed out")):
            # Fast path must still extract 100% deterministically without crashing
            res = _fast_path_extract_mca_fields(doc_text, "GNL-2", self.gnl2_field_label_map)
            self.assertEqual(res.get("gnl2.main.field_1"), "U72200TN2004PTC052429")
            self.assertEqual(res.get("gnl2.main.field_2a"), "Others")
            self.assertEqual(res.get("gnl2.main.field_2b"), "Declaration of Solvency")
            self.assertEqual(res.get("gnl2.main.field_4a"), "Companies Act, 2013")
            self.assertEqual(res.get("gnl2.main.field_4bi"), "Section 233")
            self.assertEqual(res.get("gnl2.main.field_5b"), "06/05/2024")

    # =========================================================================
    # 5. Live End-to-End Batch API Verification
    # =========================================================================
    def test_live_api_gnl2_batch_extraction(self):
        """Call running batch endpoint for GNL-2 and assert HTTP 200, status success, and populated fields."""
        import requests
        doc_content = """
        FORM NO. CAA.10
        DECLARATION OF SOLVENCY
        1. Corporate Identification Number: U72200TN2004PTC052429
        2. Name of the Company: SAKSOFT SOLUTIONS PRIVATE LIMITED
        3. Pursuant to Section 233 of Companies Act, 2013
        4. Resolution dated: 06/05/2024
        5. Date of event: 06/05/2024
        6. Date of declaration: 06/05/2024
        """
        try:
            files = [('files', ('declaration_of_solvency.txt', doc_content.encode('utf-8'), 'text/plain'))]
            data = {'template_name': 'GNL-2'}
            resp = requests.post("http://localhost:8000/api/idp/extract/batch", files=files, data=data, timeout=10)
            self.assertEqual(resp.status_code, 200, f"Batch API failed: {resp.text}")
            res_json = resp.json()
            self.assertGreaterEqual(res_json.get("total_files", 0), 1)

            results = res_json.get("results", [])
            self.assertGreaterEqual(len(results), 1)
            first_doc = results[0]
            self.assertEqual(first_doc.get("status"), "success")

            fields_extracted = {f["key"]: f["value"] for f in first_doc.get("extracted_fields", [])}
            self.assertEqual(fields_extracted.get("gnl2.main.field_1"), "U72200TN2004PTC052429")
            self.assertEqual(fields_extracted.get("gnl2.main.field_2a"), "Others")
            self.assertEqual(fields_extracted.get("gnl2.main.field_2b"), "Declaration of Solvency")
            self.assertEqual(fields_extracted.get("gnl2.main.field_4a"), "Companies Act, 2013")
            self.assertEqual(fields_extracted.get("gnl2.main.field_4bi"), "Section 233")
            self.assertEqual(fields_extracted.get("gnl2.main.field_5b"), "06/05/2024")
        except requests.exceptions.ConnectionError:
            self.skipTest("Local uvicorn server not reachable at http://localhost:8000")

    def test_live_api_pas6_batch_extraction(self):
        """Call running batch endpoint for PAS-6 and assert HTTP 200 and status success."""
        import requests
        doc_content = """
        Subject: PAS 6 for Kritilabs Technologies Private Limited (CIN: U72200TN2004PTC052429)
        ISIN: INE012345678
        Type of security: Equity
        Total number of issued shares: 1,500,000 shares
        Electronic Form through NSDL 1,000,000
        Electronic Form through CDSL 500,000
        | (i) Promoters | 800,000 | 0 |
        | (ii) Directors | 200,000 | 0 |
        | (iii) KMPs | 0 | 0 |
        """
        try:
            files = [('files', ('pas6_doc.txt', doc_content.encode('utf-8'), 'text/plain'))]
            data = {'template_name': 'Form No. PAS -6'}
            resp = requests.post("http://localhost:8000/api/idp/extract/batch", files=files, data=data, timeout=10)
            self.assertEqual(resp.status_code, 200, f"Batch API failed: {resp.text}")
            res_json = resp.json()
            results = res_json.get("results", [])
            self.assertGreaterEqual(len(results), 1)
            self.assertIn(results[0].get("status"), ["success", "review"])

            fields_extracted = {f["key"]: f["value"] for f in results[0].get("extracted_fields", [])}
            self.assertEqual(fields_extracted.get("formnopas6.main.field_1"), "U72200TN2004PTC052429")
            self.assertEqual(fields_extracted.get("formnopas6.main.field_5d"), "1,500,000")
            self.assertEqual(fields_extracted.get("formnopas6.main.field_5a"), "Equity")
        except requests.exceptions.ConnectionError:
            self.skipTest("Local uvicorn server not reachable at http://localhost:8000")


if __name__ == "__main__":
    unittest.main()
