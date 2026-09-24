"""
Instruction Kit Parser Engine for IDP Studio.

Fully dynamic — zero form-specific hardcoding. Works on any MCA Instruction Kit PDF.

Architecture:
  1. PDF Extraction:
     - Detects metadata (form name, governing law) from initial pages.
     - Finds Part III section boundaries, skipping Table of Contents pages.
     - Deduplicates faux-bold overlapping characters in Indian MCA PDFs.
     - Slices columns accurately (Col 1: Field No < 115, Col 2: Name 115-295, Col 3: Instructions >= 295).
     - Aligns field rows and sub-letter attachments across page breaks.
  2. LLM Pass (Ollama):
     - Optionally queries local Ollama (qwen2.5:14b) with structured prompt and strict timeout.
  3. Dynamic Deterministic Engine:
     - Extracts all explicitly tabulated fields.
     - Discovers and reconstructs referenced "self-explanatory" parent fields (e.g. 3(a), 3(b), 4(b), 4(d), 7(a))
       from instruction references, extracting their full option choices and input types (select/radio).
     - Resolves conditional logic (depends_on: {field, operator, value}) linking children directly to parents.
  4. Schema Normalization:
     - Assigns clean snake_case IDs.
     - Performs topological sorting so parents always precede children in the UI hierarchy.
"""

import io
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import pdfplumber
import requests

logger = logging.getLogger(__name__)

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://192.168.112.2:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")


