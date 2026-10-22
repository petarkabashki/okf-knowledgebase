"""Provenance tooling for OKF v0.2 bundles (§5.1 sources, §5.2 verified, §5.5 stale_after).

- check_citations: every footnote label resolves to a `sources[].id` (per-claim attribution).
- collect_sources: flatten every source into a verification checklist.
- upcoming: concepts that are stale, or go stale within N days (e.g. deadlines).
- add_verification: append a `verified` event (or a per-source `checked` stamp) in place.
- check_links: liveness check of every external source URL.
"""
from __future__ import annotations

import csv
import io
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from okf_kb.document import normalize_verified
from okf_kb.query import KnowledgeQueryEngine

_FOOTNOTE_REF = re.compile(r"\[\^([^\]\s]+)\](?!:)")
_FOOTNOTE_DEF = re.compile(r"^\[\^([^\]\s]+)\]:", re.MULTILINE)


# --------------------------------------------------------------------------- citations

def _is_cited(source: dict[str, Any], refs: set[str], body: str) -> bool:
    """A source is cited by a keyed footnote, or (e.g. in source tables) by its resource URL in the body."""
    if str(source.get("id")) in refs:
        return True
    res = str(source.get("resource") or "")
    return bool(res) and res in body


def check_citations(path: str | Path) -> list[dict[str, str]]:
    """Return provenance issues: {concept_id, level: error|warning, message}."""
    engine = KnowledgeQueryEngine(path)
    issues: list[dict[str, str]] = []

    for c in engine.query_concepts():
        cid = c["concept_id"]
        fm = c["frontmatter"]
        body = c["body"]

        def add(level: str, msg: str) -> None:
            issues.append({"concept_id": cid, "level": level, "message": msg})

        raw_sources = fm.get("sources") or []
        if not isinstance(raw_sources, list):
            add("error", "`sources` must be a list")
            raw_sources = []

        ids: list[str] = []
        for i, s in enumerate(raw_sources):
            if not isinstance(s, dict):
                add("error", f"sources[{i}] is not a mapping")
                continue
            if not s.get("resource"):
                add("error", f"sources[{i}] ({s.get('id', 'no id')}) is missing `resource`")
            if s.get("id") is not None:
                ids.append(str(s["id"]))

        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            add("error", f"duplicate source id `{dup}`")

        id_set = set(ids)
        refs = set(_FOOTNOTE_REF.findall(body))
        defs = set(_FOOTNOTE_DEF.findall(body))

        for label in sorted(refs - id_set):
            add("error", f"footnote [^{label}] has no matching sources[].id")
        for label in sorted(refs - defs):
            add("warning", f"footnote [^{label}] is referenced but not defined in the body")
        for s in raw_sources:
            if isinstance(s, dict) and s.get("id") is not None and not _is_cited(s, refs, body):
                add("warning", f"source `{s['id']}` is never cited in the body")

    return issues


# --------------------------------------------------------------------------- sources

SOURCE_COLUMNS = [
    "concept_id", "concept_title", "trust_tier", "source_id", "source_title",
    "resource", "author", "quality", "last_modified", "cited", "checked",
]


def collect_sources(path: str | Path, unique: bool = False) -> list[dict[str, Any]]:
    """Flatten every `sources` entry across the bundle into rows."""
    engine = KnowledgeQueryEngine(path)
    rows: list[dict[str, Any]] = []
    for c in engine.query_concepts():
        refs = set(_FOOTNOTE_REF.findall(c["body"]))
        for s in c["frontmatter"].get("sources") or []:
            if not isinstance(s, dict):
                continue
            checked = s.get("checked")
            rows.append({
                "concept_id": c["concept_id"],
                "concept_title": c["title"],
                "trust_tier": c["trust_tier"],
                "source_id": s.get("id", ""),
                "source_title": s.get("title", ""),
                "resource": s.get("resource", ""),
                "author": s.get("author", ""),
                "quality": s.get("quality", ""),
                "last_modified": s.get("last_modified", ""),
                "cited": _is_cited(s, refs, c["body"]),
                "checked": _fmt_checked(checked),
            })
    if unique:
        seen: dict[str, dict[str, Any]] = {}
        for r in rows:
            key = str(r["resource"])
            if key in seen:
                seen[key]["concept_id"] += f"; {r['concept_id']}"
            else:
                seen[key] = dict(r)
        rows = list(seen.values())
    return rows


