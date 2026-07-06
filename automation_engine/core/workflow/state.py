from typing import TypedDict, List, Dict, Any

class WorkflowState(TypedDict):
    task_id: str
    input_dir: str
    company_name: str
    module_type: str
    
    # Processed File Paths
    financial_docs: Dict[str, Any]
    previous_fla_file: str
    ocr_outputs: Dict[str, Any]
    
    # Payload Data
    extracted_data: Dict[str, Any]
    target_cells: Dict[str, Any]
    comparison_results: List[Dict[str, Any]]
    
    # Final Outputs
    output_excel: str
    status: str
    logs: List[str]
