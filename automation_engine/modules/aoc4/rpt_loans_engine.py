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
        prev_turnover = self._parse_numeric(input_data.get("prev_turnover")) or self._parse_numeric(input_data.get("turnover"))
        prev_net_worth = self._parse_numeric(input_data.get("prev_net_worth")) or self._parse_numeric(input_data.get("net_worth"))
        
        s188_items = [
            ("Sale of Goods", input_data.get("rpt_sale_goods", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Purchase or supply of goods or materials directly or through appointment of agents", input_data.get("rpt_purchase_goods", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Sale of property", input_data.get("rpt_sale_property", 0), prev_net_worth * 0.10 if prev_net_worth else None),
            ("Purchase of property", input_data.get("rpt_purchase_property", 0), prev_net_worth * 0.10 if prev_net_worth else None),
            ("Dispose of Property", input_data.get("rpt_dispose_property", 0), prev_net_worth * 0.10 if prev_net_worth else None),
            ("Availing of service", input_data.get("rpt_availing_service", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Rendering of Service", input_data.get("rpt_rendering_service", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Lease", input_data.get("rpt_lease", 0), prev_turnover * 0.10 if prev_turnover else None),
            ("Appointment to any office or place of profit in the company, its subsidiary company or associate company", input_data.get("rpt_monthly_remuneration") if input_data.get("rpt_monthly_remuneration") is not None else input_data.get("rpt_monthly_remun", 0), 250000),
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
            
        # Section 185: Loans to Directors & Firms (Priority: Check applicability from Compliance Sheet)
        loan_directors_val = self._parse_numeric(input_data.get("loan_to_directors_assets", 0)) or 0.0
        total_rpt_value = self._parse_numeric(input_data.get("total_rpt_value", 0)) or 0.0
        
        # 1. Primary Check: Compliance Sheet 'Loan to Director or Related entities' and 'AOC 2' status
        comp_sheet_loan_director = None
        comp_sheet_aoc2 = None
        if "compliance_flags" in input_data:
            for c_flag in input_data["compliance_flags"]:
                c_id = c_flag.get("id")
                c_part = str(c_flag.get("particulars", "")).lower()
                if c_id == "COMP_LOAN_DIRECTOR" or "loan to director" in c_part:
                    comp_sheet_loan_director = str(c_flag.get("user_value", "")).strip()
                elif c_id == "COMP_AOC_2" or c_part == "aoc 2" or "aoc-2" in c_part:
                    comp_sheet_aoc2 = str(c_flag.get("user_value", "")).strip()

        is_loan_director_applicable = (
            comp_sheet_loan_director.lower() == "applicable"
            if comp_sheet_loan_director
            else (loan_directors_val > 0)
        )
        is_aoc2_applicable = (
            comp_sheet_aoc2.lower() == "applicable"
            if comp_sheet_aoc2
            else (total_rpt_value > 0)
        )

        has_sec185_applicability = is_loan_director_applicable or is_aoc2_applicable
        applicability_val = "Applicable" if has_sec185_applicability else "Not Applicable"
        if is_loan_director_applicable and is_aoc2_applicable:
            applicability_reason = "Applicable as per Compliance Sheet (Loan to Director & AOC-2)"
        elif is_loan_director_applicable:
            applicability_reason = "Applicable as per Compliance Sheet (Loan to Director or Related entities)"
        elif is_aoc2_applicable:
            applicability_reason = "Applicable as per Compliance Sheet (AOC-2 Related Party Transactions)"
        else:
            applicability_reason = "No asset loans to directors or AOC-2 transactions detected"

        # Applicability header for Section 185 (Row 25)
        flags.append({
            "id": "COMP_SEC_185_APPLICABILITY",
            "particulars": "Loans to directors or interested persons of directors",
            "status": "Passed",
            "user_value": applicability_val,
            "actual_value": loan_directors_val,
            "reason": applicability_reason,
            "source": "Financial Statements & Compliance Sheet"
        })

        if not has_sec185_applicability:
            # When Section 185 is Not Applicable (both Loan to Director and AOC 2 are NA), all rows up to Row 39 / 47 are set to 'NA'
            flags.append({
                "id": "COMP_SEC_185_BASE",
                "particulars": "Has the company given any loan to Directors/ or of a company which is its holding company or any partner or relative of any such director; OR",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": 0,
                "reason": "Not Applicable (No loans to directors as per Compliance Sheet)",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_FIRM",
                "particulars": "Has the company given any loan to any firm in which any such director or relative is a partner",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": 0,
                "reason": "Not Applicable (AOC-2 Not Applicable as per Compliance Sheet)",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_EXC1",
                "particulars": "No other body corporate has invested in its share capital",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_EXC2",
                "particulars": "Its borrowings from banks/financial institutions/any Body Corporate is less than twice of its paid-up share capital or Rs. 50 crore, whichever is lower AND",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_EXC3",
                "particulars": "no default in repayment of such borrowings subsisting at the time of making transactions under this section",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_NON_COMPLIANCE",
                "particulars": "Even if one of the above conditions are YES,  Private companies cannot provide loan to its directors or of a company which is its holding company or any partner or relative of any such director",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_BASE",
                "particulars": "Has the company given loan including any loan represented by a book debt, or given any guarantee or provided any security in connection with any loan taken by any person in whom any of the director of the company is interested, being the following interested persons",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_PVT",
                "particulars": "any private company of which any such director is a director or member;",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_BODY_CORP",
                "particulars": "any body corporate at a general meeting of which not less than twenty-five per cent. of the total voting power may be exercised or controlled by any such director, or by two or more such directors, together;",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_BOARD",
                "particulars": "any body corporate, the Board of directors, managing director or manager, whereof is accustomed to act in accordance with the directions or instructions of the Board, or of any director or directors, of the lending company.",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_SR",
                "particulars": "Special resolution is passed by the company in general meeting",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_UTIL",
                "particulars": "the loans are utilised by the borrowing company for its principal business activities.",
                "status": "Passed",
                "user_value": "NA",
                "actual_value": "",
                "reason": "Not Applicable",
                "source": "Compliance Sheet Priority"
            })
        else:
            # When Section 185 is Applicable, execute detailed evaluation
            director_person_name = str(input_data.get("director_related_person_name", "") or input_data.get("loan_to_director_name", "") or input_data.get("director_name", "")).strip().lower()
            rpt_text = str(input_data.get("full_text", "")).lower()

            # Row 26: Loan to Directors check
            if is_loan_director_applicable:
                flags.append({
                    "id": "COMP_SEC_185_BASE",
                    "particulars": "Has the company given any loan to Directors/ or of a company which is its holding company or any partner or relative of any such director; OR",
                    "status": "Failed",
                    "user_value": "Yes",
                    "actual_value": loan_directors_val,
                    "reason": f"Loan to individual director ({director_person_name.title() if director_person_name else 'director'})",
                    "source": "RPT & Loans Engine"
                })
            else:
                flags.append({
                    "id": "COMP_SEC_185_BASE",
                    "particulars": "Has the company given any loan to Directors/ or of a company which is its holding company or any partner or relative of any such director; OR",
                    "status": "Passed",
                    "user_value": "NA",
                    "actual_value": 0,
                    "reason": "Not Applicable (No loans to directors as per Compliance Sheet)",
                    "source": "Compliance Sheet Priority"
                })

            # Row 27: Firm Loans check (Priority: AOC 2 applicability from Compliance Sheet)
            if is_aoc2_applicable:
                has_firm_loan = bool(
                    re.search(r"loan.*?to.*?(firm|partnership|associates|enterprises)", rpt_text) or
                    ("firm" in director_person_name or "partnership" in director_person_name)
                )
                firm_loan_val = "Yes" if has_firm_loan else "No"
                firm_loan_status = "Failed" if has_firm_loan else "Passed"

                flags.append({
                    "id": "COMP_SEC_185_FIRM",
                    "particulars": "Has the company given any loan to any firm in which any such director or relative is a partner",
                    "status": firm_loan_status,
                    "user_value": firm_loan_val,
                    "actual_value": loan_directors_val if has_firm_loan else 0,
                    "reason": "Loan given to firm where director/relative is partner" if has_firm_loan else "No loan to firm detected in RPT disclosures",
                    "source": "RPT & Loans Engine"
                })
            else:
                flags.append({
                    "id": "COMP_SEC_185_FIRM",
                    "particulars": "Has the company given any loan to any firm in which any such director or relative is a partner",
                    "status": "Passed",
                    "user_value": "NA",
                    "actual_value": 0,
                    "reason": "Not Applicable (AOC-2 Not Applicable as per Compliance Sheet)",
                    "source": "Compliance Sheet Priority"
                })

            is_subsidiary = (
                str(input_data.get("is_subsidiary_or_holding", "")).lower() == "subsidiary" or
                bool(re.search(r"(subsidiary\s+of|holding\s+company|ultimate\s+holding)", rpt_text)) or
                bool(re.search(r"shares\s+held\s+by.*?(holding|body\s+corporate|ltd|pvt)", rpt_text))
            )
            has_corp_shareholders = input_data.get("has_corporate_shareholders", 0)
            body_corp_investors = is_subsidiary or (has_corp_shareholders == 1 or str(has_corp_shareholders).lower() == "yes" or (isinstance(has_corp_shareholders, (int, float)) and has_corp_shareholders > 0))

            borrowing_limit = min(2 * (puc or 0), 50 * self.CR) if puc else None
            is_borrowing_less = borrowings < borrowing_limit if borrowings is not None and borrowing_limit is not None else False

            flags.append({
                "id": "COMP_SEC_185_EXC1",
                "particulars": "No other body corporate has invested in its share capital",
                "status": "Failed" if body_corp_investors else "Passed",
                "user_value": "yes body corporate" if body_corp_investors else "Yes",
                "actual_value": "",
                "reason": "Body corporate shareholder / subsidiary relationship detected" if body_corp_investors else "No body corporate shareholders",
                "source": "Financial Statements & Subsidiary Check"
            })
            flags.append({
                "id": "COMP_SEC_185_EXC2",
                "particulars": "Its borrowings from banks/financial institutions/any Body Corporate is less than twice of its paid-up share capital or Rs. 50 crore, whichever is lower AND",
                "status": "Passed" if is_borrowing_less else "Failed",
                "user_value": "Yes" if is_borrowing_less else "yes loan is exceeding",
                "actual_value": borrowings or 0,
                "reason": (f"Borrowings (₹{borrowings:,.2f}) within Limit (₹{borrowing_limit:,.2f})" if is_borrowing_less else f"Borrowings (₹{borrowings or 0:,.2f}) exceed Limit (₹{borrowing_limit or 0:,.2f})") if (borrowings is not None and borrowing_limit is not None) else "Borrowing limit not determined",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_185_EXC3",
                "particulars": "no default in repayment of such borrowings subsisting at the time of making transactions under this section",
                "status": "Manual",
                "user_value": "manual check",
                "actual_value": "",
                "reason": "Verify bank/FI repayment default status at the time of transaction",
                "source": "RPT & Loans Engine"
            })

            if body_corp_investors and not is_borrowing_less:
                non_comp_val = "since both condition is yes - Non- compliance"
                non_comp_status = "Failed"
                non_comp_reason = "Both Body Corporate investment and Borrowing limits exceeded"
            elif body_corp_investors or not is_borrowing_less:
                non_comp_val = "Non- compliance"
                non_comp_status = "Failed"
                non_comp_reason = "GSR 464(E) exemption conditions violated"
            else:
                non_comp_val = "Not applicable"
                non_comp_status = "Passed"
                non_comp_reason = "GSR 464(E) conditions satisfied"

            flags.append({
                "id": "COMP_SEC_185_NON_COMPLIANCE",
                "particulars": "Even if one of the above conditions are YES,  Private companies cannot provide loan to its directors or of a company which is its holding company or any partner or relative of any such director",
                "status": non_comp_status,
                "user_value": non_comp_val,
                "actual_value": "",
                "reason": non_comp_reason,
                "source": "RPT & Loans Engine"
            })

            entity_keywords = [
                r"\bpvt\.?\s*ltd\.?", r"\bprivate\s+limited\b", r"\bltd\.?\b", r"\bplc\b", r"\bco\.?\b", 
                r"\bllc\b", r"\bllp\b", r"\bcorp\.?\b", r"\binc\.?\b", r"\bhuf\b", r"\bpvt\b", 
                r"\bfirm\b", r"\benterprise\b", r"\bventures\b",
                r"\bgmbh\b", r"\bpte\.?\s*ltd\.?", r"\bpte\b", r"\bpty\.?\s*ltd\.?", r"\bpty\b"
            ]
            interested_entity_name = str(input_data.get("director_related_entity_name", "")).lower()
            has_interested_entity = any(re.search(pat, interested_entity_name) for pat in entity_keywords) or \
                                   (loan_directors_val > 0 and any(re.search(pat, rpt_text) for pat in [r"loan.*?to.*?(pvt|ltd|llp|llc|firm|corp|inc|gmbh|pte|pty)", r"advance.*?to.*?(pvt|ltd|llp|llc|firm|corp|inc|gmbh|pte|pty)"])) or \
                                   str(input_data.get("has_interested_entity_loans", "no")).lower() == "yes"

            flags.append({
                "id": "COMP_SEC_185_INTERESTED_BASE",
                "particulars": "Has the company given loan including any loan represented by a book debt, or given any guarantee or provided any security in connection with any loan taken by any person in whom any of the director of the company is interested, being the following interested persons",
                "status": "Failed" if has_interested_entity else "Passed",
                "user_value": "Yes" if has_interested_entity else "No",
                "actual_value": "",
                "reason": "Loan/Guarantee given to director-interested entity" if has_interested_entity else "No loans to director-interested entities",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_PVT",
                "particulars": "any private company of which any such director is a director or member;",
                "status": "Manual" if has_interested_entity else "Passed",
                "user_value": "manual check" if has_interested_entity else "No",
                "actual_value": "",
                "reason": "Verify if director is a director or shareholder/member in the private company" if has_interested_entity else "Not applicable",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_BODY_CORP",
                "particulars": "any body corporate at a general meeting of which not less than twenty-five per cent. of the total voting power may be exercised or controlled by any such director, or by two or more such directors, together;",
                "status": "Manual" if has_interested_entity else "Passed",
                "user_value": "manual check" if has_interested_entity else "No",
                "actual_value": "",
                "reason": "Verify if director(s) hold >= 25% voting power in the body corporate" if has_interested_entity else "Not applicable",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_BOARD",
                "particulars": "any body corporate, the Board of directors, managing director or manager, whereof is accustomed to act in accordance with the directions or instructions of the Board, or of any director or directors, of the lending company.",
                "status": "Manual" if has_interested_entity else "Passed",
                "user_value": "manual check" if has_interested_entity else "No",
                "actual_value": "",
                "reason": "Verify if Board of borrowing company acts on instructions of director(s)" if has_interested_entity else "Not applicable",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_SR",
                "particulars": "Special resolution is passed by the company in general meeting",
                "status": "Manual" if has_interested_entity else "Passed",
                "user_value": "manual check" if has_interested_entity else "NA",
                "actual_value": "",
                "reason": "Verify if Special Resolution was passed in General Meeting under Section 185(2)" if has_interested_entity else "Not applicable",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_185_INTERESTED_UTIL",
                "particulars": "the loans are utilised by the borrowing company for its principal business activities.",
                "status": "Manual" if has_interested_entity else "Passed",
                "user_value": "manual check" if has_interested_entity else "NA",
                "actual_value": "",
                "reason": "Verify borrowing company's principal business utilization" if has_interested_entity else "Not applicable",
                "source": "RPT & Loans Engine"
            })

            # Section 185 Exemptions Block: Row 42 (Loans to MD or WTD)
            # Step 1: Check if loan is given to an Individual Director (from Balance Sheet Assets / RPT / Input Sheet)
            # Step 2: If loan is given, check if that director is Managing Director (MD) / Whole-time Director (WTD)
            director_designation = str(input_data.get("director_designation", "") or input_data.get("designation", "")).lower()
            is_md_wtd = any(kw in director_designation for kw in ["md", "managing director", "wtd", "whole-time", "whole time", "executive director"]) or \
                        str(input_data.get("is_md_wtd", "no")).lower() in ["yes", "1", "true"]

            # Also check DIR-12 / Signatory details / RPT text for MD/WTD designation of the borrowing director
            if not is_md_wtd and rpt_text and is_loan_director_applicable:
                is_md_wtd = bool(re.search(r"\b(managing\s+director|whole[\s-]time\s+director|executive\s+director)\b", rpt_text))

            if is_loan_director_applicable:
                if is_md_wtd:
                    md_verdict = "Yes"
                    md_status = "Passed"
                    md_reason = "Loan given to director who is confirmed as Managing Director (MD) / Whole-Time Director (WTD) from DIR-12 / Input Sheet"
                else:
                    md_verdict = "No"
                    md_status = "Passed"
                    md_reason = "Loan given to director, but recipient director is not an MD/WTD (Non-Executive / Ordinary Director)"
            else:
                md_verdict = "NA"
                md_status = "Passed"
                md_reason = "Not Applicable as no loans given to directors"

            flags.append({
                "id": "COMP_SEC_185_EXEMPT_MD",
                "particulars": "the giving of any loan to a managing or whole-time director",
                "status": md_status,
                "user_value": md_verdict,
                "actual_value": loan_directors_val if (is_loan_director_applicable and is_md_wtd) else "",
                "reason": md_reason,
                "source": "Financial Statements (Loan check) & DIR-12 / Input Sheet (Designation check)"
            })
            flags.append({
                "id": "COMP_SEC_185_EXEMPT_SERVICE",
                "particulars": "as a part of the conditions of service extended by the company to all its employees;  or",
                "status": "Manual",
                "user_value": "Manual check",
                "actual_value": "",
                "reason": "Verify with service conditions / employee loan policy",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_185_EXEMPT_SR",
                "particulars": "pursuant to any scheme approved by the members by a special resolution;",
                "status": "Manual",
                "user_value": "Manual check",
                "actual_value": "",
                "reason": "Verify if Special Resolution is passed by members",
                "source": "RPT & Loans Engine"
            })
            # Section 185 Exemptions Block: Row 45 (Ordinary course of business - NBFC/Banking)
            # Check Financials - Significant Accounting Policy for nature of business of company
            nature_of_biz = str(input_data.get("nature_of_business", "") or input_data.get("principal_business_activities", "")).lower()
            rpt_text_lower = str(input_data.get("full_text", "")).lower()
            
            is_nbfc_banking = bool(
                re.search(r"\b(nbfc|banking\s+company|non-banking\s+financial|financing\s+activities|money\s+lending)\b", nature_of_biz) or
                re.search(r"\b(nature\s+of\s+business|principal\s+activities|company\s+overview).*?(nbfc|banking|financial\s+services|lending)", rpt_text_lower)
            )
            
            if is_nbfc_banking:
                ordinary_verdict = "Yes"
                ordinary_status = "Passed"
                ordinary_reason = "Company is an NBFC/Banking entity as per Significant Accounting Policies (Nature of Business)"
            elif nature_of_biz and not is_nbfc_banking:
                ordinary_verdict = "No"
                ordinary_status = "Passed"
                ordinary_reason = "Nature of business is not money lending/banking as per Significant Accounting Policies"
            else:
                ordinary_verdict = "read the financials - significant accounting policy for nature of business of company"
                ordinary_status = "Manual"
                ordinary_reason = "Verify Significant Accounting Policies (Note 1) in Financials for nature of business"

            flags.append({
                "id": "COMP_SEC_185_EXEMPT_ORDINARY",
                "particulars": "a company which in the ordinary course of its business provides loans or gives guarantees or securities for the due repayment of any loan and in respect of such loans an interest is charged at a rate not less than the rate of prevailing yield of one year, three year, five year or ten year Government security closest to the tenor of the loan;",
                "status": ordinary_status,
                "user_value": ordinary_verdict,
                "actual_value": "",
                "reason": ordinary_reason,
                "source": "Financial Statements - Significant Accounting Policies"
            })
            is_holding = str(input_data.get("is_subsidiary_or_holding")).lower() == "holding"
            
            # Check if text or RPT notes explicitly mention Wholly Owned Subsidiary
            is_explicit_wos = bool(re.search(r"\bwholly[\s-]owned\s+subsidiary\b|\bwos\b", rpt_text))
            is_wos_check = has_interested_entity or is_holding or is_explicit_wos
            
            if is_explicit_wos and is_holding:
                wos_verdict = "Yes"
                wos_status = "Passed"
                wos_reason = "Recipient entity is confirmed as Wholly Owned Subsidiary (WOS) as per Related Party Transactions / Financials"
            elif is_wos_check:
                wos_verdict = "check if the entity is WOS"
                wos_status = "Manual"
                wos_reason = "Loan/Guarantee given to entity - verify if recipient is a Wholly Owned Subsidiary (WOS) with Related Party Transactions (RPT) note as fallback"
            else:
                wos_verdict = "NA"
                wos_status = "Passed"
                wos_reason = "Not Applicable as no entity loans or holding company relationship"

            flags.append({
                "id": "COMP_SEC_185_EXEMPT_WOS",
                "particulars": "any loan made by a holding company to its wholly owned subsidiary company or any guarantee given or security provided by a holding company in respect of any loan made to its wholly owned subsidiary company; or",
                "status": wos_status,
                "user_value": wos_verdict,
                "actual_value": "",
                "reason": wos_reason,
                "source": "RPT & Loans Engine"
            })
            # Check for Guarantee / Security provided (ignoring Security Deposit)
            text_without_sec_deposits = re.sub(r'\bsecurity\s+deposits?\b', '', rpt_text)
            has_guarantee_or_security = (
                bool(re.search(r'\b(guarantee|guarantees|guaranteed|security\s+provided|provided\s+security|given\s+guarantee|given\s+security)\b', text_without_sec_deposits)) or
                self._parse_numeric(input_data.get("corporate_guarantees", 0)) or 0.0 > 0 or
                str(input_data.get("has_corporate_guarantee", "no")).lower() == "yes" or
                str(input_data.get("has_guarantee_security_provided", "no")).lower() == "yes"
            )
            guarantee_verdict = "check if guarantee is for subsidiary" if has_guarantee_or_security else ("Yes" if is_holding else "No")

            flags.append({
                "id": "COMP_SEC_185_EXEMPT_SUB_GUARANTEE",
                "particulars": "any guarantee given or security provided by a holding company in respect of loan made by any bank or financial institution to its subsidiary company:",
                "status": "Manual" if has_guarantee_or_security else "Passed",
                "user_value": guarantee_verdict,
                "actual_value": "",
                "reason": "Guarantee/Security provided detected (excluding security deposits) - verify if provided for subsidiary loan" if has_guarantee_or_security else ("Holding company - verify if guarantees provided" if is_holding else "No guarantee or security provided"),
                "source": "RPT & Loans Engine"
            })

        # Section 186: Loans & Investments (Priority: Check applicability from Compliance Sheet - 'Loan and Investments')
        comp_sheet_loan_186 = None
        if "compliance_flags" in input_data:
            for c_flag in input_data["compliance_flags"]:
                c_id = c_flag.get("id")
                c_part = str(c_flag.get("particulars", "")).lower()
                if c_id == "COMP_LOAN_186" or "loan and investment" in c_part or "loan investment guarantee" in c_part:
                    comp_sheet_loan_186 = str(c_flag.get("user_value", "")).strip()
                    break

        loans_given = self._parse_numeric(input_data.get("loan_given_by_company", 0)) or 0.0
        investments = self._parse_numeric(input_data.get("investments_made", 0)) or 0.0
        guarantees = self._parse_numeric(input_data.get("corporate_guarantees", 0)) or 0.0
        total_loans_inv = loans_given + investments + guarantees

        is_comp_sec186_applicable = (
            comp_sheet_loan_186.lower() == "applicable"
            if comp_sheet_loan_186
            else (total_loans_inv > 0 or str(input_data.get("has_loans_investments_guarantees", "no")).lower() == "yes")
        )

        has_loans_or_guarantees = is_comp_sec186_applicable and (
            loans_given > 0 or 
            guarantees > 0 or 
            str(input_data.get("has_loans_investments_guarantees", "no")).lower() == "yes"
        )
        has_securities_invested = is_comp_sec186_applicable and (investments > 0)

        free_reserves = self._parse_numeric(input_data.get("free_reserves", reserves)) or 0.0
        sec_premium = self._parse_numeric(input_data.get("securities_premium", 0)) or 0.0

        flags.append({
            "id": "COMP_SEC_186_LOANS",
            "particulars": "Has the Company give loan, guarantee to any person or body corporate",
            "status": "Passed",
            "user_value": ("Yes" if has_loans_or_guarantees else "No") if is_comp_sec186_applicable else "NA",
            "actual_value": loans_given + guarantees,
            "reason": f"Loans/Guarantees detected (₹{loans_given + guarantees:,.2f})" if has_loans_or_guarantees else ("No loans or guarantees given" if is_comp_sec186_applicable else "Not Applicable (Loan and Investments Not Applicable as per Compliance Sheet)"),
            "source": "Financial Statements & Compliance Sheet Priority"
        })
        flags.append({
            "id": "COMP_SEC_186_SEC",
            "particulars": "Has the Company acquired by way of subscription, purchase or otherwise, the securities of any other body corporate,",
            "status": "Passed",
            "user_value": ("Yes" if has_securities_invested else "No") if is_comp_sec186_applicable else "NA",
            "actual_value": investments,
            "reason": f"Investments detected in securities of body corporate (₹{investments:,.2f})" if has_securities_invested else ("No investments in securities detected" if is_comp_sec186_applicable else "Not Applicable (Loan and Investments Not Applicable as per Compliance Sheet)"),
            "source": "Financial Statements & Compliance Sheet Priority"
        })

        is_sec_186_applicable = is_comp_sec186_applicable and (has_loans_or_guarantees or has_securities_invested or total_loans_inv > 0)

        if is_sec_186_applicable and puc is not None:
            limit_1 = 0.60 * (puc + free_reserves + sec_premium)
            limit_2 = 1.00 * (free_reserves + sec_premium)
            max_limit = max(limit_1, limit_2)
            within_limits = (total_loans_inv <= max_limit)

            flags.append({
                "id": "COMP_SEC_186_L1",
                "particulars": "60% of Paid up capital & Free reserve and securities premium  or ",
                "status": "Passed",
                "user_value": f"{limit_1:,.2f}",
                "actual_value": limit_1,
                "reason": "",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_186_L2",
                "particulars": "100% of Free reserves and securities premium  ",
                "status": "Passed",
                "user_value": f"{limit_2:,.2f}",
                "actual_value": limit_2,
                "reason": "",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_186_WITHIN",
                "particulars": "If within limits, include in Board report",
                "status": "Passed",
                "user_value": "Yes" if within_limits else "No",
                "actual_value": "",
                "reason": "",
                "source": "RPT & Loans Engine"
            })
            flags.append({
                "id": "COMP_SEC_186_EXCEED",
                "particulars": "If exceeding limit, to mention in MGT 8 & prior approval/ratification in next AGM/EGM",
                "status": "Passed" if within_limits else "Manual",
                "user_value": "No" if within_limits else "check SR",
                "actual_value": "",
                "reason": "Within Section 186 limit" if within_limits else "Exceeds Section 186 limit - verify special resolution and MGT-8 disclosure",
                "source": "RPT & Loans Engine"
            })
        else:
            for l_id, p_text in [
                ("COMP_SEC_186_L1", "60% of Paid up capital & Free reserve and securities premium  or "),
                ("COMP_SEC_186_L2", "100% of Free reserves and securities premium  "),
                ("COMP_SEC_186_WITHIN", "If within limits, include in Board report"),
                ("COMP_SEC_186_EXCEED", "If exceeding limit, to mention in MGT 8 & prior approval/ratification in next AGM/EGM")
            ]:
                flags.append({
                    "id": l_id,
                    "particulars": p_text,
                    "status": "Passed",
                    "user_value": "NA",
                    "actual_value": "",
                    "reason": "Not Applicable as no loans or investments made",
                    "source": "RPT & Loans Engine"
                })

        return flags
