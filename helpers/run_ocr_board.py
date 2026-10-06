import os
import subprocess

def run_ocr(pdf_path, output_dir):
    print(f"[*] Running marker_single on {pdf_path}")
    os.makedirs(output_dir, exist_ok=True)
    
    # We will generate markdown output
    cmd = [
        "marker_single",
        pdf_path,
        "--output_dir", output_dir,
        "--output_format", "markdown",
        "--force_ocr"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        print(f"[+] Output: {res.stdout}")
        if res.stderr:
            print(f"[!] Stderr: {res.stderr}")
    except Exception as e:
        print(f"[!] Error running OCR: {e}")

if __name__ == "__main__":
    pdf = "/Users/apple/Desktop/FLA/signed/BOARD REPORT FY25_final.pdf"
    out = "/Users/apple/Desktop/FLA/output/marker"
    run_ocr(pdf, out)
