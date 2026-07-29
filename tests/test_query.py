import pytest
from pathlib import Path
from okf_kb.query import KnowledgeQueryEngine


def test_query_engine(tmp_path):
    tables_dir = tmp_path / "tables"
    tables_dir.mkdir()

    concept1 = """---
type: BigQuery Table
title: Customer Orders
tags: [orders, finance]
description: One row per customer order.
---

# Schema
Customer order records.
"""
    (tables_dir / "orders.md").write_text(concept1, encoding="utf-8")

    engine = KnowledgeQueryEngine(tmp_path)
    concepts = engine.query_concepts(concept_type="BigQuery Table")
    assert len(concepts) == 1
    assert concepts[0]["title"] == "Customer Orders"
    assert "orders" in concepts[0]["tags"]

    tagged = engine.query_concepts(tag="finance")
    assert len(tagged) == 1

    searched = engine.query_concepts(search_term="customer")
    assert len(searched) == 1