def _fmt_checked(checked: Any) -> str:
    events = checked if isinstance(checked, list) else [checked] if isinstance(checked, dict) else []
    return "; ".join(f"{e.get('by', '?')}@{str(e.get('at', ''))[:10]}" for e in events if isinstance(e, dict))


def sources_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=SOURCE_COLUMNS, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def sources_to_markdown(rows: list[dict[str, Any]]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    checked = sum(1 for r in rows if r["checked"])
    lines = [
        "---",
        "type: Verification Checklist",
        "title: Source verification checklist",
        f"description: {len(rows)} source row(s), {checked} checked. Regenerate with okf-kb sources --format md.",
        "generated:",
        "  by: process:okf-kb-sources",
        f"  at: {now}",
        "---",
        "",
        "# Source verification checklist",
        "",
    ]
    current = None
    for r in sorted(rows, key=lambda r: (r["concept_id"], str(r["source_id"]))):
        if r["concept_id"] != current:
            current = r["concept_id"]
            lines += ["", f"## {r['concept_title']} (`{current}`, {r['trust_tier']})", ""]
        box = "x" if r["checked"] else " "
        quality = f" — _{r['quality']}_" if r["quality"] else ""
        uncited = " — (not cited)" if not r["cited"] else ""
        lines.append(f"- [{box}] `{r['source_id']}` [{r['source_title'] or r['resource']}]({r['resource']}){quality}{uncited}")
    return "\n".join(lines).strip() + "\n"


# --------------------------------------------------------------------------- upcoming / stale

def _as_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def upcoming(path: str | Path, within_days: int = 30, today: date | None = None,
             field: str = "stale_after") -> list[dict[str, Any]]:
    """Concepts whose `field` date (default stale_after) is past or within N days, soonest first."""
    today = today or date.today()
    horizon = today + timedelta(days=within_days)
    engine = KnowledgeQueryEngine(path)
    out = []
    for c in engine.query_concepts():
        fm = c["frontmatter"]
        d = _as_date(fm.get(field))
        if d is None or d > horizon:
            continue
        out.append({
            "concept_id": c["concept_id"],
            "title": c["title"],
            "date": d,
            "days": (d - today).days,
            "stale": d <= today,
            "programme_status": fm.get("programme_status", ""),
            "deadline": fm.get("deadline", ""),
            "trust_tier": c["trust_tier"],
        })
    return sorted(out, key=lambda r: r["date"])


# --------------------------------------------------------------------------- verify

class _StrLoader(yaml.SafeLoader):
    """SafeLoader that keeps dates/timestamps as strings so round-trips don't reformat them."""


_StrLoader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


class _CompactDumper(yaml.SafeDumper):
    """Dumper that writes date-like strings unquoted (mirrors _StrLoader) and keeps small maps/lists inline."""


_CompactDumper.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeDumper.yaml_implicit_resolvers.items()
}


def _is_scalar(v: Any) -> bool:
    return not isinstance(v, (dict, list))


def _repr_dict(dumper: yaml.SafeDumper, data: dict) -> yaml.Node:
    # PyYAML can't emit ':'-containing strings (timestamps, URLs) unquoted inside flow
    # mappings, so fall back to block style for those to keep values unquoted.
    flow = len(data) <= 3 and all(_is_scalar(v) and ":" not in str(v) for v in data.values())
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=flow)


def _repr_list(dumper: yaml.SafeDumper, data: list) -> yaml.Node:
    flow = all(_is_scalar(v) and ":" not in str(v) for v in data)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


_CompactDumper.add_representer(dict, _repr_dict)
_CompactDumper.add_representer(list, _repr_list)


