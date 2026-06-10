import os
import sys

# Add parent directory to sys.path so we can import from ocr_marker.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from ocr_marker import perform_ocr_marker
except ImportError:
    # Fallback placeholder if ocr_marker is moved
    def perform_ocr_marker(pdf_path, output_dir, marker_cmd="marker_single"):
        print(f"[!] Warning: perform_ocr_marker could not be imported from ocr_marker.py")
        return None

class OcrPipeline:
    def __init__(self, output_dir="output/marker", marker_cmd="marker_single"):
        self.output_dir = output_dir
        self.marker_cmd = marker_cmd
        
    def get_cached_ocr_paths(self, pdf_path):
        """Returns paths of cached OCR results if they exist."""
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        # Subfolder structure (standard Marker output)
        md_path_sub = os.path.join(self.output_dir, base_name, f"{base_name}.md")
        
        # Flat structure (direct file/upload output)
        md_path_flat = os.path.join(self.output_dir, f"{base_name}.md")
        
        md_path = md_path_sub if os.path.exists(md_path_sub) else (md_path_flat if os.path.exists(md_path_flat) else None)
        
        return {
            "json": None,
            "md": md_path
        }

    def process_pdf(self, pdf_path, force=False):
        """Processes a PDF using Marker OCR or returns cached results."""
        if not pdf_path or not os.path.exists(pdf_path):
            print(f"[!] PDF not found: {pdf_path}")
            return None
            
        cached = self.get_cached_ocr_paths(pdf_path)
        if cached["md"] and not force:
            print(f"[*] Found cached Marker OCR results for {os.path.basename(pdf_path)}")
            return cached
            
        print(f"[*] Triggering Marker OCR pipeline for {os.path.basename(pdf_path)}...")
        md_output_raw = perform_ocr_marker(pdf_path, self.output_dir, marker_cmd=self.marker_cmd)
        
        # Resolve MD path as well
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        md_output = os.path.join(self.output_dir, base_name, f"{base_name}.md")
        if not os.path.exists(md_output) and md_output_raw and os.path.exists(md_output_raw):
            md_output = md_output_raw
            
        return {
            "json": None,
            "md": md_output if os.path.exists(md_output) else None
        }

