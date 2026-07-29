from __future__ import annotations

import json
from pathlib import Path
from okf_kb.document import OKFDocument, trust_tier, is_stale

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ bundle_name }} — OKF Bundle Visualizer</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --bg-color: #0f172a;
            --panel-bg: #1e293b;
            --text-color: #f8fafc;
            --accent-color: #38bdf8;
            --border-color: #334155;
        }
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        #header {
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 10;
            background: var(--panel-bg);
            padding: 10px 16px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }
        #header h1 { margin: 0; font-size: 1.1rem; color: var(--accent-color); }
        #cy {
            flex: 1;
            height: 100%;
        }
        #details {
            width: 400px;
            background: var(--panel-bg);
            border-left: 1px solid var(--border-color);
            padding: 20px;
            overflow-y: auto;
            box-sizing: border-box;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            background: #0284c7;
            margin-right: 4px;
        }
        .badge-trust { background: #059669; }
        .badge-stale { background: #dc2626; }
        code { background: #334155; padding: 2px 4px; border-radius: 4px; }
        pre code { display: block; padding: 10px; overflow-x: auto; }
        a { color: var(--accent-color); }
    </style>
</head>
<body>
    <div id="header">
        <h1>OKF Visualizer: {{ bundle_name }}</h1>
        <small>{{ concept_count }} concepts loaded</small>
    </div>
    <div id="cy"></div>
    <div id="details">
        <h2>Select a Concept</h2>
        <p>Click on any node in the graph to view its OKF frontmatter and content.</p>
    </div>

    <script>
        const graphData = {{ graph_json | safe }};

        const cy = cytoscape({
            container: document.getElementById('cy'),
            elements: graphData.elements,
            style: [
                {
                    selector: 'node',
                    style: {
                        'label': 'data(label)',
                        'color': '#f8fafc',
                        'font-size': '12px',
                        'background-color': 'data(color)',
                        'text-valign': 'bottom',
                        'text-margin-y': 4
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': '#475569',
                        'target-arrow-color': '#475569',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier'
                    }
                }
            ],
            layout: {
                name: 'cose',
                animate: false
            }
        });

        cy.on('tap', 'node', function(evt){
            const node = evt.target;
            const data = node.data();
            const details = document.getElementById('details');
            
            let html = `<h2>${data.label}</h2>`;
            html += `<p><span class="badge">${data.type}</span>`;
            if (data.trust) html += `<span class="badge badge-trust">${data.trust}</span>`;
            if (data.is_stale) html += `<span class="badge badge-stale">stale</span>`;
            html += `</p>`;
            
            if (data.description) html += `<p><em>${data.description}</em></p>`;
            if (data.body) {
                html += `<hr style="border-color:#334155;"><div class="markdown-body">${marked.parse(data.body)}</div>`;
            }
            details.innerHTML = html;
        });
    </script>
</body>
</html>
"""


def generate_bundle_visualization(bundle_root: str | Path, out_path: str | Path | None = None, bundle_name: str | None = None) -> Path:
    root_p = Path(bundle_root).resolve()
    if not root_p.exists():
        raise FileNotFoundError(f"Bundle path not found: {root_p}")

    b_name = bundle_name or root_p.name
    out_p = Path(out_path).resolve() if out_path else root_p / "viz.html"

    nodes = []
    edges = []
    concept_map = {}

    type_colors = {
        "ROLE": "#38bdf8",
        "PROJECT": "#a855f7",
        "SKILL": "#22c55e",
        "ACHIEVEMENT": "#eab308",
        "Attested Computation": "#f97316",
        "DEFAULT": "#64748b",
    }

    for f in root_p.rglob("*.md"):
        if f.name in ("index.md", "log.md", "README.md"):
            continue
        rel_path = str(f.relative_to(root_p))
        try:
            doc = OKFDocument.parse(f.read_text(encoding="utf-8"))
            concept_id = rel_path.replace("\\", "/").removesuffix(".md")
            c_type = str(doc.frontmatter.get("type", "Concept"))
            color = type_colors.get(c_type.upper(), type_colors.get(c_type, type_colors["DEFAULT"]))

            nodes.append({
                "data": {
                    "id": concept_id,
                    "label": doc.frontmatter.get("title") or f.stem,
                    "type": c_type,
                    "description": doc.frontmatter.get("description", ""),
                    "color": color,
                    "trust": trust_tier(doc.frontmatter),
                    "is_stale": is_stale(doc.frontmatter),
                    "body": doc.body,
                }
            })
            concept_map[concept_id] = doc
        except Exception:
            continue

    graph_json = json.dumps({"elements": {"nodes": nodes, "edges": edges}})

    rendered = _HTML_TEMPLATE.replace("{{ bundle_name }}", b_name)\
                             .replace("{{ concept_count }}", str(len(nodes)))\
                             .replace("{{ graph_json | safe }}", graph_json)

    out_p.write_text(rendered, encoding="utf-8")
    return out_p
