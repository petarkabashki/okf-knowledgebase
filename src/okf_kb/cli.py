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


if __name__ == "__main__":
    cli()
