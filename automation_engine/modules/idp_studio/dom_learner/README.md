# 🌳 Intelligent DOM Learning Engine — PoC

> Convert OCR Markdown into a **Logical Document Tree (DOM)** for
> structure-based extraction instead of coordinate-based extraction.

---

## Overview

This module is a self-contained Proof of Concept (PoC) that demonstrates how OCR
documents can be parsed into a navigable document object model — similar to how
browsers build a DOM from HTML.

### Pipeline

```
OCR Markdown  →  Markdown Parser  →  Section Detector  →  Table Detector
    →  Relationship Builder  →  Logical Document Tree  →  Export (JSON + Tree)
```

### Why a DOM?

Instead of the traditional approach:

```
OCR → Regex → Extract
```

The DOM approach enables:

```
OCR Markdown → Markdown Parser → Logical Document Tree → Relationships → DOM Navigation
```

This allows a user to:
1. Draw a box around one value
2. Learn its **structural position** (section → table → row → column)
3. Automatically find that value in future documents — **no coordinates needed**

---

## Quick Start

```bash
# From the idp_studio directory:
cd automation_engine/modules/idp_studio

# Run the demo
python -m dom_learner.demo

# Or with custom paths:
python -m dom_learner.demo --input path/to/file.md --output path/to/output/
```

### Output Files

| File | Description |
|------|-------------|
| `logical_document_tree.json` | Full DOM tree with all nodes, hierarchy, and metadata |
| `relationships.json` | 8,000+ semantic relationships (16 types) |
| `tree.txt` | ASCII tree visualization for debugging |
| `tree.html` | Interactive collapsible HTML tree (open in browser) |

---

## Architecture

```
dom_learner/
│
├── models/
│   └── node.py              # All DOM node types (DOMNode base + 9 concrete types)
│
├── parser/
│   ├── markdown_parser.py   # Line-by-line tokenizer (HEADING, TABLE, PARAGRAPH, etc.)
│   ├── section_parser.py    # Groups tokens into sections by heading level
│   └── table_parser.py      # Parses markdown table blocks into structured data
│
├── engine/
│   ├── dom_builder.py       # Orchestrates parsers → builds DOM tree
│   ├── relationship_builder.py  # Generates 16 types of semantic relationships
│   └── dom_query.py         # Navigable query API (the key differentiator)
│
├── exporters/
│   ├── json_exporter.py     # DOM + relationships → JSON files
│   └── tree_exporter.py     # ASCII tree + interactive HTML tree
│
├── demo.py                  # CLI entry point
├── __init__.py
├── __main__.py
│
├── output/                  # Generated at runtime
│   ├── logical_document_tree.json
│   ├── relationships.json
│   ├── tree.txt
│   └── tree.html
│
└── Docs/                    # Input files (pre-existing)
    ├── ocr_output/
    │   └── AR_Financials_MSME_Disclosures.md
    └── Intelligent_DOM_Extraction_Architecture.png
```

---

## Module Details

### `models/node.py` — Node Definitions

All DOM nodes inherit from `DOMNode`:

| Node Type | Purpose |
|-----------|---------|
| `DocumentNode` | Root of the tree |
| `SectionNode` | Document section (introduced by a heading) |
| `HeadingNode` | Heading text (H1–H6) |
| `TableNode` | Markdown table container |
| `HeaderNode` | Table header row |
| `RowNode` | Table body row |
| `CellNode` | Individual cell |
| `ParagraphNode` | Free-form text |
| `NoteNode` | Note reference (e.g., "Note 4") |

Every node contains:

```python
id          # e.g., "section_3", "row_12", "cell_45"
node_type   # NodeType enum
text        # Raw text content
parent      # Reference to parent DOMNode
children    # Ordered list of child DOMNodes
metadata    # Extensible dict with:
            #   bbox       → [x0, y0, x1, y1] or None (future OCR coordinates)
            #   page       → 0-indexed page number or None
            #   confidence → OCR confidence 0.0–1.0 or None
            #   + type-specific fields (heading_level, column_index, etc.)
```

**Built-in navigation:**

```python
node.parent              # parent node
node.children            # child nodes
node.next_sibling        # next sibling
node.previous_sibling    # previous sibling
node.siblings            # all siblings (excluding self)
node.section             # nearest SectionNode ancestor
node.table               # nearest TableNode ancestor
node.depth               # distance from root
node.walk()              # pre-order depth-first traversal
```

### `parser/` — Generic Parsers

- **`MarkdownParser`**: Reads `.md` line-by-line, classifies as HEADING / TABLE / PARAGRAPH / IMAGE / BLANK, merges consecutive table lines into blocks.
- **`SectionParser`**: Groups parsed blocks into sections based on heading boundaries.
- **`TableParser`**: Splits markdown table blocks into headers + rows, cleans HTML artifacts, normalizes column counts.

All parsers are **fully generic** — no domain-specific hardcoding.

### `engine/dom_builder.py` — Tree Construction

Orchestrates the parsers and builds the tree using a **stack-based nesting** algorithm for heading levels:

```
H3 "Balance Sheet" → pushed to stack
  H3 "Notes" → pops "Balance Sheet", pushes "Notes" (same level = sibling)
    H3 "2.1 Basis" → nested under if heading level is deeper
```

Note references are detected via:
1. Dedicated "Note" column in tables
2. Inline regex matching `Note X` patterns

### `engine/relationship_builder.py` — Semantic Relationships

Generates **16 relationship types** across 3 categories:

