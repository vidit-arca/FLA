import json

class RuleEngine:
    def __init__(self, config_path="rules_config.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
            
    def evaluate_all(self, extracted_data):
        """Evaluate rules and return mapped cell values."""
        cell_values = {}
        
        # --- OVERRIDE LOGIC: Source from List of Shareholders for Section 1 ---
        # If the Excel Extractor found Equity/CCPS data in the Shareholders file, it becomes the Absolute Truth
        # Override the Regex-extracted numbers to prevent hallucination.
        if "excel_equity_shares_count" in extracted_data and extracted_data["excel_equity_shares_count"] > 0:
            extracted_data["equity_shares_count_fy"] = extracted_data["excel_equity_shares_count"]
            extracted_data["equity_shares_count_py"] = extracted_data["excel_equity_shares_count"] # Default PY to FY
            extracted_data["equity_shares_amount_fy"] = extracted_data["excel_equity_amount"] / 100000.0
            extracted_data["equity_shares_amount_py"] = extracted_data["excel_equity_amount"] / 100000.0
            
        if "excel_part_pref_shares_count" in extracted_data and extracted_data["excel_part_pref_shares_count"] > 0:
            extracted_data["part_pref_shares_count_fy"] = extracted_data["excel_part_pref_shares_count"]
            extracted_data["part_pref_shares_count_py"] = extracted_data["excel_part_pref_shares_count"]
            extracted_data["part_pref_shares_amount_fy"] = extracted_data["excel_part_pref_amount"] / 100000.0
            extracted_data["part_pref_shares_amount_py"] = extracted_data["excel_part_pref_amount"] / 100000.0
            
        if "excel_non_part_pref_shares_count" in extracted_data and extracted_data["excel_non_part_pref_shares_count"] > 0:
            extracted_data["non_part_pref_shares_count_fy"] = extracted_data["excel_non_part_pref_shares_count"]
            extracted_data["non_part_pref_shares_count_py"] = extracted_data["excel_non_part_pref_shares_count"]
            extracted_data["non_part_pref_shares_amount_fy"] = extracted_data["excel_non_part_pref_amount"] / 100000.0
            extracted_data["non_part_pref_shares_amount_py"] = extracted_data["excel_non_part_pref_amount"] / 100000.0
            
        # Start with a copy of extracted data populated with defaults from rules_config
        state = {}
        
        # Populate defaults
        for section, fields in self.config.get("cell_mappings", {}).items():
            for key, field_cfg in fields.items():
                field_type = field_cfg.get("type")
                field_name = field_cfg.get("field")
                default_val = field_cfg.get("default")
                
                if field_type == "extracted" and field_name:
                    # Take extracted value if present
                    if field_name in extracted_data:
                        state[field_name] = extracted_data[field_name]
                    # Else, set default only if not already set, or if new default is not None
                    elif field_name not in state or state[field_name] is None:
                        if default_val is not None or field_name not in state:
                            state[field_name] = default_val
                    
        # Extra explicit bindings for fields that might be calculated or extracted
        state["filing_year"] = extracted_data.get("filing_year", 2025)
        
        # Determine Listed Status dynamically from CIN
        cin_number = str(state.get("cin_number", extracted_data.get("cin_number", ""))).strip().upper()
        if cin_number.startswith("L"):
            state["listed_status"] = "Yes"
        elif cin_number.startswith("U"):
            state["listed_status"] = "No"
        elif "listed_status" not in state or state["listed_status"] is None:
            state["listed_status"] = "No"
        if "company_type" not in state or state["company_type"] is None:
            pass # Removed default, wait for auto-fill from Previous FLA
            
        # Helper to convert share count to Lakhs
        def shares_to_lakhs(shares, face_value):
            s_val = state.get(shares, 0.0) or 0.0
            fv_val = state.get(face_value, 0.0) or 0.0
            # If s_val or fv_val are strings, parse them
            try:
                s_val = float(s_val)
                fv_val = float(fv_val)
            except Exception:
                pass
            return (s_val * fv_val) / 100000.0

        # Bind calculations
        # Section I calculated values
        state["get_closing_date()"] = extracted_data.get('closing_date') or f"31/03/{state.get('filing_year', 2025)}"
        state["get_listed_market_price('py')"] = "N/A" if state.get("listed_status") == "No" else 0.0
        state["get_listed_market_price('fy')"] = "N/A" if state.get("listed_status") == "No" else 0.0
        
        # Override counts if extracted from Shareholders Excel directly
        if extracted_data.get("excel_equity_shares_count", 0.0) > 0:
            state["equity_shares_count_py"] = extracted_data["excel_equity_shares_count"]
            state["equity_shares_count_fy"] = extracted_data["excel_equity_shares_count"]
        if extracted_data.get("excel_part_pref_shares_count", 0.0) > 0:
            state["part_pref_shares_count_py"] = extracted_data["excel_part_pref_shares_count"]
            state["part_pref_shares_count_fy"] = extracted_data["excel_part_pref_shares_count"]
        if extracted_data.get("excel_non_part_pref_shares_count", 0.0) > 0:
            state["non_part_pref_shares_count_py"] = extracted_data["excel_non_part_pref_shares_count"]
            state["non_part_pref_shares_count_fy"] = extracted_data["excel_non_part_pref_shares_count"]
            
        state["equity_class_count_py"] = extracted_data.get("excel_equity_class_count") if extracted_data.get("excel_equity_class_count") is not None else 1
        state["equity_class_count_fy"] = extracted_data.get("excel_equity_class_count") if extracted_data.get("excel_equity_class_count") is not None else 1
        state["part_pref_class_count_py"] = extracted_data.get("excel_part_pref_class_count") if extracted_data.get("excel_part_pref_class_count") is not None else 0
        state["part_pref_class_count_fy"] = extracted_data.get("excel_part_pref_class_count") if extracted_data.get("excel_part_pref_class_count") is not None else 0
        state["non_part_pref_class_count_py"] = extracted_data.get("excel_non_part_pref_class_count") if extracted_data.get("excel_non_part_pref_class_count") is not None else 0
        state["non_part_pref_class_count_fy"] = extracted_data.get("excel_non_part_pref_class_count") if extracted_data.get("excel_non_part_pref_class_count") is not None else 0
        
        if extracted_data.get("excel_equity_face_value") is not None:
            state["equity_face_value_py"] = extracted_data["excel_equity_face_value"]
            state["equity_face_value_fy"] = extracted_data["excel_equity_face_value"]
        if extracted_data.get("excel_part_pref_face_value") is not None:
            state["part_pref_face_value_py"] = extracted_data["excel_part_pref_face_value"]
            state["part_pref_face_value_fy"] = extracted_data["excel_part_pref_face_value"]
        if extracted_data.get("excel_non_part_pref_face_value") is not None:
            state["non_part_pref_face_value_py"] = extracted_data["excel_non_part_pref_face_value"]
            state["non_part_pref_face_value_fy"] = extracted_data["excel_non_part_pref_face_value"]

        # Section II calculations (shares to lakhs)
        # 1. Using New Strategy: Read Amounts straight from List of Shareholders
        state["equity_amount_lakhs_py"] = extracted_data.get("excel_equity_amount", 0.0) / 100000.0
        state["equity_amount_lakhs_fy"] = extracted_data.get("excel_equity_amount", 0.0) / 100000.0
        
        state["part_pref_amount_lakhs_py"] = extracted_data.get("excel_part_pref_amount", 0.0) / 100000.0
        state["part_pref_amount_lakhs_fy"] = extracted_data.get("excel_part_pref_amount", 0.0) / 100000.0
        
        state["non_part_pref_amount_lakhs_py"] = extracted_data.get("excel_non_part_pref_amount", 0.0) / 100000.0
        state["non_part_pref_amount_lakhs_fy"] = extracted_data.get("excel_non_part_pref_amount", 0.0) / 100000.0
        

        # NR Holdings extraction & Lakh conversion
        if extracted_data.get("excel_nr_individuals_shares_count") is not None:
            state["nr_shares_individuals_py"] = extracted_data["excel_nr_individuals_shares_count"]
            state["nr_shares_individuals_fy"] = extracted_data["excel_nr_individuals_shares_count"]
            state["nr_amount_individuals_lakhs_py"] = extracted_data.get("excel_nr_individuals_amount", 0.0) / 100000.0
            state["nr_amount_individuals_lakhs_fy"] = extracted_data.get("excel_nr_individuals_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_companies_shares_count") is not None:
            state["nr_shares_companies_py"] = extracted_data["excel_nr_companies_shares_count"]
            state["nr_shares_companies_fy"] = extracted_data["excel_nr_companies_shares_count"]
            state["nr_amount_companies_lakhs_py"] = extracted_data.get("excel_nr_companies_amount", 0.0) / 100000.0
            state["nr_amount_companies_lakhs_fy"] = extracted_data.get("excel_nr_companies_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_fii_shares_count") is not None:
            state["nr_shares_fii_py"] = extracted_data["excel_nr_fii_shares_count"]
            state["nr_shares_fii_fy"] = extracted_data["excel_nr_fii_shares_count"]
            state["nr_amount_fii_lakhs_py"] = extracted_data.get("excel_nr_fii_amount", 0.0) / 100000.0
            state["nr_amount_fii_lakhs_fy"] = extracted_data.get("excel_nr_fii_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_fvci_shares_count") is not None:
            state["nr_shares_fvci_py"] = extracted_data["excel_nr_fvci_shares_count"]
            state["nr_shares_fvci_fy"] = extracted_data["excel_nr_fvci_shares_count"]
            state["nr_amount_fvci_lakhs_py"] = extracted_data.get("excel_nr_fvci_amount", 0.0) / 100000.0
            state["nr_amount_fvci_lakhs_fy"] = extracted_data.get("excel_nr_fvci_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_trusts_shares_count") is not None:
            state["nr_shares_trusts_py"] = extracted_data["excel_nr_trusts_shares_count"]
            state["nr_shares_trusts_fy"] = extracted_data["excel_nr_trusts_shares_count"]
            state["nr_amount_trusts_lakhs_py"] = extracted_data.get("excel_nr_trusts_amount", 0.0) / 100000.0
            state["nr_amount_trusts_lakhs_fy"] = extracted_data.get("excel_nr_trusts_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_pe_funds_shares_count") is not None:
            state["nr_shares_pe_funds_py"] = extracted_data["excel_nr_pe_funds_shares_count"]
            state["nr_shares_pe_funds_fy"] = extracted_data["excel_nr_pe_funds_shares_count"]
            state["nr_amount_pe_funds_lakhs_py"] = extracted_data.get("excel_nr_pe_funds_amount", 0.0) / 100000.0
            state["nr_amount_pe_funds_lakhs_fy"] = extracted_data.get("excel_nr_pe_funds_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_pension_funds_shares_count") is not None:
            state["nr_shares_pension_funds_py"] = extracted_data["excel_nr_pension_funds_shares_count"]
            state["nr_shares_pension_funds_fy"] = extracted_data["excel_nr_pension_funds_shares_count"]
            state["nr_amount_pension_funds_lakhs_py"] = extracted_data.get("excel_nr_pension_funds_amount", 0.0) / 100000.0
            state["nr_amount_pension_funds_lakhs_fy"] = extracted_data.get("excel_nr_pension_funds_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_swf_shares_count") is not None:
            state["nr_shares_swf_py"] = extracted_data["excel_nr_swf_shares_count"]
            state["nr_shares_swf_fy"] = extracted_data["excel_nr_swf_shares_count"]
            state["nr_amount_swf_lakhs_py"] = extracted_data.get("excel_nr_swf_amount", 0.0) / 100000.0
            state["nr_amount_swf_lakhs_fy"] = extracted_data.get("excel_nr_swf_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_partnerships_shares_count") is not None:
            state["nr_shares_partnerships_py"] = extracted_data["excel_nr_partnerships_shares_count"]
            state["nr_shares_partnerships_fy"] = extracted_data["excel_nr_partnerships_shares_count"]
            state["nr_amount_partnerships_lakhs_py"] = extracted_data.get("excel_nr_partnerships_amount", 0.0) / 100000.0
            state["nr_amount_partnerships_lakhs_fy"] = extracted_data.get("excel_nr_partnerships_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_fin_institutions_shares_count") is not None:
            state["nr_shares_fin_institutions_py"] = extracted_data["excel_nr_fin_institutions_shares_count"]
            state["nr_shares_fin_institutions_fy"] = extracted_data["excel_nr_fin_institutions_shares_count"]
            state["nr_amount_fin_institutions_lakhs_py"] = extracted_data.get("excel_nr_fin_institutions_amount", 0.0) / 100000.0
            state["nr_amount_fin_institutions_lakhs_fy"] = extracted_data.get("excel_nr_fin_institutions_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_nri_pio_shares_count") is not None:
            state["nr_shares_nri_pio_py"] = extracted_data["excel_nr_nri_pio_shares_count"]
            state["nr_shares_nri_pio_fy"] = extracted_data["excel_nr_nri_pio_shares_count"]
            state["nr_amount_nri_pio_lakhs_py"] = extracted_data.get("excel_nr_nri_pio_amount", 0.0) / 100000.0
            state["nr_amount_nri_pio_lakhs_fy"] = extracted_data.get("excel_nr_nri_pio_amount", 0.0) / 100000.0
        if extracted_data.get("excel_nr_non_part_pref_shares_count") is not None:
            state["nr_shares_non_part_pref_py"] = extracted_data["excel_nr_non_part_pref_shares_count"]
            state["nr_shares_non_part_pref_fy"] = extracted_data["excel_nr_non_part_pref_shares_count"]
            state["nr_amount_non_part_pref_lakhs_py"] = extracted_data.get("excel_nr_non_part_pref_amount", 0.0) / 100000.0
            state["nr_amount_non_part_pref_lakhs_fy"] = extracted_data.get("excel_nr_non_part_pref_amount", 0.0) / 100000.0

        # 2. Legacy fallback strategy (in case list of shareholders is missing)
        state["shares_to_lakhs('equity_shares_count_py', 'equity_face_value_py')"] = shares_to_lakhs('equity_shares_count_py', 'equity_face_value_py')
        state["shares_to_lakhs('equity_shares_count_fy', 'equity_face_value_fy')"] = shares_to_lakhs('equity_shares_count_fy', 'equity_face_value_fy')
        state["shares_to_lakhs('part_pref_shares_count_py', 'part_pref_face_value_py')"] = shares_to_lakhs('part_pref_shares_count_py', 'part_pref_face_value_py')
        state["shares_to_lakhs('part_pref_shares_count_fy', 'part_pref_face_value_fy')"] = shares_to_lakhs('part_pref_shares_count_fy', 'part_pref_face_value_fy')
        state["shares_to_lakhs('non_part_pref_shares_count_py', 'non_part_pref_face_value_py')"] = shares_to_lakhs('non_part_pref_shares_count_py', 'non_part_pref_face_value_py')
        state["shares_to_lakhs('non_part_pref_shares_count_fy', 'non_part_pref_face_value_fy')"] = shares_to_lakhs('non_part_pref_shares_count_fy', 'non_part_pref_face_value_fy')

        # We will keep a dictionary to store section cell values dynamically
        # which allows cell-to-cell formulas like sum_cells or subtract_cells
        cell_values = {
            "Section I": {},
            "Section II": {},
            "Section III": {},
            "Section IV": {}
        }
        
        # Phase 1: Populate all extracted and direct calculated values into the coordinate system
        for section in ["Section I", "Section II", "Section III", "Section IV"]:
            for key, field_cfg in self.config["cell_mappings"][section].items():
                cell = field_cfg["cell"]
                ftype = field_cfg["type"]
                
                if ftype == "extracted":
                    field_name = field_cfg.get("field")
                    val = state.get(field_name, field_cfg.get("default", 0.0))
                    
                    # Apply financial scale if applicable
                    financial_fields = [
                        "profit_before_tax_py", "profit_before_tax_fy",
                        "profit_after_tax_py", "profit_after_tax_fy",
                        "dividend_paid_py", "dividend_paid_fy",
                        "tax_on_dividend_py", "tax_on_dividend_fy",
                        "reserves_and_surplus_py", "reserves_and_surplus_fy",
                        "pl_balance_py", "pl_balance_fy",
                        "domestic_sales_py", "domestic_sales_fy",
                        "export_sales_py", "export_sales_fy",
                        "revenue_from_operations_py", "revenue_from_operations_fy",
                        "domestic_purchases_py", "domestic_purchases_fy",
                        "import_purchases_py", "import_purchases_fy",
                        "total_purchases_py", "total_purchases_fy"
                    ]
                    if field_name in financial_fields:
                        scale = state.get("financials_scale", "Actuals")
                        try:
                            f_val = float(val)
                            if scale == "Actuals":
                                val = f_val / 100000.0
                            elif scale == "Thousands":
                                val = f_val / 100.0
                        except Exception:
                            pass
                            
                    cell_values[section][cell] = val
                elif ftype == "calculated":
                    formula = field_cfg.get("formula")
                    if formula in state:
                        cell_values[section][cell] = state[formula]
                    else:
                        cell_values[section][cell] = 0.0 # Placeholder for nested formulas
                        
        # Helper to get cell value safely as float
        def get_val(sec, coord):
            val = cell_values[sec].get(coord, 0.0)
            if val == "N/A" or val is None:
                return 0.0
            try:
                return float(val)
            except ValueError:
                return 0.0

        # Phase 2: Resolve intermediate sheet formulas
        # Section II
        # F5 = F6 + F9 (Total Paid-up PY)
        # G5 = G6 + G9 (Total Paid-up FY)
        # F6 = F7 + F8 (Total Equity & Part Pref PY)
        # G6 = G7 + G8 (Total Equity & Part Pref FY)
        cell_values["Section II"]["D6"] = get_val("Section II", "D7") + get_val("Section II", "D8")
        cell_values["Section II"]["E6"] = get_val("Section II", "E7") + get_val("Section II", "E8")
        cell_values["Section II"]["D5"] = get_val("Section II", "D6") + get_val("Section II", "D9")
        cell_values["Section II"]["E5"] = get_val("Section II", "E6") + get_val("Section II", "E9")

        cell_values["Section II"]["F6"] = get_val("Section II", "F7") + get_val("Section II", "F8")
        cell_values["Section II"]["G6"] = get_val("Section II", "G7") + get_val("Section II", "G8")
        cell_values["Section II"]["F5"] = get_val("Section II", "F6") + get_val("Section II", "F9")
        cell_values["Section II"]["G5"] = get_val("Section II", "G6") + get_val("Section II", "G9")

        # NR Holdings
        # Calculate proportional Rs. LAKHS amount for each category (rows 12 to 22) in Columns F and G:
        # Amount = (Shares held / Total Shares) * Total Share Capital
        total_sh_py = get_val("Section II", "D7") + get_val("Section II", "D8")
        total_sh_fy = get_val("Section II", "E7") + get_val("Section II", "E8")
        f6_val = get_val("Section II", "F6")
        g6_val = get_val("Section II", "G6")
        
        for r in range(12, 23):
            sh_py = get_val("Section II", f"D{r}")
            sh_fy = get_val("Section II", f"E{r}")
            cell_values["Section II"][f"F{r}"] = (sh_py / total_sh_py * f6_val) if total_sh_py > 0 else 0.0
            cell_values["Section II"][f"G{r}"] = (sh_fy / total_sh_fy * g6_val) if total_sh_fy > 0 else 0.0

        # F11 = Sum of F12..F22
        # G11 = Sum of G12..G22
        nr_rows = [f"F{r}" for r in range(12, 23)]
        cell_values["Section II"]["F11"] = sum(get_val("Section II", r) for r in nr_rows)
        nr_rows_fy = [f"G{r}" for r in range(12, 23)]
        cell_values["Section II"]["G11"] = sum(get_val("Section II", r) for r in nr_rows_fy)
        
        # NR Equity % (F24 = (F11 / F6) * 100, G24 = (G11 / G6) * 100)
        cell_values["Section II"]["F24"] = (get_val("Section II", "F11") / f6_val * 100.0) if f6_val > 0 else 0.0
        cell_values["Section II"]["G24"] = (get_val("Section II", "G11") / g6_val * 100.0) if g6_val > 0 else 0.0
        
        # Retained Profit (F30 = F27 - F28 - F29, G30 = G27 - G28 - G29)
        cell_values["Section II"]["F30"] = get_val("Section II", "F27") - get_val("Section II", "F28") - get_val("Section II", "F29")
        cell_values["Section II"]["G30"] = get_val("Section II", "G27") - get_val("Section II", "G28") - get_val("Section II", "G29")
        
        # Net Worth (F34 = F6 + F32, G34 = G6 + G32)
        cell_values["Section II"]["F34"] = get_val("Section II", "F6") + get_val("Section II", "F32")
        cell_values["Section II"]["G34"] = get_val("Section II", "G6") + get_val("Section II", "G32")
        
        # Total Purchases (F41 = F39 + F40, G41 = G39 + G40)
        cell_values["Section II"]["F41"] = get_val("Section II", "F39") + get_val("Section II", "F40")
        cell_values["Section II"]["G41"] = get_val("Section II", "G39") + get_val("Section II", "G40")

        # Section III FDI / DI calculations
        # FDI 1 Equity Capital holding (D20 = (D17 / 100) * Net_Worth_PY, E20 = (E17 / 100) * Net_Worth_FY)
        net_worth_py = cell_values["Section II"]["F34"]
        net_worth_fy = cell_values["Section II"]["G34"]
        
        fdi1_eq_pct_py = get_val("Section III", "D17")
        fdi1_eq_pct_fy = get_val("Section III", "E17")
        cell_values["Section III"]["D20"] = (fdi1_eq_pct_py / 100.0) * net_worth_py
        cell_values["Section III"]["E20"] = (fdi1_eq_pct_fy / 100.0) * net_worth_fy
        
        # FDI 1: 1.1 Liabilities to Direct Investors (D21, E21)
        cell_values["Section III"]["D21"] = cell_values["Section III"]["D20"]
        cell_values["Section III"]["E21"] = cell_values["Section III"]["E20"]
        
        # FDI 1 Other Capital (D23 = D24 - D25, E23 = E24 - E25)
        cell_values["Section III"]["D23"] = get_val("Section III", "D24") - get_val("Section III", "D25")
        cell_values["Section III"]["E23"] = get_val("Section III", "E24") - get_val("Section III", "E25")

        # FDI 2 Equity Capital holding (Z33 = (Z31 / 100) * Net_Worth_PY, Z34 = (Z32 / 100) * Net_Worth_FY)
        fdi2_eq_pct_py = get_val("Section III", "Z31")
        fdi2_eq_pct_fy = get_val("Section III", "Z32")
        cell_values["Section III"]["Z33"] = (fdi2_eq_pct_py / 100.0) * net_worth_py
        cell_values["Section III"]["Z34"] = (fdi2_eq_pct_fy / 100.0) * net_worth_fy
        
        # FDI 2: 1.1 Liabilities to Direct Investors (Z35, Z36)
        cell_values["Section III"]["Z35"] = cell_values["Section III"]["Z33"]
        cell_values["Section III"]["Z36"] = cell_values["Section III"]["Z34"]

        # FDI 2 Other Capital (Z39 = Z41 - Z43, Z40 = Z42 - Z44)
        cell_values["Section III"]["Z39"] = get_val("Section III", "Z41") - get_val("Section III", "Z43")
        cell_values["Section III"]["Z40"] = get_val("Section III", "Z42") - get_val("Section III", "Z44")

        # Block 2 DI 1 Equity Capital holding (D44 = (C41 / 100) * Net_Worth_PY, E44 = (D41 / 100) * Net_Worth_FY)
        di1_eq_pct_py = get_val("Section III", "C41")
        di1_eq_pct_fy = get_val("Section III", "D41")
        cell_values["Section III"]["D44"] = (di1_eq_pct_py / 100.0) * net_worth_py
        cell_values["Section III"]["E44"] = (di1_eq_pct_fy / 100.0) * net_worth_fy
        
        # Block 2 DI 1: 1.1 Liabilities to Direct Investors (D45, E45)
        cell_values["Section III"]["D45"] = cell_values["Section III"]["D44"]
        cell_values["Section III"]["E45"] = cell_values["Section III"]["E44"]

        # Block 2 DI 1 Other Capital (D47 = D48 - D49, E47 = E48 - E49)
        cell_values["Section III"]["D47"] = get_val("Section III", "D48") - get_val("Section III", "D49")
        cell_values["Section III"]["E47"] = get_val("Section III", "E48") - get_val("Section III", "E49")
        
        # Pass multi-country JSON if present to Section III cell_values
        cell_values["Section III"]["fdi_investor_2_countries_json"] = extracted_data.get("fdi_investor_2_countries_json", "[]")
        
        # Unrelated Total Liabilities (D74 = Sum of D70..D73, E74 = Sum of E70..E73)
        cell_values["Section III"]["D74"] = sum(get_val("Section III", f"D{r}") for r in range(70, 74))
        cell_values["Section III"]["E74"] = sum(get_val("Section III", f"E{r}") for r in range(70, 74))

        # Section IV ODI calculations
        # DIE 1 Net Worth (D30 = D26 + D28, E30 = E26 + E28)
        cell_values["Section IV"]["D30"] = get_val("Section IV", "D26") + get_val("Section IV", "D28")
        cell_values["Section IV"]["E30"] = get_val("Section IV", "E26") + get_val("Section IV", "E28")
        
        # DIE 1 Equity Capital and PPS (in INR Lakhs) (D39 = (D27 * D31) / 100,000, E39 = (E27 * E31) / 100,000)
        # where D27 is Equity held by you (face value, in FC) and D31 is Exchange rate
        cell_values["Section IV"]["D39"] = (get_val("Section IV", "D27") * get_val("Section IV", "D31")) / 100000.0
        cell_values["Section IV"]["E39"] = (get_val("Section IV", "E27") * get_val("Section IV", "E31")) / 100000.0
        
        # DIE 1 Other Capital (D42 = D43 - D44, E42 = E43 - E44)
        cell_values["Section IV"]["D42"] = get_val("Section IV", "D43") - get_val("Section IV", "D44")
        cell_values["Section IV"]["E42"] = get_val("Section IV", "E43") - get_val("Section IV", "E44")
        
        # Unrelated Total Claims (D100 = Sum of D96..D99, E100 = Sum of E96..E99)
        cell_values["Section IV"]["D100"] = sum(get_val("Section IV", f"D{r}") for r in range(96, 100))
        cell_values["Section IV"]["E100"] = sum(get_val("Section IV", f"E{r}") for r in range(96, 100))
        
        return cell_values
