import re

class PrivateComplianceEngine:
    def __init__(self):
        pass
        
    def _parse_numeric(self, value):
        if value is None or str(value).strip() == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        
        # Remove commas, currency symbols, and text
        clean_str = re.sub(r'[^\d.-]', '', str(value))
        try:
            return float(clean_str) if clean_str else None
        except ValueError:
            return None
            
    def execute(self, input_data: dict) -> list:
        """
        Evaluate financial metrics against compliance thresholds.
        Values are assumed to be supplied in absolute Rupees.
        """
        flags = []
        CR = 10000000.0 # 1 Crore in Rupees
        
        turnover = self._parse_numeric(input_data.get("turnover"))
        puc = self._parse_numeric(input_data.get("paid_up_capital"))
        net_worth = self._parse_numeric(input_data.get("net_worth"))
        reserves = self._parse_numeric(input_data.get("reserves_and_surplus"))
        borrowings = self._parse_numeric(input_data.get("borrowings"))
        net_profit = self._parse_numeric(input_data.get("net_profit_before_tax"))
        
        is_subsidiary_or_holding = str(input_data.get("is_subsidiary_or_holding", "no")).lower() == "yes"
        is_listed = str(input_data.get("is_listed", "no")).lower() == "yes"
        is_ind_as = str(input_data.get("is_ind_as", "no")).lower() == "yes"
        company_type = str(input_data.get("company_type", "private limited company")).lower()
        
        # 1. Is it a Small Company?
        if turnover is None or puc is None:
            flags.append({"id": "COMP_SMALL_CO", "particulars": "Is it a Small Company?", "status": "Manual", "user_value": "Missing Data", "reason": "Missing Turnover or PUC data", "source": "Compliance Engine"})
            is_small_company = False
        elif turnover < (100 * CR) and puc < (10 * CR) and not is_subsidiary_or_holding:
            flags.append({"id": "COMP_SMALL_CO", "particulars": "Is it a Small Company?", "status": "Passed", "user_value": "Yes, It is a Small Company", "reason": "Meets limits and not holding/sub", "source": "Compliance Engine"})
            is_small_company = True
        else:
            flags.append({"id": "COMP_SMALL_CO", "particulars": "Is it a Small Company?", "status": "Failed", "user_value": "No", "reason": "Exceeds limits or is holding/sub", "source": "Compliance Engine"})
            is_small_company = False

        # 2. CARO Applicability
        if "private" in company_type and not is_small_company:
            if puc is None or reserves is None or borrowings is None or turnover is None:
                flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Manual", "user_value": "Missing Data", "reason": "Missing required financial fields", "source": "Compliance Engine"})
            elif (puc + reserves) <= (1 * CR) and borrowings <= (1 * CR) and turnover <= (10 * CR):
                flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Passed", "user_value": "Not Applicable", "reason": "Exempted Private Company thresholds met", "source": "Compliance Engine"})
            else:
                flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Failed", "user_value": "Applicable", "reason": "Exceeded Private Company exemption thresholds", "source": "Compliance Engine"})
        elif is_small_company or "one person" in company_type:
            flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Passed", "user_value": "Not Applicable", "reason": "Small Company or OPC", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Failed", "user_value": "Applicable", "reason": "Standard Applicability", "source": "Compliance Engine"})

        # 3. Corporate Social Responsibility (CSR)
        if net_worth is None or turnover is None or net_profit is None:
            flags.append({"id": "COMP_CSR", "particulars": "Corporate Social Responsibility", "status": "Manual", "user_value": "Missing Data", "reason": "Missing Net Worth, Turnover, or Net Profit", "source": "Compliance Engine"})
        elif net_worth >= (500 * CR) or turnover >= (1000 * CR) or net_profit >= (5 * CR):
            flags.append({"id": "COMP_CSR", "particulars": "Corporate Social Responsibility", "status": "Failed", "user_value": "Applicable", "reason": "Threshold met", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_CSR", "particulars": "Corporate Social Responsibility", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})
            
        # 4. Rotation of Auditors
        if puc is None and "private" in company_type and not is_listed:
            flags.append({"id": "COMP_ROTATION", "particulars": "Rotation of Auditors", "status": "Manual", "user_value": "Missing Data", "reason": "Missing PUC", "source": "Compliance Engine"})
        elif is_listed or "public" in company_type:
            flags.append({"id": "COMP_ROTATION", "particulars": "Rotation of Auditors", "status": "Failed", "user_value": "Applicable", "reason": "Listed or Public Company", "source": "Compliance Engine"})
        elif "private" in company_type and puc >= (50 * CR):
            flags.append({"id": "COMP_ROTATION", "particulars": "Rotation of Auditors", "status": "Failed", "user_value": "Applicable", "reason": "Private Company with PUC >= 50 Cr", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_ROTATION", "particulars": "Rotation of Auditors", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})
            
        # 5. XBRL Filing
        if puc is None or turnover is None:
            flags.append({"id": "COMP_XBRL", "particulars": "XBRL filing", "status": "Manual", "user_value": "Missing Data", "reason": "Missing PUC or Turnover", "source": "Compliance Engine"})
        elif is_listed or puc >= (5 * CR) or turnover >= (100 * CR) or is_ind_as:
            flags.append({"id": "COMP_XBRL", "particulars": "XBRL filing", "status": "Failed", "user_value": "Applicable", "reason": "Listed, PUC >= 5Cr, TO >= 100Cr, or IND AS", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_XBRL", "particulars": "XBRL filing", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})
            
        # 6. Vigil Mechanism
        if borrowings is None:
            flags.append({"id": "COMP_VIGIL", "particulars": "Vigil Mechanism", "status": "Manual", "user_value": "Missing Data", "reason": "Missing Borrowings data", "source": "Compliance Engine"})
        elif borrowings > (50 * CR):
            flags.append({"id": "COMP_VIGIL", "particulars": "Vigil Mechanism", "status": "Failed", "user_value": "Applicable", "reason": "Borrowings exceed 50 Cr", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_VIGIL", "particulars": "Vigil Mechanism", "status": "Passed", "user_value": "Not Applicable", "reason": "Borrowings under 50 Cr", "source": "Compliance Engine"})

        # 7. Internal Financial Controls
        if "private" in company_type:
            if turnover is None or borrowings is None:
                flags.append({"id": "COMP_IFC", "particulars": "Internal Financial Controls", "status": "Manual", "user_value": "Missing Data", "reason": "Missing Turnover or Borrowings", "source": "Compliance Engine"})
            elif turnover < (50 * CR) and borrowings < (25 * CR):
                flags.append({"id": "COMP_IFC", "particulars": "Internal Financial Controls", "status": "Passed", "user_value": "Not Applicable", "reason": "Private Co with TO < 50Cr and Borrowings < 25Cr", "source": "Compliance Engine"})
            else:
                flags.append({"id": "COMP_IFC", "particulars": "Internal Financial Controls", "status": "Failed", "user_value": "Applicable", "reason": "Standard Applicability", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_IFC", "particulars": "Internal Financial Controls", "status": "Failed", "user_value": "Applicable", "reason": "Standard Applicability", "source": "Compliance Engine"})

        # 8. Internal Audit
        if turnover is None or borrowings is None:
            flags.append({"id": "COMP_INT_AUDIT", "particulars": "Internal Audit", "status": "Manual", "user_value": "Missing Data", "reason": "Missing Turnover or Borrowings", "source": "Compliance Engine"})
        elif turnover >= (200 * CR) or borrowings >= (100 * CR):
            flags.append({"id": "COMP_INT_AUDIT", "particulars": "Internal Audit", "status": "Failed", "user_value": "Applicable", "reason": "Turnover >= 200Cr or Borrowings >= 100Cr", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_INT_AUDIT", "particulars": "Internal Audit", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})

        # 9. IND AS Applicability
        if net_worth is None and not (is_ind_as or is_listed):
            flags.append({"id": "COMP_IND_AS", "particulars": "IND AS applicability", "status": "Manual", "user_value": "Missing Data", "reason": "Missing Net Worth", "source": "Compliance Engine"})
        elif is_ind_as or is_listed or net_worth >= (250 * CR):
            flags.append({"id": "COMP_IND_AS", "particulars": "IND AS applicability", "status": "Failed", "user_value": "Applicable", "reason": "Listed or NW >= 250Cr", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_IND_AS", "particulars": "IND AS applicability", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})

        # 10. MGT 8 Applicability
        if puc is None or turnover is None:
            flags.append({"id": "COMP_MGT_8", "particulars": "MGT 8 Applicability", "status": "Manual", "user_value": "Missing Data", "reason": "Missing PUC or Turnover", "source": "Compliance Engine"})
        elif is_listed or puc >= (10 * CR) or turnover >= (50 * CR):
            flags.append({"id": "COMP_MGT_8", "particulars": "MGT 8 Applicability", "status": "Failed", "user_value": "Applicable", "reason": "Listed, PUC >= 10Cr, or TO >= 50Cr", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_MGT_8", "particulars": "MGT 8 Applicability", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})

        # 11. Certification of MGT 7
        if is_small_company:
            flags.append({"id": "COMP_MGT_7_CERT", "particulars": "Certification of MGT 7", "status": "Passed", "user_value": "Not Applicable", "reason": "It is a small company", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_MGT_7_CERT", "particulars": "Certification of MGT 7", "status": "Failed", "user_value": "Applicable", "reason": "Not a small company", "source": "Compliance Engine"})

        # 12. Secretarial Audit
        if puc is None or turnover is None or borrowings is None:
            flags.append({"id": "COMP_SEC_AUDIT", "particulars": "Secretarial Audit", "status": "Manual", "user_value": "Missing Data", "reason": "Missing PUC, Turnover, or Borrowings", "source": "Compliance Engine"})
        elif is_listed or borrowings >= (100 * CR) or ("public" in company_type and (puc >= (50 * CR) or turnover >= (250 * CR))):
            flags.append({"id": "COMP_SEC_AUDIT", "particulars": "Secretarial Audit", "status": "Failed", "user_value": "Applicable", "reason": "Listed, Borrowings >= 100Cr, or Public Co with PUC>=50Cr/TO>=250Cr", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_SEC_AUDIT", "particulars": "Secretarial Audit", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})

        # 13. KMP appointment
        if puc is None:
            flags.append({"id": "COMP_KMP", "particulars": "KMP appointment", "status": "Manual", "user_value": "Missing Data", "reason": "Missing PUC", "source": "Compliance Engine"})
        elif is_listed or ("public" in company_type and puc >= (10 * CR)) or puc >= (10 * CR):
            flags.append({"id": "COMP_KMP", "particulars": "KMP appointment", "status": "Failed", "user_value": "Applicable", "reason": "Listed, or PUC >= 10Cr", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_KMP", "particulars": "KMP appointment", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})

        # 14. Loan Investment Guarantee - 186
        has_loans = str(input_data.get("has_loans_investments_guarantees", "no")).lower() == "yes"
        if has_loans:
            flags.append({"id": "COMP_LOAN_186", "particulars": "Loan Investment Guarantee - 186", "status": "Failed", "user_value": "Check for Boards Approval", "reason": "Company has loans/investments/guarantees", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_LOAN_186", "particulars": "Loan Investment Guarantee - 186", "status": "Passed", "user_value": "Not Applicable", "reason": "No loans/investments/guarantees", "source": "Compliance Engine"})

        return flags
