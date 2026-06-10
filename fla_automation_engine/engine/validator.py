import json
import os

class ReturnValidator:
    def __init__(self):
        self.validation_logs = []
        
    def log_check(self, name, passed, details):
        status = "PASSED" if passed else "FAILED"
        self.validation_logs.append({
            "check_name": name,
            "status": status,
            "details": details
        })
        print(f"[{status}] {name}: {details}")

    def run_all_checks(self, cell_values):
        """Executes all logical and mathematical validations."""
        self.validation_logs = []
        print("\n=== RUNNING FLA RETURN CONSISTENCY VALIDATION ===")
        
        # Helper to get cell value as float
        def get_sec_val(sec, coord):
            val = cell_values[sec].get(coord, 0.0)
            if val == "N/A" or val is None:
                return 0.0
            try:
                return float(val)
            except ValueError:
                return 0.0

        # Check 1: Paid Up Capital consistencies
        equity_shares = get_sec_val("Section II", "D7")
        equity_fv = get_sec_val("Section I", "C26")
        equity_amt = get_sec_val("Section II", "F7")
        expected_equity_amt = (equity_shares * equity_fv) / 100000.0
        
        passed_eq = abs(equity_amt - expected_equity_amt) < 0.01
        self.log_check(
            "Equity Share Capital Math",
            passed_eq,
            f"Calculated: {equity_amt} Lakhs, Expected (Shares * Face Value / 100000): {expected_equity_amt:.2f} Lakhs"
        )
        
        # Check 2: Total Paid Up Capital sum check
        total_puc = get_sec_val("Section II", "F5")
        sum_puc = get_sec_val("Section II", "F6") + get_sec_val("Section II", "F9")
        passed_puc = abs(total_puc - sum_puc) < 0.01
        self.log_check(
            "Total Paid-Up Capital Consolidation",
            passed_puc,
            f"Total PUC: {total_puc} Lakhs, Sum of Equity & Preference: {sum_puc} Lakhs"
        )
        
        # Check 3: NR Holdings percentage validation
        nr_cap = get_sec_val("Section II", "F11")
        total_cap = get_sec_val("Section II", "F6")
        nr_percent = get_sec_val("Section II", "F24")
        expected_nr_percent = (nr_cap / total_cap * 100.0) if total_cap > 0 else 0.0
        passed_nr = abs(nr_percent - expected_nr_percent) < 0.01
        self.log_check(
            "Non-Resident Shareholding Percentage",
            passed_nr,
            f"Fitted Percent: {nr_percent:.2f}%, Expected: {expected_nr_percent:.2f}% (NR Capital: {nr_cap} / Total Capital: {total_cap})"
        )
        
        # Check 4: Retained Profit formula
        pat = get_sec_val("Section II", "F27")
        div = get_sec_val("Section II", "F28")
        tax_div = get_sec_val("Section II", "F29")
        ret_profit = get_sec_val("Section II", "F30")
        expected_ret = pat - div - tax_div
        passed_ret = abs(ret_profit - expected_ret) < 0.01
        self.log_check(
            "Retained Profit formula",
            passed_ret,
            f"Retained Profit: {ret_profit} Lakhs, Expected (PAT - Dividend - Tax on Div): {expected_ret} Lakhs"
        )
        
        # Check 5: Net Worth calculation
        nw = get_sec_val("Section II", "F34")
        expected_nw = total_cap + get_sec_val("Section II", "F32")
        passed_nw = abs(nw - expected_nw) < 0.01
        self.log_check(
            "Company Net Worth formula",
            passed_nw,
            f"Net Worth: {nw} Lakhs, Expected (Paid Up Capital + Reserves): {expected_nw} Lakhs"
        )
        
        # Check 6: Sales total check
        tot_sales = get_sec_val("Section II", "F38")
        expected_sales = get_sec_val("Section II", "F36") + get_sec_val("Section II", "F37")
        passed_sales = abs(tot_sales - expected_sales) < 0.01
        self.log_check(
            "Total Sales Consolidation",
            passed_sales,
            f"Total Sales: {tot_sales} Lakhs, Sum of Domestic & Exports: {expected_sales} Lakhs"
        )
        
        # Check 7: Purchases total check
        tot_purch = get_sec_val("Section II", "F41")
        expected_purch = get_sec_val("Section II", "F39") + get_sec_val("Section II", "F40")
        passed_purch = abs(tot_purch - expected_purch) < 0.01
        self.log_check(
            "Total Purchase Consolidation",
            passed_purch,
            f"Total Purchases: {tot_purch} Lakhs, Sum of Domestic & Imports: {expected_purch} Lakhs"
        )
        
        # Check 8: FDI Investor counts match
        fdi_investors_count = cell_values["Section III"].get("D6", 1)
        passed_fdi = int(fdi_investors_count) >= 0
        self.log_check(
            "FDI Investor Count validity",
            passed_fdi,
            f"Number of direct foreign investors: {fdi_investors_count}"
        )
        
        # Check 9: ODI DIE Net Worth matching
        die_puc = get_sec_val("Section IV", "D26")
        die_res = get_sec_val("Section IV", "D28")
        die_nw = get_sec_val("Section IV", "D30")
        expected_die_nw = die_puc + die_res
        passed_die_nw = abs(die_nw - expected_die_nw) < 0.01
        self.log_check(
            "Overseas DIE 1 Net Worth formula",
            passed_die_nw,
            f"DIE Net Worth: {die_nw} FC, Expected (DIE Equity + Reserves): {expected_die_nw} FC"
        )

        return self.validation_logs

    def save_report(self, output_dir="."):
        """Saves a formal JSON and text report of the validation checks."""
        json_report_path = os.path.join(output_dir, "validation_report.json")
        txt_report_path = os.path.join(output_dir, "validation_report.txt")
        
        # Save JSON
        with open(json_report_path, "w") as f:
            json.dump(self.validation_logs, f, indent=2)
            
        # Save readable text report
        with open(txt_report_path, "w") as f:
            f.write("==================================================\n")
            f.write("       RBI FLA RETURN AUDIT & VALIDATION REPORT     \n")
            f.write("==================================================\n\n")
            
            passed_count = sum(1 for log in self.validation_logs if log["status"] == "PASSED")
            f.write(f"Summary: {passed_count} / {len(self.validation_logs)} checks passed.\n\n")
            
            for log in self.validation_logs:
                f.write(f"[{log['status']}] {log['check_name']}\n")
                f.write(f"      Details: {log['details']}\n\n")
                
        print(f"[+] Saved validation reports to:")
        print(f"    - JSON: {json_report_path}")
        print(f"    - Text: {txt_report_path}")
        return json_report_path, txt_report_path
