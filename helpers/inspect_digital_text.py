import os
import pypdf

def check_pdf_text(pdf_path):
    print(f"=== Checking {os.path.basename(pdf_path)} ===")
    reader = pypdf.PdfReader(pdf_path)
    text_by_page = {}
    for i, page in enumerate(reader.pages):
        t = page.extract_text()
        if t and len(t.strip()) > 10:
            text_by_page[i+1] = len(t.strip())
    
    if text_by_page:
        print(f"Found digital text on {len(text_by_page)} pages: {list(text_by_page.keys())}")
        # Print a sample of page 1 or the first page with text
        first_page_with_text = min(text_by_page.keys())
        print(f"Sample from page {first_page_with_text}:")
        print(reader.pages[first_page_with_text-1].extract_text()[:500])
    else:
        print("No digital text found. Completely scanned/image PDF.")
    print()

if __name__ == "__main__":
    signed_dir = "/Users/apple/Desktop/FLA/signed"
    for f in os.listdir(signed_dir):
        if f.lower().endswith(".pdf"):
            check_pdf_text(os.path.join(signed_dir, f))
