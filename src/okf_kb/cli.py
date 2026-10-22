from __future__ import annotations

from pathlib import Path
import click
from rich.console import Console
from rich.table import Table

from okf_kb.document import OKFDocument, trust_tier, is_stale
from okf_kb.query import KnowledgeQueryEngine
from okf_kb.ingest import IngestionPipeline
from okf_kb.manage import KnowledgeManager
from okf_kb.viewer import generate_bundle_visualization
from okf_kb.index import build_bundle_indices
from okf_kb.product_cli import product
from okf_kb.provenance import (
    add_verification,
    check_citations,
    check_internal_links,
    check_links,
    collect_sources,
    resolve_concept,
    sources_to_csv,
    sources_to_markdown,
    upcoming,
)

console = Console()


@click.group()
def cli():
    """OKF Knowledgebase CLI (OKF v0.2) — Generic bundle parser, query engine, and visualizer"""
    pass


@cli.command("list")
@click.option("--path", "-p", default=".", help="Path to OKF bundle root")
@click.option("--type", "-t", "concept_type", help="Filter by concept type (e.g. Metric, Table, Playbook)")
@click.option("--tag", help="Filter by tag")
@click.option("--search", "-s", help="Search in title, description, body, or tags")
@click.option("--status", help="Filter by status (draft, stable, deprecated)")
def list_concepts(path: str, concept_type: str | None, tag: str | None, search: str | None, status: str | None):
    """List concepts in an OKF bundle with generic filters"""
    engine = KnowledgeQueryEngine(path)
    concepts = engine.query_concepts(concept_type=concept_type, tag=tag, search_term=search, status=status)

    table = Table(title=f"OKF Concepts in {path}")
    table.add_column("Concept ID", style="cyan")
    table.add_column("Type", style="bold green")
    table.add_column("Title", style="white")
    table.add_column("Status", style="yellow")
    table.add_column("Trust Tier", style="magenta")

    for c in concepts:
        table.add_row(c["concept_id"], c["type"], c["title"], c["status"], c["trust_tier"])

    console.print(table)


@cli.command()
@click.argument("concept_id")
@click.option("--path", "-p", default=".", help="Path to OKF bundle root")
def show(concept_id: str, path: str):
    """Show details of a specific concept in an OKF bundle"""
    engine = KnowledgeQueryEngine(path)
    concepts = engine.query_concepts()
    matched = [c for c in concepts if c["concept_id"].lower() == concept_id.lower() or Path(c["file_path"] or "").stem.lower() == concept_id.lower()]

    if not matched:
        console.print(f"[bold red]Concept not found:[/] {concept_id}")
        return

    c = matched[0]
    console.print(f"[bold cyan]ID:[/] {c['concept_id']}")
    console.print(f"[bold green]Type:[/] {c['type']}")
    console.print(f"[bold white]Title:[/] {c['title']}")
    console.print(f"[bold yellow]Status:[/] {c['status']} | [bold magenta]Trust:[/] {c['trust_tier']}")
    if c["description"]:
        console.print(f"[italic]{c['description']}[/italic]")
    console.print("\n[bold]Body:[/]")
    console.print(c["body"])


@cli.command()
@click.option("--file", "-f", required=True, help="Path to source Markdown concept file")
@click.option("--type", "-t", required=True, help="Concept type (e.g. Metric, Table, Playbook, Role, Project)")
@click.option("--slug", required=True, help="Concept slug / filename")
@click.option("--subfolder", help="Target subdirectory within bundle")
@click.option("--target", "-p", default=".", help="Path to target OKF bundle root")
@click.option("--archive", help="Optional archive directory for source file")
def ingest(file: str, type: str, slug: str, subfolder: str | None, target: str, archive: str | None):
    """Ingest any Markdown document into an OKF bundle"""
    pipeline = IngestionPipeline(target)
    out_path = pipeline.ingest_file(file, type, slug, subfolder=subfolder, archive_dir=archive)
    console.print(f"[bold green]Ingested concept ({type}) into:[/] {out_path}")


@cli.command()
@click.argument("concept_id")
@click.option("--path", "-p", default=".", help="Path to OKF bundle root")
def archive(concept_id: str, path: str):
    """Archive a concept in an OKF bundle"""
    mgr = KnowledgeManager(path)
    dest = mgr.archive_concept(concept_id)
    console.print(f"[bold yellow]Archived concept {concept_id} to:[/] {dest}")


@cli.command()
@click.option("--bundle", "-b", required=True, help="Path to OKF bundle root")
@click.option("--out", "-o", help="Output HTML path")
def visualize(bundle: str, out: str | None):
    """Render an interactive Cytoscape.js HTML graph visualization of an OKF bundle"""
    out_file = generate_bundle_visualization(bundle, out_path=out)
    console.print(f"[bold green]Visualizer generated successfully:[/] {out_file}")


@cli.command()
@click.argument("path", default=".")
def validate(path: str):
    """Validate OKF v0.2 conformance of a directory or bundle"""
    root_p = Path(path).resolve()
    count = 0
    errors = 0
    warnings = 0

    for f in root_p.rglob("*.md"):
        if f.name in ("index.md", "log.md", "README.md"):
            continue
        count += 1
        try:
            doc = OKFDocument.parse(f.read_text(encoding="utf-8"))
            w = doc.validate(strict=False)
            if w:
                warnings += len(w)
                console.print(f"[yellow]WARNING[/] {f.relative_to(root_p)}: {', '.join(w)}")
        except Exception as e:
            errors += 1
            console.print(f"[bold red]ERROR[/] {f.relative_to(root_p)}: {e}")

    console.print(f"\n[bold]Validation complete:[/] {count} document(s) checked. {errors} error(s), {warnings} warning(s).")


