# Akshayam Platform — GCP On-Demand Hosting & Cost Estimate (with Marker OCR)

### 1. Recommended Setup: "Single-Box On-Demand VM"
Run the complete stack on a **single GPU Compute Engine VM**:
* **Frontend**: React SPA
* **Backend**: FastAPI (`automation_engine`)
* **OCR Engine**: **Marker OCR** (PyTorch + Surya Layout/Text models, ~4–5 GB VRAM)
* **AI Models**: Ollama running `qwen2.5:14b` & `qwen2.5-coder:7b` (~15 GB VRAM)
* **When STOPPED**: GCP charges **$0.00 for Compute (vCPU, RAM, GPU)**. You only pay for disk retention.

---

### 2. Machine Specs Required (Updated for Marker OCR)

| Component | Specification | Why |
| :--- | :--- | :--- |
| **GPU** | **1x NVIDIA L4 (24 GB VRAM)** | **Fits all simultaneously in VRAM:** Ollama 14B (~10GB) + Marker OCR (~5GB) + Coder 7B (~5GB) = ~20GB / 24GB. |
| **Machine Type** | **`g2-standard-8`** *(or `g2-standard-4`)* | **8 vCPUs, 32 GB RAM** — provides the CPU & RAM headroom needed for PyTorch PDF rasterization alongside Uvicorn. |
| **Disk** | **200 GB Balanced SSD** | Holds OS + Docker + Ollama models (16GB) + Marker/HuggingFace weights (10GB) + PyTorch CUDA libs (8GB). |
| **Region** | `asia-south1` (Mumbai) | Lowest latency for India. |

---

### 3. Cost Breakdown

* **Fixed Standby Cost (When VM is STOPPED)**:
  * 200 GB Balanced SSD: **~$20 / month** (~₹1,650/mo)
  * Optional Static IP: **~$3 / month** (~₹250/mo)
  * **Base Standby Total: ~$20 – $23 / month (~₹1,700–₹1,900/mo)**

* **Active Running Cost (Only when powered ON)**:
  * **Option A (`g2-standard-8` + 1x L4 24GB)**: **~$1.05 / hour** (~₹88 / hr) — *(Recommended for Marker OCR + Ollama)*
  * **Option B (`g2-standard-4` + 1x L4 24GB)**: **~$0.82 / hour** (~₹68 / hr) — *(Budget, 16GB RAM)*

---

### 4. Monthly Billing Scenarios (Option A: 32GB RAM + L4 GPU)

| Scenario | Active Hours | Estimated Monthly Bill |
| :--- | :--- | :--- |
| **Minimal (Demos & Client Walkthroughs)** | ~20 hrs / month | **~$41 / month** (~₹3,400) |
| **Active QA & Document Extraction** | ~50 hrs / month (~2.5 hrs/day) | **~$73 / month** (~₹6,000) |
| **Heavy Staging / Batch Runs** | ~100 hrs / month (~5 hrs/day) | **~$125 / month** (~₹10,400) |

---

### 5. Safeguard: Auto-Shutdown (Zero Accidental Billing)
1. **Nightly Auto-Stop**: Cloud Scheduler automatically powers down the VM at 8:00 PM IST daily.
2. **Idle-Detection Script**: Shuts down the VM automatically if idle for 45 minutes.

---

### Executive Summary:
> *"Adding **Marker OCR** requires ~5 GB VRAM and extra RAM for PyTorch rasterization. The **1x NVIDIA L4 (24GB GPU)** fits both Ollama 14B and Marker OCR concurrently without swapping. With **`g2-standard-8` (32GB RAM)** and a **200 GB SSD**, standby cost is **~$20/month** (~₹1,700), and running cost is **~$1.05/hour** (~₹88/hr). A typical month of ~40–50 hours of active testing costs roughly **~$65–$73 / month** (₹5,500–₹6,000)."*
