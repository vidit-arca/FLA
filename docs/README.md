# FLA & IDP Studio Documentation Index

Welcome to the centralized documentation repository for the **FLA (Foreign Liabilities and Assets) & IDP Studio (Intelligent Document Processing) Platform**.

This directory is organized into domain-specific modules for rapid navigation, maintenance, and developer onboarding.

---

## Directory Structure

```text
docs/
├── architecture/             # System-wide platform architecture, backend guides & UI specs
├── idp_studio/               # IDP Studio Form Engine, Multi-Agent pipeline, HLDs & DB specs
│   ├── specifications/       # Dynamic form rendering, spatial parsing, & multi-tenant specs
│   ├── hld/                  # High-Level Design documents, PDFs, and architecture diagrams
│   ├── dom_learner/          # DOM learner, intelligent xpath scoping & integration guides
│   └── database/             # Database isolation & schema migration guides
├── fla/                      # Foreign Liabilities & Assets (FLA Return) documentation
│   ├── section_logic/        # Detailed statutory logic for Sections 1.1, 1.2, 2, 3, & P&L
│   └── comparison_module/    # Year-over-year FLA reconciliation and comparison specs
├── aoc4/                     # Form AOC-4 Financial Statements filing module
│   ├── workflows/            # Extraction workflows and holding/subsidiary code flows
│   ├── rpt_and_loans/        # Related Party Transactions (RPT) & Section 186 loan guides
│   ├── common_errors/        # Common filing defects and validation flow diagrams
│   └── compliance_private/   # CARO 2020 applicability and private company compliance rules
└── mca_instruction_kits/     # Official MCA Part III Instruction Kit PDFs (GNL-2, MGT-14, etc.)
```

---

## Module Summaries & Quick Links

### 1. IDP Studio & Multi-Agent Form Engine (`docs/idp_studio/`)
- **[Architecture & Agent Pipeline](idp_studio/ARCHITECTURE_AND_PIPELINE.md):** Specification of the 6-stage deterministic parser, specialized multi-model allocation (`qwen3.5:4b`, `qwen2.5-coder:7b`, `qwen2.5:14b`), and zero-hallucination guarantees.
- **[Engineering Troubleshooting Log](idp_studio/ENGINEERING_LOG.md):** Chronological activity log tracking all bug fixes, root-cause analyses, regex collisions, and regression test results.
- **[High-Level Design (HLD)](idp_studio/hld/HLD_IDP_Studio_Multi_Tenant.md):** Comprehensive multi-tenant architecture and component specifications.
- **[Database Isolation & Schema Plan](idp_studio/database/IDP_Studio_Database_Isolation_and_Schema_Plan.md):** Database schema, migration guides, and data segregation rules.
- **[DOM Learner Integration](idp_studio/dom_learner/DOM_Integration_Guide.md):** Real-world alias learning, spatial coordinate mapping, and DOM extraction rules.

### 2. System Architecture (`docs/architecture/`)
- **[System Architecture](architecture/system_architecture.md):** Global platform topology, microservices, and Triton OCR inference servers.
- **[Backend Architecture Guide](architecture/backend_architecture_guide.md):** FastAPI services, database connection pooling, and endpoint contracts.
- **[Magic Pen Evolution](architecture/magic_pen_evolution.md):** Evolution of the interactive field resolver and smart autofill platform.

### 3. FLA Return Platform (`docs/fla/`)
- **[FLA Extraction Documentation](fla/FLA_extraction_documentation.md):** Core RBI compliance extraction engine for Foreign Direct Investment (FDI) and Overseas Direct Investment (ODI).
- **[Section Logic Guides](fla/section_logic/):**
  - [Section 1 Share Capital](fla/section_logic/section1_share_capital_logic.md)
  - [Section 2 Logic Documentation](fla/section_logic/section_2_logic_documentation.md)
  - [Section 3 Logic Diagram](fla/section_logic/section3_logic_diagram.md)
  - [Profit and Loss Logic](fla/section_logic/profit_and_loss_logic.md)
- **[Comparison Module](fla/comparison_module/Comparsion_Module.md):** Automated prior-year vs current-year variance analysis.

### 4. Form AOC-4 Module (`docs/aoc4/`)
- **[AOC-4 Compliance Architecture](aoc4/compliance_private/aoc4_compliance_architecture.md):** Balance sheet and P&L financial statement extraction.
- **[CARO 2020 Applicability Guide](aoc4/compliance_private/caro_applicability_guide.md):** Companies (Auditor's Report) Order applicability rules.
- **[RPT & Section 186 Loan Limits](aoc4/rpt_and_loans/section_186_limits_guide.md):** Statutory thresholds for loans, guarantees, and securities.

### 5. MCA Instruction Kits (`docs/mca_instruction_kits/`)
Contains all 14 official MCA Instruction Kit PDFs used as canonical ground truth by the parser:
- `Instruction_Kit_GNL-2.pdf`
- `Instruction Kit_ADT-1.pdf`
- `Instruction Kit_MGT-14.pdf`
- `Instruction Kit_PAS-6.pdf`
- `Instruction Kit_INC-20A.pdf`
- `Instruction Kit_INC-28.pdf`
- `Instruction Kit_LLP Form No. 8.pdf`
- `Instruction Kit_LLP Form No. 11_clean copy.pdf`
- `Instruction Kit_CHG-4.pdf`
- `Instruction Kit_MGT-7.pdf`
- `InstructionKit_GNL-1.pdf`
- `Instruction Kit_Form No DIR 12.pdf`
- `Instruction_Kit_BEN-2.pdf`
- `Instruction_Kit_MGT-6.pdf`
