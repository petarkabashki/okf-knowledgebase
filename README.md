# OKF Knowledgebase (`okf-kb`)

**Open Knowledge Format (OKF) v0.2 Knowledgebase Framework & Tooling**

`okf-kb` is a vendor-neutral Python framework, query engine, visualizer, and CLI for managing knowledge bundles and content databases represented in standard Markdown files with YAML frontmatter.

---

## Features

- **Document Parsing & Validation**: Full OKF v0.2 frontmatter parsing, `type` field validation, trust tier derivation (`unverified`, `machine-confirmed`, `human-reviewed`), and staleness checking (`is_stale`).
- **Database Query Engine**: Query roles, projects, achievements, skills, and skill matches across your knowledge base.
- **Interactive Visualizer**: Renders any OKF knowledge bundle into a self-contained interactive HTML graph (Cytoscape.js force-directed graph + Markdown renderer). Runs 100% offline.
- **Ingestion Pipeline**: Structured file ingestion and auto-archiving.
- **CLI Commands**: Unified `okf-kb` CLI interface for query, validation, ingestion, and visualization.
- **Provenance Tooling**: Per-claim citation checks, source verification checklists, `verified`/per-source `checked` stamping, staleness/deadline views, and source link checks (`okf_kb.provenance`).
- **Agent Skills**: Reusable agent skill instructions (`skills/okf-knowledgebase/SKILL.md`, `skills/okf-provenance/SKILL.md`).

---

## Installation

Using `uv` (recommended):

```bash
uv pip install -e .
```

Or standard pip:

```bash
pip install -e .
```

---

## CLI Usage

```bash
# Query roles in a knowledge base
okf-kb query roles --path /path/to/database

# Match target skills
okf-kb match --skills "Python,React,AI" --path /path/to/database

# Extract bullets for a role
okf-kb bullets --role lloyds-2025-2026 --path /path/to/database

# Render interactive HTML visualization
okf-kb visualize --bundle /path/to/database --out viz.html

# Validate OKF conformance
okf-kb validate /path/to/database

# Provenance (§5): citation check, source checklist, staleness, verification, link liveness
okf-kb citations /path/to/bundle
okf-kb sources /path/to/bundle --format md --out checklist.md
okf-kb upcoming /path/to/bundle --within 30
okf-kb verify concept-id --by human:you --path /path/to/bundle
okf-kb verify concept-id --source source-id --by human:you --path /path/to/bundle
okf-kb linkcheck /path/to/bundle --only-broken
```

---

## Python API

```python
from okf_kb.document import OKFDocument, trust_tier, is_stale
from okf_kb.query import KnowledgeQueryEngine

# Parse OKF document
doc = OKFDocument.parse(open("path/to/concept.md").read())
print(doc.frontmatter["type"])
print("Trust tier:", trust_tier(doc.frontmatter))

# Query knowledge base
engine = KnowledgeQueryEngine("/path/to/database")
roles = engine.query_roles()
matches = engine.match_skills(["Python", "AI"])
```

---

## License

MIT
