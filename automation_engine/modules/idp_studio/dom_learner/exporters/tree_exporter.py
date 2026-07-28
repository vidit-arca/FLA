"""
tree_exporter.py — Export the DOM as an ASCII tree and an interactive HTML tree.

ASCII tree (tree.txt):
    Uses box-drawing characters (├──, └──, │) for a clean visual.
    Cell nodes show column header + value inline for quick scanning.

HTML tree (tree.html):
    Uses nested <details><summary> elements for collapsible browsing.
    Styled with inline CSS — no external dependencies.
"""

from __future__ import annotations

import html
import logging
from pathlib import Path
from io import StringIO

from dom_learner.models import DOMNode, NodeType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ASCII tree
# ---------------------------------------------------------------------------

_PIPE   = "│   "
_TEE    = "├── "
_ELBOW  = "└── "
_BLANK  = "    "


def _format_node_label(node: DOMNode) -> str:
    """Human-readable one-line label for a node."""
    ntype = node.node_type.value.capitalize()

    if node.node_type == NodeType.CELL:
        col = node.metadata.get("column_header", "")
        text = node.text.strip()
        if col and text:
            return f"Cell [{col}]: {text}"
        elif text:
            return f"Cell: {text}"
        return "Cell: (empty)"

    if node.node_type == NodeType.NOTE:
        return f"Note: {node.metadata.get('note_number', node.text)}"

    if node.node_type == NodeType.ROW:
        label = node.metadata.get("row_label", "")
        idx = node.metadata.get("row_index", "")
        if label:
            return f"Row {idx} — {label}"
        return f"Row {idx}"

    if node.node_type == NodeType.HEADER:
        return "Header"

    if node.node_type == NodeType.TABLE:
        cols = node.metadata.get("column_count", 0)
        return f"Table ({cols} cols)"

    if node.node_type == NodeType.SECTION:
        level = node.metadata.get("heading_level", "")
        return f"Section (H{level}): {node.text}"

    if node.node_type == NodeType.HEADING:
        level = node.metadata.get("level", "")
        return f"Heading (H{level}): {node.text}"

    if node.node_type == NodeType.PARAGRAPH:
        preview = node.text[:60] + ("…" if len(node.text) > 60 else "")
        return f"Paragraph: {preview}"

    if node.node_type == NodeType.DOCUMENT:
        return "Document"

    return f"{ntype}: {node.text[:40]}"


def _render_tree(buf: StringIO, node: DOMNode, prefix: str, is_last: bool) -> None:
    """Recursively render *node* into *buf* with box-drawing prefixes."""
    connector = _ELBOW if is_last else _TEE
    buf.write(f"{prefix}{connector}{_format_node_label(node)}\n")

    child_prefix = prefix + (_BLANK if is_last else _PIPE)
    for i, child in enumerate(node.children):
        _render_tree(buf, child, child_prefix, i == len(node.children) - 1)


def export_tree_txt(document: DOMNode, output_path: Path) -> Path:
    """Write an ASCII tree representation to *output_path*.

    Returns the path written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    buf = StringIO()
    buf.write(f"{_format_node_label(document)}\n")

    for i, child in enumerate(document.children):
        _render_tree(buf, child, "", i == len(document.children) - 1)

    output_path.write_text(buf.getvalue(), encoding="utf-8")
    logger.info("Exported ASCII tree → %s", output_path.name)
    return output_path


# ---------------------------------------------------------------------------
# HTML tree
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DOM Tree — {title}</title>
<style>
  :root {{
    --bg: #0f1117;
    --fg: #e6edf3;
    --accent: #58a6ff;
    --border: #30363d;
    --node-bg: #161b22;
    --hover: #1c2128;
    --green: #3fb950;
    --orange: #d29922;
    --purple: #bc8cff;
    --red: #f85149;
    --cyan: #56d4dd;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', 'Inter', system-ui, sans-serif;
    background: var(--bg);
    color: var(--fg);
    padding: 2rem;
    line-height: 1.5;
  }}
  h1 {{
    color: var(--accent);
    font-size: 1.4rem;
    margin-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
  }}
  .stats {{
    color: #8b949e;
    font-size: 0.85rem;
    margin-bottom: 1.5rem;
  }}
  details {{
    margin-left: 1.2rem;
    border-left: 1px solid var(--border);
    padding-left: 0.8rem;
  }}
  details[open] > summary {{
    margin-bottom: 0.2rem;
  }}
  summary {{
    cursor: pointer;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.9rem;
    transition: background 0.15s;
  }}
  summary:hover {{
    background: var(--hover);
  }}
  .type-tag {{
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 3px;
    margin-right: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .type-document  {{ background: var(--accent); color: #000; }}
  .type-section   {{ background: var(--green); color: #000; }}
  .type-heading   {{ background: var(--green); color: #000; opacity: 0.7; }}
  .type-table     {{ background: var(--orange); color: #000; }}
  .type-header    {{ background: var(--purple); color: #000; }}
  .type-row       {{ background: var(--cyan); color: #000; }}
  .type-cell      {{ background: #30363d; color: var(--fg); }}
  .type-paragraph {{ background: #30363d; color: var(--fg); }}
  .type-note      {{ background: var(--red); color: #fff; }}
  .leaf {{
    margin-left: 1.2rem;
    padding: 3px 8px;
    font-size: 0.9rem;
    border-left: 1px solid var(--border);
    padding-left: 0.8rem;
  }}
  .node-id {{
    color: #484f58;
    font-size: 0.75rem;
    margin-left: 8px;
  }}
  .expand-all {{
    background: var(--node-bg);
    color: var(--accent);
    border: 1px solid var(--border);
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    margin-bottom: 1rem;
    display: inline-block;
    transition: background 0.2s;
  }}
  .expand-all:hover {{ background: var(--hover); }}
</style>
</head>
<body>
<h1>🌳 Logical Document Tree</h1>
<p class="stats">{stats}</p>
<button class="expand-all" onclick="toggleAll(true)">Expand All</button>
<button class="expand-all" onclick="toggleAll(false)">Collapse All</button>
<hr style="border-color: var(--border); margin: 1rem 0;">
{tree}
<script>
function toggleAll(open) {{
  document.querySelectorAll('details').forEach(d => d.open = open);
}}
</script>
</body>
</html>
"""


def _html_node(node: DOMNode) -> str:
    """Render a single node (and its children recursively) as HTML."""
    type_class = f"type-{node.node_type.value}"
    label = html.escape(_format_node_label(node))
    node_id = html.escape(node.id)

    if not node.children:
        return (
            f'<div class="leaf">'
            f'<span class="{type_class} type-tag">{node.node_type.value}</span>'
            f'{label}'
            f'<span class="node-id">{node_id}</span>'
            f'</div>\n'
        )

    children_html = "".join(_html_node(c) for c in node.children)
    return (
        f'<details>\n'
        f'<summary>'
        f'<span class="{type_class} type-tag">{node.node_type.value}</span>'
        f'{label}'
        f'<span class="node-id">{node_id}</span>'
        f'</summary>\n'
        f'{children_html}'
        f'</details>\n'
    )


def export_tree_html(document: DOMNode, output_path: Path, *, stats: str = "") -> Path:
    """Write a collapsible HTML tree to *output_path*.

    Returns the path written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree_html = _html_node(document)
    title = html.escape(document.metadata.get("source_file", "Document"))

    full_html = _HTML_TEMPLATE.format(title=title, tree=tree_html, stats=html.escape(stats))
    output_path.write_text(full_html, encoding="utf-8")
    logger.info("Exported HTML tree → %s", output_path.name)
    return output_path