@cli.command()
@click.argument("bundle", default=".")
def index(bundle: str):
    """Generate or update index.md files for progressive disclosure (§8)"""
    generated = build_bundle_indices(bundle)
    console.print(f"[bold green]Updated {len(generated)} index.md file(s).[/]")


@cli.command()
@click.argument("path", default=".")
@click.option("--strict", is_flag=True, help="Treat warnings (uncited sources, undefined footnotes) as failures")
def citations(path: str, strict: bool):
    """Check per-claim attribution: every footnote resolves to a sources[].id (§5.1)"""
    issues = check_citations(path)
    errors = [i for i in issues if i["level"] == "error"]
    warns = [i for i in issues if i["level"] == "warning"]
    for i in issues:
        colour = "bold red" if i["level"] == "error" else "yellow"
        console.print(f"[{colour}]{i['level'].upper()}[/] {i['concept_id']}: {i['message']}")
    console.print(f"\n[bold]Citation check:[/] {len(errors)} error(s), {len(warns)} warning(s).")
    if errors or (strict and warns):
        raise SystemExit(1)


@cli.command()
@click.argument("path", default=".")
@click.option("--format", "fmt", type=click.Choice(["table", "csv", "md"]), default="table")
@click.option("--unique", is_flag=True, help="One row per distinct resource URL")
@click.option("--out", "-o", help="Write to file instead of stdout")
def sources(path: str, fmt: str, unique: bool, out: str | None):
    """Export every source across the bundle as a verification checklist"""
    rows = collect_sources(path, unique=unique)
    if fmt == "csv":
        text = sources_to_csv(rows)
    elif fmt == "md":
        text = sources_to_markdown(rows)
    else:
        table = Table(title=f"Sources in {path} ({len(rows)})")
        for col in ("concept_id", "source_id", "quality", "cited", "checked", "resource"):
            table.add_column(col)
        for r in rows:
            table.add_row(str(r["concept_id"]), str(r["source_id"]), str(r["quality"]),
                          "yes" if r["cited"] else "no", r["checked"], str(r["resource"]))
        console.print(table)
        return
    if out:
        Path(out).write_text(text, encoding="utf-8")
        console.print(f"[bold green]Wrote {len(rows)} source row(s) to:[/] {out}")
    else:
        click.echo(text)


@cli.command("upcoming")
@click.argument("path", default=".")
@click.option("--within", "within_days", default=30, show_default=True, help="Days ahead to look")
@click.option("--field", default="stale_after", show_default=True, help="Date field to use (e.g. deadline)")
def upcoming_cmd(path: str, within_days: int, field: str):
    """List concepts that are stale or go stale (or hit a date field) within N days (§5.5)"""
    rows = upcoming(path, within_days=within_days, field=field)
    table = Table(title=f"{field} within {within_days} days")
    for col in ("Date", "Days", "Concept", "Status", "Trust Tier"):
        table.add_column(col)
    for r in rows:
        days = "[bold red]stale[/]" if r["stale"] else str(r["days"])
        table.add_row(str(r["date"]), days, f"{r['title']} ({r['concept_id']})",
                      str(r["programme_status"]), r["trust_tier"])
    console.print(table)


@cli.command()
@click.argument("concept_id")
@click.option("--by", required=True, help="Actor, e.g. human:peter (§7)")
@click.option("--source", "source_id", help="Stamp one source as checked instead of the whole concept")
@click.option("--note", help="Optional note recorded with the event")
@click.option("--path", "-p", default=".", help="Path to OKF bundle root")
def verify(concept_id: str, by: str, source_id: str | None, note: str | None, path: str):
    """Record a verification event on a concept (§5.2), or a checked stamp on one source"""
    f = resolve_concept(path, concept_id)
    fm = add_verification(f, by=by, source_id=source_id, note=note)
    what = f"source `{source_id}` of " if source_id else ""
    console.print(f"[bold green]Verified {what}{f}[/] — trust tier now [magenta]{trust_tier(fm)}[/]")


@cli.command()
@click.argument("path", default=".")
@click.option("--timeout", default=10.0, show_default=True)
@click.option("--workers", default=8, show_default=True)
@click.option("--only-broken", is_flag=True)
def linkcheck(path: str, timeout: float, workers: int, only_broken: bool):
    """Check that every external source URL still resolves"""
    results = check_links(path, timeout=timeout, workers=workers)
    table = Table(title=f"Source link check ({len(results)} URLs)")
    for col in ("OK", "Status", "URL", "Used by", "Error"):
        table.add_column(col)
    for r in results:
        if only_broken and r["ok"]:
            continue
        table.add_row("✓" if r["ok"] else "[red]✗[/]", str(r["status"] or "-"), r["resource"],
                      r["concept_id"], r["error"])
    console.print(table)
    if any(not r["ok"] for r in results):
        raise SystemExit(1)


@cli.command()
@click.argument("path", default=".")
def deadlinks(path: str):
    """List bundle-internal links whose target doesn't exist (§6.1 tolerates them; this surfaces them)"""
    broken = check_internal_links(path)
    for b in broken:
        console.print(f"[yellow]BROKEN[/] {b['concept_id']}: [{b['label']}]({b['target']})")
    console.print(f"\n[bold]{len(broken)} broken internal link(s).[/]")


cli.add_command(product)


if __name__ == "__main__":
    cli()
