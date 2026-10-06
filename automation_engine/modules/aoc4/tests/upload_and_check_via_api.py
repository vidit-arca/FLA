"""
End-to-end AOC-4 smoke test against the *running* FLA backend.

This drives exactly the same HTTP flow the frontend uses
(``GenericUpload.jsx`` -> ``/api/upload`` -> ``/api/process/{id}``) so the
compliance-sheet pipeline can be verified without clicking through the UI.

Flow
----
    POST /api/upload?company_name=<C>&module_type=aoc4   (multipart files)
    POST /api/process/<task_id>                          (background LangGraph run)
    GET  /api/tasks/<task_id>                            (poll status + logs)
    GET  /api/download/<task_id>                         (populated Excel)

Usage
-----
    python automation_engine/modules/aoc4/tests/upload_and_check_via_api.py ^
        "Y:\\Main-OCR-main\\Main-OCR-main\\data\\Insap\\ocr_output" --company-name Insap

    # upload the raw PDFs instead (needs the Marker OCR binary installed/cached)
    ... --pattern "*.pdf"

Notes
-----
* ``--pattern`` defaults to ``*.md`` because the AOC-4 path is fully exercised by
  the OCR markdown files; PDFs additionally require the Marker OCR binary.
* Files whose name contains a previous-year token (prev/prior/last_year/py_) are
  listed but the parser excludes them from ``full_text``.
"""

import argparse
import json
import os
import sys
import time
from glob import glob

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("requests is required: pip install requests")

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
PREV_TOKENS = ("prev", "prior", "last_year", "py_")


class open_many:
    """Context manager so all upload file handles are closed on exit."""

    def __init__(self, paths):
        self.paths = paths
        self.handles = []

    def __enter__(self):
        self.handles = [(p, open(p, "rb")) for p in self.paths]
        return self.handles

    def __exit__(self, *exc):
        for _, h in self.handles:
            h.close()
        return False


def upload(base_url, company_name, files, module_type="aoc4"):
    """Mirrors GenericUpload.jsx: multipart POST with query-string params."""
    with open_many(files) as handles:
        payload = [("files", (os.path.basename(p), h, "application/octet-stream"))
                   for p, h in handles]
        res = requests.post(
            f"{base_url}/api/upload",
            params={"company_name": company_name, "module_type": module_type},
            files=payload,
            timeout=180,
        )
    res.raise_for_status()
    return res.json()["task_id"]


def poll(base_url, task_id, timeout=900, interval=3):
    """Wait for the background pipeline, mirroring the UI's 2 s poll."""
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        res = requests.get(f"{base_url}/api/tasks/{task_id}", timeout=60)
        res.raise_for_status()
        task = res.json()
        status = task.get("status")
        if status != last_status:
            print(f"    status = {status}")
            last_status = status
        if status in ("completed", "review_needed", "error"):
            return task
        time.sleep(interval)
    raise TimeoutError(f"task {task_id} did not finish within {timeout}s (last={last_status})")


def summarise(task):
    """Print the parts of the task payload the AOC-4 wizard actually renders."""
    extracted = task.get("extracted_data") or {}
    flags = extracted.get("flags", []) or []
    comparison = extracted.get("comparison_results", []) or []

    print("\n[4/5] Task payload")
    print(f"    company_name   : {task.get('company_name')}")
    print(f"    module_type    : {task.get('module_type')}")
    print(f"    status         : {task.get('status')}")
    print(f"    output_excel   : {task.get('output_excel')}")
    print(f"    full_text chars: {len(extracted.get('full_text') or '')}")
    print(f"    PY comparison  : {len(comparison)} row(s)")

    def line(step, label):
        subset = [f for f in flags if label(f)]
        failed = [f for f in subset if f.get("status") in ("Failed", "Manual")]
        print(f"    {step:<26}: {len(subset):>3} rule(s), {len(failed)} needs review")

    print("\n[5/5] Wizard step coverage (getFlagsForStep in AOC4TaskView.jsx)")
    line("Step 1 Common Errors", lambda f: f.get("source") not in
         ("Compliance Engine", "RPT & Loans Engine"))
    line("Step 2 Compliance Review", lambda f: f.get("source") == "Compliance Engine")
    line("Step 3 RPT & Loans", lambda f: f.get("source") == "RPT & Loans Engine")
    line("Total flags", lambda f: True)
    return flags, comparison


