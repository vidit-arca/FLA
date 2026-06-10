import os
import argparse
import sys

# Defensive mock for _lzma C library (bypasses torchvision datasets optical_flow import failure)
try:
    import _lzma
except ImportError:
    from types import ModuleType
    mock_lzma = ModuleType("_lzma")
    mock_lzma.LZMA_CONCATENATED = 1
    mock_lzma.FORMAT_AUTO = 0
    mock_lzma.FORMAT_XZ = 1
    mock_lzma.FORMAT_ALONE = 2
    mock_lzma.FORMAT_RAW = 3
    mock_lzma.CHECK_NONE = 0
    mock_lzma.CHECK_CRC32 = 1
    mock_lzma.CHECK_CRC64 = 4
    mock_lzma.CHECK_SHA256 = 12
    
    class MockLZMADecompressor:
        def __init__(self, *args, **kwargs):
            pass
    class MockLZMACompressor:
        def __init__(self, *args, **kwargs):
            pass
            
    mock_lzma.LZMADecompressor = MockLZMADecompressor
    mock_lzma.LZMACompressor = MockLZMACompressor
    mock_lzma.LZMAError = Exception
    sys.modules["_lzma"] = mock_lzma

# Ensure engine package is in sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from engine.ingestion import DocumentIngestion
from engine.ocr_pipeline import OcrPipeline

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    default_input = os.path.join(base_dir, "signed") if os.path.exists(os.path.join(base_dir, "signed")) else "signed"
    default_ocr_dir = os.path.join(os.path.dirname(__file__), "output", "marker")

    parser = argparse.ArgumentParser(description="Standalone Batch OCR Processor for FLA Return Engine")
    parser.add_argument("--input-dir", default=default_input, help="Path to folder containing inputs (PDFs)")
    parser.add_argument("--ocr-dir", default=default_ocr_dir, help="Path to output folder for Marker cache")
    parser.add_argument("--ocr-cmd", default="marker_single", help="Command or path to the marker_single executable")
    parser.add_argument("--force", action="store_true", help="Force re-running OCR even if cache exists")
    
    args = parser.parse_args()
    
    print("==========================================================")
    print("           STARTING BATCH OCR PROCESSOR (MARKER)          ")
    print("==========================================================\n")
    
    if not os.path.exists(args.ocr_dir):
        os.makedirs(args.ocr_dir, exist_ok=True)
        
    ingestion = DocumentIngestion(args.input_dir)
    ocr = OcrPipeline(output_dir=args.ocr_dir, marker_cmd=args.ocr_cmd)
    
    print(f"[*] Scanning input directory: {args.input_dir}")
    docs = ingestion.find_documents()
    
    processed_count = 0
    skipped_count = 0
    
    for role, doc_path in docs.items():
        if not doc_path:
            continue
            
        basename = os.path.basename(doc_path)
        
        if not doc_path.lower().endswith(".pdf"):
            print(f"  [-] Skipping {basename} (Not a PDF)")
            continue
            
        is_scanned = ingestion.is_scanned_pdf(doc_path)
        if not is_scanned:
            print(f"  [-] Skipping {basename} (Native digital text detected, OCR unnecessary)")
            continue
            
        cached = ocr.get_cached_ocr_paths(doc_path)
        if (cached["md"] or cached["json"]) and not args.force:
            print(f"  [+] Skipping {basename} (Valid cache already exists in {args.ocr_dir})")
            skipped_count += 1
            continue
            
        print(f"\n  [!] Processing Scanned Document: {basename}")
        print(f"      Role: {role}")
        print(f"      This may take a few minutes depending on document length and GPU availability...")
        
        # Trigger the actual heavy ML OCR process inline (this will block until finished)
        result = ocr.process_pdf(doc_path, force=args.force)
        
        if result and (result["md"] or result["json"]):
            print(f"  [+] Successfully processed and cached OCR for {basename}")
            processed_count += 1
        else:
            print(f"  [x] Failed to process {basename}")
            
    print("\n==========================================================")
    print(f" Batch OCR Complete. Processed: {processed_count} | Skipped: {skipped_count}")
    print(" You can now run `python fla_automation_engine/run_pipeline.py` safely.")
    print("==========================================================")

if __name__ == "__main__":
    main()
