import pandas as pd
from typing import Dict, Any, List
from ..base import BaseComparisonPlatformModule

class FLAComparisonModule(BaseComparisonPlatformModule):
    def __init__(self, template_path: str = "/Users/apple/Desktop/FLA/excel/FLA_comparsion_.xlsx"):
        self.template_path = template_path

    def compare(self, source_path: str, target_path: str) -> List[Dict[str, Any]]:
        results = []
        
        try:
            template_dfs = pd.read_excel(self.template_path, sheet_name=None)
        except Exception as e:
            raise Exception(f"Failed to load FLA comparison template: {str(e)}")
            
        try:
            source_dfs = pd.read_excel(source_path, sheet_name=None, engine="openpyxl")
            target_dfs = pd.read_excel(target_path, sheet_name=None, engine="openpyxl")
        except Exception as e:
            raise Exception(f"Failed to load source or target excel files: {str(e)}")

        # Based on the rule, look in column G (index 6) for PREVIOUS FLA flags
        for sheet_name, template_df in template_dfs.items():
            if len(template_df.columns) <= 6:
                continue
                
            col_g_name = template_df.columns[6]
            for idx, row in template_df.iterrows():
                val_g = str(row[col_g_name]).upper()
                if "PREVIOUS FLA" in val_g:
                    field_name = str(row.iloc[2]) if len(row) > 2 else f"Row {idx+2}"
                    
                    source_val = "N/A"
                    target_val = "N/A"
                    
                    if sheet_name in source_dfs:
                        src_df = source_dfs[sheet_name]
                        if idx < len(src_df) and len(src_df.columns) > 3:
                            source_val = src_df.iloc[idx, 3] # Column D is index 3
                            
                    if sheet_name in target_dfs:
                        tgt_df = target_dfs[sheet_name]
                        if idx < len(tgt_df) and len(tgt_df.columns) > 3:
                            target_val = tgt_df.iloc[idx, 3]

                    # Clean up pandas NaN/NaT string representations
                    s_str = "" if pd.isna(source_val) else str(source_val)
                    t_str = "" if pd.isna(target_val) else str(target_val)
                    
                    status = "Match" if s_str == t_str else "Mismatch"
                    
                    results.append({
                        "cell": f"{sheet_name} | {field_name}",
                        "sourceValue": s_str,
                        "targetValue": t_str,
                        "status": status
                    })
                    
        return results
