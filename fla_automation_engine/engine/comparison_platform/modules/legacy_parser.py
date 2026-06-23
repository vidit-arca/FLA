import re
import pandas as pd
from typing import Dict, Any, List, Tuple


class LegacyFLAParser:
    """
    Parses the legacy RBI exported FLA format from either:
    - .xlsx (Legacy RBI export with Tables 1-9)
    - .md (OCR'd markdown with clean tables and key-value pairs)
    
    Returns a flat dictionary where keys are standardised field names
    and values are the extracted data.
    """

    # ── MD Parsing ────────────────────────────────────────────────

    def parse_md(self, md_text: str) -> Dict[str, Any]:
        """
        Parse a previous-year FLA markdown file.
        
        Strategy:
        1. Parse all markdown tables into row-dicts with column headers.
        2. Parse all key-value lines (e.g., "**Field** : Value").
        3. Build a flat lookup dict keyed by the item/field name.
        """
        data: Dict[str, Any] = {}

        # ── 1. Key-value lines (bold key : value) ──
        # Matches lines like: **Name of the Contact Person** : VILVA NATARAJAN
        kv_pattern = re.compile(
            r'\*\*(.+?)\*\*\s*:\s*(.+)', re.MULTILINE
        )
        for m in kv_pattern.finditer(md_text):
            key = m.group(1).replace('<br>', ' ').strip()
            val = m.group(2).replace('<br>', ' ').strip()
            data[key] = val

        # Also match non-bold numbered kv lines like:
        # 1.a No. of foreign direct investors ... : 0
        numbered_kv = re.compile(
            r'^\s*(\d+\.[\w.]*)\s+(.+?)\s*:\s*(.+)', re.MULTILINE
        )
        for m in numbered_kv.finditer(md_text):
            key = f"{m.group(1).strip()} {m.group(2).replace('<br>', ' ').strip()}"
            val = m.group(3).replace('<br>', ' ').strip()
            data[key] = val

        # ── 2. Markdown tables ──
        tables = self._parse_md_tables(md_text)
        for table in tables:
            headers = table["headers"]
            rows = table["rows"]

            if not headers or not rows:
                continue

            # Identify which columns hold PY vs FY data
            # We look for headers containing "End March 2024" or "April - March 2024" (PY)
            # and "End March 2025" or "April - March 2025" (FY)
            py_col_indices = []
            fy_col_indices = []
            item_col_idx = 0  # Usually the first column

            for i, h in enumerate(headers):
                h_lower = h.lower().strip()
                if "item" in h_lower or "type" in h_lower:
                    item_col_idx = i
                if "2024" in h:
                    py_col_indices.append(i)
                elif "2025" in h:
                    fy_col_indices.append(i)

            # If headers didn't contain year info, check first few data rows
            # (some MD tables have a sub-header row like ['Item', 'End March 2024', ...])
            for row in rows[:3]:
                if not py_col_indices and not fy_col_indices:
                    for ci, cell in enumerate(row):
                        cell_s = cell.strip()
                        if "2024" in cell_s:
                            py_col_indices.append(ci)
                        elif "2025" in cell_s:
                            fy_col_indices.append(ci)
                        if "item" in cell_s.lower() or "type" in cell_s.lower():
                            item_col_idx = ci

            for row in rows:
                if len(row) <= item_col_idx:
                    continue
                item_name = row[item_col_idx].replace('<br>', ' ').strip()
                if not item_name:
                    continue
                # Skip sub-header rows
                item_lower = item_name.lower()
                if item_lower in ["item", "type of capital", "portfolio investments", ""]:
                    continue

                # The FY of previous year = PY of current year
                for ci in fy_col_indices:
                    if ci < len(row) and row[ci].strip():
                        key = item_name
                        data[key] = row[ci].strip()

                # Also store with PY suffix for explicit lookups
                for ci in py_col_indices:
                    if ci < len(row) and row[ci].strip():
                        data[f"{item_name}__PY"] = row[ci].strip()

        return data

    def _parse_md_tables(self, md_text: str) -> List[Dict[str, Any]]:
        """
        Extract all markdown tables from the text.
        Returns a list of dicts with 'headers' and 'rows'.
        """
        tables = []
        lines = md_text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # A table row starts with |
            if line.startswith('|') and '|' in line[1:]:
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith('|'):
                    table_lines.append(lines[i].strip())
                    i += 1

                if len(table_lines) >= 2:
                    # First line = headers, second line = separator (---|---), rest = data
                    headers = [c.strip() for c in table_lines[0].split('|')[1:-1]]

                    data_rows = []
                    for tl in table_lines[2:]:  # Skip header + separator
                        cells = [c.strip() for c in tl.split('|')[1:-1]]
                        data_rows.append(cells)

                    tables.append({"headers": headers, "rows": data_rows})
            else:
                i += 1

        return tables

    # ── Excel Parsing (Legacy RBI .xlsx) ──────────────────────────

    def parse_previous_fla(self, source_dfs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses the legacy RBI exported FLA format (.xlsx) which has data
        stored in unstructured text blocks across Table 1 through Table 9.
        """
        full_text_block = ""
        for sheet_name, df in source_dfs.items():
            if not df.empty:
                full_text_block += df.to_string() + "\n"

        return self.parse_from_text(full_text_block)

    def parse_from_text(self, full_text_block: str) -> Dict[str, Any]:
        """
        Regex-based extraction from a raw text dump (Excel .to_string() output).
        """
        extracted_data = {}

        patterns = {
            "1. Name of the Indian Company": r"1\.\s*Name of the Indian Company.*?:\s*(.*)",
            "2. PAN number*": r"2\.\s*PAN Number.*?:\s*(.*)",
            "3. CIN number*": r"3\.\s*CIN Number.*?:\s*(.*)",
            "Name of the Contact Person": r"Name of the Contact Person.*?:\s*(.*)",
            "Telephone No. (with extension)": r"Telephone no\..*?\n?\s{10,}(\d+)",
            "Mobile Number*": r"Mobile No.*?\n?\s{10,}(\d+)",
            "E-Mail ID (Head of the institution)": r"Email \(Head of institution\).*?:\s*(.*)",
            "E-Mail of Contact person*": r"Email of Contact Person.*?:\s*(.*)",
            "Designation*": r"Designation.*?:\s*(.*)",
            "Website (if any)": r"Website \(if any\).*?:\s*(.*)",
            "Account Closing date*": r"5\.\s*Account closing date.*?:\s*(.*)",
            "Whether your company is merged / amalgamated during the year*": r"7\.\s*Whether your company is merged.*?:\s*(.*)",
            "Whether the company is listed?*": r"8\.\s*Whether the Company is listed.*?:\s*(.*)",
            # Section III & IV
            "No. of foreign direct investors during the year (10% or more Equity participation)": r"1\.a\s*No\. of foreign direct investors.*?(\d+)",
            "Month and Year of receiving FDI first time (in your company)": r"1\.a\.1\s*Month and Year of receiving FDI first time.*?:\s*(.*)",
            "Number of countries (with less than 10% Equity holding) from each during the year": r"2\.a\s*Number of countries \(with less than 10% Equity holding\).*?(\d+)",
            "No. of Direct Investment Enterprises (DIE) Abroad as on end-March 2021": r"1\.a\s*No\. of Direct Investment Enterprises \(DIE\) Abroad.*?(\d+)",
            "Month and Year of ODI made first time (by your company)": r"1\.a\.\s*Month and Year.*?ODI made first time.*?:\s*(.*)",
            "Total Equity of DIE (Paid Up Capital of DIE)": r"Total Equity of DIE \(Paid Up Capital of DIE\).*?(\d+)",
            "Equity of DIE held by you (at face value)": r"Equity of DIE held by you \(at face value\).*?(\d+)",
            "Liabilities to Direct Investment Enterprise": r"1\.1\s*Liabilities to Direct Investment Enterprise.*?(\d+)",
            "No. of Countries where your company holds less than 10 % equity shares in each under the ODI Scheme": r"2\.a\s*No\. of Countries where your company holds less than 10 % equity shares.*?(\d+)",
        }

        for standardized_key, pattern in patterns.items():
            match = re.search(pattern, full_text_block, re.IGNORECASE | re.MULTILINE)
            if match:
                extracted_data[standardized_key] = match.group(1).strip()

        return extracted_data
