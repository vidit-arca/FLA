import os

docs = {}
files = ["1.pdf", "Merged_Financials.md", "odi_detailes.md"]
for f in files:
    lower_name = f.lower()
    if "odi" in lower_name:
        docs["odi_details"] = f
        
print(docs)
