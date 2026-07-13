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
        
        # Mathematical Fallback: If Net Worth is not explicitly stated in the document, calculate it.
        if net_worth is None and puc is not None and reserves is not None:
            net_worth = puc + reserves
            
        borrowings = self._parse_numeric(input_data.get("borrowings"))
        net_profit = self._parse_numeric(input_data.get("net_profit_before_tax"))
        
        is_subsidiary_or_holding = str(input_data.get("is_subsidiary_or_holding", "no")).lower() == "yes"
        is_listed = str(input_data.get("is_listed", "no")).lower() == "yes"
        is_ind_as = str(input_data.get("is_ind_as", "no")).lower() == "yes"
        company_type = str(input_data.get("company_type", "private limited company")).lower()
        
        loan_to_directors_assets = self._parse_numeric(input_data.get("loan_to_directors_assets")) or 0.0
        secured_loan = self._parse_numeric(input_data.get("secured_loan")) or 0.0
        loan_from_directors = self._parse_numeric(input_data.get("loan_from_directors")) or 0.0
        advance_from_customers = self._parse_numeric(input_data.get("advance_from_customers")) or 0.0
        dues_to_msme = self._parse_numeric(input_data.get("dues_to_msme")) or 0.0
        
        has_corporate_shareholders = input_data.get("has_corporate_shareholders")
        if isinstance(has_corporate_shareholders, str):
            has_corporate_shareholders = has_corporate_shareholders.lower()
        
        rpt_sale_goods = self._parse_numeric(input_data.get("rpt_sale_goods")) or 0.0
        rpt_purchase_goods = self._parse_numeric(input_data.get("rpt_purchase_goods")) or 0.0
        rpt_monthly_remun = self._parse_numeric(input_data.get("rpt_monthly_remun")) or 0.0
        total_rpt_value = rpt_sale_goods + rpt_purchase_goods + rpt_monthly_remun
        
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
            flags.append({"id": "COMP_IND_AS", "particulars": "IND AS applicability", "status": "Failed", "user_value": "Applicable", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_IND_AS", "particulars": "IND AS applicability", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})

        # 10. MGT 8 Applicability
        if puc is None or turnover is None:
            flags.append({"id": "COMP_MGT_8", "particulars": "MGT 8 Applicability", "status": "Manual", "user_value": "Missing Data", "reason": "Missing PUC or Turnover", "source": "Compliance Engine"})
        elif is_listed or puc >= (10 * CR) or turnover >= (50 * CR):
            flags.append({"id": "COMP_MGT_8", "particulars": "MGT 8 Applicability", "status": "Failed", "user_value": "Applicable", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_MGT_8", "particulars": "MGT 8 Applicability", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})

        # 11. Certification of MGT 7
        if is_small_company:
            flags.append({"id": "COMP_MGT_7_CERT", "particulars": "Certification of MGT 7", "status": "Passed", "user_value": "Not Applicable", "reason": "It is a small company", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_MGT_7_CERT", "particulars": "Certification of MGT 7", "status": "Failed", "user_value": "Applicable", "reason": "", "source": "Compliance Engine"})

        # 12. Secretarial Audit
        if puc is None or turnover is None or borrowings is None:
            flags.append({"id": "COMP_SEC_AUDIT", "particulars": "Secretarial Audit", "status": "Manual", "user_value": "Missing Data", "reason": "Missing PUC, Turnover, or Borrowings", "source": "Compliance Engine"})
        elif is_listed or borrowings >= (100 * CR) or ("public" in company_type and (puc >= (50 * CR) or turnover >= (250 * CR))):
            flags.append({"id": "COMP_SEC_AUDIT", "particulars": "Secretarial Audit", "status": "Failed", "user_value": "Applicable", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_SEC_AUDIT", "particulars": "Secretarial Audit", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})

        # 13. KMP appointment
        if puc is None:
            flags.append({"id": "COMP_KMP", "particulars": "KMP appointment", "status": "Manual", "user_value": "Missing Data", "reason": "Missing PUC", "source": "Compliance Engine"})
        elif is_listed or ("public" in company_type and puc >= (10 * CR)) or puc >= (10 * CR):
            flags.append({"id": "COMP_KMP", "particulars": "KMP appointment", "status": "Failed", "user_value": "Applicable", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_KMP", "particulars": "KMP appointment", "status": "Passed", "user_value": "Not Applicable", "reason": "Thresholds not met", "source": "Compliance Engine"})

        # 14. Loan Investment Guarantee - 186
        has_loans = str(input_data.get("has_loans_investments_guarantees", "no")).lower() == "yes"
        if has_loans:
            flags.append({"id": "COMP_LOAN_186", "particulars": "Loan Investment Guarantee - 186", "status": "Failed", "user_value": "Check for Boards Approval", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_LOAN_186", "particulars": "Loan Investment Guarantee - 186", "status": "Passed", "user_value": "Not Applicable", "reason": "No loans/investments/guarantees", "source": "Compliance Engine"})

        # 15. Loan to Director or Related entities
        if loan_to_directors_assets > 0:
            flags.append({"id": "COMP_LOAN_DIRECTOR", "particulars": "Loan to Director or Related entities", "status": "Failed", "user_value": "Check for Sec 185 Compliance", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_LOAN_DIRECTOR", "particulars": "Loan to Director or Related entities", "status": "Passed", "user_value": "Not Applicable", "reason": "No loans to directors", "source": "Compliance Engine"})
            
        # 16. Cost Audit
        flags.append({"id": "COMP_COST_AUDIT", "particulars": "Cost Audit", "status": "Passed", "user_value": "NA", "reason": "Manual review required", "source": "Compliance Engine"})
        
        # 17. Charge form
        if (borrowings or 0) > 0:
            flags.append({"id": "COMP_CHARGE_FORM", "particulars": "Charge form", "status": "Failed", "user_value": "Applicable, Check if CHG form filed", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_CHARGE_FORM", "particulars": "Charge form", "status": "Passed", "user_value": "Not Applicable", "reason": "No borrowings", "source": "Compliance Engine"})
            
        # 18. AOC 1
        if is_subsidiary_or_holding:
            flags.append({"id": "COMP_AOC_1", "particulars": "AOC 1", "status": "Failed", "user_value": "Applicable, Check AOC 1 is annexed with Board's report", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_AOC_1", "particulars": "AOC 1", "status": "Passed", "user_value": "Not Applicable", "reason": "Not a holding/subsidiary", "source": "Compliance Engine"})
            
        # 19. AOC 2 & RPT Resolution
        if total_rpt_value > 0:
            flags.append({"id": "COMP_AOC_2", "particulars": "AOC 2", "status": "Failed", "user_value": "Applicable, Fill in Sec 188 Compliance sheet", "reason": "", "source": "Compliance Engine"})
            flags.append({"id": "COMP_RPT_OMNIBUS", "particulars": "RPT Resolution for omnibus approval", "status": "Failed", "user_value": "Applicable, Fill in Sec 188 Compliance sheet", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_AOC_2", "particulars": "AOC 2", "status": "Passed", "user_value": "Not Applicable", "reason": "No specific RPT found", "source": "Compliance Engine"})
            flags.append({"id": "COMP_RPT_OMNIBUS", "particulars": "RPT Resolution for omnibus approval", "status": "Passed", "user_value": "Not Applicable", "reason": "No specific RPT found", "source": "Compliance Engine"})
            
        # 20. CSR Committee
        if net_profit is not None and (net_profit * 3 * 0.02) > 5000000:
            flags.append({"id": "COMP_CSR_COMMITTEE", "particulars": "CSR Committee", "status": "Failed", "user_value": "Check CSR Committee compliance", "reason": "", "source": "Compliance Engine"})
        elif net_profit is not None:
            flags.append({"id": "COMP_CSR_COMMITTEE", "particulars": "CSR Committee", "status": "Passed", "user_value": "Not Applicable", "reason": "Estimated CSR spend under 50L", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_CSR_COMMITTEE", "particulars": "CSR Committee", "status": "Manual", "user_value": "Missing Data", "reason": "Missing Net Profit", "source": "Compliance Engine"})
            
        # 21. Deposit declaration
        if loan_from_directors > 0:
            flags.append({"id": "COMP_DEPOSIT_DEC", "particulars": "Deposit declaration", "status": "Failed", "user_value": "Applicable, Is deposit declaration obtained", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_DEPOSIT_DEC", "particulars": "Deposit declaration", "status": "Passed", "user_value": "Not Applicable", "reason": "No loan from directors", "source": "Compliance Engine"})
            
        # 22. DPT 3
        if (borrowings or 0) + advance_from_customers > 0:
            flags.append({"id": "COMP_DPT_3", "particulars": "DPT 3", "status": "Failed", "user_value": "Applicable, Is Form DPT 3 filed", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_DPT_3", "particulars": "DPT 3", "status": "Passed", "user_value": "Not Applicable", "reason": "No borrowings or advances", "source": "Compliance Engine"})
            
        # 23. MSME
        if dues_to_msme > 0:
            flags.append({"id": "COMP_MSME", "particulars": "MSME", "status": "Failed", "user_value": "Applicable, Is Form MSME filed", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_MSME", "particulars": "MSME", "status": "Passed", "user_value": "Not Applicable", "reason": "No dues to MSME", "source": "Compliance Engine"})
            
        # 24. Ben 2
        if has_corporate_shareholders is None:
            flags.append({"id": "COMP_BEN_2", "particulars": "Ben 2", "status": "Manual", "user_value": "Missing Data", "reason": "Could not locate Share Capital / Shareholder notes in document", "source": "Compliance Engine"})
        elif has_corporate_shareholders == "yes":
            flags.append({"id": "COMP_BEN_2", "particulars": "Ben 2", "status": "Failed", "user_value": "Ben Compliance to be checked", "reason": "", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_BEN_2", "particulars": "Ben 2", "status": "Passed", "user_value": "Not Applicable", "reason": "No corporate shareholders found", "source": "Compliance Engine"})

        return flags