| Category | Types |
|----------|-------|
| **Hierarchical** | `HAS_SECTION`, `HAS_TABLE`, `HAS_ROW`, `HAS_CELL`, `BELONGS_TO` |
| **Positional** | `NEXT_ROW`, `PREVIOUS_ROW`, `NEXT_COLUMN`, `PREVIOUS_COLUMN` |
| **Semantic** | `REFERS_TO_NOTE`, `ROW_HAS_LABEL`, `CELL_IN_COLUMN`, `CELL_IN_ROW`, `TABLE_IN_SECTION`, `SECTION_IN_DOCUMENT`, `HEADER_FOR_COLUMN` |

### `engine/dom_query.py` — DOM Query API ⭐

The key differentiator — makes the DOM **navigable**, not just a data export.

```python
from dom_learner.engine import DOMBuilder, DOMQuery

dom = DOMBuilder().build(Path("document.md"))
q   = DOMQuery(dom)

# Find by text
q.find_by_text("Trade Payables")

# Find by structure
q.find_section("Balance Sheet")
q.find_table_in_section("Balance Sheet")
q.find_row("Trade Payables")
q.find_cell(row_text="Trade Payables", column_header="March 31, 2025")

# Navigate
cell = q.find_cell(row_text="Partners' contribution", column_header="March 31, 2025")
cell.parent              # → RowNode
cell.next_sibling        # → next cell in row
cell.previous_sibling    # → previous cell
cell.section             # → parent SectionNode
cell.table               # → parent TableNode

# Row navigation
q.get_previous_row(row)
q.get_next_row(row)
q.get_siblings(node)

# Note lookup
q.find_note("4")
q.find_rows_referring_to_note("4")

# Structural path (foundation for Rule Learning Engine)
q.get_structural_path(cell)
# → [{"type": "document"}, {"type": "section", "text": "Balance Sheet"},
#    {"type": "table"}, {"type": "row", "label": "Trade Payables"},
#    {"type": "cell", "column": "March 31, 2025"}]
```

---

## DOM Structure

```
Document
│
├── Section (H3): Balance Sheet
│   ├── Heading (H3): Balance Sheet
│   ├── Table (5 cols)
│   │   ├── Header
│   │   │   ├── Cell: Particulars
│   │   │   ├── Cell: Note
│   │   │   ├── Cell: As at (March 31, 2025)
│   │   │   └── Cell: As at (March 31, 2024)
│   │   ├── Row 0 — EQUITY AND LIABILITIES
│   │   │   ├── Cell [Particulars]: EQUITY AND LIABILITIES
│   │   │   └── ...
│   │   ├── Row 8 — Trade payables
│   │   │   ├── Cell: (a)
│   │   │   ├── Cell [Particulars]: Trade payables
│   │   │   ├── Cell [Note]: 4
│   │   │   ├── Cell [As at]: 12,10,692
│   │   │   ├── Cell [As at]: 84,740
│   │   │   └── Note: 4  ← auto-detected note reference
│   │   └── ...
│   └── Paragraph: The accompanying notes...
│
├── Section (H3): Profit and Loss
│   └── Table (5 cols)
│       └── ...
│
└── Section (H3): Notes to Financial Statements
    ├── Section (H3): Note 1 — General Information
    ├── Section (H3): Note 2 — Accounting Policies
    │   ├── Section (H3): 2.1 Basis of Preparation
    │   ├── Section (H3): 2.2 Use of Estimates
    │   └── ...
    └── ...
```

---

## Sample Output

### Node Counts (from demo)

| Type | Count |
|------|-------|
| document | 1 |
| section | 27 |
| heading | 27 |
| table | 10 |
| header | 10 |
| row | 211 |
| cell | 1,322 |
| paragraph | 106 |
| note | 23 |
| **Total** | **1,737** |

### Relationship Counts

| Type | Count |
|------|-------|
| BELONGS_TO | 1,736 |
| CELL_IN_ROW | 1,322 |
| HAS_CELL | 1,322 |
| NEXT_COLUMN | 1,101 |
| PREVIOUS_COLUMN | 1,101 |
| CELL_IN_COLUMN | 805 |
| HAS_ROW | 221 |
| NEXT_ROW | 211 |
| PREVIOUS_ROW | 211 |
| ROW_HAS_LABEL | 197 |
| HEADER_FOR_COLUMN | 38 |
| REFERS_TO_NOTE | 23 |
| HAS_SECTION | 22 |
| SECTION_IN_DOCUMENT | 22 |
| TABLE_IN_SECTION | 10 |
| HAS_TABLE | 10 |
| **Total** | **8,352** |

---

## Future Integration Points

This PoC builds Phase 1 of the architecture. Future modules (all inside `engine/`):

| Module | Purpose | Depends On |
|--------|---------|------------|
| **Selection Resolver** | Maps a user's bounding-box selection to a DOM node | `DOMQuery.get_structural_path()` |
| **Rule Learning Engine** | Generates reusable extraction rules from structural paths | `DOMQuery`, `RelationshipBuilder` |
| **DOM Navigation Engine** | Walks the DOM using learned rules on new documents | `DOMQuery`, `DOMBuilder` |
| **Rule Repository** | Stores and retrieves learned rules | JSON/DB storage |

---

## Dependencies

**None** — stdlib only:
- `dataclasses`, `pathlib`, `typing`, `logging`, `re`, `json`, `html`, `enum`, `itertools`, `argparse`, `time`

---

## Constraints Respected

✅ All code inside `dom_learner/` — zero modifications to any external file  
✅ No pip installs required  
✅ Generic parser — no hardcoded domain terms  
✅ Bounding box / page / confidence metadata pre-wired for future OCR integration  
✅ DOM is navigable, not just a data export  
