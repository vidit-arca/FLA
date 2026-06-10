# FLA Return Automation Engine Architecture

This document outlines the current system architecture of the RBI FLA Return Automation Engine.

## High-Level Architecture Diagram

```mermaid
graph TD
    %% Define external inputs
    subgraph Input Layer
        A1[Raw PDFs<br/>Board Report, Financials]
        A2[Raw Excels<br/>Shareholders, ODI]
        A3[User-Provided MDs<br/>OCR Fallback]
        Skeletal[Blank Skeletal Excel<br/>Template]
        Config[rules_config.json<br/>Keywords & Formulas]
    end

    %% Define Engine Components
    subgraph Core Automation Engine
        B[Ingestion Layer<br/>ingestion.py]
        
        subgraph OCR Processing
            C1[OCR Pipeline<br/>ocr_pipeline.py]
            C2((Marker VLM<br/>Heavy GPU OCR))
        end
        
        subgraph Extraction Layer
            D1[Document Parser<br/>parser.py]
            D2[Excel Extractor<br/>excel_extractor.py]
        end
        
        E[Rule Engine<br/>rule_engine.py]
        F[Excel Writer<br/>excel_writer.py]
        G[Validator<br/>validator.py]
    end

    %% Define Outputs
    subgraph Output Layer
        H1[Populated FLA Excel<br/>Final Output]
        H2[Validation Reports<br/>TXT / JSON]
        H3[Audit Reports<br/>TXT / JSON]
    end

    %% Map Data Flow
    A1 --> B
    A2 --> B
    A3 --> B
    
    B -->|Classifies & Routes Docs| C1
    C1 -.->|If Scanned PDF| C2
    C2 -.->|Generates Markdown| C1
    
    C1 -->|Passes Text/MD| D1
    B -->|Passes Target Excels| D2
    
    D1 -->|Extracts Meta & Financials| E
    D2 -->|Extracts FDI / ODI| E
    Config -->|Applies Business Logic| E
    
    E -->|Computed Cell Values| F
    Skeletal -->|Base Template| F
    
    F -->|Writes to Coordinates| H1
    E -->|Passes Computed Data| G
    G -->|Checks RBI Math| H2
    E -->|Missing/Found Fields| H3
```

## Component Breakdown

### 1. Input Layer
- **Raw Documents:** The client provides arbitrarily named files (PDFs for reports, Excels for shareholder data).
- **Configuration (`rules_config.json`):** The central brain of the system. It contains keyword aliases for financial metrics, mathematical formulas for derived fields (like Net Worth), and exact Excel coordinate mappings (e.g., `D15`).
- **Skeletal Excel:** A blank, perfectly formatted `.xlsx` file mimicking the RBI portal structure.

### 2. Core Automation Engine
- **Ingestion (`ingestion.py`):** Opens files and scans their contents to dynamically classify them (e.g., identifying a file as `shareholders_fdi` because it has "Name" and "Shares" columns).
- **OCR Pipeline (`ocr_pipeline.py`):** Acts as a bridge between the Python engine and the heavy Machine Learning OCR tool (**Marker**). It handles checking for cached markdown files or triggering the VLM to convert scanned tables into machine-readable text.
- **Extraction (`parser.py` & `excel_extractor.py`):** Uses Regex and fuzzy string matching to pull exact numerical and text values from the raw documents based on the `rules_config.json`.
- **Rule Engine (`rule_engine.py`):** Receives the raw extracted values, scales them (e.g., Absolute $\rightarrow$ Lakhs), evaluates mathematical formulas, and pre-formats them for Excel injection.
- **Excel Writer (`excel_writer.py`):** Uses `openpyxl` to inject the processed dictionary of values directly into the target coordinates of the Skeletal Excel.
- **Validator (`validator.py`):** Re-calculates critical portal logic (like ensuring Total Equity matches the breakdown) and flags discrepancies.

### 3. Output Layer
- **Populated Excel:** The final deliverable ready for RBI upload.
- **Audit/Validation Reports:** Logs detailing exactly what parameters were found, which ones fell back to defaults, and whether the final math passes RBI logic checks.
