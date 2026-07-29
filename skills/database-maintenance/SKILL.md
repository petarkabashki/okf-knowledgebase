---
name: database-maintenance
description: Generic instructions for maintaining, querying, archiving, and validating OKF knowledge bundles.
---

# Generic OKF Database Maintenance Skill (OKF v0.2)

Use this skill when maintaining, querying, archiving, or auditing an OKF knowledge bundle.

## Tooling & CLI Commands

Use the generic `okf-kb` CLI:

```bash
# List concepts with optional filters
okf-kb list --path /path/to/bundle
okf-kb list --type Metric --path /path/to/bundle
okf-kb list --tag finance --path /path/to/bundle

# Archive a concept
okf-kb archive concept-id --path /path/to/bundle

# Conformance validation
okf-kb validate /path/to/bundle

# Generate interactive HTML graph visualizer
okf-kb visualize --bundle /path/to/bundle --out viz.html
```
