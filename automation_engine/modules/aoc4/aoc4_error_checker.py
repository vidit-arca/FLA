import pandas as pd
import os

class AOC4CommonErrorEngine:
    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.rules = []
        self._load_rules()
        
    def _load_rules(self):
        """Load the rules from the ANNFIL COMMONERROR.xlsx file."""
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(f"Rules file not found at: {self.excel_path}")
            
        df = pd.read_excel(self.excel_path, sheet_name='Common Error')
        
        for idx, row in df.iterrows():
            particulars = str(row.get('Particulars', '')).strip()
            source = str(row.get('SOURCE', '')).strip()
            
            # Skip empty or structural rows (like headers or NaNs)
            if not particulars or particulars == 'nan':
                continue
                
            self.rules.append({
                "id": f"RULE_{idx}",
                "particulars": particulars,
                "source": source
            })

    def execute(self, input_data: dict) -> list:
        """
        Evaluate the parsed input_data against the loaded rules.
        Returns a list of flags for any checks that failed or are missing.
        """
        flags = []
        
        for rule in self.rules:
            particulars = rule["particulars"]
            
            # Strict exact-string lookup from the input JSON
            # The upstream parser must output exact string matches for these rules
            extracted_value = input_data.get(particulars, None)
            
            # Normalize the extracted value to check for 'No'
            val_lower = str(extracted_value).strip().lower() if extracted_value else ""
            
            if not extracted_value or val_lower == 'no':
                reason = "Value is missing in extraction." if not extracted_value else "Validation check failed (No)."
                
                flags.append({
                    "rule_id": rule["id"],
                    "particulars": particulars,
                    "source": rule["source"],
                    "status": "Failed",
                    "user_value": extracted_value,
                    "reason": reason
                })
                
        return flags
