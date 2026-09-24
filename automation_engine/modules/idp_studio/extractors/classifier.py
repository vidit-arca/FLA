"""
Document Classifier Engine for IDP Studio & Extractor App.
Determines document type and operative statutory branch from legal resolutions.
"""

import re
from typing import Optional, Dict, Any

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


def detect_operative_statutory_branch(text: str, filename: str = "") -> Dict[str, Any]:
    """
    Scans the Operative Clause (text following 'RESOLVED THAT') to detect which statutory
    branch of MCA Form ADT-1 / appointment applies.
    
    Precedence Hierarchy under the Companies Act, 2013:
      1. Section 140(5) / NCLT Tribunal Order
      2. Section 139(5) / Central Government (CAG) Appointment
      3. Section 139(8) / Casual Vacancy (Resignation or Death)
      4. Section 139(1) / Regular AGM Appointment (Statutory Baseline)
    """
    clean_text = text or ""
    
    # 1. Isolate the operative clause starting from 'RESOLVED THAT'
    # under ICSI SS-1 standard, the operative resolution is the primary legal declaration
    match = re.search(r"RESOLVED\s+THAT.*?(?=RESOLVED\s+FURTHER|\.\s+[A-Z]|\Z)", clean_text, re.DOTALL | re.IGNORECASE)
    operative_clause = match.group(0).strip() if match else clean_text

    # Helper to create clean evidence snippet
    def _snippet(cl: str, max_len: int = 180) -> str:
        s = " ".join(cl.split())
        return s[:max_len] + "..." if len(s) > max_len else s

    # Check 1: Section 140(5) / Tribunal Order
    if re.search(r"140\s*\(\s*5\s*\)|tribunal|nclt|national\s+company\s+law\s+tribunal", operative_clause, re.IGNORECASE):
        return {
            "recommended_branch": "Auditor appointed by the Tribunal",
            "scenario_key": "tribunal_order",
            "sub_reason": None,
            "section_cited": "Section 140(5)",
            "confidence": 0.98 if "140" in operative_clause else 0.85,
            "evidence_snippet": _snippet(operative_clause)
        }

    # Check 2: Section 139(5) / Central Government / CAG
    if re.search(r"139\s*\(\s*5\s*\)|139\s*\(\s*7\s*\)|comptroller|cag|central\s+government", operative_clause, re.IGNORECASE):
        return {
            "recommended_branch": "Auditor appointed by Central Government",
            "scenario_key": "central_gov",
            "sub_reason": None,
            "section_cited": "Section 139(5)",
            "confidence": 0.98 if "139" in operative_clause else 0.85,
            "evidence_snippet": _snippet(operative_clause)
        }

    # Check 3: Section 139(8) / Casual Vacancy
    if re.search(r"139\s*\(\s*8\s*\)|casual\s+vacancy|resignation|demise|death", operative_clause, re.IGNORECASE):
        reason = "Resignation"
        if re.search(r"demise|death|deceased", operative_clause, re.IGNORECASE):
            reason = "Death"
        return {
            "recommended_branch": "Casual Vacancy",
            "scenario_key": "casual_vacancy",
            "sub_reason": reason,
            "section_cited": "Section 139(8)",
            "confidence": 0.98 if ("139" in operative_clause or "casual vacancy" in operative_clause.lower()) else 0.88,
            "evidence_snippet": _snippet(operative_clause)
        }

    # Check 4: Section 139(1) / Regular AGM Appointment (Statutory Baseline)
    if re.search(r"139\s*\(\s*1\s*\)|annual\s+general\s+meeting|agm|5\s+consecutive\s+years", operative_clause, re.IGNORECASE):
        return {
            "recommended_branch": "Appointment/ Re-appointment in AGM",
            "scenario_key": "agm_appointment",
            "sub_reason": None,
            "section_cited": "Section 139(1)",
            "confidence": 0.95,
            "evidence_snippet": _snippet(operative_clause)
        }

    # Fallback default if document is unclear or generic
    return {
        "recommended_branch": "Appointment/ Re-appointment in AGM",
        "scenario_key": "agm_appointment",
        "sub_reason": None,
        "section_cited": "Section 139(1)",
        "confidence": 0.60,
        "evidence_snippet": _snippet(operative_clause) if operative_clause else "Standard statutory baseline"
    }