def inspect_excel(path):
    """List the sheets of the generated workbook (the 'compliance sheet' output)."""
    if not path or not os.path.exists(path):
        print(f"\n[!] No populated Excel at {path!r}")
        return
    try:
        import openpyxl
    except ImportError:
        print("\n[i] openpyxl not installed - skipping workbook inspection")
        return
    wb = openpyxl.load_workbook(path, read_only=True)
    print(f"\n[+] Populated workbook: {path}")
    for name in wb.sheetnames:
        ws = wb[name]
        print(f"      - {name!r} ({ws.max_row} rows x {ws.max_column} cols)")
    wb.close()



def main():
    ap = argparse.ArgumentParser(description="AOC-4 end-to-end API smoke test")
    ap.add_argument("input_dir", help="Folder holding the documents to upload")
    ap.add_argument("--company-name", default=None, help="Company name (default: folder name)")
    ap.add_argument("--pattern", default="*.md",
                    help="Glob for the files to upload (default: *.md; e.g. '*.pdf' or '*')")
    ap.add_argument("--module-type", default="aoc4")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--timeout", type=int, default=900, help="Pipeline timeout in seconds")
    ap.add_argument("--report", default=None, help="Optional path to dump the raw task JSON")
    args = ap.parse_args()

    folder = os.path.abspath(args.input_dir)
    if not os.path.isdir(folder):
        sys.exit(f"[!] Not a folder: {folder}")

    company = args.company_name or os.path.basename(folder.rstrip("\\/"))
    files = sorted(glob(os.path.join(folder, args.pattern)))
    if not files:
        sys.exit(f"[!] No files matching {args.pattern!r} in {folder}")

    print("=" * 90)
    print(f"AOC-4 end-to-end API check | {args.base_url} | module_type={args.module_type}")
    print("=" * 90)

    print("\n[0/5] Backend reachability")
    try:
        requests.get(f"{args.base_url}/api/tasks", timeout=15).raise_for_status()
        print("    /api/tasks reachable")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"    [!] Backend not reachable at {args.base_url}: {e}\n"
                 "    Start it with:  python -m uvicorn automation_engine.api.main:app "
                 "--host 127.0.0.1 --port 8000")

    print(f"\n[1/5] Uploading {len(files)} file(s) for '{company}'")
    for f in files:
        is_prev = any(t in os.path.basename(f).lower() for t in PREV_TOKENS)
        print(f"    - {os.path.basename(f)} ({os.path.getsize(f) / 1024:.0f} KB)"
              f"{'   [previous-year -> excluded from full_text]' if is_prev else ''}")
    task_id = upload(args.base_url, company, files, args.module_type)
    print(f"    task_id = {task_id}")

    print(f"\n[2/5] Triggering POST /api/process/{task_id}")
    requests.post(f"{args.base_url}/api/process/{task_id}", timeout=60).raise_for_status()

    print(f"\n[3/5] Polling GET /api/tasks/{task_id} (timeout {args.timeout}s)")
    t0 = time.time()
    task = poll(args.base_url, task_id, timeout=args.timeout)
    print(f"    finished in {time.time() - t0:.1f}s")

    logs = task.get("logs") or ""
    if logs:
        print("\n    --- pipeline log (tail) ---")
        for ln in logs.splitlines()[-15:]:
            print(f"    {ln}")

    flags, comparison = summarise(task)
    inspect_excel(task.get("output_excel"))

    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(task, fh, indent=2, default=str)
        print(f"\n[+] Raw task JSON -> {args.report}")

    print("\n" + "=" * 90)
    print(f"RESULT: status={task.get('status')}  flags={len(flags)}  PY rows={len(comparison)}")
    print(f"UI    : http://localhost:5173/m/{args.module_type}/task/{task_id}")
    print(f"Excel : {args.base_url}/api/download/{task_id}")
    print(f"Zip   : {args.base_url}/api/download_package/{task_id}")
    print("=" * 90)
    return 0 if task.get("status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
