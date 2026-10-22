---
name: okf-product
description: Keep a product knowledge bundle in OKF v0.2 - product briefs, strategic directions, ideas, features and numbered decision records (ADRs) - using the `okf-kb product` commands. Use when capturing a product or feature idea, recording an architectural or product decision, superseding an earlier decision, or reviewing what is proposed, active or parked.
---

# OKF product profile

A product bundle is an ordinary OKF bundle whose concepts use five types.
Each type has a folder, a lifecycle (`stage`) and required body sections.
Run `okf-kb product types` for the authoritative table; the profile lives
in `okf_kb/product.py`.

| Type | Folder | Use it for |
|---|---|---|
| `Product Brief` | bundle root | Who it is for, the core claim, evidence, non-goals |
| `Direction` | `directions/` | A strategic bet that shapes many later choices |
| `Idea` | `ideas/` | Anything not yet committed to |
| `Feature` | `features/` | A committed, user-visible outcome |
| `Decision` | `decisions/` | A choice and its reasons, numbered `NNNN-slug.md` |

## Rules

- **`stage` is the product lifecycle; `status` is not.** OKF reserves
  `status` (`draft | stable | deprecated`) for the page's own maturity.
  Never put a product stage there.
- **Point to the tracker, do not copy it.** Work that closes with evidence
  lives in the issue tracker. List its numbers under `issues:`; do not
  restate whether it is open.
- **Decisions are superseded, never edited into a different decision.**
  Write a new one, set `supersedes:` on it and `superseded_by:` plus
  `stage: superseded` on the old one. `okf-kb product check` rejects a
  one-sided link.
- **Trust follows OKF §5.2.** An agent writes `generated.by:
  <agent>/<model>`. Only the person who made a decision stamps it, with
  `okf-kb verify <id> --by human:<id>`, which is what makes it
  `human-reviewed`. An agent never stamps `human:`.

## Commands

```bash
okf-kb product new decisions <slug> --title "..." --by <actor> -p <bundle>
okf-kb product new Idea <slug> --title "..." --by <actor> -p <bundle>
okf-kb product check <bundle>        # exit 1 on any error
okf-kb product board <bundle>        # concepts by type and stage
okf-kb product decisions <bundle>    # decision log, oldest first
okf-kb index <bundle>                # regenerate index.md files
```

Scaffolds carry `TBD.` in every section. `check` warns when a concept has
moved past its first stage with a section still unfilled.
