# The Evolution of Data Extraction in IDP Studio

This document captures the journey of how we solved the complex problem of extracting key-value pairs from highly unstructured financial documents.

---

## 1. The Original Approach: The "Magic Pen" (Spatial Coordinates)

Our initial approach to extraction relied on drawing physical bounding boxes over a rendered PDF canvas, commonly referred to as the "Magic Pen".

### How it worked:
1. The user drew a rectangle over a label (Key) and another rectangle over a number (Value).
2. The frontend calculated the `x, y, width, height` coordinates of both boxes relative to the PDF page size.
3. The backend received these coordinates and used libraries like `pdfplumber` or `PyMuPDF` to extract whatever text intersected with those bounding boxes.

### Where we struggled:
*   **Coordinate Drift:** Rendering a PDF at different zoom levels on the frontend often caused the X/Y coordinates to slightly drift when sent to the backend.
*   **OCR Misalignment:** In scanned PDFs, the visual location of text rarely perfectly aligned with the OCR bounding boxes.
*   **Text Bleed:** Drawing a box around a value in a tight table would often accidentally capture pieces of adjacent columns, resulting in messy data like `14,000 Total`.
*   **Slow & Fragile:** Every extraction required a heavy backend network request to re-parse the PDF coordinates, which was slow and prone to errors.

---

## 2. The Intermediate Approach: Row-Based DOM Extraction

To fix the coordinate issues, we switched to processing the document upfront using Triton OCR and building a **Document Object Model (DOM)** tree. We rendered the document as structured HTML tables instead of a visual canvas.

### How it worked:
1. The user clicked anywhere on an HTML table row (`<tr>`).
2. The backend received the `row_id` and attempted to guess the Key and Value.
3. *Heuristic:* "The first cell is the Key, the first cell that looks like a number is the Value."

### Where we struggled:
*   **Financial Table Quirks:** Financial tables are incredibly messy. A row might start with a serial number like `(a)`, `2.`, or `II`. The heuristic would incorrectly grab `(a)` as the Key instead of `"Current investments"`.
*   **Note Columns:** Many financial tables include a "Note" column (e.g., Note `14`). The backend heuristic would see `14` as the first number in the row and incorrectly assign it as the monetary Value, ignoring the actual value entirely!
*   **Heuristic Whack-A-Mole:** Fixing these issues required writing increasingly complex Regex rules on the backend, which inevitably failed on edge cases.

---

## 3. The Final Solution: AI-Assisted Cell Selection

We realized that guessing data from a row was fundamentally flawed. The ultimate solution was to give the user absolute control at the **Cell Level (`<td>`)**, while making it lightning fast.

### How it works now:
1. **The DOM is in the Browser:** The frontend holds the entire structured document tree natively in React.
2. **Two-Click Selection:** The user clicks the precise Key cell (highlights Blue). 
3. **AI Suggestion (0ms Latency):** The frontend instantly scans the neighboring cells, uses smart heuristics to ignore small "Note" numbers, and highlights the actual large numeric value with a dashed green border.
4. **Keyboard Workflow:** The user simply presses `Enter` to accept the suggestion.

### Why this solved everything:
> [!TIP]
> **The Perfect Balance of Speed and Accuracy**
> * **Zero Coordinates:** We completely abandoned fragile X/Y math.
> * **Zero Backend Latency:** The extraction logic happens instantly in the browser without waiting for network requests.
> * **100% Deterministic Override:** If the AI suggestion is wrong (e.g., you want the value from a different column), you just click the correct cell manually. The user is never blocked by a failing heuristic.
