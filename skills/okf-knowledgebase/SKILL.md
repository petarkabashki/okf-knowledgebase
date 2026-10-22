---
name: okf-knowledgebase
description: Standard instructions and tooling for managing, querying, validating, and visualizing Open Knowledge Format (OKF v0.2) knowledge bases and bundles.
---

# OKF Knowledgebase Skill (OKF v0.2)

Use this skill when creating, querying, validating, maintaining, or visualizing any Open Knowledge Format (OKF v0.2) knowledge bundle or content collection.

## OKF Format Conventions (§4–§5)

An OKF bundle is a directory of Markdown files with YAML frontmatter.

```yaml
---
type: <Concept Type>                         # REQUIRED (e.g. Table, Metric, Playbook, Reference)
title: <Display Title>
description: <One-line summary of the concept>
resource: <Canonical URI or asset link>
tags: [<tag1>, <tag2>]
generated: { by: <actor>, at: <ISO-8601> }
verified: { by: <actor>, at: <ISO-8601> }
status: draft | stable | deprecated
stale_after: YYYY-MM-DD
---

# Section Heading

Body content in standard Markdown.
```

### Trust Tiers (§5.3)

Derived automatically from `verified`:
- **`unverified`**: No `verified` key present.
- **`machine-confirmed`**: `verified` by automated/process actors only.
- **`human-reviewed`**: `verified` by a `human:<id>` actor.

---

## Generic Tooling & Commands

Use the generic `okf-kb` CLI:

```bash
# List concepts in a bundle with optional filters
okf-kb list --path /path/to/bundle
okf-kb list --type Metric --path /path/to/bundle
okf-kb list --tag finance --path /path/to/bundle
okf-kb list --search "revenue" --path /path/to/bundle

# View concept details
okf-kb show concept-id --path /path/to/bundle

# Ingest a new concept document
okf-kb ingest --file concept.md --type Metric --slug revenue --target /path/to/bundle

# Archive a concept
okf-kb archive concept-id --path /path/to/bundle

# Validate OKF conformance
okf-kb validate /path/to/bundle

# Render interactive HTML visualization
okf-kb visualize --bundle /path/to/bundle --out viz.html

# Build progressive disclosure index.md files (§8)
okf-kb index /path/to/bundle

# Provenance (§5) — see skills/okf-provenance/SKILL.md
okf-kb citations /path/to/bundle                 # footnotes resolve to sources[].id
okf-kb sources /path/to/bundle --format md       # verification checklist
okf-kb upcoming /path/to/bundle --within 30      # stale / deadlines soon
okf-kb verify concept-id --by human:<id> --path /path/to/bundle
okf-kb linkcheck /path/to/bundle --only-broken
```

---

## Python API Usage

```python
from okf_kb.document import OKFDocument, trust_tier, is_stale
from okf_kb.query import KnowledgeQueryEngine

# Parse concept
doc = OKFDocument.parse(open("path/to/concept.md").read())
tier = trust_tier(doc.frontmatter)
stale = is_stale(doc.frontmatter)

# Query generic bundle
engine = KnowledgeQueryEngine("/path/to/bundle")
metrics = engine.query_concepts(concept_type="Metric")
tagged = engine.query_concepts(tag="finance")
```
