# Statutory Dynamic Table Grid Rendering Specification

## 1. Overview & Purpose

In statutory filings (e.g., **MCA Form No. INC-20A**, **LLP Form No. 11**, **Form No. DIR-12**), repeating schedules and shareholder/partner tables cannot be rendered as simple 2-column key-value text pairs.

This engine component in [`router.py`](file:///Users/apple/Desktop/FLA/automation_engine/modules/idp_studio/router.py#L825-L918) detects fields with `type: "table"` and transforms them into multi-column statutory PDF grid tables with column headers, serial numbers, zebra striping, and automatic pagination.

---

## 2. Code Breakdown: Data Ingestion & Row Normalization

```python
# Check if value is list of rows or JSON string
table_rows = []
if isinstance(val_str, list):
    table_rows = val_str
elif isinstance(val_str, str) and (val_str.startswith("[") or val_str.startswith("{")):
    try:
        parsed_rows = python_json.loads(val_str)
        table_rows = parsed_rows if isinstance(parsed_rows, list) else [parsed_rows]
    except Exception:
        table_rows = []
elif isinstance(val_str, dict):
    table_rows = [val_str]

# If no rows or empty rows, render at least 2 default statutory rows so grid is clearly visible
if not table_rows:
    table_rows = [{c.get("key", ""): "" for c in table_cols}, {c.get("key", ""): "" for c in table_cols}]

header_h = 22.0
col_header_h = 20.0
row_h = 20.0
total_table_min_h = header_h + col_header_h + row_h
```

---

## 3. Key Architectural Mechanisms

### A. Polymorphic Input Parsing

Field values arriving from OCR extraction, LLM parsing, or database stores can vary in format:

1. **Native Python `list`:** Pre-parsed rows (e.g. `[{"shareholder_name": "ABC", ...}]`).
2. **JSON String:** Stringified payload from database JSON columns or API requests (e.g. `'[{"key": "val"}]'`).
3. **Single `dict`:** Single-row objects, automatically wrapped into a 1-item list.
4. **Invalid / Null:** Resiliently falls back to an empty list without crashing.

### B. Statutory Blank-Row Baseline (Lines 844–846)

* **Problem:** In official MCA forms, an unpopulated table must still display its statutory grid structure with blank lines for manual inspection, rather than disappearing completely.
* **Solution:** If `table_rows` is empty or unmapped, the engine automatically injects **two blank rows** keyed by the schema column definitions (`{col_key: ""}`).

### C. Dimension Matrix & Geometric Layout (Lines 848–851)

| Component                      | Height      | Geometry / Coordinates                            | Styling                                                |
| :----------------------------- | :---------- | :------------------------------------------------ | :----------------------------------------------------- |
| **Table Title Banner**   | `22.0 pt` | `x: 35` to `560` (Width: `525 pt`)          | Fill:`#E0E8F5`, Border: `0.8 pt`                   |
| **Column Headers**       | `20.0 pt` | S.No Col:`26 pt`, Data Cols: `(525 - 26) / N` | Fill:`#EDF2FA`, Font: `6.8 pt Helvetica Bold`      |
| **Data Rows**            | `20.0 pt` | S.No Col:`26 pt`, Data Cols: `(525 - 26) / N` | Alternating`#FAFCFF` / `#FFFFFF`, Font: `7.5 pt` |
| **Minimum Block Height** | `62.0 pt` | `header_h + col_header_h + row_h`               | Pre-flight boundary threshold for page breaks          |

---

## 4. Multi-Page Pagination & Auto-Header Continuation

* **Page Overflow Check:** If `y + total_table_min_h > 780 pt` (bottom A4 margin), the engine automatically closes the current page, stamps the page footer (`Page X • Official MCA Filing Return`), spawns a new page with the official outer border, and resets `y = 45 pt`.
* **Header Re-Stamping:** If a large table spans multiple pages, column headers are automatically re-drawn at the top of subsequent pages (`Lines 890–898`) so readers never lose column context.

---

## 5. Sample Rendered Example (Form No. INC-20A Field 4 Table)

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. Particulars of payment received towards subscription to Memorandum   [STATUTORY DYNAMIC GRID] │
├────┬────────────────────────┬──────────────────┬────────────────┬────────────────┬──────────────┤
│ #  │ 4(b). Shareholder Name │ 4(c). Bank Name  │ 4(d). A/c No.  │ 4(e). Date     │ 4(f). Amount │
├────┼────────────────────────┼──────────────────┼────────────────┼────────────────┼──────────────┤
│ 1  │ ABC Holdings Ltd       │ HDFC Bank Ltd    │ 50200012345678 │ 12/04/2026     │ 10,00,000    │
├────┼────────────────────────┼──────────────────┼────────────────┼────────────────┼──────────────┤
│ 2  │ John Doe               │ ICICI Bank Ltd   │ 001201567890   │ 14/04/2026     │ 5,00,000     │
└────┴────────────────────────┴──────────────────┴────────────────┴────────────────┴──────────────┘
```