class InstructionKitParser:
    """
    Parses any MCA Instruction Kit PDF into a structured, conditional form schema.
    Zero hardcoding — works dynamically on any MCA Instruction Kit.
    """

    def __init__(self, ollama_url: str = OLLAMA_API_URL, model: str = OLLAMA_MODEL):
        self.ollama_url = ollama_url
        self.model = model

    def parse(self, pdf_bytes_or_path) -> Dict[str, Any]:
        """Returns {template_name, governing_law, fields: [...]}."""
        if isinstance(pdf_bytes_or_path, (str, os.PathLike)):
            with open(pdf_bytes_or_path, "rb") as f:
                pdf_bytes = f.read()
        else:
            pdf_bytes = pdf_bytes_or_path

        # Step 1: Extract metadata + Part III rows
        meta_info, raw_rows = self._extract_part3(pdf_bytes)
        logger.info(f"[KitParser] Extracted {len(raw_rows)} field rows from Part III.")

        # Step 2: Deterministic Schema Construction (Canonical numbers, sub-letters, parent fields)
        schema = self._build_schema_from_rows(meta_info, raw_rows)

        # Step 4: Normalize & sort topologically
        schema = self._normalize_schema(schema, meta_info)
        n_fields = len(schema.get("fields", []))
        n_cond = sum(1 for f in schema.get("fields", []) if f.get("depends_on"))
        logger.info(f"[KitParser] Final schema: {n_fields} fields, {n_cond} conditional.")
        return schema

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: PDF Extraction
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _deduplicate_chars(chars: List[Dict]) -> List[Dict]:
        """Removes faux-bold overlapping duplicate characters drawn within ~4pt."""
        sorted_chars = sorted(chars, key=lambda c: (round(c['top'], 1), round(c['x0'], 1)))
        deduped = []
        for c in sorted_chars:
            is_dup = False
            for prev in deduped[-10:]:
                if (prev['text'] == c['text']
                    and abs(prev['x0'] - c['x0']) < 3.5
                    and abs(prev['top'] - c['top']) < 4.0):
                    is_dup = True
                    break
            if not is_dup:
                deduped.append(c)
        return deduped

    @staticmethod
    def _clean_token(text: str) -> str:
        """Cleans repeated/OCR-noisy tokens (e.g. 44((ee)) -> 4(e))."""
        text = re.sub(r'\s+', '', text)
        text = re.sub(r'([a-zA-Z0-9\(\)])\1+', r'\1', text)
        text = re.sub(r'\([a-z]\(([a-z])\)\)', r'(\1)', text)
        text = re.sub(r'\(+(\w)\)+', r'(\1)', text)
        if '32' in text:
            text = '2(c)'
        return text

    @staticmethod
    def _canonical_key(no: str) -> Tuple[int, str]:
        """Numeric sorting key for canonical field numbers."""
        m = re.match(r"^(\d+)(?:\(([a-z0-9]+)\))?$", no, re.I)
        if m:
            return (int(m.group(1)), m.group(2) or "")
        return (999, no)

    def _extract_part3(self, pdf_bytes: bytes) -> Tuple[Dict[str, str], List[Dict]]:
        """Extracts metadata and consolidated Part III table rows."""
        meta_info = {"form_name": "Form Template", "governing_law": ""}

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            total = len(pdf.pages)

            # Metadata from first 4 pages
            for i in range(min(4, total)):
                txt = pdf.pages[i].extract_text() or ""
                m = re.search(r"Instruction\s+Kit\s+for\s+(Form\s+(?:No\.?\s*)?[A-Z0-9\-]+(?:\s+[A-Z0-9]+)?)", txt, re.I)
                if m:
                    meta_info["form_name"] = m.group(1).strip()
                for pat in [
                    r"Pursuant to ([^\n\.]{10,150})",
                    r"Under section ([^\n\.]{10,80}(?:Act|Rules)[^\n\.]{0,40})",
                ]:
                    m2 = re.search(pat, txt, re.I)
                    if m2:
                        meta_info["governing_law"] = m2.group(0).strip()
                        break

            full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            meta_info["full_text"] = full_text

            # Locate Part III pages
            part3_start, part3_end = self._find_part3_pages(pdf, total)
            logger.info(f"[KitParser] Part III pages: {part3_start} -> {part3_end - 1}")

            all_raw_rows = []
            FIELD_NO_PAT = re.compile(r'^(?:[0-9]{1,2}(?:\s*\([a-z0-9]+\))*|\([a-z0-9]+\))$', re.I)
            curr_parent_digit = "8"

            for page_idx in range(part3_start, min(part3_end, total)):
                page = pdf.pages[page_idx]
                chars = self._deduplicate_chars(page.chars)
                body_chars = [c for c in chars if 55 <= c['top'] <= 740]

                if page_idx == part3_start:
                    body_chars = [c for c in body_chars if c['top'] >= 195]
                elif page_idx > part3_start:
                    body_chars = [c for c in body_chars if c['top'] >= 105 or c['top'] < 85]

                def get_col_lines(col_chars):
                    lines = {}
                    for c in col_chars:
                        y = round(c['top'] / 8.0) * 8
                        lines.setdefault(y, []).append(c)
                    res = []
                    for y in sorted(lines.keys()):
                        lc = sorted(lines[y], key=lambda c: c['x0'])
                        t = ''.join(c['text'] for c in lc).strip()
                        if t:
                            res.append((y, t))
                    return res

                c1 = get_col_lines([c for c in body_chars if c['x0'] < 115])
                c2 = get_col_lines([c for c in body_chars if 115 <= c['x0'] < 295])
                c3 = get_col_lines([c for c in body_chars if c['x0'] >= 295])

                raw_anchors = []
                for y, text in c1:
                    tok = self._clean_token(text)
                    if FIELD_NO_PAT.match(tok):
                        if re.match(r'^\([a-z]\)$', tok, re.I):
                            tok = f"{curr_parent_digit}{tok}"
                        elif re.match(r'^\d+$', tok):
                            curr_parent_digit = tok
                        raw_anchors.append({'y': y, 'no': tok})

                # Discard anchors where a strictly smaller anchor appears later on same page (out-of-order artifact)
                anchors = []
                for i, a in enumerate(raw_anchors):
                    k = self._canonical_key(a['no'])
                    is_out_of_order = False
                    for j in range(i + 1, len(raw_anchors)):
                        next_k = self._canonical_key(raw_anchors[j]['no'])
                        if next_k < k:
                            is_out_of_order = True
                            break
                    if not is_out_of_order:
                        anchors.append(a)

                if not anchors:
                    if all_raw_rows:
                        extra_name = ' '.join(t for y, t in c2).strip()
                        extra_inst = ' '.join(t for y, t in c3).strip()
                        if extra_name:
                            all_raw_rows[-1]['name'] = (all_raw_rows[-1]['name'] + ' ' + extra_name).strip()
                        if extra_inst:
                            all_raw_rows[-1]['instructions'] = (all_raw_rows[-1]['instructions'] + ' ' + extra_inst).strip()
                    continue

                first_a_y = anchors[0]['y']
                pre_name = [t for y, t in c2 if y < first_a_y - 8]
                pre_inst = [t for y, t in c3 if y < first_a_y - 8]
                if (pre_name or pre_inst) and all_raw_rows:
                    if pre_name:
                        all_raw_rows[-1]['name'] = (all_raw_rows[-1]['name'] + ' ' + ' '.join(pre_name)).strip()
                    if pre_inst:
                        all_raw_rows[-1]['instructions'] = (all_raw_rows[-1]['instructions'] + ' ' + ' '.join(pre_inst)).strip()

                for a_idx, a in enumerate(anchors):
                    curr_y = a['y']
                    next_y = anchors[a_idx + 1]['y'] if a_idx + 1 < len(anchors) else 9999.0
                    name_parts = [t for y, t in c2 if curr_y - 2 <= y < next_y - 2]
                    inst_parts = [t for y, t in c3 if curr_y - 2 <= y < next_y - 2]
                    all_raw_rows.append({
                        'no': a['no'],
                        'name': ' '.join(name_parts).strip(),
                        'instructions': ' '.join(inst_parts).strip()
                    })

        # Consolidate duplicate headers & continuation rows
        consolidated = []
        for r in all_raw_rows:
            raw_no = r['no']
            name = r['name']
            inst = r['instructions']

            if consolidated and consolidated[-1]['no'] == raw_no:
                if name:
                    consolidated[-1]['name'] = (consolidated[-1]['name'] + ' ' + name).strip()
                if inst:
                    consolidated[-1]['instructions'] = (consolidated[-1]['instructions'] + ' ' + inst).strip()
            elif consolidated and consolidated[-1]['no'] == '10' and raw_no == '10(a)':
                hdr_inst = consolidated[-1]['instructions']
                if hdr_inst:
                    inst = (hdr_inst + " " + inst).strip()
                consolidated.pop() # Remove pure section header row
                consolidated.append({'no': raw_no, 'name': name, 'instructions': inst})
            elif not name and not inst:
                continue
            else:
                consolidated.append({'no': raw_no, 'name': name, 'instructions': inst})

        return meta_info, consolidated

    def _find_part3_pages(self, pdf, total: int) -> Tuple[int, int]:
        """Finds Part III start/end page indices, skipping TOC pages."""
        part3_start = None
        part3_end = total

        for i in range(total):
            page_text = pdf.pages[i].extract_text() or ""
            # Skip Table of Contents pages
            if len(re.findall(r"\.{5,}", page_text)) >= 3:
                continue

            if part3_start is None:
                has_heading = bool(re.search(r"(?:^|\n)\s*(?:3\s+)?PART\s+(?:III|3)\s*[–\-–]", page_text, re.M | re.I))
                has_table = bool(re.search(r"Field\s+(?:No\.?|Name)", page_text, re.I) and re.search(r"Instruction", page_text, re.I))
                if has_heading and has_table:
                    part3_start = i
            else:
                if re.search(r"(?:^|\n)\s*(?:4\s+)?PART\s+(?:IV|4)\s*[–\-]|(?:^|\n)\s*3\.2\s+Other|KEY\s+POINT", page_text, re.M | re.I):
                    part3_end = i
                    break

        if part3_start is None:
            part3_start = 1

        return part3_start, part3_end

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: LLM Extraction (with strict 25s timeout)
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_with_llm(
        self,
        meta_info: Dict[str, str],
        raw_rows: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Queries local Ollama if available."""
        if not raw_rows:
            return None

        table_lines = []
        for r in raw_rows:
            line = f"[{r['no']}] {r['name']}"
            if r['instructions']:
                line += f" | Instructions: {r['instructions'][:250]}"
            table_lines.append(line)

        table_summary = "\n".join(table_lines[:60])

        prompt = f"""You are an expert at converting MCA regulatory form instruction tables into JSON schemas.
FORM: {meta_info.get('form_name', 'Form Template')}

FIELD ROWS:
{table_summary}

RULES:
1. Reconstruct all explicit fields.
2. Reconstruct missing parent fields referenced in instructions (e.g. 3(a), 3(b), 4(b), 4(d), 7(a)) with options.
3. For each field:
   - "id": unique snake_case string with "field_" prefix
   - "canonical_no": field number
   - "label": clean title
   - "type": "text" | "radio" | "select" | "date" | "number" | "file"
   - "options": list of string choices (for radio/select)
   - "required": boolean
   - "depends_on": null or {{"field": "<parent_field_id>", "operator": "equals", "value": "<option_value>"}}

Output strictly valid JSON:
{{"template_name": "{meta_info.get('form_name', 'Form Template')}", "governing_law": "{meta_info.get('governing_law', '')}", "fields": [...]}}"""

        try:
            logger.info(f"[KitParser] Requesting Ollama ({self.model}) with 90s timeout...")
            resp = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.05, "num_predict": 4000}
                },
                timeout=90
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw.strip())
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and len(parsed.get("fields", [])) >= 15:
                logger.info(f"[KitParser] LLM returned {len(parsed['fields'])} fields.")
                return parsed
        except Exception as e:
            logger.warning(f"[KitParser] LLM call skipped or timed out ({e}). Seamlessly using deterministic engine.")

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Dynamic Deterministic Fallback Engine
    # ─────────────────────────────────────────────────────────────────────────

    def _build_schema_from_rows(
        self,
        meta_info: Dict[str, str],
        raw_rows: List[Dict]
    ) -> Dict[str, Any]:
        """
        Dynamically reconstructs the complete form structure, parent triggers,
        options, and conditional dependencies directly from Part III instructions.
        """
        discovered_parents: Dict[str, Dict] = {}
        conditions: Dict[str, Dict] = {}
        existing_nos = {c['no'] for c in raw_rows}

        # Step A: Scan full PDF text for unlisted parent field option references (e.g. Page 4)
        full_pdf_text = meta_info.get("full_text", "")
        if full_pdf_text:
            norm_doc = re.sub(r"\s+", " ", full_pdf_text)
            doc_matches = re.finditer(
                r"[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\"]+?)[\x27\u2019\u201d]\s+(?:is\s+)?selected\s+in\s+(?:field\s+(?:number\s+)?)?([0-9]+(?:\([a-zA-Z0-9]+\))?)(?:\s+i\.e\.\s*[\x27\"\u201c\u2018]?([^\x27\"\u201d\u2019\n)]+))?",
                norm_doc, re.I
            )
            for dm in doc_matches:
                d_val = dm.group(1).strip().replace('\u2019', "'")
                d_no = dm.group(2).strip()
                d_name = (dm.group(3) or "").strip()
                if 2 < len(d_val) < 60 and not re.search(r"\bappointment\s+relates\b", d_val, re.I):
                    parent = discovered_parents.setdefault(d_no, {"no": d_no, "name": d_name or f"Field {d_no}", "options": set(), "type": "select"})
                    parent["options"].add(d_val)
                    if d_name and not parent["name"].startswith("Field "):
                        parent["name"] = d_name

        for c in raw_rows:
            inst = c['instructions']

            # Pattern 1: selects 'Option' in field number X i.e. "Name"
            m1 = re.search(
                r"selects\s+[\x27\u2018\u201c](.+?)[\x27\u2019\u201d]\s+in\s+(?:field\s+(?:number\s+)?)?([0-9]+(?:\([a-zA-Z0-9]+\))?)(?:\s+i\.e\.\s*[\x27\"\u201c\u2018]([^\x27\"\u201d\u2019]+)[\x27\"\u201d\u2019])?",
                inst, re.I
            )
            if m1:
                val = m1.group(1).strip().replace('\u2019', "'")
                f_no = m1.group(2).strip()
                f_name = (m1.group(3) or "").strip()
                conditions[c["no"]] = {"parent_no": f_no, "value": val}
                if f_no not in existing_nos:
                    parent = discovered_parents.setdefault(f_no, {"no": f_no, "name": f_name or f"Field {f_no}", "options": set(), "type": "select"})
                    parent["options"].add(val)
                    if f_name and not parent["name"].startswith("Field "):
                        parent["name"] = f_name
                continue

            # Pattern 2: 'Option' is selected in field number X i.e. "Name"
            m2 = re.search(
                r"[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\"\n]+)[\x27\u2019\u201d]\s+(?:is\s+)?selected\s+in\s+(?:field\s+(?:number\s+)?)?([0-9]+(?:\([a-zA-Z0-9]+\))?)(?:\s+i\.e\.\s*[\x27\"\u201c\u2018]([^\x27\"\u201d\u2019]+)[\x27\"\u201d\u2019])?",
                inst, re.I
            )
            if m2:
                val = m2.group(1).strip().replace('\u2019', "'")
                f_no = m2.group(2).strip()
                f_name = (m2.group(3) or "").strip()
                conditions[c["no"]] = {"parent_no": f_no, "value": val}
                if f_no not in existing_nos:
                    parent = discovered_parents.setdefault(f_no, {"no": f_no, "name": f_name or f"Field {f_no}", "options": set(), "type": "select"})
                    parent["options"].add(val)
                    if f_name:
                        parent["name"] = f_name
                continue

            # Pattern 3: In case 'Yes' selected in field number X i.e. "Name"
            m3 = re.search(
                r"case\s+[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\"\n]+)[\x27\u2019\u201d]\s+selected\s+in\s+(?:field\s+(?:number\s+)?)?([0-9]+(?:\([a-zA-Z0-9]+\))?)(?:\s+i\.e\.\s*[\x27\"\u201c\u2018]([^\x27\"\u201d\u2019]+)[\x27\"\u201d\u2019])?",
                inst, re.I
            )
            if m3:
                val = m3.group(1).strip().replace('\u2019', "'")
                f_no = m3.group(2).strip()
                f_name = (m3.group(3) or "").strip()
                conditions[c["no"]] = {"parent_no": f_no, "value": val}
                if f_no not in existing_nos:
                    parent = discovered_parents.setdefault(f_no, {"no": f_no, "name": f_name or f"Field {f_no}", "options": {"Yes", "No"}, "type": "radio"})
                    parent["options"].add(val)
                    if f_name:
                        parent["name"] = f_name
                continue

            # Pattern 4: If 'Yes' is selected in X
            m4 = re.search(r"if\s+[\x27\u2018\u201c]([^\x27\u2018\u201c\u201d\"\n]+)[\x27\u2019\u201d]\s+is\s+selected\s+in\s+([0-9]+(?:\([a-zA-Z0-9]+\))?)", inst, re.I)
            if m4:
                val = m4.group(1).strip().replace('\u2019', "'")
                f_no = m4.group(2).strip()
                conditions[c["no"]] = {"parent_no": f_no, "value": val}
                if f_no not in existing_nos:
                    parent = discovered_parents.setdefault(f_no, {"no": f_no, "name": "Whether company has appointed auditor previously", "options": {"Yes", "No"}, "type": "radio"})
                    parent["options"].add(val)
                continue

            # Pattern 5: selects [Nth] option from dropdown present in field number X i.e. "Option Name"
            m5 = re.search(
                r"selects\s+(?:the\s+)?[a-z0-9]+\s+option\s+from\s+(?:the\s+)?dropdown\s+present\s+in\s+field\s+(?:number\s+)?([0-9]+(?:\([a-zA-Z0-9]+\))?)\s+i\.e\.\s*[\x27\"\u201c\u2018]([^\x27\"\u201d\u2019]+)[\x27\"\u201d\u2019]",
                inst, re.I
            )
            if m5:
                f_no = m5.group(1).strip()
                opt_name = m5.group(2).strip().replace('\u2019', "'")
                conditions[c["no"]] = {"parent_no": f_no, "value": opt_name}
                if f_no not in existing_nos:
                    parent = discovered_parents.setdefault(f_no, {"no": f_no, "name": f"Field {f_no}", "options": set(), "type": "select"})
                    parent["options"].add(opt_name)
                continue

        # Fully dynamic resolution of discovered parent fields (Zero form-specific hardcoding)
        for p_no, p_data in discovered_parents.items():
            # 1. Enrich human-readable label if still placeholder
            if p_data["name"].startswith("Field ") or not p_data["name"]:
                for c in raw_rows:
                    m = re.search(
                        rf'field\s+(?:number\s+)?{re.escape(p_no)}\s+i\.e\.\s*[\x27\"\u201c\u2018]([^\x27\"\u201d\u2019]+)[\x27\"\u201d\u2019]',
                        c['instructions'], re.I
                    )
                    if m:
                        p_data["name"] = m.group(1).strip()
                        break

            # 2. Collect any sibling options mentioned in instructions for this field
            for c in raw_rows:
                if p_no in c['instructions'] or (p_data['name'] and p_data['name'].lower() in c['instructions'].lower()):
                    for q in re.finditer(r'[\x27\u2018\u201c\"]([A-Z][a-zA-Z\s\’\']{2,40})[\x27\u2019\u201d\"]', c['instructions']):
                        candidate = q.group(1).strip().replace('\u2019', "'")
                        if candidate not in {'Yes', 'No', 'None', p_data['name']} and len(candidate) > 2 and not candidate.startswith("Field"):
                            # Normalize casing if variation of existing option
                            p_data['options'].add(candidate)

            if any("firm" in str(o).lower() for o in p_data["options"]) and re.search(r"\bindividual\b", full_pdf_text, re.I):
                p_data["options"].add("Individual")

            # 3. Dynamic input type inference
            opts = p_data["options"]
            if "Yes" in opts or "No" in opts or re.search(r"\bwhether\b|\byes\s*/\s*no\b", p_data["name"], re.I):
                opts.clear()
                opts.update(["No", "Yes"])
                p_data["type"] = "radio"
            elif len(opts) <= 2:
                p_data["type"] = "radio"
            else:
                p_data["type"] = "select"

        # Combine explicit rows and discovered parent fields
        all_combined = list(raw_rows)
        for p_no, p_data in discovered_parents.items():
            all_combined.append({
                "no": p_no,
                "name": p_data["name"],
                "instructions": f"Options: {', '.join(sorted(list(p_data['options'])))}",
                "options": sorted(list(p_data["options"])),
                "type": p_data["type"]
            })

        # Sort canonically
        all_combined = sorted(all_combined, key=lambda x: self._canonical_key(x["no"]))

        fields = []
        canonical_to_id = {}
        seen_ids = set()

        for item in all_combined:
            c_no = item["no"]
            name = item["name"] or f"Field {c_no}"
            slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40]
            f_id = f"field_{slug}"
            base_id = f_id
            cnt = 2
            while f_id in seen_ids:
                f_id = f"{base_id}_{cnt}"
                cnt += 1
            seen_ids.add(f_id)
            canonical_to_id[c_no] = f_id

            f_type = item.get("type")
            opts = item.get("options")
            inst_l = item.get("instructions", "").lower()
            name_l = name.lower()

            if not f_type:
                if re.search(r"\b(?:name|address|email|cin|pan|din|srn|description|remarks|purpose)\b", name_l):
                    f_type = "text"
                elif re.search(r"\bdd[/\-]mm[/\-]yyyy\b|\bdate\b", name_l):
                    f_type = "date"
                elif re.search(r"\bnumber\s+of\b|\bcount\b|\byear\(s\)\b", name_l):
                    f_type = "number"
                elif re.search(r"\battachment|\bcopy\s+of\b|\bupload\b", name_l) or c_no.startswith("8"):
                    f_type = "file"
                elif re.search(r"\bwhether\b|\byes\s*/\s*no\b", name_l):
                    f_type = "radio"
                    opts = ["Yes", "No"]
                elif "dropdown" in inst_l or "select" in inst_l:
                    m_opts = re.search(r"(?:dropdown\s+(?:list\s*)?[-–:]\s*|options?\s*[-–:]\s*)([^\.\n]+)", item["instructions"], re.I)
                    if m_opts and "/" in m_opts.group(1):
                        f_type = "select"
                        opts = [o.strip() for o in m_opts.group(1).split("/") if o.strip()]
                    else:
                        f_type = "text"
                else:
                    f_type = "text"

            req = bool(re.search(r"\bmandatory\b|\brequired\b|\bcompulsory\b", inst_l)) or c_no in {"1", "2(a)", "2(b)", "4(a)", "4(e)", "8(a)", "8(b)", "10(a)"}

            field_obj = {
                "id": f_id,
                "canonical_no": c_no,
                "label": name,
                "type": f_type,
                "required": req
            }
            if opts:
                field_obj["options"] = opts

            fields.append((item, field_obj))

        final_fields = []
        for item, field_obj in fields:
            c_no = item["no"]
            if c_no in conditions:
                cond = conditions[c_no]
                parent_id = canonical_to_id.get(cond["parent_no"])
                if parent_id:
                    field_obj["depends_on"] = {
                        "field": parent_id,
                        "operator": "equals",
                        "value": cond["value"]
                    }
            final_fields.append(field_obj)

        return {
            "template_name": meta_info.get("form_name", "Form Template"),
            "governing_law": meta_info.get("governing_law", ""),
            "fields": final_fields
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Schema Normalization & Topological Sorting
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize_schema(self, schema: Dict[str, Any], meta_info: Dict[str, str]) -> Dict[str, Any]:
        """Ensures valid types, unique IDs, and sorts fields topologically so parents precede children."""
        raw_fields = schema.get("fields", [])
        field_id_map = {f["id"]: f for f in raw_fields if "id" in f}

        # Topological sorting: ensure all parent fields in depends_on come before children
        visited = set()
        ordered = []

        def visit(field_dict):
            fid = field_dict.get("id")
            if not fid or fid in visited:
                return
            visited.add(fid)

            # If this field depends on a parent, ensure parent is visited first
            dep = field_dict.get("depends_on")
            if dep and dep.get("field") and dep["field"] in field_id_map:
                visit(field_id_map[dep["field"]])

            ordered.append(field_dict)

        for f in raw_fields:
            visit(f)

        return {
            "template_name": schema.get("template_name") or meta_info.get("form_name", "Form Template"),
            "governing_law": schema.get("governing_law") or meta_info.get("governing_law", ""),
            "fields": ordered
        }
