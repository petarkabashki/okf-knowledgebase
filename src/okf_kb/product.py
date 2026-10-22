"""Product profile: concept types for product ideation, features, directions
and decision records, layered on OKF v0.2 without changing it.

OKF leaves `type` producer-defined (§4.1) and reserves `status` for the
document's own maturity (`draft | stable | deprecated`, §5.4). A product
concept also has a *product* lifecycle - an idea is shaped, accepted or
parked; a decision is proposed, accepted or superseded - and that is a
different axis from whether the page is a finished draft. So the profile
records it in a separate producer-defined key, `stage`, and never overloads
`status`. A bundle using this profile stays plain OKF: a consumer that knows
nothing about it sees ordinary typed concepts.

Work that closes with evidence is tracked elsewhere (an issue tracker). A
product concept points at it with `issues:` rather than restating its state,
so the bundle holds the *why* and the tracker holds the *whether*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from okf_kb.document import OKFDocument
from okf_kb.query import KnowledgeQueryEngine

STAGE_KEY = "stage"


@dataclass(frozen=True)
class ProductType:
    name: str
    subdir: str
    stages: tuple[str, ...]
    initial_stage: str
    # Stages a concept can no longer leave. Used only to order the board.
    terminal: tuple[str, ...]
    # `## <section>` headings the body must carry.
    sections: tuple[str, ...]
    # Frontmatter keys required beyond `type`, `title` and `stage`.
    required: tuple[str, ...] = ()


PRODUCT_TYPES: dict[str, ProductType] = {
    t.name: t
    for t in (
        ProductType(
            name="Product Brief",
            subdir="",
            stages=("draft", "current", "superseded"),
            initial_stage="draft",
            terminal=("superseded",),
            sections=("Problem", "Users", "Claim", "Evidence", "Non-goals"),
        ),
        ProductType(
            name="Direction",
            subdir="directions",
            stages=("proposed", "active", "paused", "retired"),
            initial_stage="proposed",
            terminal=("retired",),
            sections=("Bet", "Why now", "Signals"),
        ),
        ProductType(
            name="Idea",
            subdir="ideas",
            stages=("raw", "shaping", "accepted", "parked", "rejected"),
            initial_stage="raw",
            terminal=("accepted", "rejected"),
            sections=("Problem", "Proposal", "Value", "Open questions"),
        ),
        ProductType(
            name="Feature",
            subdir="features",
            stages=("proposed", "building", "shipped", "dropped"),
            initial_stage="proposed",
            terminal=("shipped", "dropped"),
            sections=("Outcome", "Scope", "Acceptance"),
        ),
        ProductType(
            name="Decision",
            subdir="decisions",
            stages=("proposed", "accepted", "superseded", "rejected"),
            initial_stage="proposed",
            terminal=("superseded", "rejected"),
            sections=("Context", "Decision", "Consequences", "Alternatives considered"),
            required=("decided",),
        ),
    )
}

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_DECISION_NUMBER_RE = re.compile(r"^(\d{4})-")


class ProductProfileError(ValueError):
    pass


def product_type(name: str) -> ProductType:
    for key, value in PRODUCT_TYPES.items():
        if key.lower() == name.lower() or value.subdir == name.lower():
            return value
    known = ", ".join(PRODUCT_TYPES)
    raise ProductProfileError(f"Unknown product type {name!r}; expected one of: {known}")


def _next_decision_number(bundle: Path) -> int:
    folder = bundle / PRODUCT_TYPES["Decision"].subdir
    numbers = [
        int(m.group(1))
        for p in folder.glob("*.md")
        if (m := _DECISION_NUMBER_RE.match(p.name))
    ] if folder.exists() else []
    return max(numbers, default=0) + 1


def new_concept(
    bundle: str | Path,
    type_name: str,
    slug: str,
    title: str,
    by: str,
    description: str = "",
    today: date | None = None,
) -> Path:
    """Scaffold a product concept with the type's frontmatter and sections.

    Decisions are numbered (`0007-<slug>.md`) so their order survives renames.
    Refuses to overwrite an existing file.
    """
    ptype = product_type(type_name)
    if not _SLUG_RE.match(slug):
        raise ProductProfileError(f"Invalid slug {slug!r}: use lowercase letters, digits and hyphens")
    root = Path(bundle)
    folder = root / ptype.subdir if ptype.subdir else root
    filename = slug
    if ptype.name == "Decision":
        filename = f"{_next_decision_number(root):04d}-{slug}"
    target = folder / f"{filename}.md"
    if target.exists():
        raise ProductProfileError(f"Refusing to overwrite {target}")

    today = today or date.today()
    fm: dict[str, Any] = {"type": ptype.name, "title": title}
    if description:
        fm["description"] = description
    fm["status"] = "draft"
    fm[STAGE_KEY] = ptype.initial_stage
    if "decided" in ptype.required:
        fm["decided"] = today.isoformat()
    fm["issues"] = []
    fm["generated"] = {
        "by": by,
        "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    body = f"# {title}\n\n" + "\n".join(f"## {s}\n\nTBD.\n" for s in ptype.sections)
    folder.mkdir(parents=True, exist_ok=True)
    target.write_text(OKFDocument(frontmatter=fm, body=body).serialize(), encoding="utf-8")
    return target


def _concepts(bundle: str | Path) -> list[dict[str, Any]]:
    engine = KnowledgeQueryEngine(bundle)
    return [c for c in engine.query_concepts() if c["type"] in PRODUCT_TYPES]


def _issue_refs(fm: dict[str, Any]) -> list[str]:
    raw = fm.get("issues") or []
    if not isinstance(raw, list):
        raw = [raw]
    return [str(i) for i in raw]


def check_bundle(bundle: str | Path) -> list[dict[str, str]]:
    """Validate every product concept against the profile.

    Errors: an unknown stage, a missing required key or section, a decision
    whose supersession link does not resolve or is not reciprocated, and a
    `superseded` decision naming no successor. Warning: a section still
    holding the scaffold's `TBD.` placeholder in a concept that claims to be
    past its initial stage.
    """
    concepts = _concepts(bundle)
    by_id = {c["concept_id"]: c for c in concepts}
    issues: list[dict[str, str]] = []

    def report(level: str, concept: dict[str, Any], message: str) -> None:
        issues.append({"level": level, "concept_id": concept["concept_id"], "message": message})

    for c in concepts:
        ptype = PRODUCT_TYPES[c["type"]]
        fm = c["frontmatter"]
        stage = fm.get(STAGE_KEY)
        if stage is None:
            report("error", c, f"missing `{STAGE_KEY}` (one of: {', '.join(ptype.stages)})")
        elif stage not in ptype.stages:
            report("error", c, f"stage {stage!r} is not one of: {', '.join(ptype.stages)}")
        if not fm.get("title"):
            report("error", c, "missing `title`")
        for key in ptype.required:
            if not fm.get(key):
                report("error", c, f"missing required `{key}`")

        headings = {h.strip().lower() for h in _HEADING_RE.findall(c["body"])}
        for section in ptype.sections:
            if section.lower() not in headings:
                report("error", c, f"missing section `## {section}`")

        if stage and stage != ptype.initial_stage and re.search(r"^TBD\.\s*$", c["body"], re.MULTILINE):
            report("warning", c, f"stage is {stage!r} but a section still reads `TBD.`")

        if ptype.name == "Decision":
            for key, back in (("supersedes", "superseded_by"), ("superseded_by", "supersedes")):
                target = fm.get(key)
                if not target:
                    continue
                target_id = str(target).lstrip("/").removesuffix(".md")
                other = by_id.get(target_id)
                if other is None:
                    report("error", c, f"`{key}: {target}` does not resolve to a concept in the bundle")
                    continue
                other_back = str(other["frontmatter"].get(back) or "").lstrip("/").removesuffix(".md")
                if other_back != c["concept_id"]:
                    report("error", c, f"`{key}: {target}` is not reciprocated by `{back}` on {target_id}")
            if stage == "superseded" and not fm.get("superseded_by"):
                report("error", c, "stage is 'superseded' but `superseded_by` names no successor")
    return issues


def board(bundle: str | Path) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Group product concepts by type, then by stage in lifecycle order."""
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for c in _concepts(bundle):
        ptype = PRODUCT_TYPES[c["type"]]
        stages = grouped.setdefault(ptype.name, {s: [] for s in ptype.stages})
        stage = str(c["frontmatter"].get(STAGE_KEY) or "?")
        stages.setdefault(stage, []).append(
            {
                "concept_id": c["concept_id"],
                "title": c["title"],
                "issues": _issue_refs(c["frontmatter"]),
                "trust_tier": c["trust_tier"],
            }
        )
    order = list(PRODUCT_TYPES)
    return {k: grouped[k] for k in order if k in grouped}


def decision_log(bundle: str | Path) -> list[dict[str, Any]]:
    """Every decision, oldest first by `decided`, then by number."""
    rows = []
    for c in _concepts(bundle):
        if c["type"] != "Decision":
            continue
        fm = c["frontmatter"]
        rows.append(
            {
                "concept_id": c["concept_id"],
                "title": c["title"],
                "decided": str(fm.get("decided") or ""),
                "stage": str(fm.get(STAGE_KEY) or "?"),
                "superseded_by": str(fm.get("superseded_by") or ""),
                "trust_tier": c["trust_tier"],
            }
        )
    return sorted(rows, key=lambda r: (r["decided"], r["concept_id"]))
