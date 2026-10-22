"""`okf-kb product ...` commands for the product profile (see product.py)."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from okf_kb.product import PRODUCT_TYPES, board, check_bundle, decision_log, new_concept

console = Console()


@click.group()
def product():
    """Product profile: briefs, directions, ideas, features and decision records"""


@product.command("new")
@click.argument("type_name", metavar="TYPE")
@click.argument("slug")
@click.option("--title", required=True)
@click.option("--by", required=True, help="Actor writing it, e.g. human:peter or agent/model (§7)")
@click.option("--description", default="")
@click.option("--path", "-p", default=".", help="Path to the product bundle root")
def new_cmd(type_name: str, slug: str, title: str, by: str, description: str, path: str):
    """Scaffold a concept. TYPE: one of the profile's types, or its folder name (e.g. decisions)"""
    target = new_concept(path, type_name, slug, title=title, by=by, description=description)
    console.print(f"[bold green]Created[/] {target}")


@product.command("check")
@click.argument("path", default=".")
@click.option("--strict", is_flag=True, help="Treat warnings as failures")
def check_cmd(path: str, strict: bool):
    """Validate stages, required keys, sections and decision supersession links"""
    issues = check_bundle(path)
    for i in issues:
        colour = "bold red" if i["level"] == "error" else "yellow"
        console.print(f"[{colour}]{i['level'].upper()}[/] {i['concept_id']}: {i['message']}")
    errors = [i for i in issues if i["level"] == "error"]
    warns = [i for i in issues if i["level"] == "warning"]
    console.print(f"\n[bold]Product check:[/] {len(errors)} error(s), {len(warns)} warning(s).")
    if errors or (strict and warns):
        raise SystemExit(1)


@product.command("board")
@click.argument("path", default=".")
def board_cmd(path: str):
    """Show every product concept grouped by type and lifecycle stage"""
    for type_name, stages in board(path).items():
        table = Table(title=type_name)
        table.add_column("Stage", style="yellow")
        table.add_column("Concept", style="cyan")
        table.add_column("Issues")
        table.add_column("Trust", style="magenta")
        for stage, rows in stages.items():
            for r in rows:
                table.add_row(stage, f"{r['title']} ({r['concept_id']})", ", ".join(r["issues"]), r["trust_tier"])
        console.print(table)


@product.command("decisions")
@click.argument("path", default=".")
def decisions_cmd(path: str):
    """List decision records in the order they were made"""
    table = Table(title="Decision log")
    for col in ("Decided", "Stage", "Decision", "Superseded by", "Trust"):
        table.add_column(col)
    for r in decision_log(path):
        table.add_row(r["decided"], r["stage"], f"{r['title']} ({r['concept_id']})", r["superseded_by"], r["trust_tier"])
    console.print(table)


@product.command("types")
def types_cmd():
    """List the profile's concept types, folders, stages and required sections"""
    table = Table(title="Product profile types")
    for col in ("Type", "Folder", "Stages", "Sections"):
        table.add_column(col)
    for t in PRODUCT_TYPES.values():
        table.add_row(t.name, t.subdir or "(root)", " > ".join(t.stages), ", ".join(t.sections))
    console.print(table)
