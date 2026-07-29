---
name: data-ingestion
description: Generic instructions for ingesting concept documents into OKF knowledge bundles.
---

# Generic OKF Data Ingestion Skill (OKF v0.2)

Use this skill when ingesting new concept documents into an OKF knowledge bundle.

## Frontmatter Template

Every concept document requires YAML frontmatter followed by a markdown body:

```markdown
---
type: <Concept Type>                         # REQUIRED
title: <Display Title>
description: <One-line summary>
resource: <Canonical URI or path>
tags: [<tag1>, <tag2>]
---

# Concept Title

Content description in standard Markdown.
```

---

## Workflow & CLI Commands

Use `okf-kb ingest` for ingesting concept files:

```bash
# Ingest single file into bundle
okf-kb ingest --file /path/to/source.md --type Metric --slug revenue --target /path/to/bundle

# Ingest with specific subfolder
okf-kb ingest --file /path/to/source.md --type Table --slug customer-orders --subfolder tables --target /path/to/bundle
```
