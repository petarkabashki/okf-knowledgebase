from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner

from okf_kb.cli import cli
from okf_kb.document import OKFDocument
from okf_kb.product import (
    PRODUCT_TYPES,
    ProductProfileError,
    board,
    check_bundle,
    decision_log,
    new_concept,
)


def _rewrite(path: Path, **frontmatter) -> None:
    doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
    for key, value in frontmatter.items():
        if value is None:
            doc.frontmatter.pop(key, None)
        else:
            doc.frontmatter[key] = value
    path.write_text(doc.serialize(), encoding="utf-8")


def _messages(bundle: Path, level: str = "error") -> list[str]:
    return [i["message"] for i in check_bundle(bundle) if i["level"] == level]


def test_every_type_scaffolds_to_a_clean_bundle(tmp_path):
    for name in PRODUCT_TYPES:
        new_concept(tmp_path, name, "sample", title=f"Sample {name}", by="human:t")
    assert check_bundle(tmp_path) == []


def test_scaffold_keeps_okf_status_separate_from_product_stage(tmp_path):
    path = new_concept(tmp_path, "Idea", "x", title="X", by="human:t")
    fm = OKFDocument.parse(path.read_text()).frontmatter
    assert fm["type"] == "Idea"
    assert fm["status"] == "draft"  # OKF §5.4 vocabulary, untouched
    assert fm["stage"] == "raw"  # product lifecycle lives in its own key
    assert path.parent.name == "ideas"


def test_decisions_are_numbered_in_order(tmp_path):
    first = new_concept(tmp_path, "decisions", "a", title="A", by="human:t", today=date(2026, 1, 1))
    second = new_concept(tmp_path, "Decision", "b", title="B", by="human:t", today=date(2026, 1, 2))
    assert first.name == "0001-a.md"
    assert second.name == "0002-b.md"
    assert [r["title"] for r in decision_log(tmp_path)] == ["A", "B"]


def test_scaffold_refuses_to_overwrite_and_rejects_bad_slugs(tmp_path):
    new_concept(tmp_path, "Idea", "x", title="X", by="human:t")
    with pytest.raises(ProductProfileError):
        new_concept(tmp_path, "Idea", "x", title="X", by="human:t")
    with pytest.raises(ProductProfileError):
        new_concept(tmp_path, "Idea", "../escape", title="X", by="human:t")
    with pytest.raises(ProductProfileError):
        new_concept(tmp_path, "Roadmap", "x", title="X", by="human:t")


def test_unknown_stage_is_an_error(tmp_path):
    path = new_concept(tmp_path, "Idea", "x", title="X", by="human:t")
    _rewrite(path, stage="done")
    assert any("stage 'done'" in m for m in _messages(tmp_path))


def test_missing_stage_and_missing_section_are_errors(tmp_path):
    path = new_concept(tmp_path, "Feature", "x", title="X", by="human:t")
    _rewrite(path, stage=None)
    text = path.read_text().replace("## Acceptance", "## Something else")
    path.write_text(text)
    messages = _messages(tmp_path)
    assert any("missing `stage`" in m for m in messages)
    assert any("## Acceptance" in m for m in messages)


def test_decision_requires_decided(tmp_path):
    path = new_concept(tmp_path, "Decision", "x", title="X", by="human:t")
    _rewrite(path, decided=None)
    assert any("`decided`" in m for m in _messages(tmp_path))


def test_supersession_must_resolve_and_be_reciprocated(tmp_path):
    old = new_concept(tmp_path, "Decision", "old", title="Old", by="human:t")
    new = new_concept(tmp_path, "Decision", "new", title="New", by="human:t")
    _rewrite(old, stage="superseded", superseded_by="decisions/0002-new")
    # One-sided: the successor does not say what it supersedes.
    assert any("not reciprocated" in m for m in _messages(tmp_path))
    _rewrite(new, stage="accepted", supersedes="/decisions/0001-old.md")
    assert _messages(tmp_path) == []
    _rewrite(new, supersedes="decisions/0099-missing")
    assert any("does not resolve" in m for m in _messages(tmp_path))


def test_superseded_without_successor_is_an_error(tmp_path):
    path = new_concept(tmp_path, "Decision", "x", title="X", by="human:t")
    _rewrite(path, stage="superseded")
    assert any("names no successor" in m for m in _messages(tmp_path))


def test_placeholder_past_initial_stage_warns(tmp_path):
    path = new_concept(tmp_path, "Idea", "x", title="X", by="human:t")
    assert _messages(tmp_path, "warning") == []
    _rewrite(path, stage="shaping")
    assert any("TBD." in m for m in _messages(tmp_path, "warning"))


def test_non_product_concepts_are_ignored(tmp_path):
    (tmp_path / "metric.md").write_text("---\ntype: Metric\n---\n\nbody\n")
    assert check_bundle(tmp_path) == []
    assert board(tmp_path) == {}


def test_board_groups_by_type_and_stage(tmp_path):
    path = new_concept(tmp_path, "Idea", "x", title="X", by="human:t")
    _rewrite(path, issues=[42])
    grouped = board(tmp_path)
    assert list(grouped["Idea"]) == list(PRODUCT_TYPES["Idea"].stages)
    assert grouped["Idea"]["raw"][0]["issues"] == ["42"]


def test_cli_check_exits_nonzero_on_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["product", "new", "Idea", "x", "--title", "X", "--by", "human:t", "-p", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert runner.invoke(cli, ["product", "check", str(tmp_path)]).exit_code == 0
    _rewrite(tmp_path / "ideas" / "x.md", stage="nope")
    assert runner.invoke(cli, ["product", "check", str(tmp_path)]).exit_code == 1
