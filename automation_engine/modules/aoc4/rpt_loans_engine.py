import re

class RPTLoansEngine:
    def __init__(self):
        self.CR = 10000000.0 # 1 Crore in Rupees

    def _parse_numeric(self, value, default=None):
        if value is None or str(value).strip() == "":
            return default
        if isinstance(value, (int, float)):
            return float(value)
        
        clean_str = re.sub(r'[^\d.-]', '', str(value))
        try:
            return float(clean_str) if clean_str else default
        except ValueError:
            return default

    def execute(self, input_data: dict) -> list:
        flags = []
        
        company_type = str(input_data.get("company_type", "private limited company")).lower()
        puc = self._parse_numeric(input_data.get("paid_up_capital"))
        reserves = self._parse_numeric(input_data.get("reserves_and_surplus"))
        borrowings = self._parse_numeric(input_data.get("borrowings"))
        
        # Section 188 Strings (AOC-2 Materiality)
        prev_turnover = self._parse_numeric(input_data.get("prev_turnover"))
        prev_net_worth = self._parse_numeric(input_data.get("prev_net_worth"))
        
        s188_items = [
            ("Sale of Goods", input_data.get("rpt_sale_goods", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Purchase or supply of goods or materials directly or through appointment of agents", input_data.get("rpt_purchase_goods", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Sale of property", input_data.get("rpt_sale_property", 0), prev_net_worth * 0.10 if prev_net_worth else None),
            ("Purchase of property", input_data.get("rpt_purchase_property", 0), prev_net_worth * 0.10 if prev_net_worth else None),
            ("Dispose of Property", input_data.get("rpt_dispose_property", 0), prev_net_worth * 0.10 if prev_net_worth else None),
            ("Availing of service", input_data.get("rpt_availing_service", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Rendering of Service", input_data.get("rpt_rendering_service", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Lease", input_data.get("rpt_lease", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Appointment to any office or place of profit in the company, its subsidiary company or associate company", input_data.get("rpt_monthly_remuneration", 0), 250000),
            ("remuneration for underwriting the subscription of any securities or derivatives thereof, of the company", input_data.get("rpt_remuneration_underwriting", 0), prev_net_worth * 0.01 if prev_net_worth else None)
        ]
        
        for idx, (particulars, actual, limit) in enumerate(s188_items):
            actual_val = self._parse_numeric(actual) or 0.0
            if limit is not None:
                is_material = "Yes" if actual_val >= limit else "No"
                status = "Failed" if is_material == "Yes" else "Passed"
            else:
                is_material = "Missing Data"
                status = "Manual"
                
            flags.append({
                "id": f"COMP_SEC_188_{idx}",
                "particulars": particulars,
                "status": status,
                "user_value": is_material,
                "actual_value": actual_val,
                "reason": f"Limit: {limit}",
                "source": "RPT & Loans Engine"
            })
            
        # Section 186 Strings
        free_reserves = self._parse_numeric(input_data.get("free_reserves", reserves)) or 0.0
        sec_premium = self._parse_numeric(input_data.get("securities_premium", 0)) or 0.0
        total_loans_inv = self._parse_numeric(input_data.get("total_loans_investments_given", 0)) or 0.0
        
        limit_1 = 0.60 * (puc + free_reserves + sec_premium) if puc is not None else None
        limit_2 = 1.00 * (free_reserves + sec_premium)
        max_limit = max(limit_1 or 0, limit_2)
        
        flags.append({
            "id": "COMP_SEC_186_LOANS",
            "particulars": "Has the Company give loan, guarantee to any person or body corporate",
            "status": "Passed",
            "user_value": "Yes" if total_loans_inv > 0 else "No",
            "actual_value": total_loans_inv,
            "reason": "",
            "source": "RPT & Loans Engine"
        })
        flags.append({
            "id": "COMP_SEC_186_SEC",
            "particulars": "Has the Company acquired by way of subscription, purchase or otherwise, the securities of any other body corporate,",
            "status": "Passed",
            "user_value": "No", # Default
            "actual_value": 0,
            "reason": "",
            "source": "RPT & Loans Engine"
        })
        flags.append({
            "id": "COMP_SEC_186_L1",
            "particulars": "60% of Paid up capital & Free reserve and securities premium  or ",
            "status": "Manual" if limit_1 is None else "Passed",
            "user_value": "Applicable",
            "actual_value": limit_1 if limit_1 is not None else "Missing Data",
            "reason": "",
            "source": "RPT & Loans Engine"
        })
        flags.append({
            "id": "COMP_SEC_186_L2",
            "particulars": "100% of Free reserves and securities premium  ",
            "status": "Manual" if limit_2 is None else "Passed",
            "user_value": "Applicable",
            "actual_value": limit_2 if limit_2 is not None else "Missing Data",
            "reason": "",
            "source": "RPT & Loans Engine"
        })

        # Section 185 Strings
        has_loans_to_directors = str(input_data.get("has_loans_to_directors", "no")).lower() == "yes"
        body_corp_investors = str(input_data.get("body_corporate_investors", "no")).lower() == "yes"
        borrowing_defaults = str(input_data.get("borrowing_defaults", "no")).lower() == "yes"
        
        flags.append({
            "id": "COMP_SEC_185_BASE",
            "particulars": "Has the company given any loan to Directors/ or of a company which is its holding company or any partner or relative of any such director; OR",
            "status": "Failed" if has_loans_to_directors else "Passed",
            "user_value": "Yes" if has_loans_to_directors else "No",
            "actual_value": "",
            "reason": "",
            "source": "RPT & Loans Engine"
        })
        
        flags.append({
            "id": "COMP_SEC_185_EXC1",
            "particulars": "No other body corporate has invested in its share capital",
            "status": "Passed",
            "user_value": "No" if body_corp_investors else "Yes",
            "actual_value": "",
            "reason": "",
            "source": "RPT & Loans Engine"
        })
        
        borrowing_limit = min(2 * puc, 50 * self.CR) if puc else None
        is_borrowing_less = borrowings < borrowing_limit if borrowings is not None and borrowing_limit is not None else False
        
        flags.append({
            "id": "COMP_SEC_185_EXC2",
            "particulars": "Its borrowings from banks/financial institutions/any Body Corporate is less than twice of its paid-up share capital or Rs. 50 crore, whichever is lower AND",
            "status": "Passed",
            "user_value": "Yes" if is_borrowing_less else "No",
            "actual_value": borrowings or 0,
            "reason": f"Limit: {borrowing_limit}",
            "source": "RPT & Loans Engine"
        })
        
        flags.append({
            "id": "COMP_SEC_185_EXC3",
            "particulars": "no default in repayment of such borrowings subsisting at the time of making transactions under this section",
            "status": "Passed",
            "user_value": "No" if borrowing_defaults else "Yes",
            "actual_value": "",
            "reason": "",
            "source": "RPT & Loans Engine"
        })

        return flags
