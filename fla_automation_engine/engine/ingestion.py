import os
import pypdf
import json

class DocumentIngestion:
    def __init__(self, signed_dir):
        self.signed_dir = signed_dir
        
    def find_documents(self):
        """Scans the signed directory and returns identified document types and their roles."""
        # 1. Try to load manifest file
        manifest_path = os.path.join(self.signed_dir, "inputs_manifest.json")
        if not os.path.exists(manifest_path):
            manifest_path = os.path.join(os.path.dirname(self.signed_dir), "inputs_manifest.json")
            
        if os.path.exists(manifest_path):
            print(f"    [+] Loading input mapping from manifest: {manifest_path}")
            try:
                with open(manifest_path, 'r') as f:
                    manifest_data = json.load(f)
                
                # Resolve relative paths relative to the manifest directory
                manifest_dir = os.path.dirname(manifest_path)
                resolved_docs = {}
                for role, rel_path in manifest_data.items():
                    full_path = os.path.join(manifest_dir, rel_path)
                    if os.path.exists(full_path):
                        resolved_docs[role] = full_path
                    else:
                        print(f"    [!] Warning: File {full_path} specified in manifest not found.")
                return resolved_docs
            except Exception as e:
                print(f"    [!] Error parsing manifest. Falling back to heuristics. Error: {e}")

        # 2. Heuristic Fallback
        files_to_check = []
        for root, _, files in os.walk(self.signed_dir):
            for f in files:
                if not f.startswith('.') and not 'venv' in root:
                    files_to_check.append((root, f))
        
        docs = {}
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "marker")
        
        financial_pdfs = []
        financial_mds = []
        
        for root, f in files_to_check:
            lower_name = f.lower()
            full_path = os.path.join(root, f)
            
            # PDF and MD Heuristics
            if f.endswith('.pdf') or f.endswith('.md'):
                if "board" in lower_name:
                    docs["board_report"] = full_path
                elif "odi" not in lower_name and any(k in lower_name for k in ["financial", "merged", "auditor", "auditor financial", "balance sheet", "profit and loss", "p&l", "bspl", "standalone"]):
                    if f.endswith('.md'):
                        financial_mds.append(full_path)
                    elif "merged_financials_combined.pdf" not in lower_name:
                        financial_pdfs.append(full_path)
                    
            # Shareholder, ODI, & Extra Heuristics
            if any(f.endswith(ext) for ext in ['.xlsx', '.xls', '.md', '.pdf']):
                if "shareholder" in lower_name:
                    docs["shareholders_fdi"] = full_path
                elif "odi" in lower_name:
                    docs["odi_details"] = full_path
                elif "details" in lower_name or "extra" in lower_name:
                    docs["extra_details"] = full_path

        # Prioritize MD file if provided by user directly
        if financial_mds:
            docs["financials"] = financial_mds[0]
            if len(financial_mds) > 1:
                print(f"    [!] Multiple MD files found for financials. Using {financial_mds[0]}")
        elif financial_pdfs:
            if len(financial_pdfs) == 1:
                docs["financials"] = financial_pdfs[0]
            else:
                print(f"    [*] Merging {len(financial_pdfs)} financial PDFs...")
                merged_path = os.path.join(self.signed_dir, "merged_financials_combined.pdf")
                merger = pypdf.PdfWriter()
                for pdf_path in sorted(financial_pdfs):
                    merger.append(pdf_path)
                with open(merged_path, "wb") as out:
                    merger.write(out)
                docs["financials"] = merged_path
                    

        # Fallbacks for missing basic PDFs
        pdfs = [f for f in files if f.endswith('.pdf')]
        if "board_report" not in docs and len(pdfs) > 0:
            docs["board_report"] = os.path.join(self.signed_dir, pdfs[0])
        if "financials" not in docs and len(pdfs) > 1:
            docs["financials"] = os.path.join(self.signed_dir, pdfs[1])
            
        return docs

    def is_scanned_pdf(self, pdf_path):
        """Returns True if the PDF is scanned / has no extractable digital text layer."""
        if not pdf_path or not os.path.exists(pdf_path) or not pdf_path.endswith('.pdf'):
            return True
            
        try:
            reader = pypdf.PdfReader(pdf_path)
            for page in reader.pages[:3]: # check first 3 pages
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    return False
            return True
        except Exception as e:
            print(f"[!] Error checking PDF digital layer: {e}")
            return True
