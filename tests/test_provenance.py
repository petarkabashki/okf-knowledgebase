from datetime import date

import pytest
from click.testing import CliRunner

from okf_kb.cli import cli
from okf_kb.document import OKFDocument, trust_tier
from okf_kb.provenance import (
    check_internal_links,
    add_verification,
    check_citations,
    collect_sources,
    sources_to_csv,
    sources_to_markdown,
    upcoming,
)

GOOD = """---
type: Funding Programme
title: Example Grant
description: A grant.
tags: [grants, open]
programme_status: open
deadline: 2026-11-11
generated: { by: claude-research-agent/claude-opus-5-5, at: 2026-10-20T21:30:00Z }
stale_after: 2026-11-11
sources:
  - id: official
    resource: https://example.gov.uk/grant
    title: Official page
    author: org:example
  - id: press
    resource: https://press.example.com/story
    title: Press story
    quality: secondary
---

# Overview

Up to £250k.[^official] Success rate about 2%.[^press]

[^official]: Official page
[^press]: Press story
"""

BAD = """---
type: Funding Programme
title: Broken
stale_after: 2027-06-01
sources:
  - id: a
    resource: https://a.example.com
  - id: a
    resource: https://a2.example.com
  - id: unused
    resource: https://unused.example.com
  - id: nores
---

Claim.[^missing] Other.[^a]

[^a]: A
"""


@pytest.fixture
def bundle(tmp_path):
    (tmp_path / "programmes").mkdir()
    (tmp_path / "programmes" / "good.md").write_text(GOOD, encoding="utf-8")
    (tmp_path / "programmes" / "bad.md").write_text(BAD, encoding="utf-8")
    return tmp_path


def test_check_citations(bundle):
    issues = check_citations(bundle)
    good = [i for i in issues if i["concept_id"] == "programmes/good"]
    bad = {(i["level"], i["message"]) for i in issues if i["concept_id"] == "programmes/bad"}
    assert good == []
    assert ("error", "duplicate source id `a`") in bad
    assert ("error", "footnote [^missing] has no matching sources[].id") in bad
    assert ("warning", "footnote [^missing] is referenced but not defined in the body") in bad
    assert ("warning", "source `unused` is never cited in the body") in bad
    assert any(lvl == "error" and "missing `resource`" in msg for lvl, msg in bad)


def test_source_cited_by_url_in_body(tmp_path):
    (tmp_path / "log.md").write_text("# reserved", encoding="utf-8")
    (tmp_path / "research.md").write_text(
        "---\ntype: Research Log\nsources:\n  - id: s1\n    resource: https://x.example.com/a\n---\n\n"
        "| Source | URL |\n|---|---|\n| S1 | https://x.example.com/a |\n", encoding="utf-8")
    assert check_citations(tmp_path) == []
    assert collect_sources(tmp_path)[0]["cited"]


def test_collect_sources_and_exports(bundle):
    rows = collect_sources(bundle)
    good = [r for r in rows if r["concept_id"] == "programmes/good"]
    assert {r["source_id"] for r in good} == {"official", "press"}
    assert all(r["cited"] for r in good)
    assert next(r for r in good if r["source_id"] == "press")["quality"] == "secondary"
    assert "resource" in sources_to_csv(rows).splitlines()[0]
    md = sources_to_markdown(rows)
    assert "- [ ] `official` [Official page](https://example.gov.uk/grant)" in md
    assert OKFDocument.parse(md).frontmatter["type"] == "Verification Checklist"


def test_collect_sources_unique(bundle):
    (bundle / "programmes" / "dup.md").write_text(GOOD.replace("Example Grant", "Dup"), encoding="utf-8")
    rows = collect_sources(bundle, unique=True)
    official = [r for r in rows if r["resource"] == "https://example.gov.uk/grant"]
    assert len(official) == 1
    assert "programmes/dup" in official[0]["concept_id"] and "programmes/good" in official[0]["concept_id"]


def test_upcoming(bundle):
    rows = upcoming(bundle, within_days=30, today=date(2026, 10, 20))
    assert [r["concept_id"] for r in rows] == ["programmes/good"]
    assert rows[0]["days"] == 22 and not rows[0]["stale"]
    stale = upcoming(bundle, within_days=0, today=date(2026, 11, 12))
    assert stale[0]["stale"]


def test_add_verification_concept_and_source(bundle):
    f = bundle / "programmes" / "good.md"
    add_verification(f, by="human:peter", at="2026-10-21T09:00:00Z")
    doc = OKFDocument.parse(f.read_text(encoding="utf-8"))
    assert trust_tier(doc.frontmatter) == "human-reviewed"
    # body and footnotes preserved; timestamps not reformatted
    assert "[^official]: Official page" in doc.body
    text = f.read_text(encoding="utf-8")
    assert "at: 2026-10-20T21:30:00Z" in text
    assert "deadline: 2026-11-11" in text

    add_verification(f, by="process:linkcheck", at="2026-10-22T00:00:00Z", source_id="press")
    rows = [r for r in collect_sources(bundle) if r["source_id"] == "press"]
    assert rows[0]["checked"] == "process:linkcheck@2026-10-22"
    assert check_citations(bundle) == [i for i in check_citations(bundle) if i["concept_id"] != "programmes/good"]


def test_add_verification_rejects_bad_actor(bundle):
    with pytest.raises(ValueError):
        add_verification(bundle / "programmes" / "good.md", by="peter")
    with pytest.raises(KeyError):
        add_verification(bundle / "programmes" / "good.md", by="human:peter", source_id="nope")


def test_cli_commands(bundle):
    runner = CliRunner()
    res = runner.invoke(cli, ["citations", str(bundle)])
    assert res.exit_code == 1 and "duplicate source id" in res.output

    (bundle / "programmes" / "bad.md").unlink()
    assert runner.invoke(cli, ["citations", str(bundle)]).exit_code == 0

    res = runner.invoke(cli, ["sources", str(bundle), "--format", "csv"])
    assert res.exit_code == 0 and "https://example.gov.uk/grant" in res.output

    res = runner.invoke(cli, ["verify", "good", "--by", "human:peter", "--path", str(bundle)])
    assert res.exit_code == 0 and "human-reviewed" in res.output

    res = runner.invoke(cli, ["upcoming", str(bundle), "--within", "100000"])
    assert res.exit_code == 0 and "Example Grant" in res.output


def test_check_internal_links(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.md").write_text(
        "---\ntype: T\n---\n\nSee [y](/a/y.md), [z](./z.md), [dir](/a/), [web](https://e.com), [anchor](#h).\n",
        encoding="utf-8")
    (tmp_path / "a" / "y.md").write_text("---\ntype: T\n---\n", encoding="utf-8")
    broken = check_internal_links(tmp_path)
    assert [b["target"] for b in broken] == ["./z.md"]
