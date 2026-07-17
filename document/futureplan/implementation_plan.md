# Intelligent Document Processing (IDP) Studio - Implementation Plan

## Goal
Implement the IDP Interactive Dual-Panel UI (as outlined in `idp_architecture_diagram.md`) allowing users to visually map PDF fields to form templates. This must be built as a parallel extension to ensure the existing zero-touch automated extraction pipeline remains completely unaffected.

## Architectural Approach: "Parallel Extension & Override Injection"

To prevent breaking the current flow, we will build the IDP feature as a separate "Studio Mode". The existing `/api/upload` endpoint, `run_pipeline.py`, and standard React Dashboard will remain exactly as they are. The IDP rules will only interact with the main engine via an optional **upstream override injection**.

---

## 1. Database Layer (Spatial Rules Storage)
We will create a new table in the database to store spatial relationship rules without touching the existing `rules_config.json`.

*   **New Table**: `idp_spatial_rules`
*   **Schema**:
    *   `rule_id` (Primary Key)
    *   `template_name` (e.g., "FLA", "AOC4")
    *   `field_name` (e.g., "net_worth")
    *   `anchor_text` (The text to search for, e.g., "Total Liabilities")
    *   `x_offset`, `y_offset` (Distance from the anchor text bounding box)
    *   `width`, `height` (Dimensions of the target value bounding box)

## 2. Backend Layer (Non-Destructive API)
We will add dedicated endpoints for the IDP Studio, leaving the current endpoints untouched.

### New API Endpoints (`api/main.py`)
*   `GET /api/idp/rules/{template_name}`: Fetch all trained spatial rules for a template.
*   `POST /api/idp/rules`: Save a new spatial mapping rule from the frontend canvas.
*   `POST /api/idp/extract_interactive`: A lightweight endpoint to test a spatial rule on a live PDF before saving it.

### Extraction Engine Injection (`parser.py`)
*   **The Override:** When `parser_engine.parse_all()` runs, it will first query the `idp_spatial_rules` table. 
*   If a rule exists for a field, it locates the `anchor_text` in the PDF's bounding box data, applies the `x/y offsets`, crops the region, and extracts the text.
*   **The Fallback:** If no spatial rule exists for a field, the engine silently falls back to the current regex/keyword parsing logic. This guarantees zero disruption to current capabilities.

## 3. Frontend Layer (Dual-Panel UI)
We will create a completely new route, avoiding any modifications to the current `TaskView` or `Dashboard`.

### New Route: `/idp-studio`
*   **Component**: `IdpStudio.jsx`
*   **Left Panel (Interactive PDF Canvas)**: 
    *   Integrate a robust PDF renderer (like `react-pdf` or `pdf.js`).
    *   Overlay an interactive, transparent SVG layer to allow the user to draw bounding boxes and select anchor text.
*   **Right Panel (Template Form)**:
    *   A dropdown to select the target form template.
    *   A list of fields. Clicking a field puts the Left Panel into "Mapping Mode" so the user can draw the spatial relationship.

---

## Phased Execution Strategy

1.  **Phase 1: Backend & DB Foundations**
    *   Create the `idp_spatial_rules` database schema.
    *   Build the CRUD API endpoints for rules.
2.  **Phase 2: Coordinate Extraction Engine**
    *   Write the Python utility that takes a PDF, an anchor string, and spatial offsets, and returns the target text using bounding box mathematics.
3.  **Phase 3: Frontend Dual-Panel UI**
    *   Build the `/idp-studio` React route.
    *   Implement the PDF renderer and drawing canvas.
4.  **Phase 4: Pipeline Integration**
    *   Inject the spatial override check into the main extraction pipeline.

---

> [!IMPORTANT]
> **User Review Required**
> 
> 1. **PDF Rendering Library:** To render the PDF interactively on the frontend, I recommend using `react-pdf`. Are you comfortable adding this dependency to `fla_frontend`?
> 2. **Bounding Box Data:** To calculate offsets (Phase 2), the backend needs access to word-level bounding boxes. Are we currently using a PDF parsing library (like `pdfplumber` or `PyMuPDF/fitz`) that can return coordinate data, or should I integrate `pdfplumber` for this specific IDP extraction module?

Please review this approach. If approved, I will begin Phase 1 immediately.
