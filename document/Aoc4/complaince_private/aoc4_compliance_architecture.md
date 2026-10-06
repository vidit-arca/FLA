# AOC4 Compliance Excel Architecture

This diagram visualizes how data flows through the `"compliance for Private "` Excel sheet, from raw extraction to final compliance reporting.

```mermaid
flowchart TD
    %% Data Sources
    subgraph Sources ["1. Company Financial Documents"]
        BS["Balance Sheet"]
        PL["P and L Statement"]
        Notes["Notes to Accounts / Board Report"]
    end

    %% 1. Input Engine
    subgraph Phase1 ["2. Input Engine (Rows 7 - 32)"]
        direction TB
        Mapping["Keywords and Mappings Cols A-C"]
        ExtractedCY["Extracted Current Year Values Cols D-E"]
        ExtractedPY["Extracted Previous Year Values Cols F-G"]
        
        Mapping -.-> ExtractedCY
        Mapping -.-> ExtractedPY
    end

    %% 2. Logic & Calculation Block
    subgraph Phase2 ["3. Logic and Calculation Block (Cols K, L, M)"]
        direction TB
        SubConditions["Sub-Condition Checks (e.g., Turnover > 200)"]
        Calculations["Formula Evaluations"]
        LogicResult["Final Logic Result (Applicable / NA)"]
        
        SubConditions --> Calculations
        Calculations --> LogicResult
    end

    %% 3. Output Checklist
    subgraph Phase3 ["4. Output Checklist (Rows 33 - 59)"]
        direction TB
        ComplianceReq["Compliance Requirements Col C"]
        ApplicabilityCY["Applicability - Current Year Col D"]
        ApplicabilityPY["Applicability - Previous Year Col F"]
        ManualEntry["Manual Filing Info Cols E and G"]
        
        ComplianceReq --- ApplicabilityCY
        ComplianceReq --- ApplicabilityPY
        ApplicabilityCY -.- ManualEntry
    end

    %% Connections across phases
    BS --> Phase1
    PL --> Phase1
    Notes --> Phase1

    ExtractedCY --> SubConditions
    ExtractedPY --> SubConditions

    LogicResult --> ApplicabilityCY
    LogicResult --> ApplicabilityPY
```

### Key Takeaways:
- **Data Flow:** The system relies on a strictly linear flow. Raw data is extracted based on keywords (Phase 1), fed horizontally across the sheet to the logic formulas on the right (Phase 2), and then the final Boolean answers are pulled back to the left into the master checklist (Phase 3).
- **Modularity:** By keeping the logic (Phase 2) separate from the display checklist (Phase 3), the spreadsheet avoids overly complex nested `IF` statements in a single cell, making it easier to read and audit manually.
