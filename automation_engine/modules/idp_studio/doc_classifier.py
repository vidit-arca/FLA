"""
Document Classifier Engine for IDP Studio & Extractor App.
Determines document type to enable strict document-type scoped rule evaluation.
"""

import re
from typing import Optional

def classify_document(filename: str = "", text: str = "") -> str:
    """
    Classifies a document into its specific document type based on filename and text content.
    Returns one of:
      - 'consent_letter'
      - 'board_resolution'
      - 'auditor_certificate'
      - 'generic'
    """
    fname = (filename or "").lower().replace("-", " ").replace("_", " ")
    doc_text = (text or "").lower()

    # 1. Check Board Resolution / Certified True Copy (CTC)
    br_keywords = [
        "certified true copy",
        "board resolution",
        "ctc bm",
        "ctc agm",
        "meeting of the board of directors",
        "resolved that",
        "board meeting",
        "extract of the resolution"
    ]
    if any(k in fname for k in ["ctc", "board resolution", "bm signed", "agm auditor"]):
        return "board_resolution"
    if any(k in doc_text for k in br_keywords):
        return "board_resolution"

    # 2. Check Consent / Appointment Letter
    consent_keywords = [
        "consent and eligibility",
        "consent letter",
        "appointment as statutory auditor",
        "appointment letter",
        "eligibility certificate",
        "we hereby give our consent",
        "subject: appointment",
        "sub: appointment"
    ]
    if any(k in fname for k in ["consent", "appointment letter", "appointment ltr"]):
        return "consent_letter"
    if any(k in doc_text for k in consent_keywords):
        return "consent_letter"

    # 3. Check Auditor Certificate
    cert_keywords = [
        "auditor certificate",
        "certificate of auditor",
        "to whomsoever it may concern",
        "certificate under section",
        "statutory auditor certificate"
    ]
    if any(k in fname for k in ["auditor cert", "certificate merged", "auditor certificate"]):
        return "auditor_certificate"
    if any(k in doc_text for k in cert_keywords):
        return "auditor_certificate"

    return "generic"