def _split(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Document has no frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("Unterminated frontmatter")
    fm = yaml.load("\n".join(lines[1:end]), Loader=_StrLoader) or {}
    body = "\n".join(lines[end + 1:])
    return fm, body


def _join(fm: dict[str, Any], body: str) -> str:
    fm_text = yaml.dump(fm, Dumper=_CompactDumper, sort_keys=False, allow_unicode=True, width=1000).rstrip()
    if not body.startswith("\n"):
        body = "\n" + body
    if not body.endswith("\n"):
        body += "\n"
    return f"---\n{fm_text}\n---\n{body}"


def resolve_concept(path: str | Path, concept_id: str) -> Path:
    root = Path(path).resolve()
    cand = root / (concept_id.lstrip("/").removesuffix(".md") + ".md")
    if cand.exists():
        return cand
    matches = [p for p in root.rglob("*.md") if p.stem.lower() == Path(concept_id).stem.lower()
               and p.name not in ("index.md", "log.md", "README.md")]
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(f"Concept not found or ambiguous: {concept_id} ({len(matches)} matches)")


def add_verification(file_path: str | Path, by: str, at: str | None = None,
                     source_id: str | None = None, note: str | None = None) -> dict[str, Any]:
    """Append a verification event to a concept (or a `checked` stamp to one of its sources).

    `by` should follow the actor convention (§7): `human:<id>`, `process:<id>` or `<agent>/<version>`.
    """
    if not (by.startswith("human:") or by.startswith("process:") or "/" in by):
        raise ValueError("`by` must be an actor: human:<id>, process:<id> or <producer>/<version>")
    p = Path(file_path)
    fm, body = _split(p.read_text(encoding="utf-8"))
    at = at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    event: dict[str, Any] = {"by": by, "at": at}
    if note:
        event["note"] = note

    if source_id:
        sources = fm.get("sources") or []
        target = next((s for s in sources if isinstance(s, dict) and str(s.get("id")) == source_id), None)
        if target is None:
            raise KeyError(f"No source with id `{source_id}` in {p}")
        existing = target.get("checked")
        events = existing if isinstance(existing, list) else [existing] if isinstance(existing, dict) else []
        target["checked"] = events + [event]
    else:
        fm["verified"] = normalize_verified(fm) + [event]

    p.write_text(_join(fm, body), encoding="utf-8")
    return fm


# --------------------------------------------------------------------------- internal links

_MD_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)\)")


def check_internal_links(path: str | Path) -> list[dict[str, str]]:
    """Find bundle links (§6.1) whose target file/dir doesn't exist. OKF tolerates these; this lists them."""
    root = Path(path).resolve()
    engine = KnowledgeQueryEngine(root)
    broken = []
    for c in engine.query_concepts():
        here = (root / c["file_path"]).parent
        for m in _MD_LINK.finditer(c["body"]):
            target = m.group(2).split("#", 1)[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue  # external URL, mailto:, pure anchor
            resolved = (root / target.lstrip("/")) if target.startswith("/") else (here / target)
            if not resolved.exists():
                broken.append({"concept_id": c["concept_id"], "label": m.group(1), "target": target})
    return broken


# --------------------------------------------------------------------------- link check

def check_links(path: str | Path, timeout: float = 10.0, workers: int = 8) -> list[dict[str, Any]]:
    """HEAD (falling back to GET) every unique http(s) source URL. Returns status per URL."""
    rows = collect_sources(path, unique=True)
    urls = [r for r in rows if str(r["resource"]).startswith(("http://", "https://"))]

    def probe(row: dict[str, Any]) -> dict[str, Any]:
        url = str(row["resource"])
        result = {"resource": url, "concept_id": row["concept_id"], "status": None, "ok": False, "error": ""}
        for method in ("HEAD", "GET"):
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "okf-kb-linkcheck/0.2"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    result.update(status=resp.status, ok=200 <= resp.status < 400, error="")
                    return result
            except urllib.error.HTTPError as e:
                result.update(status=e.code, ok=False, error=str(e.reason))
                if e.code not in (403, 405, 501):
                    return result
            except Exception as e:  # network errors, timeouts
                result.update(status=None, ok=False, error=type(e).__name__ + ": " + str(e)[:120])
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return sorted(pool.map(probe, urls), key=lambda r: (r["ok"], r["resource"]))


__all__ = [
    "check_citations", "collect_sources", "sources_to_csv", "sources_to_markdown",
    "upcoming", "add_verification", "resolve_concept", "check_links", "check_internal_links",
]
