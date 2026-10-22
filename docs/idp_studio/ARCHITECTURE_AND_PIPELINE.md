# IDP Studio: Generic Agentic Form Pipeline Architecture

## 1. Executive Overview

The IDP Studio Form Engine automates the ingestion, extraction, semantic mapping, validation, and filling of Ministry of Corporate Affairs (MCA) statutory forms (54+ forms including GNL-2, MGT-14, PAS-6, ADT-1, INC-20A, LLP-8, LLP-11).

The architecture is built on a **zero-hallucination, configuration-driven multi-agent framework** where:
1. **Form Definitions & Schemas** are extracted with **100% deterministic PDF geometry and statutory grammars** directly from MCA Instruction Kit PDFs without generative LLM guesswork.
2. **Execution & Cognitive Tasks** are distributed across specialized, right-sized local models and deterministic extractors to maintain sub-3.5s latency, prevent Ollama queue stalls, and enforce strict legal fidelity.

---

## 2. Multi-Agent & Heterogeneous Model Allocation

Rather than routing all tasks through a monolithic general-purpose model, the engine assigns specialized components to discrete stages:

```mermaid
graph TD
    subgraph Intake ["1. Document Layout & Intake"]
        PDF[Instruction Kit PDF / Dossier PDFs] --> DOC_AGENT[DocLayoutAgent: Triton marker_model + pdfplumber]
        DOC_AGENT --> MD[Physical Canvas Geometry & Structured Text]
    end

    subgraph Compiler ["2. Deterministic Schema Compilation"]
        MD --> COMPILER[SchemaCompilerAgent: Pure Python Geometry & AST]
        COMPILER -->|AST Fallback for Custom Tables| CODER[qwen2.5-coder:7b]
        COMPILER --> REGISTRY[(Universal Form Registry & SQLite)]
    end

    subgraph Triage ["3. Document Classification"]
        MD --> TRIAGE_AGENT[DocTriageAgent: qwen3.5:4b]
        TRIAGE_AGENT -->|Sub-150ms classification| DOC_TYPE[Document Type Tag]
    end

    subgraph Extraction ["4. 3-Tier Statutory Extraction"]
        DOC_TYPE --> MAP_AGENT[StatutoryMappingAgent]
        REGISTRY --> MAP_AGENT
        MAP_AGENT -->|Tier 1: < 5ms| T1[Deterministic Regex & Universal Statutory Grammars]
        MAP_AGENT -->|Tier 2: < 10ms| T2[Learned DOM Rules & Schema Aliases]
        MAP_AGENT -->|Tier 3: Scoped| T3[qwen2.5:14b (Only for Unmapped Options)]
    end

    subgraph Validation ["5. Validation & Pruning"]
        T1 --> VAL_AGENT[FormValidationAgent: Pure Python]
        T2 --> VAL_AGENT
        T3 --> VAL_AGENT
        VAL_AGENT -->|Sub-millisecond| PAYLOAD[Validated Form Execution Payload]
    end
```

### Component Matrix

| Agent / Component | Underlying Engine | Role & Responsibility | Latency SLA |
|---|---|---|---|
| **DocLayoutAgent** | Triton `marker_model` (`:8000`) + `pdfplumber` | Canvas layout, bounding box coordinates, line deduplication, Part III scanline slicing. | ~300ms |
| **DocTriageAgent** | `qwen3.5:4b` (`:11434`) | Rapid document categorization (board resolutions, consents, notices). | < 150ms |
| **SchemaCompilerAgent** | Deterministic 6-Stage Procedural Engine + `qwen2.5-coder:7b` | Extracts fields, canonical numbers, options, table schemas, and DAG conditions verbatim from Instruction Kits. | ~1.2s (one-time) |
| **StatutoryMappingAgent** | `UniversalStatutoryExtractor` + `idp_dom_extraction_rules` + `qwen2.5:14b` | Resolves statutory identifiers (CIN, PAN, DIN, SRN, Dates) and dropdown options against source evidence. | Avg < 250ms |
| **FormValidationAgent** | Pure Python Rule & DAG Engine | Enforces `DD/MM/YYYY` date grammar, deactivates dormant branches, checks required fields. | < 10ms |

---

## 3. The 6-Stage Deterministic Instruction Kit Compilation Engine

Form schemas are **never generated out of thin air by an LLM**. The 6-stage compiler in `automation_engine/modules/idp_studio/forms/stages/` extracts ground-truth statutory definitions:

