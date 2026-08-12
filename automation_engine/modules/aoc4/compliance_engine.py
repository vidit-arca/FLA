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
        
        turnover = self._parse_numeric(input_data.get("turnover")) or 0.0
        puc = self._parse_numeric(input_data.get("paid_up_capital")) or 0.0
        net_worth = self._parse_numeric(input_data.get("net_worth")) or 0.0
        reserves = self._parse_numeric(input_data.get("reserves_and_surplus")) or 0.0
        
        # Mathematical Fallback: If Net Worth is not explicitly stated in the document, calculate it.
        if net_worth == 0.0 and (puc != 0.0 or reserves != 0.0):
            net_worth = puc + reserves
            
        borrowings = self._parse_numeric(input_data.get("borrowings")) or 0.0
        net_profit = self._parse_numeric(input_data.get("net_profit_before_tax")) or 0.0
        
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
            flags.append({"id": "COMP_SMALL_CO", "particulars": "Is it a Small Company?", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Turnover or PUC data.", "source": "Compliance Engine"})
            is_small_company = False
        elif turnover < (100 * CR) and puc < (10 * CR) and not is_subsidiary_or_holding:
            flags.append({"id": "COMP_SMALL_CO", "particulars": "Is it a Small Company?", "status": "Passed", "user_value": "Yes", "rationale": f"Turnover ({turnover/CR:.2f} Cr) < 100 Cr AND PUC ({puc/CR:.2f} Cr) < 10 Cr AND Not Holding/Sub.", "source": "Compliance Engine"})
            is_small_company = True
        else:
            reason_str = f"Limits Exceeded: Turnover ({turnover/CR:.2f} Cr), PUC ({puc/CR:.2f} Cr), or Holding/Sub ({is_subsidiary_or_holding})"
            flags.append({"id": "COMP_SMALL_CO", "particulars": "Is it a Small Company?", "status": "Failed", "user_value": "No", "rationale": reason_str, "source": "Compliance Engine"})
            is_small_company = False
            
        input_data["is_small_company_calculated"] = is_small_company

        # 2. CARO Applicability
        if "private" in company_type and not is_small_company:
            if puc is None or reserves is None or borrowings is None or turnover is None:
                flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing data for PUC, Reserves, Borrowings, or Turnover.", "source": "Compliance Engine"})
            elif (puc + reserves) <= (1 * CR) and borrowings <= (1 * CR) and turnover <= (10 * CR):
                flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Passed", "user_value": "Not Applicable", "rationale": f"PUC+Reserves ({(puc+reserves)/CR:.2f} Cr) <= 1 Cr AND Borrowings ({borrowings/CR:.2f} Cr) <= 1 Cr AND Turnover ({turnover/CR:.2f} Cr) <= 10 Cr.", "source": "Compliance Engine"})
            else:
                flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Failed", "user_value": "Applicable", "rationale": f"Threshold Exceeded: PUC+Reserves ({(puc+reserves)/CR:.2f} Cr) > 1 Cr OR Borrowings ({borrowings/CR:.2f} Cr) > 1 Cr OR Turnover ({turnover/CR:.2f} Cr) > 10 Cr.", "source": "Compliance Engine"})
        elif is_small_company or "one person" in company_type:
            flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Passed", "user_value": "Not Applicable", "rationale": "Exempt because it is a Small Company or OPC.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_CARO", "particulars": "CARO Applicability", "status": "Failed", "user_value": "Applicable", "rationale": f"Not a private company. Type is {company_type}.", "source": "Compliance Engine"})

        # 3. Corporate Social Responsibility (CSR)
        is_csr_applicable = False
        if net_worth is None or turnover is None or net_profit is None:
            flags.append({"id": "COMP_CSR", "particulars": "Corporate Social Responsibility", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Net Worth, Turnover, or PBT data.", "source": "Compliance Engine"})
        elif net_worth >= (500 * CR) or turnover >= (1000 * CR) or net_profit >= (5 * CR):
            is_csr_applicable = True
            flags.append({"id": "COMP_CSR", "particulars": "Corporate Social Responsibility", "status": "Failed", "user_value": "Applicable", "rationale": f"Threshold Exceeded: Net Worth ({net_worth/CR:.2f} Cr) >= 500 Cr OR Turnover ({turnover/CR:.2f} Cr) >= 1000 Cr OR Net Profit ({net_profit/CR:.2f} Cr) >= 5 Cr.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_CSR", "particulars": "Corporate Social Responsibility", "status": "Passed", "user_value": "Not Applicable", "rationale": f"Net Worth ({net_worth/CR:.2f} Cr) < 500 Cr, Turnover ({turnover/CR:.2f} Cr) < 1000 Cr, Net Profit ({net_profit/CR:.2f} Cr) < 5 Cr.", "source": "Compliance Engine"})
        
        input_data["is_csr_applicable_calculated"] = is_csr_applicable
            
        # 4. Rotation of Auditors
        if puc is None and "private" in company_type and not is_listed:
            flags.append({"id": "COMP_ROTATION", "particulars": "Rotation of Auditors", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Paid-up Capital data.", "source": "Compliance Engine"})
        elif is_listed or "public" in company_type:
            flags.append({"id": "COMP_ROTATION", "particulars": "Rotation of Auditors", "status": "Failed", "user_value": "Applicable", "rationale": "Listed or Public company.", "source": "Compliance Engine"})
        elif "private" in company_type and puc >= (50 * CR):
            flags.append({"id": "COMP_ROTATION", "particulars": "Rotation of Auditors", "status": "Failed", "user_value": "Applicable", "rationale": f"Private company with Paid-up Capital ({puc/CR:.2f} Cr) >= 50 Cr.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_ROTATION", "particulars": "Rotation of Auditors", "status": "Passed", "user_value": "Not Applicable", "rationale": f"Private unlisted company with Paid-up Capital ({puc/CR:.2f} Cr) < 50 Cr.", "source": "Compliance Engine"})
            
        # 5. XBRL Filing
        if puc is None or turnover is None:
            flags.append({"id": "COMP_XBRL", "particulars": "XBRL filing", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Paid-up Capital or Turnover data.", "source": "Compliance Engine"})
        elif is_listed or puc >= (5 * CR) or turnover >= (100 * CR) or is_ind_as:
            flags.append({"id": "COMP_XBRL", "particulars": "XBRL filing", "status": "Failed", "user_value": "Applicable", "rationale": f"Listed ({is_listed}) OR Ind AS ({is_ind_as}) OR PUC ({puc/CR:.2f} Cr) >= 5 Cr OR Turnover ({turnover/CR:.2f} Cr) >= 100 Cr.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_XBRL", "particulars": "XBRL filing", "status": "Passed", "user_value": "Not Applicable", "rationale": f"PUC ({puc/CR:.2f} Cr) < 5 Cr AND Turnover ({turnover/CR:.2f} Cr) < 100 Cr (Unlisted, non-Ind AS).", "source": "Compliance Engine"})
            
        # 6. Vigil Mechanism
        if borrowings is None:
            flags.append({"id": "COMP_VIGIL", "particulars": "Vigil Mechanism", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Borrowings data.", "source": "Compliance Engine"})
        elif borrowings > (50 * CR):
            flags.append({"id": "COMP_VIGIL", "particulars": "Vigil Mechanism", "status": "Failed", "user_value": "Applicable", "rationale": f"Total Borrowings ({borrowings/CR:.2f} Cr) > 50 Cr limit.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_VIGIL", "particulars": "Vigil Mechanism", "status": "Passed", "user_value": "Not Applicable", "rationale": f"Total Borrowings ({borrowings/CR:.2f} Cr) <= 50 Cr.", "source": "Compliance Engine"})

        # 7. Internal Financial Controls
        if "private" in company_type:
            if turnover is None or borrowings is None:
                flags.append({"id": "COMP_IFC", "particulars": "Internal Financial Controls", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Turnover or Borrowings data.", "source": "Compliance Engine"})
            elif turnover < (50 * CR) and borrowings < (25 * CR):
                flags.append({"id": "COMP_IFC", "particulars": "Internal Financial Controls", "status": "Passed", "user_value": "Not Applicable", "rationale": f"Private company with Turnover ({turnover/CR:.2f} Cr) < 50 Cr AND Borrowings ({borrowings/CR:.2f} Cr) < 25 Cr.", "source": "Compliance Engine"})
            else:
                flags.append({"id": "COMP_IFC", "particulars": "Internal Financial Controls", "status": "Failed", "user_value": "Applicable", "rationale": f"Threshold Exceeded: Turnover ({turnover/CR:.2f} Cr) >= 50 Cr OR Borrowings ({borrowings/CR:.2f} Cr) >= 25 Cr.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_IFC", "particulars": "Internal Financial Controls", "status": "Failed", "user_value": "Applicable", "rationale": "Not a private company.", "source": "Compliance Engine"})

        # 8. Internal Audit
        if turnover is None or borrowings is None:
            flags.append({"id": "COMP_INT_AUDIT", "particulars": "Internal Audit", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Turnover or Borrowings data.", "source": "Compliance Engine"})
        elif turnover >= (200 * CR) or borrowings >= (100 * CR):
            flags.append({"id": "COMP_INT_AUDIT", "particulars": "Internal Audit", "status": "Failed", "user_value": "Applicable", "rationale": f"Threshold Exceeded: Turnover ({turnover/CR:.2f} Cr) >= 200 Cr OR Borrowings ({borrowings/CR:.2f} Cr) >= 100 Cr.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_INT_AUDIT", "particulars": "Internal Audit", "status": "Passed", "user_value": "Not Applicable", "rationale": f"Turnover ({turnover/CR:.2f} Cr) < 200 Cr AND Borrowings ({borrowings/CR:.2f} Cr) < 100 Cr.", "source": "Compliance Engine"})

        # 9. IND AS Applicability
        if net_worth is None and not (is_ind_as or is_listed):
            flags.append({"id": "COMP_IND_AS", "particulars": "IND AS applicability", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Net Worth data.", "source": "Compliance Engine"})
        elif is_ind_as or is_listed or net_worth >= (250 * CR):
            flags.append({"id": "COMP_IND_AS", "particulars": "IND AS applicability", "status": "Failed", "user_value": "Applicable", "rationale": f"Listed ({is_listed}) OR Ind AS Applied ({is_ind_as}) OR Net Worth ({net_worth/CR:.2f} Cr) >= 250 Cr.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_IND_AS", "particulars": "IND AS applicability", "status": "Passed", "user_value": "Not Applicable", "rationale": f"Unlisted, non-Ind AS, with Net Worth ({net_worth/CR:.2f} Cr) < 250 Cr.", "source": "Compliance Engine"})

        # 10. MGT 8 Applicability
        if puc is None or turnover is None:
            flags.append({"id": "COMP_MGT_8", "particulars": "MGT 8 Applicability", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Paid-up Capital or Turnover data.", "source": "Compliance Engine"})
        elif is_listed or puc >= (10 * CR) or turnover >= (50 * CR):
            flags.append({"id": "COMP_MGT_8", "particulars": "MGT 8 Applicability", "status": "Failed", "user_value": "Applicable", "rationale": f"Listed ({is_listed}) OR PUC ({puc/CR:.2f} Cr) >= 10 Cr OR Turnover ({turnover/CR:.2f} Cr) >= 50 Cr.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_MGT_8", "particulars": "MGT 8 Applicability", "status": "Passed", "user_value": "Not Applicable", "rationale": f"PUC ({puc/CR:.2f} Cr) < 10 Cr AND Turnover ({turnover/CR:.2f} Cr) < 50 Cr.", "source": "Compliance Engine"})

        # 11. Certification of MGT 7
        if is_small_company:
            flags.append({"id": "COMP_MGT_7_CERT", "particulars": "Certification of MGT 7", "status": "Passed", "user_value": "Not Applicable", "rationale": "Exempt because it is a Small Company.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_MGT_7_CERT", "particulars": "Certification of MGT 7", "status": "Failed", "user_value": "Applicable", "rationale": "Applicable because Small Company exemption is lost.", "source": "Compliance Engine"})

        # 12. Secretarial Audit
        if puc is None or turnover is None or borrowings is None:
            flags.append({"id": "COMP_SEC_AUDIT", "particulars": "Secretarial Audit", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing PUC, Turnover, or Borrowings data.", "source": "Compliance Engine"})
        elif is_listed or borrowings >= (100 * CR) or ("public" in company_type and (puc >= (50 * CR) or turnover >= (250 * CR))):
            flags.append({"id": "COMP_SEC_AUDIT", "particulars": "Secretarial Audit", "status": "Failed", "user_value": "Applicable", "rationale": f"Listed ({is_listed}) OR Borrowings ({borrowings/CR:.2f} Cr) >= 100 Cr OR Public Co with PUC >= 50 Cr / Turnover >= 250 Cr.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_SEC_AUDIT", "particulars": "Secretarial Audit", "status": "Passed", "user_value": "Not Applicable", "rationale": f"Borrowings ({borrowings/CR:.2f} Cr) < 100 Cr (and not a public/listed co matching limits).", "source": "Compliance Engine"})

        # 13. KMP appointment
        if puc is None:
            flags.append({"id": "COMP_KMP", "particulars": "KMP appointment", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Paid-up Capital data.", "source": "Compliance Engine"})
        elif is_listed or ("public" in company_type and puc >= (10 * CR)) or puc >= (10 * CR):
            flags.append({"id": "COMP_KMP", "particulars": "KMP appointment", "status": "Failed", "user_value": "Applicable", "rationale": f"Listed ({is_listed}) OR PUC ({puc/CR:.2f} Cr) >= 10 Cr.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_KMP", "particulars": "KMP appointment", "status": "Passed", "user_value": "Not Applicable", "rationale": f"PUC ({puc/CR:.2f} Cr) < 10 Cr.", "source": "Compliance Engine"})

        # 14. Loan Investment Guarantee - 186
        has_loans = str(input_data.get("has_loans_investments_guarantees", "no")).lower() == "yes"
        if has_loans:
            flags.append({"id": "COMP_LOAN_186", "particulars": "Loan Investment Guarantee - 186", "status": "Failed", "user_value": "Applicable", "rationale": "Found loans, investments, or guarantees in financials.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_LOAN_186", "particulars": "Loan Investment Guarantee - 186", "status": "Passed", "user_value": "Not Applicable", "rationale": "No relevant loans, investments, or guarantees detected.", "source": "Compliance Engine"})

        # 15. Loan to Director or Related entities
        if loan_to_directors_assets > 0:
            flags.append({"id": "COMP_LOAN_DIRECTOR", "particulars": "Loan to Director or Related entities", "status": "Failed", "user_value": "Applicable", "rationale": f"Loan to Directors/Related Entities (Assets) = {loan_to_directors_assets:,.2f} > 0.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_LOAN_DIRECTOR", "particulars": "Loan to Director or Related entities", "status": "Passed", "user_value": "Not Applicable", "rationale": "No asset loans to directors detected.", "source": "Compliance Engine"})
            
        # 16. Cost Audit
        flags.append({"id": "COMP_COST_AUDIT", "particulars": "Cost Audit", "status": "Passed", "user_value": "Not Applicable", "rationale": "Not automatically evaluated. (Requires manual verification if applicable)", "source": "Compliance Engine"})
        
        # 17. Charge form
        if secured_loan > 0:
            flags.append({"id": "COMP_CHARGE_FORM", "particulars": "Charge form", "status": "Failed", "user_value": "Applicable", "rationale": f"Secured Loan = {secured_loan:,.2f} > 0.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_CHARGE_FORM", "particulars": "Charge form", "status": "Passed", "user_value": "Not Applicable", "rationale": "Secured Loan = 0.", "source": "Compliance Engine"})
            
        # 18. AOC 1
        if is_subsidiary_or_holding:
            flags.append({"id": "COMP_AOC_1", "particulars": "AOC 1", "status": "Failed", "user_value": "Applicable", "rationale": "Company is identified as a Holding or Subsidiary.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_AOC_1", "particulars": "AOC 1", "status": "Passed", "user_value": "Not Applicable", "reason": "Not Applicable", "source": "Compliance Engine"})
            
        # 19. AOC 2 & RPT Resolution
        if total_rpt_value > 0:
            flags.append({"id": "COMP_AOC_2", "particulars": "AOC 2", "status": "Failed", "user_value": "Applicable", "rationale": f"RPT Transactions Total = {total_rpt_value:,.2f} > 0.", "source": "Compliance Engine"})
            flags.append({"id": "COMP_RPT_OMNIBUS", "particulars": "RPT Resolution for omnibus approval", "status": "Failed", "user_value": "Applicable", "rationale": f"RPT Transactions Total = {total_rpt_value:,.2f} > 0.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_AOC_2", "particulars": "AOC 2", "status": "Passed", "user_value": "Not Applicable", "rationale": "No Related Party Transactions (Sales, Purchases, Remuneration) detected.", "source": "Compliance Engine"})
            flags.append({"id": "COMP_RPT_OMNIBUS", "particulars": "RPT Resolution for omnibus approval", "status": "Passed", "user_value": "Not Applicable", "rationale": "No Related Party Transactions (Sales, Purchases, Remuneration) detected.", "source": "Compliance Engine"})
            
        # 20. CSR Committee
        if net_profit is not None and (net_profit * 3 * 0.02) > 5000000:
            flags.append({"id": "COMP_CSR_COMMITTEE", "particulars": "CSR Committee", "status": "Failed", "user_value": "Applicable", "rationale": f"Estimated CSR Spend (2% of PBT {net_profit/CR:.2f} Cr * 3 yrs) > 50 Lakhs.", "source": "Compliance Engine"})
        elif net_profit is not None:
            flags.append({"id": "COMP_CSR_COMMITTEE", "particulars": "CSR Committee", "status": "Passed", "user_value": "Not Applicable", "rationale": f"Estimated CSR Spend (2% of PBT {net_profit/CR:.2f} Cr * 3 yrs) <= 50 Lakhs.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_CSR_COMMITTEE", "particulars": "CSR Committee", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Net Profit data.", "source": "Compliance Engine"})
            
        # 21. Deposit declaration
        if loan_from_directors > 0:
            flags.append({"id": "COMP_DEPOSIT_DEC", "particulars": "Deposit declaration", "status": "Failed", "user_value": "Applicable", "rationale": f"Loan from Directors/Relatives = {loan_from_directors:,.2f} > 0.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_DEPOSIT_DEC", "particulars": "Deposit declaration", "status": "Passed", "user_value": "Not Applicable", "rationale": "No loans from Directors/Relatives detected.", "source": "Compliance Engine"})
            
        # 22. DPT 3
        if (borrowings or 0) + advance_from_customers > 0:
            flags.append({"id": "COMP_DPT_3", "particulars": "DPT 3", "status": "Failed", "user_value": "Applicable", "rationale": f"Borrowings + Customer Advances = {(borrowings or 0) + advance_from_customers:,.2f} > 0.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_DPT_3", "particulars": "DPT 3", "status": "Passed", "user_value": "Not Applicable", "rationale": "Borrowings and Customer Advances are 0.", "source": "Compliance Engine"})
            
        # 23. MSME
        if dues_to_msme > 0:
            flags.append({"id": "COMP_MSME", "particulars": "MSME", "status": "Failed", "user_value": "Applicable", "rationale": f"Dues to MSME = {dues_to_msme:,.2f} > 0.", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_MSME", "particulars": "MSME", "status": "Passed", "user_value": "Not Applicable", "rationale": "No Dues to MSME detected.", "source": "Compliance Engine"})
            
        # 24. Ben 2
        if has_corporate_shareholders is None:
            flags.append({"id": "COMP_BEN_2", "particulars": "Ben 2", "status": "Manual", "user_value": "Missing Data", "rationale": "Missing Shareholders data.", "source": "Compliance Engine"})
        elif has_corporate_shareholders == "yes":
            flags.append({"id": "COMP_BEN_2", "particulars": "Ben 2", "status": "Failed", "user_value": "Applicable", "rationale": "Corporate Shareholders detected (Keywords: Ltd, Inc, etc).", "source": "Compliance Engine"})
        else:
            flags.append({"id": "COMP_BEN_2", "particulars": "Ben 2", "status": "Passed", "user_value": "Not Applicable", "rationale": "No Corporate Shareholders detected.", "source": "Compliance Engine"})

        return flags
