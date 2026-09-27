"""
6-Stage Statutory MCA Form Pipeline Orchestrator.
Coordinates Stage 1 through Stage 6 to ingest official MCA Instruction Kit PDFs.
"""

import re
from typing import Dict, Any, List
from .stages.stage1_pdf_layout import Stage1PdfLayout
from .stages.stage2_structure import Stage2DocumentStructure
from .stages.stage3_instruction_ai import Stage3InstructionAI
from .stages.stage4_dag_engine import Stage4DagEngine
from .stages.stage5_validator import Stage5Validator
from .stages.stage6_generator import Stage6FormGenerator


BRANCH_PAT = re.compile(
    r"In\s+case\s+(?:where\s+)?[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+?)[\x27\u2019\u201d\']\s+is\s+selected\s+in\s+this\s+field\s+then\s+fields\s+from\s+[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+?)[\x27\u2019\u201d\'](?:\s+to\s+(?:field\s+)?[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\']+?)[\x27\u2019\u201d\'])?",
    re.IGNORECASE | re.DOTALL
)


class StatutoryFormPipeline:
    """
    6-Stage Modular Architecture for MCA Instruction Kit Ingestion.
    """

    def __init__(self):
        self.stage1 = Stage1PdfLayout()
        self.stage2 = Stage2DocumentStructure()
        self.stage3 = Stage3InstructionAI()
        self.stage4 = Stage4DagEngine()
        self.stage5 = Stage5Validator()
        self.stage6 = Stage6FormGenerator()

    def run(self, pdf_bytes_or_path: Any) -> Dict[str, Any]:
        """
        Executes the full 6-stage ingestion pipeline.
        """
        # Stage 1: PDF Understanding
        layouts, form_name, governing_law, part3_start, part3_end = self.stage1.process(pdf_bytes_or_path)

        # Stage 2: Document Structure Identification
        raw_rows, section_blocks = self.stage2.process(layouts)

        # Detect root branches from root row instructions
        branches = []
        root_idx = None
        for idx, r in enumerate(raw_rows):
            found = list(BRANCH_PAT.finditer(r.instructions))
            if found:
                root_idx = idx
                for m in found:
                    branches.append({
                        "option": m.group(1).strip(),
                        "start_text": m.group(2).strip(),
                        "end_text": m.group(3).strip() if m.group(3) else "",
                        "resolved_start": None
                    })
                break

        # Map section assignments when branches exist
        if branches and root_idx is not None:
            raw_rows[root_idx].section_slug = "common"
            for b in branches:
                st = b["start_text"].lower()
                for r_idx in range(root_idx + 1, len(raw_rows)):
                    r = raw_rows[r_idx]
                    full_r = f"{r.canonical_no} {r.field_name} {r.instructions}".lower()
                    if st[:15] in full_r or r.field_name.lower().startswith(st[:15]):
                        b["resolved_start"] = r_idx
                        break

            valid_starts = [
                (b["resolved_start"], f"section_{i+1}", b["option"])
                for i, b in enumerate(branches)
                if b["resolved_start"] is not None
            ]
            valid_starts.sort(key=lambda x: x[0])

            for k in range(len(valid_starts)):
                s_idx, s_name, opt_val = valid_starts[k]
                e_idx = valid_starts[k + 1][0] if k + 1 < len(valid_starts) else len(raw_rows)
                for r_idx in range(s_idx, e_idx):
                    raw_rows[r_idx].section_slug = s_name

        # Stage 3: AI Instruction Understanding
        semantic_fields = self.stage3.process(raw_rows, branches)

        # Stage 4: Rule & Dependency DAG Engine (with Reverse Option Harvesting)
        connected_nodes = self.stage4.process(semantic_fields, form_name, branches)

        # Stage 5: Validation & Review Gate
        validation_report = self.stage5.validate(connected_nodes, raw_rows, branches)

        # Stage 6: Dynamic Form Generator
        schema = self.stage6.generate(form_name, governing_law, connected_nodes, validation_report)

        return schema