1. **Stage 1 — PDF Understanding (`stage1_pdf_layout.py`):**
   - Uses `pdfplumber` to inspect raw character stream and `(x, y)` canvas coordinates.
   - Dynamically locates **Part III: Field-wise Instructions**.
   - Slices scanlines into the 3 statutory columns:
     - Column 1 (`x < col1_max`): Serial Number / Field Number (`1`, `2(b)`, `3(a)`).
     - Column 2 (`col1_max ≤ x < col2_max`): Field Name / Label (`Corporate Identity Number`).
     - Column 3 (`x ≥ col2_max`): Statutory Instructions and guidance.

2. **Stage 2 — Structure Identification (`stage2_structure.py`):**
   - Applies statutory regex `FIELD_NO_PAT` to Column 1.
   - Detects continuation lines where labels or instructions wrap across multiple scanlines.
   - Preserves exact physical sequencing.

3. **Stage 3 — Semantic Rule Inference (`stage3_instruction_ai.py`):**
   - Evaluates text patterns to infer field types deterministically:
     - Date fields: Matches `(DD/MM/YYYY)` or `"date"`.
     - File attachments: Matches `"Attachment"`, `"Copy of"`, `"Upload"`.
     - Radio options: Matches `"whether"`, `"Yes/No"`, `"Associate/Fellow"`.
     - Dropdown choices: Harvests single-quoted option strings (`‘...’`).
   - **Self-Synthesizing Parent Engine:** When MCA omits a self-explanatory parent field from the table (e.g., GNL-2 Field 2(a)), the engine scans child trigger instructions (`"is selected in field number 2(a) i.e. '...'"`), restores the parent field, auto-harvests all choices, and links dependent fields.
   - **Dynamic Table Coder:** If a table schema does not match existing templates, `qwen2.5-coder:7b` parses the instruction text into structured column definitions.

4. **Stage 4 — DAG Engine (`stage4_dag_engine.py`):**
   - Parses conditional trigger clauses (`"in case X is selected in field number Y"`).
   - Generates DAG dependency nodes with operator conditions (`equals`, `in`, `contains`).

5. **Stage 5 — Schema Validator (`stage5_validator.py`):**
   - Verifies DAG connectivity, checks for dangling branches, and eliminates duplicate options.

6. **Stage 6 — Schema Generator (`stage6_generator.py`):**
   - Serializes the verified schema to production JSON stored in `FormRegistry` and SQLite `IdpTemplate`.

---

## 4. Universal Statutory Extractors

Located in [`automation_engine/modules/idp_studio/extractors/universal_statutory.py`](file:///Users/apple/Desktop/FLA/automation_engine/modules/idp_studio/extractors/universal_statutory.py):

- **CIN Extractor:** `\b([LU][0-9]{5}[A-Za-z]{2}[0-9]{4}[A-Za-z]{3}[0-9]{6})\b`
- **PAN Extractor:** Word-bounded `\b([A-Za-z]{5}[0-9]{4}[A-Za-z])\b` with explicit exclusion of `"company"`.
- **DIN Extractor:** Word-bounded 8-digit numeric matcher with DIN/DPIN prefixes.
- **Universal Date Normalizer:** Parses alphanumeric (`24th april 2025`, `April 24, 2025`), ordinal, ISO (`2025-04-24`), and DMY dates into standard statutory `DD/MM/YYYY`.
- **SRN Extractor:** Service request numbers (`[A-Za-z][0-9]{8}`).
- **Canonical Option Matcher:** 3-tier matcher (exact string &rarr; containment &rarr; token overlap) matching extracted document values to schema options.

---

## 5. Directory Structure & Key Files

```text
automation_engine/modules/idp_studio/
├── core/
│   ├── db.py                     # SQLite engine & database initialization
│   ├── models.py                 # ORM models (IdpTemplate, SchemaAliasRule, DomExtractionRule)
│   └── llm_router.py             # Centralized LLM router with specialized model roles
├── extractors/
│   ├── classifier.py             # Document classification cascade
│   ├── spatial.py                # Scenario lexicon & spatial DOM rule lookup
│   └── universal_statutory.py    # Standardized statutory extractors & date normalizer
├── forms/
│   ├── stages/                   # 6-Stage Deterministic Instruction Kit Parser
│   │   ├── stage1_pdf_layout.py
│   │   ├── stage2_structure.py
│   │   ├── stage3_instruction_ai.py
│   │   ├── stage4_dag_engine.py
│   │   ├── stage5_validator.py
│   │   └── stage6_generator.py
│   ├── filler.py                 # Autonomous FormFiller engine with DAG pruning
│   ├── kit_parser.py             # Public wrapper for 6-stage pipeline
│   └── registry.py               # FormRegistry catalog
├── router.py                     # FastAPI REST API endpoints
└── idp_studio.db                 # Persistent SQLite store
```
