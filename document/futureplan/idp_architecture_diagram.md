# Intelligent Document Processing (IDP) Workflow

Here is a comprehensive breakdown of the Human-in-the-Loop system. It is highly recommended to use **all three diagrams** when explaining this system, as they cover both the user experience and the evolution of the technical architecture:

* **Diagram 1 (Sequence Diagram):** Explains the **User Experience** and chronological timeline.
* **Diagram 2 (Initial Setup Architecture):** Explains the **Traditional Flow**, where a client's document is mapped manually the very first time to train the database.
* **Diagram 3 (Automated Architecture):** Explains the **Final Automated Flow**, where the dual-panel UI fetches the trained rules first and auto-populates the form instantly.

---

### 1. Step-by-Step Interaction Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as Dual-Panel UI
    participant Backend as Extraction Engine
    participant DB as Rules Database

    %% Phase 1: Upload & Template Selection
    rect rgb(240, 248, 255)
    Note right of User: Phase 1: Dual-Panel UI (Selection & Upload)
    User->>Frontend: Selects target Form Template from Right Panel
    User->>Frontend: Uploads Financial PDF into Left Panel
    Frontend->>Backend: Sends PDF + Selected Template ID for processing
    end

    %% Phase 2: Zero-Touch Automation
    rect rgb(240, 255, 240)
    Note right of User: Phase 2: Automated Extraction (Zero-Touch)
    Backend->>DB: Fetches saved Mapping Rules for selected Template
    Backend->>Backend: Perform OCR & Parse Document (Coordinates)
    Backend->>Backend: Locates Anchors and applies spatial extraction rules
    Backend-->>Frontend: Returns Auto-Extracted Data mapped to the Form
    Frontend->>Frontend: Instantly auto-fills Form Template (Right Panel)
    end

    %% Phase 3: Interactive Mapping (Training/Fallback)
    rect rgb(255, 245, 238)
    Note right of User: Phase 3: Interactive Training (If fields are missing or new layout)
    User->>Frontend: Reviews auto-filled form
    Frontend->>Frontend: Overlays invisible clickable zones over the PDF
    User->>Frontend: Clicks PDF text to manually map a missing field
    Frontend->>Backend: Sends new spatial relationship (e.g. Value 50px Right of Anchor)
    Backend->>DB: Updates and stores new Mapping Rule for future use
    end
```

<br>

### 2. Initial Setup Flow (First-Time Client Mapping)

This diagram shows the initial state of the system when a new client's document is uploaded for the very first time. The data flows sequentially through the manual mapping UI before being saved to the database.

```mermaid
flowchart LR
    %% Styling definitions
    classDef userAction fill:#f9d0c4,stroke:#e06666,stroke-width:2px,color:#333;
    classDef systemProc fill:#cfe2f3,stroke:#6fa8dc,stroke-width:2px,color:#333;
    classDef dataStore fill:#d9ead3,stroke:#93c47d,stroke-width:2px,color:#333;

    %% Nodes
    UserUpload["User Uploads Document"]:::userAction
  
    subgraph Extraction["1. Extraction Engine"]
        direction TB
        OCR["OCR / PDF Parsing"]:::systemProc
        BBoxes["Extract Text & Bounding Boxes"]:::systemProc
    end
  
    subgraph UI["2. Interactive Mapping (Frontend)"]
        direction TB
        Canvas["Render PDF Canvas"]:::systemProc
        MapClick["User Maps Anchor to Value"]:::userAction
        CalcOffset["Calculate Spatial Offset"]:::systemProc
    end
  
    subgraph Auto["3. Automation Engine (Backend)"]
        direction TB
        RulesDB[("Client Template DB")]:::dataStore
        TemplateMatch["Template Matching Engine"]:::systemProc
        AutoFill["Auto-Populated Form Output"]:::systemProc
    end

    %% Connections
    UserUpload --> OCR
    OCR --> BBoxes
    BBoxes --> Canvas
    Canvas --> MapClick
    MapClick --> CalcOffset
    CalcOffset --> RulesDB
  
    UserUpload -. "Next Year's Upload" .-> TemplateMatch
    RulesDB --> TemplateMatch
    TemplateMatch --> AutoFill
```

<br>

### 3. Final Automated Flow (Dual-Panel UI)

This diagram shows the final, optimized state of the system. By selecting the form template upfront, the system retrieves the rules from the database *first*, automating the extraction process entirely. The manual mapping is only used as a fallback if data is missing.

```mermaid
flowchart LR
    %% Styling definitions
    classDef userAction fill:#f9d0c4,stroke:#e06666,stroke-width:2px,color:#333;
    classDef systemProc fill:#cfe2f3,stroke:#6fa8dc,stroke-width:2px,color:#333;
    classDef dataStore fill:#d9ead3,stroke:#93c47d,stroke-width:2px,color:#333;

    %% Nodes
    subgraph UI["1. Interactive Dual-Panel Frontend"]
        direction TB
        SelectTemplate["Right Panel: Select Form Template"]:::userAction
        UploadDoc["Left Panel: Upload Document"]:::userAction
        Canvas["Interactive PDF Canvas"]:::systemProc
        ManualMap["User Clicks to Map Fields"]:::userAction
    end
  
    subgraph Auto["2. Automation Engine (Backend)"]
        direction TB
        RulesDB[("Client Template DB")]:::dataStore
        TemplateMatch["Fetch & Apply Rules"]:::systemProc
        OCR["OCR / Bounding Box Extractor"]:::systemProc
        CalcOffset["Calculate Spatial Offset"]:::systemProc
    end
  
    subgraph Output["3. Final Output"]
        AutoFill["Auto-Populated Form Displayed"]:::systemProc
    end

    %% Connections
    SelectTemplate --> UploadDoc
    UploadDoc --> TemplateMatch
    TemplateMatch --> OCR
    OCR --> AutoFill
  
    %% Training loop connection
    AutoFill -. "If missing data" .-> Canvas
    Canvas --> ManualMap
    ManualMap --> CalcOffset
    CalcOffset --> RulesDB
    RulesDB -. "Provides Rules to" .-> TemplateMatch
```
