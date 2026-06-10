import pandas as pd
import sys

try:
    df = pd.read_excel("/Users/apple/Desktop/FLA/excel/FLA Return existing skeletal.xlsx", sheet_name="Section III", header=None)
    for row_idx, row in df.iterrows():
        for col_idx, cell in enumerate(row):
            if pd.notna(cell) and isinstance(cell, str) and ("B1.1:" in cell or "Equity Capital" in cell or "B1:" in cell):
                # Excel rows are 1-indexed
                print(f"Row {row_idx+1}, Col {col_idx}: {cell}")
except Exception as e:
    print(f"Error: {e}")
