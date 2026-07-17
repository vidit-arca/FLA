# Backend Architecture & Developer Onboarding Guide

Welcome to the Statutory Compliance Automation Engine! This guide explains the core backend architecture, how the rule engine works end-to-end, and the strict contract you must follow when adding new compliance modules (like MGT-7, ADT-1, etc.).

---

## 🚨 FOR EXTERNAL DEVELOPERS: The "Plug-and-Play" Integration Modules 

If you are an external developer hired to build a new module, your code **must be 100% isolated and plug-and-play**. The core team will simply copy your completed folder into `automation_engine/modules/` and expect it to work without modifying the rest of the application.

To achieve this, you are required to follow this exact interface pattern. **Do not modify anything outside of your specific module folder.**

### Your Workspace

You will create and work entirely inside a single isolated folder: `automation_engine/modules/<your_form_name>/` (e.g., `modules/mgt7/`).

Inside this folder, you must deliver exactly 4 items:

1. `rules_config.json`
2. `parser.py`
3. `rule_engine.py`
4. `validator.py`

### 1. The Parser Interface (`parser.py`)

Your class (e.g., `MGT7Parser`) must accept raw OCR outputs and document paths, and return a flat Python dictionary of raw extracted values.

```python
# REQUIRED INTERFACE
class MGT7Parser:
    def __init__(self, config_path):
        # Load your rules_config.json here
        pass
      
    def parse_all(self, docs_paths, ocr_outputs=None):
        # Your extraction logic here (Regex, Pandas, etc.)
        # MUST return a flat dictionary of raw extracted variables.
        return {
            "turnover": 500000.0, 
            "cin_number": "L123456",
            "is_listed": "Yes"
        }
```

### 2. The Rule Engine Interface (`rule_engine.py`)

Your class (e.g., `MGT7RuleEngine`) must accept the flat dictionary produced by your parser, apply business logic/math, and return a nested dictionary mapping values to exact Excel cell coordinates.

```python
# REQUIRED INTERFACE
class MGT7RuleEngine:
    def __init__(self, config_path):
        pass

    def evaluate_all(self, extracted_data):
        # Apply mathematical thresholds, formulas, and defaults here.
        # MUST return a nested dictionary categorized by Excel Sheet Name -> Cell -> Value
        return {
            "Sheet 1": {
                "A1": "Value", 
                "B2": 500000.0
            },
            "Sheet 2": {
                "C5": 10.5
            }
        }
```

### 3. The Validator Interface (`validator.py`)

Your class (e.g., `MGT7Validator`) must mathematically verify the final computed cell values to ensure compliance formulas balance out (e.g., Assets == Liabilities).

```python
# REQUIRED INTERFACE
class MGT7Validator:
    def run_all_checks(self, cell_values):
        # Execute cross-verification checks on the final Excel coordinate dictionary
        # Return a list of logs containing {"check_name", "status", "details"}
        pass
      
    def save_report(self, output_dir="."):
        # Save the validation results to JSON/TXT
        pass
```

### How to Test Your Code Locally Before Handoff

Since you won't have access to the main `run_pipeline.py` or the core ingestion engine, you should test your module by creating a dummy script inside your folder that mimics the main pipeline:

```python
# dummy_test.py (Keep this inside your module folder for local testing)
from parser import MGT7Parser
from rule_engine import MGT7RuleEngine

# 1. Mock the input paths that the core engine would normally pass to you
dummy_docs = {"financials": "path/to/test/fin.pdf"}

# 2. Run your parser
parser = MGT7Parser("rules_config.json")
raw_data = parser.parse_all(dummy_docs)

# 3. Run your rule engine
engine = MGT7RuleEngine("rules_config.json")
final_cells = engine.evaluate_all(raw_data)

print(final_cells) # Verify your output matches the expected Excel coordinate format
```

When you deliver your code, the core team will simply map your classes in `core/factory.py`, and the main system will automatically execute them.

---

## High-Level Architecture Overview

The backend is strictly divided into two layers to ensure maximum modularity:

1. **Core Pipeline (`automation_engine/core/`)**: Generic infrastructure that handles document ingestion, OCR, and writing final Excel files. It does not know anything about specific compliance rules.
2. **Modules Layer (`automation_engine/modules/`)**: Specific compliance logic (e.g., `fla`, `aoc4`).

---

## Coding Standards & Best Practices

1. **Never Hardcode Mapping Rules:** If a keyword changes, it should be updated in `rules_config.json`, NOT inside the python scripts.
2. **Defensive Excel Parsing:** Do not rely on hardcoded row/column indexes in Pandas. Use dynamic header scanning (e.g., look for "Particulars" or "Current Year" in the first 15 rows).
3. **Graceful Fallbacks:** If a variable cannot be found in the OCR text, the `rule_engine.py` should catch it and gracefully apply a default value (like `0.0` or `"No"`) to prevent pipeline crashes.
