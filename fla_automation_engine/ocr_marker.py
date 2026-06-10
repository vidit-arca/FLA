import os
import subprocess
import sys

def perform_ocr_marker(pdf_path, output_dir, marker_cmd="marker_single"):
    print(f"[*] Starting Marker VLM OCR on: {pdf_path}")
    print("[*] Note: The first run will download models (2-3GB). Please wait...")

    # Run 1: Generate Markdown (.md)
    print("[*] Generating Markdown output...")
    cmd_md = [
        marker_cmd,
        pdf_path,
        "--output_dir", output_dir,
        "--output_format", "markdown",
        "--force_ocr"
    ]
    
    # Execute the command
    try:
        # Run MD conversion
        subprocess.run(cmd_md, check=True, capture_output=True, text=True)
        print("[+] Marker finished processing markdown format.")
    except subprocess.CalledProcessError as e:
        print(f"[!] Error during Marker OCR: {e}")
        if e.stderr:
            print(f"[!] Details: {e.stderr}")
        return None

    # Define the base output path (will check for .md)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_path = os.path.join(output_dir, base_name, f"{base_name}.md")
    
    return output_path


def main():
    data_dir = "data"
    output_dir = "output/marker"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    target_pdf = "BOARD REPORT_s.pdf"
    pdf_path = os.path.join(data_dir, target_pdf)
    
    if not os.path.exists(pdf_path):
        pdf_files = [f for f in os.listdir(data_dir) if f.lower().endswith('.pdf')]
        if not pdf_files:
            print("[!] No PDF files found in data/ directory.")
            return
        target_pdf = pdf_files[0]
        pdf_path = os.path.join(data_dir, target_pdf)
    
    output_file = perform_ocr_marker(pdf_path, output_dir)
    
    if output_file and os.path.exists(output_file):
        print(f"\n[+] VLM OCR Complete!")
        print(f"[+] Structured results saved to: {output_file}")
        
        print("\n--- Snippet of Results ---")
        with open(output_file, 'r') as f:
            content = f.read(1000)
            print(content + "..." if len(content) >= 1000 else content)
    else:
        print("[!] Could not find output file. Please check the output/marker directory.")

if __name__ == "__main__":
    main()
