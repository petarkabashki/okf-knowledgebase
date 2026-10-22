---
name: okf-provenance
description: Record, check and verify provenance in OKF v0.2 bundles — keyed sources, per-claim footnotes, verification events, staleness and link liveness. Use when writing researched concepts or verifying them later.
---

# OKF Provenance Skill (OKF v0.2 §5)

Use this skill whenever a concept is built from external research, and whenever someone checks or re-checks
that research. The goal: every claim can be traced to a source, every source can be checked, and the bundle
says what has and hasn't been checked.

## Writing researched concepts

1. List every source in frontmatter `sources` with a stable `id`, the exact `resource` URL, a `title`, and an
   `author` actor (`org:<name>`, `press:<name>`, `consultancy:<name>`).
2. Flag weak sources with the extension key `quality: secondary` (aggregator, vendor guide, press) or
   `quality: headline-only` (only a search-result title was seen). Primary/official sources need no flag.
3. Attribute each claim with a footnote keyed to the source id, and define the footnote in the body:
   ```markdown
   Grants cover up to 70% of costs.[^iuk-comp]

   [^iuk-comp]: Innovate UK competition page
   ```
   Source tables in research logs may cite by URL instead; a URL appearing in the body counts as a citation.
4. Record authorship with `generated: { by: <agent>/<model>, at: <ISO-8601> }`. Do NOT add `verified` when an
   agent wrote the content — the concept stays `unverified` until checked.
5. Set `stale_after` to the date the content stops being trustworthy (a deadline, or a review horizon such as
   three months out). Put uncertainty, conflicts between sources and inferences under `# Caveats and open questions`.

## Checking a bundle

```bash
okf-kb citations <bundle>              # every footnote resolves to a sources[].id; exit 1 on errors
okf-kb citations <bundle> --strict     # also fail on uncited sources / undefined footnotes
okf-kb upcoming <bundle> --within 30   # stale or going stale soon (deadlines, review dates)
okf-kb upcoming <bundle> --field deadline --within 60
okf-kb linkcheck <bundle> --only-broken  # are source URLs still live? (needs network)
```

## Verifying (human or process)

```bash
# Export a checklist of every source (md has tick boxes; csv for spreadsheets)
okf-kb sources <bundle> --format md --out verification-checklist.md
okf-kb sources <bundle> --unique --format csv --out sources.csv

# Stamp one source as checked after reading it
okf-kb verify <concept-id> --source <source-id> --by human:<id> --path <bundle>

# Mark a whole concept as verified once its claims match its sources -> trust tier human-reviewed
okf-kb verify <concept-id> --by human:<id> --note "checked against official page" --path <bundle>
```

Use `human:<id>` only for a person's own check; automated checks use `process:<id>` (machine-confirmed tier).
Per-source stamps live in the extension key `sources[].checked` and do not change the trust tier; only a
concept-level `verified` event does (§5.3).

## Python API

```python
from okf_kb.provenance import check_citations, collect_sources, upcoming, add_verification, check_links
issues = check_citations("/path/to/bundle")
rows = collect_sources("/path/to/bundle", unique=True)
soon = upcoming("/path/to/bundle", within_days=30)
add_verification("/path/to/bundle/programmes/x.md", by="human:peter", source_id="official")
```

After changing concepts, log the change in the nearest `log.md` (§9) and rebuild indexes with `okf-kb index`.
