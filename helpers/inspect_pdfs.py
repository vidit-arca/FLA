import os
try:
    import pypdf
except ImportError:
    import subprocess
    subprocess.run(["pip", "install", "pypdf"])
    import pypdf

def inspect_pdf(pdf_path):
    print(f"=== Inspecting {os.path.basename(pdf_path)} ===")
    try:
        reader = pypdf.PdfReader(pdf_path)
        print(f"Number of pages: {len(reader.pages)}")
        # Get metadata
        meta = reader.metadata
        print(f"Metadata: {meta}")
        
        # Extract text from first 2 pages
        text = ""
        for i in range(min(5, len(reader.pages))):
            page_text = reader.pages[i].extract_text()
            if page_text:
                text += f"\n--- PAGE {i+1} ---\n" + page_text
                
        print("First few pages preview (first 1500 chars):")
        print(text[:1500])
        print("\n" + "="*50 + "\n")
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")

if __name__ == "__main__":
    signed_dir = "/Users/apple/Desktop/FLA/signed"
    for f in os.listdir(signed_dir):
        if f.lower().endswith(".pdf"):
            inspect_pdf(os.path.join(signed_dir, f))
