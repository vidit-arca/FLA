# Compliance Sheet Architecture Flow

Here is the end-to-end data flow detailing how raw financial documents are parsed and ultimately populated into the Private Compliance sheet in Excel.

```mermaid
flowchart TD
    %% Input Sources
    subgraph Input [1. Input Documents]
        A1[Financial Excel]
        A2[Markdown and PDFs]
    end

    %% Data Extraction
    subgraph Extraction [2. Data Extraction Layer]
        B1[AOC4 Excel Extractor]
        B2[AOC4 Text Parser]
        
        A1 --> B1
        A2 --> B2
        B1 --> |Raw Numeric Data| C[Combined Financial Data Dictionary]
        B2 --> |Fallback Text Values| C
    end

    %% Logic Evaluation
    subgraph Evaluation [3. Compliance Logic Evaluation]
        C --> D[rule_engine.py]
        
        D --> |Sends Extracted Data| E[compliance_engine.py]
        
        E --> |Rule 1: Small Company| E
        E --> |Rule 2: CARO| E
        E --> |Rules 3-25...| E
        
        E --> |Returns Compliance Flags| D
    end

    %% Mapping & Writing
    subgraph Output [4. Mapping and Excel Generation]
        D --> |Maps Rule IDs to Rows| F[Target Cells Dictionary]
        
        F --> |Sends Mapped Cells| G[excel_writer.py]
        
        H[Skeletal Template Excel] --> G
        
        G --> |Writes to Col D and E| I[Final Populated Excel File]
    end

    %% Styling
    classDef input fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef extract fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px;
    classDef eval fill:#fff3e0,stroke:#f57c00,stroke-width:2px;
    classDef output fill:#e8f5e9,stroke:#388e3c,stroke-width:2px;
    classDef file fill:#ffebee,stroke:#d32f2f,stroke-width:2px;

    class A1,A2 input;
    class B1,B2,C extract;
    class D,E eval;
    class F,G output;
    class H,I file;
```

### Flow Breakdown:
1. **Extraction:** The system reads the provided source documents. `excel_extractor.py` scans for standard tables, and `parser.py` uses Regex to scrape numbers from text paragraphs (if tabular data is missing).
2. **Evaluation:** `rule_engine.py` passes all extracted values (Turnover, Borrowings, etc.) to the `PrivateComplianceEngine`. The engine runs 25 math formulas and generates a status (`Applicable` / `Not Applicable`) and a detailed mathematical `Rationale` for each rule.
3. **Mapping:** The `rule_engine.py` maps the returned statuses to their exact template rows (e.g., Row 36 for CARO). Applicability maps to Column D, and the mathematical Rationale maps to Column E.
4. **Writing:** Finally, `excel_writer.py` loads the blank skeletal Excel file, injects the values into the target cells without breaking existing merged cells, and saves the populated Excel file.
