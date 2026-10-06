import os
import sys
from typing import Dict, Any

class FLABridgeAdapter:
    """
    IDP-to-FLA Bridge Adapter (Layer 2)
    
    Bridges modern IDP Studio PDF semantic extraction (Layer 1) to the untouched
    RBI FLA RuleEngine accounting formulas & Excel cell mapper (Layer 3).
    
    Ensures zero changes to `/modules/fla/` while providing:
    - Phase 1: Pre-Evaluation Translation (protects IDP data from legacy zero overrides)
    - Phase 2: Untouched FLA accounting math execution (100% of RBI rules & formulas)
    - Phase 3: Post-Evaluation Direct Mapping Guarantee & Summary Total Reconciliation
    """

    def __init__(self, config_path: str = "modules/fla/rules_config.json"):
        # Add project root to sys.path so modules can be imported cleanly
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if root_dir not in sys.path:
            sys.path.append(root_dir)
            
        from modules.fla.rule_engine import RuleEngine
        self.engine = RuleEngine(config_path=config_path)

    def get_all_cell_labels(self) -> Dict[str, Dict[str, str]]:
        """
        Returns a mapping of Section -> {Cell Code -> Official RBI Row Label}
        for all cells across Section I, Section II, Section III, Section IV.
        """
        labels = {}
        cell_mappings = self.engine.config.get("cell_mappings", {})
        for section, fields in cell_mappings.items():
            labels[section] = {}
            for key, field_cfg in fields.items():
                cell_code = field_cfg.get("cell")
                row_label = field_cfg.get("row_label") or field_cfg.get("description") or key
                if cell_code and row_label:
                    labels[section][cell_code] = str(row_label).rstrip("*").strip()
        return labels

    def normalize_payload_keys(self, idp_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 0: Semantic Field Normalizer & Alias Mapper.
        Bridges incoming IDP Studio extraction keys (e.g. FIELD_2PANNUMBER, FIELD_NAMEOFTHECONTACTPERSON,
        FIELD_10TOTALPAIDUPCAPITAL...) to official rules_config.json field names.
        """
        normalized = dict(idp_payload)
        
        mapping_rules = [
            ("pan_number", ["pan", "pannumber", "field_2pannumber", "field_pan"]),
            ("cin_number", ["cin", "cinnumber", "field_3cinnumber", "field_cin"]),
            ("contact_name", ["contactname", "contactperson", "nameofthecontactperson", "nameofcontactperson", "contact_name"]),
            ("telephone", ["telephone", "telephoneno", "telephonenowithextension", "field_telephone"]),
            ("mobile_number", ["mobile", "mobileno", "mobilenumber", "field_mobile"]),
            ("email_id", ["emailhead", "emailheadofinstitution", "emailid", "email_id"]),
            ("email_contact", ["emailofcontact", "emailcontact", "emailofcontactperson", "email_contact"]),
            ("designation", ["designation", "field_designation"]),
            ("website", ["website", "websiteifany", "field_website"]),
            ("company_name", ["companyname", "nameoftheindiancompany", "nameofindiancompany", "indiancompany", "company_name"]),
            ("filing_year", ["filingyear", "filing_year", "year", "field_year"]),
            ("closing_date", ["closingdate", "closing_date", "closingdateofreferenceperiod"]),
            ("listed_status", ["listed", "listedstatus", "whethercompanyislisted", "listed_status"]),
            ("equity_amount_lakhs_fy", ["equityamountlakhsfy", "paidupcapital", "totalpaidupcapital", "totalpaidupcapital101112167631", "totalequityandparticipating167631", "ordinaryequityamount", "ordinaryequityamountfy", "ordinaryequityshareamount"]),
            ("equity_amount_lakhs_py", ["equityamountlakhspy", "paidupcapitalpy", "ordinaryequityamountpy", "ordinaryequityshareamountpy"])
        ]
        
        cleaned_incoming = {}
        for k, v in idp_payload.items():
            if v is not None and v != "" and v != "Unknown" and v != "N/A":
                clean_k = ''.join(c for c in str(k).lower() if c.isalnum())
                cleaned_incoming[clean_k] = (k, v)
            
        for official_field, kw_list in mapping_rules:
            if official_field not in normalized or not normalized[official_field] or normalized[official_field] in ["Unknown", "N/A"]:
                for clean_k, (original_k, val) in cleaned_incoming.items():
                    if any(kw == clean_k or kw in clean_k for kw in kw_list):
                        normalized[official_field] = val
                        break
                        
        # Token-based robust matcher for ALL official fields (handles "3.1 Profit (+)/Loss (-) before tax PY" -> "profit_before_tax_py")
        official_fields = []
        for section, fields in self.engine.config.get("cell_mappings", {}).items():
            for key, field_cfg in fields.items():
                if field_cfg.get("type") == "extracted" and field_cfg.get("field"):
                    official_fields.append(field_cfg.get("field"))
                    
        for official_field in official_fields:
            if official_field not in normalized or not normalized[official_field] or normalized[official_field] in ["Unknown", "N/A"]:
                is_py = official_field.endswith('_py')
                is_fy = official_field.endswith('_fy')
                
                base_field = official_field.rsplit('_', 1)[0] if (is_py or is_fy) else official_field
                tokens = [t for t in base_field.split('_') if t not in ['and', 'of', 'the', 'amount', 'lakhs', 'count', 'share', 'shares']]
                
                for clean_k, (original_k, val) in cleaned_incoming.items():
                    # Year distinction check
                    if is_py and not any(py_kw in clean_k for py_kw in ['py', 'previous', '2024', 'prior']):
                        continue
                    if is_fy and any(py_kw in clean_k for py_kw in ['py', 'previous', '2024', 'prior']):
                        continue
                        
                    if tokens and all(t in clean_k for t in tokens):
                        normalized[official_field] = val
                        break
                        
        return normalized

    def adapt_and_evaluate(self, idp_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Executes the 3-Phase Bridge pipeline and returns the final Excel grid coordinates.
        """
        # ==============================================================================
        # PHASE 1: Pre-Evaluation Translation (The Shield)
        # ==============================================================================
        # Phase 0: Normalize incoming custom IDP keys to rules_config standard field names
        adapted = self.normalize_payload_keys(idp_payload)

        # Helper to safely get float from payload
        def _get_float(key: str, default: float = 0.0) -> float:
            val = adapted.get(key, default)
            if val == "N/A" or val is None or val == "":
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        # ==============================================================================
        # PHASE 2: Untouched Legacy RuleEngine Evaluation (100% of FLA Accounting Math)
        # ==============================================================================
        # Executes all 401 lines of rule_engine.py untouched
        target_cells = self.engine.evaluate_all(adapted)

        # ==============================================================================
        # PHASE 3: Direct Mapping Guarantee & Summary Total Reconciliation
        # ==============================================================================
        # 1. Guarantee that any field explicitly mapped in IDP Studio is preserved in the cell grid
        cell_mappings = self.engine.config.get("cell_mappings", {})
        for section, fields in cell_mappings.items():
            if section not in target_cells:
                target_cells[section] = {}
            for key, field_cfg in fields.items():
                if field_cfg.get("type") == "extracted":
                    field_name = field_cfg.get("field")
                    cell_code = field_cfg.get("cell")
                    if field_name and cell_code and field_name in adapted and adapted[field_name] not in [None, "", "Unknown", "N/A"]:
                        # Direct Mapping Guarantee: IDP Studio extracted value is absolute truth
                        target_cells[section][cell_code] = adapted[field_name]

        # 1B. True Previous Year (PY) Isolation Guard:
        # Ensure Previous Year (PY) values come strictly from PY only without legacy FY fallback overrides.
        for section, fields in cell_mappings.items():
            if section not in target_cells:
                continue
            for key, field_cfg in fields.items():
                if field_cfg.get("type") == "extracted":
                    field_name = field_cfg.get("field")
                    cell_code = field_cfg.get("cell")
                    if field_name and cell_code and field_name.endswith("_py"):
                        if field_name not in adapted or adapted[field_name] in [None, "", "Unknown", "N/A"]:
                            target_cells[section][cell_code] = 0.0

        # 2. Reconcile Section II Summary Totals so the Excel sheet is mathematically consistent
        def _cell_val(sec: str, coord: str) -> float:
            val = target_cells.get(sec, {}).get(coord, 0.0)
            if val == "N/A" or val is None or val == "":
                return 0.0
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0.0

        sec_ii = target_cells.get("Section II", {})
        if sec_ii:
            # Total Equity & Part Pref Shares PY/FY
            sec_ii["D6"] = _cell_val("Section II", "D7") + _cell_val("Section II", "D8")
            sec_ii["E6"] = _cell_val("Section II", "E7") + _cell_val("Section II", "E8")
            # Total Paid-up Capital Shares PY/FY
            sec_ii["D5"] = _cell_val("Section II", "D6") + _cell_val("Section II", "D9")
            sec_ii["E5"] = _cell_val("Section II", "E6") + _cell_val("Section II", "E9")

            # Total Equity & Part Pref Amount PY/FY (Lakhs)
            sec_ii["F6"] = _cell_val("Section II", "F7") + _cell_val("Section II", "F8")
            sec_ii["G6"] = _cell_val("Section II", "G7") + _cell_val("Section II", "G8")
            # Total Paid-up Capital Amount PY/FY (Lakhs)
            sec_ii["F5"] = _cell_val("Section II", "F6") + _cell_val("Section II", "F9")
            sec_ii["G5"] = _cell_val("Section II", "G6") + _cell_val("Section II", "G9")

            # Net Worth PY/FY (if unmapped, compute as Total Capital + Reserves & Surplus)
            if "net_worth_py" not in idp_payload:
                sec_ii["F34"] = _cell_val("Section II", "F6") + _cell_val("Section II", "F32")
            if "net_worth_fy" not in idp_payload:
                sec_ii["G34"] = _cell_val("Section II", "G6") + _cell_val("Section II", "G32")

            # Total Purchases PY/FY (Domestic + Imports)
            sec_ii["F41"] = _cell_val("Section II", "F39") + _cell_val("Section II", "F40")
            sec_ii["G41"] = _cell_val("Section II", "G39") + _cell_val("Section II", "G40")

        # 3. Reconcile Section III Summary Totals (Unrelated Total Liabilities D74 / E74)
        sec_iii = target_cells.get("Section III", {})
        if sec_iii:
            sec_iii["D74"] = sum(_cell_val("Section III", f"D{r}") for r in range(70, 74))
            sec_iii["E74"] = sum(_cell_val("Section III", f"E{r}") for r in range(70, 74))

        # 4. Reconcile Section IV Summary Totals (ODI Net Worth D30/E30 & Total Claims D100/E100)
        sec_iv = target_cells.get("Section IV", {})
        if sec_iv:
            sec_iv["D30"] = _cell_val("Section IV", "D26") + _cell_val("Section IV", "D28")
            sec_iv["E30"] = _cell_val("Section IV", "E26") + _cell_val("Section IV", "E28")
            sec_iv["D100"] = sum(_cell_val("Section IV", f"D{r}") for r in range(96, 100))
            sec_iv["E100"] = sum(_cell_val("Section IV", f"E{r}") for r in range(96, 100))

        return target_cells
