import pdfplumber

def search_text_bbox(pdf_path, search_text):
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            # words is a list of dicts: {'text': '...', 'x0': ..., 'top': ..., 'x1': ..., 'bottom': ...}
            
            # Simple substring search across words or just find exact match
            # For multi-word anchors, we might need to combine bounding boxes
            
            # Let's print out some words to see
            print("First 10 words:", words[:10])
            break

