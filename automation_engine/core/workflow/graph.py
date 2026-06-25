from langgraph.graph import StateGraph, END

from .state import WorkflowState
from .nodes import node_ingest, node_ocr, node_extract, node_output, node_compare, check_comparison

def create_workflow_graph():
    workflow = StateGraph(WorkflowState)

    workflow.add_node("ingest", node_ingest)
    workflow.add_node("ocr", node_ocr)
    workflow.add_node("extract", node_extract)
    workflow.add_node("output", node_output)
    workflow.add_node("compare", node_compare)

    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "ocr")
    workflow.add_edge("ocr", "extract")
    workflow.add_edge("extract", "output")
    
    workflow.add_conditional_edges(
        "output",
        check_comparison,
        {
            "compare": "compare",
            "end": END
        }
    )
    
    workflow.add_edge("compare", END)

    return workflow.compile()
