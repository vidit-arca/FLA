# System & Hardware Metrics Implementation Plan

The objective of this plan is to build out the backend logic required to serve **live, real-time data** to the generic Platform Dashboard's "System & Hardware Metrics" widgets. This will replace the current hardcoded frontend mock data with actual database and hardware metrics.

## User Review Required

> [!IMPORTANT]
> The backend will require a new dependency (`GPUtil`) to actively ping your NVIDIA GPU for its VRAM usage. This allows the platform to accurately display how much memory the OCR engine is consuming during extraction.

## Proposed Changes

### 1. New Backend Endpoint for Metrics
We will add a new GET endpoint to the FastAPI backend that aggregates system health and hardware usage.

#### [MODIFY] [api/main.py](file:///Users/apple/Desktop/FLA/fla_automation_engine/api/main.py)
- **New Endpoint:** `@app.get("/api/metrics/global")`
- **Avg Extraction Time Logic:** 
  - Query all `ExtractionTask` records where `status == "completed"`.
  - Calculate `(task.completed_at - task.created_at).total_seconds()` for each task.
  - Return the average in seconds.
- **Global Confidence Score:** 
  - Since Marker-PDF currently does not emit a unified confidence float, we will either return a placeholder constant or compute a mock score based on the number of successfully extracted vs. required fields.
- **GPU Usage Logic:**
  - Import `GPUtil`.
  - Query the first available GPU (`GPUtil.getGPUs()[0]`).
  - Calculate `(gpu.memoryUsed / gpu.memoryTotal) * 100` to get the storage used percentage.
  - Return the formatted string (e.g., `"12GB / 24GB"`).

### 2. Frontend Integration
Once the backend endpoint is live, we will update the generic Dashboard to fetch this data on load.

#### [MODIFY] [Dashboard.jsx](file:///Users/apple/Desktop/FLA/fla_frontend/src/pages/Dashboard.jsx)
- **Add `useEffect` & `useState`:** Add a React hook to call `http://localhost:8000/api/metrics/global`.
- **Replace Hardcoded Values:** Swap the hardcoded `45sec`, `94.2%`, and `12GB` with state variables dynamically populated from the API response.

### 3. Dependencies
#### [MODIFY] `requirements.txt`
- **[NEW]** Add `GPUtil` to the project dependencies for querying NVIDIA hardware metrics safely across operating systems.

## Verification Plan

### Automated Tests
- None required, but error handling will be built into the GPU check so the app doesn't crash if it is run on a system without an NVIDIA GPU.

### Manual Verification
1. I will query the `/api/metrics/global` endpoint locally to ensure it returns a valid JSON payload with `avg_time`, `confidence`, and `gpu_usage`.
2. I will refresh the Frontend Dashboard and verify the hardware UI widgets display the actual live numbers.
