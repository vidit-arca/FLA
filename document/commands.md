Step 1: Run the OCR Batch Process
This command processes the PDFs and caches the extracted text.

bash
cd /Users/apple/Desktop/FLA/fla_automation_engine
python run_ocr_batch.py --input-dir "/Users/apple/Desktop/FLA/data/ERIC"
Step 2: Run the Main Pipeline
Once the OCR process is complete, run this command to populate the FLA return skeletal Excel file with the extracted data.

bash
cd /Users/apple/Desktop/FLA/fla_automation_engine
python run_pipeline.py \
  --input-dir "/Users/apple/Desktop/FLA/data/ERIC" \
  --skeletal "/Users/apple/Desktop/FLA/excel/FLA Return existing skeletal.xlsx" \
  --config rules_config.json \
  --output "/Users/apple/Desktop/FLA/data/ERIC/ERIC_FLA_Return_Final.xlsx"



**OCR commands**


# ---------------------------------------------------------
# Document 1: KTPL BSPL Standalone 24-25
# ---------------------------------------------------------
marker_single "/Users/apple/Desktop/FLA/data/Karomi/1. KTPL BSPL Standalone 24-25.pdf" --output_dir output/marker --output_format json

marker_single "/Users/apple/Desktop/FLA/data/Karomi/1. KTPL BSPL Standalone 24-25.pdf" --output_dir output/marker --output_format markdown


# ---------------------------------------------------------
# Document 2: Karomi Financials March 2025-signed
# ---------------------------------------------------------
marker_single "/Users/apple/Desktop/FLA/data/Karomi/2. Karomi Financials March 2025-signed.pdf" --output_dir output/marker --output_format json

marker_single "/Users/apple/Desktop/FLA/data/Karomi/2. Karomi Financials March 2025-signed.pdf" --output_dir output/marker --output_format markdown


# ---------------------------------------------------------
# Document 3: KAROMI AUDIT REPORT DETAILLED 2025-03-31
# ---------------------------------------------------------
marker_single "/Users/apple/Desktop/FLA/data/Karomi/3. KAROMI AUDIT REPORT DETAILLED 2025-03-31.pdf" --output_dir output/marker --output_format json

marker_single "/Users/apple/Desktop/FLA/data/Karomi/3. KAROMI AUDIT REPORT DETAILLED 2025-03-31.pdf" --output_dir output/marker --output_format markdown



marker_single "data/Audited financials.pdf" --output_dir output/marker --output_format markdown