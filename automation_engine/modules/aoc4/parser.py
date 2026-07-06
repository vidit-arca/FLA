import json
import os
import docx
import pdfplumber
import re

class AOC4Parser:
    def __init__(self, config_path: str):
        self.config_path = config_path
        with open(config_path, "r") as f:
            self.config = json.load(f)

    def extract_docx_text(self, path: str) -> str:
        """Extracts text from a native .docx file."""
        try:
            doc = docx.Document(path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            
            # Also extract from tables
            for table in doc.tables:
                for row in table.rows:
                    row_data = [cell.text for cell in row.cells]
                    text += " | ".join(row_data) + "\n"
            return text
        except Exception as e:
            print(f"[!] Error reading docx {path}: {e}")
            return ""

    def extract_excel_text(self, path: str) -> str:
        """Extracts text from all sheets of a native .xlsx/.xls file."""
        import pandas as pd
        try:
            excel_file = pd.ExcelFile(path)
            text_blocks = []
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                # Convert the dataframe into a string format
                text_blocks.append(df.to_string(index=False, na_rep=''))
            return "\n".join(text_blocks)
        except Exception as e:
            print(f"[!] Error reading excel {path}: {e}")
            return ""

    def parse_all(self, docs: dict, ocr_outputs: dict) -> dict:
        print("[*] AOC 4 Parser initialized: Extracting full text...")
        full_text = ""
        
        # Combine all provided financial docs
        for doc_key, doc_path in docs.items():
            if not doc_path or not os.path.exists(doc_path):
                continue
                
            basename = os.path.basename(doc_path).lower()
            
            # 1. Native DOCX
            if basename.endswith(".docx") or basename.endswith(".doc"):
                print(f"[*] AOC 4 Parser: Extracting text natively from {basename}")
                full_text += self.extract_docx_text(doc_path) + "\n\n"
                
            # 1.5 Native Excel (AOC4 only)
            elif basename.endswith(".xlsx") or basename.endswith(".xls"):
                print(f"[*] AOC 4 Parser: Extracting text natively from {basename}")
                full_text += self.extract_excel_text(doc_path) + "\n\n"
                
            # 2. Native PDF (pdfplumber) or OCR Markdown
            elif basename.endswith(".pdf"):
                extracted = False
                original_basename = os.path.basename(doc_path)
                
                # Try OCR Markdown first
                if ocr_outputs and original_basename in ocr_outputs:
                    md_path = ocr_outputs[original_basename].get("md")
                    if md_path and os.path.exists(md_path):
                        print(f"[*] AOC 4 Parser: Extracting from Marker OCR Markdown for {basename}")
                        with open(md_path, "r", encoding="utf-8") as f:
                            full_text += f.read() + "\n\n"
                        extracted = True
                
                # Fallback to pdfplumber
                if not extracted:
                    print(f"[*] AOC 4 Parser: Extracting natively from PDF {basename}")
                    try:
                        with pdfplumber.open(doc_path) as pdf:
                            for page in pdf.pages:
                                text = page.extract_text()
                                if text:
                                    full_text += text + "\n"
                    except Exception as e:
                        print(f"[!] Error parsing PDF {basename}: {e}")
            
            # 3. Markdown directly
            elif basename.endswith(".md"):
                print(f"[*] AOC 4 Parser: Reading Markdown file {basename}")
                try:
                    with open(doc_path, "r", encoding="utf-8") as f:
                        full_text += f.read() + "\n\n"
                except Exception as e:
                    print(f"[!] Error reading MD {basename}: {e}")

        # Extract CIN and determine if listed
        cin_match = re.search(r'\b([LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b', full_text, re.IGNORECASE)
        extracted_data = {
            "full_text": full_text,
            "docs": docs
        }
        
        if cin_match:
            cin_number = cin_match.group(1).upper()
            extracted_data["cin_number"] = cin_number
            if cin_number.startswith("L"):
                extracted_data["is_listed"] = "yes"
            elif cin_number.startswith("U"):
                extracted_data["is_listed"] = "no"

        return extracted_data
