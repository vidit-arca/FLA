import os
import re
from difflib import SequenceMatcher
from .excel_extractor import AOC4ExcelExtractor

class AOC4PreviousYearReconciler:
    """
    Dedicated Additional Feature for AOC-4:
    Performs full line-by-line cross-reconciliation across ALL Financial Statement tables
    (Balance Sheet, Statement of Profit & Loss, and Notes to Accounts).
    Compares CY Financials (Previous Year Comparative Column) vs Last Year Filed Financials (Actual Filed Column).
    """
    def __init__(self, config_path: str = None):
        self.excel_extractor = AOC4ExcelExtractor()

    def _clean_number(self, val_str: str):
        """Extracts float from currency string, handling parentheses, dashes, commas."""
        if not val_str or not isinstance(val_str, str):
            return None
        clean = val_str.strip().replace(",", "").replace(" ", "")
        if clean in ["-", "–", "—", "nil", "NIL", "Nil", "pt", "_", ""]:
            return 0.0
        # Check for percentage
        if "%" in clean:
            return None
        # Handle parentheses for negative numbers (e.g. (17,719.08) -> -17719.08)
        if clean.startswith("(") and clean.endswith(")"):
            clean = "-" + clean[1:-1]
        try:
            return float(clean)
        except ValueError:
            return None

    def _normalize_title(self, title: str) -> str:
        """Normalizes line item title for robust matching."""
        t = title.lower()
        t = re.sub(r'^\s*\(?[a-z0-9ivx]+\)?[.)\s]*', '', t) # remove numbering like (a), 1., etc.
        t = re.sub(r'[^a-z0-9 ]', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def _extract_table_rows(self, text: str, scale: float = 1.0) -> list:
        """
        Extracts all financial statement table rows containing particulars and figures.
        Returns list of dicts: {'particulars': str, 'norm_title': str, 'cy_val': float, 'py_val': float, 'section': str}
        """
        rows = []
        lines = text.split("\n")
        
        current_section = "Financial Statements"
        in_board_report = False

        for idx, line in enumerate(lines):
            line_clean = line.strip()
            line_lower = line_clean.lower()
            
            # Track sections
            if re.search(r'^(#+\s*)?(board(\'s)? report|directors?\'? report)', line_lower):
                in_board_report = True
                continue
            elif re.search(r'^(#+\s*)?(independent auditor\'s report|auditor\'s report|notes to the financial statements|notes to accounts|balance sheet|statement of profit)', line_lower):
                in_board_report = False
                
            if in_board_report:
                continue

            if "balance sheet" in line_lower:
                current_section = "Balance Sheet"
            elif "statement of profit" in line_lower or "profit and loss" in line_lower:
                current_section = "Statement of Profit and Loss"
            elif line_lower.startswith("note") or "notes to" in line_lower:
                current_section = f"Notes ({line_clean[:40]})"

            # Check for markdown table row
            if line_clean.startswith("|") and line_clean.endswith("|"):
                cells = [c.strip() for c in line_clean.strip("|").split("|")]
                if len(cells) < 2:
                    continue

                # Skip header separator rows
                if all(re.match(r'^[-:\s]+$', c) for c in cells if c):
                    continue

                # Header rows like "Particulars | Note | As at..."
                if any(h in cells[0].lower() for h in ["particulars", "description", "statement of", "balance sheet as at", "for the year ended"]):
                    continue

                # Check if first cell is a valid line item title
                title = cells[0].strip()
                if not title or len(title) < 2:
                    continue

                # Filter out pure date or noise headers
                if re.match(r'^(as at|for the year|inr|amount in|\d+&?\d*)$', title.lower()):
                    continue

                # Find numerical values in remaining cells
                numbers = []
                for cell in cells[1:]:
                    num = self._clean_number(cell)
                    if num is not None:
                        numbers.append(num)

                # Skip rows with no numerical values
                if not numbers:
                    continue

                # Filter out single small integers that are likely Note numbers (e.g. Note 3, Note 15)
                filtered_nums = []
                for n_idx, n in enumerate(numbers):
                    # If first number is integer < 50 and there are subsequent numbers, it's a note number
                    if n_idx == 0 and len(numbers) > 1 and n.is_integer() and 1 <= n < 50:
                        continue
                    # Skip calendar years
                    if 1990 <= abs(n) <= 2035 and n.is_integer():
                        continue
                    filtered_nums.append(n * scale)

                if filtered_nums:
                    cy_val = filtered_nums[0] if len(filtered_nums) >= 1 else None
                    py_val = filtered_nums[1] if len(filtered_nums) >= 2 else None
                    
                    rows.append({
                        "particulars": title,
                        "norm_title": self._normalize_title(title),
                        "cy_val": cy_val,
                        "py_val": py_val,
                        "section": current_section
                    })

        return rows

    def reconcile(self, cy_text_or_data, py_text_or_data) -> dict:
        """
        Performs full line-by-line cross-reconciliation across ALL Financial Statement tables.
        """
        scale_cy = 1.0
        scale_py = 1.0

        if isinstance(cy_text_or_data, str):
            scale_cy = self.excel_extractor.detect_financials_scale(cy_text_or_data)
            cy_rows = self._extract_table_rows(cy_text_or_data, scale=scale_cy)
        else:
            cy_rows = []

        if isinstance(py_text_or_data, str):
            scale_py = self.excel_extractor.detect_financials_scale(py_text_or_data)
            py_rows = self._extract_table_rows(py_text_or_data, scale=scale_py)
        else:
            py_rows = []

        # Cross-match each CY row's Previous Year Comparative value against PY row's Actual Filed value
        reconciliation_items = []
        matched_count = 0
        mismatches_count = 0
        seen_keys = set()

        for cy_row in cy_rows:
            # We want rows that have a Previous Year comparative figure in CY Financials
            if cy_row["py_val"] is None:
                continue

            norm_cy = cy_row["norm_title"]
            if not norm_cy or len(norm_cy) < 3:
                continue

            # Find best matching row in PY filed financials
            best_match = None
            best_score = 0.0

            for py_row in py_rows:
                norm_py = py_row["norm_title"]
                if not norm_py:
                    continue

                # Exact normalized match
                if norm_cy == norm_py:
                    best_match = py_row
                    best_score = 1.0
                    break

                # Substring match
                if norm_cy in norm_py or norm_py in norm_cy:
                    score = 0.9
                    if score > best_score:
                        best_score = score
                        best_match = py_row
                else:
                    # Fuzzy match
                    score = SequenceMatcher(None, norm_cy, norm_py).ratio()
                    if score > 0.82 and score > best_score:
                        best_score = score
                        best_match = py_row

            if best_match and best_match["cy_val"] is not None:
                item_key = (cy_row["section"], norm_cy)
                if item_key in seen_keys:
                    continue
                seen_keys.add(item_key)

                v_cy_py = cy_row["py_val"]
                v_py_actual = best_match["cy_val"]
                diff = round(v_cy_py - v_py_actual, 2)

                # Tolerance: within 1 unit or 0.1% for minor rounding differences
                is_match = abs(diff) <= max(1.0, abs(v_py_actual) * 0.001)
                status = "MATCHED" if is_match else "MISMATCH"

                if is_match:
                    matched_count += 1
                else:
                    mismatches_count += 1

                reconciliation_items.append({
                    "section": cy_row["section"],
                    "line_item": cy_row["particulars"],
                    "cy_reported_py": v_cy_py,
                    "last_year_filed": v_py_actual,
                    "variance": diff,
                    "status": status
                })

        return {
            "summary": {
                "total_compared": len(reconciliation_items),
                "matched": matched_count,
                "mismatches": mismatches_count,
                "status": "ALL_MATCHED" if mismatches_count == 0 and len(reconciliation_items) > 0 else ("MISMATCH_FOUND" if mismatches_count > 0 else "NO_DATA")
            },
            "reconciliation_items": reconciliation_items
        }

    def export_to_excel(self, report_result: dict, output_path: str):
        """Exports the full line-by-line variance report to a standalone Excel spreadsheet."""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Full Statement PY Variance"

        # Title Block
        ws.merge_cells("A1:F1")
        ws["A1"] = "PREVIOUS YEAR FIGURES COMPREHENSIVE RECONCILIATION REPORT"
        ws["A1"].font = Font(name="Arial", size=13, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 28

        # Summary Block
        sum_data = report_result.get("summary", {})
        ws["A2"] = f"Total Line Items Reconciled: {sum_data.get('total_compared', 0)} | Matched: {sum_data.get('matched', 0)} | Mismatches: {sum_data.get('mismatches', 0)}"
        ws["A2"].font = Font(name="Arial", size=10, italic=True)
        ws.merge_cells("A2:F2")

        # Headers
        headers = ["S.No", "Financial Section", "Financial Line Item", "CY FS (PY Comparative Col)", "Last Year Filed Financials", "Variance / Difference", "Status"]
        ws.append([]) # Blank row 3
        ws.append(headers) # Row 4

        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")

        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[4].height = 22

        # Populate rows
        items = report_result.get("reconciliation_items", [])
        for idx, item in enumerate(items, 1):
            status = item["status"]
            status_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") if status == "MATCHED" else PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
            status_font = Font(name="Arial", size=9, bold=True, color="375623" if status == "MATCHED" else "C65911")

            row_cells = [
                idx,
                item.get("section", ""),
                item["line_item"],
                item["cy_reported_py"],
                item["last_year_filed"],
                item["variance"],
                status
            ]
            ws.append(row_cells)
            curr_row = ws.max_row
            
            # Format numbers
            ws.cell(row=curr_row, column=4).number_format = '#,##0.00'
            ws.cell(row=curr_row, column=5).number_format = '#,##0.00'
            ws.cell(row=curr_row, column=6).number_format = '#,##0.00'
            
            # Format status cell
            stat_cell = ws.cell(row=curr_row, column=7)
            stat_cell.fill = status_fill
            stat_cell.font = status_font
            stat_cell.alignment = Alignment(horizontal="center")

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        wb.save(output_path)
        print(f"[+] Saved Comprehensive PY Variance Report to: {output_path}")
        return output_path

