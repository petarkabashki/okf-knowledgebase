import pytest
from datetime import date
from okf_kb.document import OKFDocument, trust_tier, is_stale, normalize_verified


def test_parse_valid_document():
    raw = """---
type: Role
title: Lead Architect
tags: [ai, lead]
verified:
  by: human:ahormati
  at: 2026-06-25T09:00:00Z
stale_after: 2026-12-31
---

# Summary

This is a test summary.
"""
    doc = OKFDocument.parse(raw)
    assert doc.frontmatter["type"] == "Role"
    assert doc.frontmatter["title"] == "Lead Architect"
    assert "This is a test summary." in doc.body


def test_trust_tier():
    fm_unverified = {"type": "Role"}
    fm_machine = {"type": "Role", "verified": {"by": "process:nightly", "at": "2026-01-01"}}
    fm_human = {"type": "Role", "verified": {"by": "human:ahormati", "at": "2026-01-01"}}

    assert trust_tier(fm_unverified) == "unverified"
    assert trust_tier(fm_machine) == "machine-confirmed"
    assert trust_tier(fm_human) == "human-reviewed"


def test_is_stale():
    fm_not_stale = {"stale_after": "2099-01-01"}
    fm_stale = {"stale_after": "2020-01-01"}

    assert is_stale(fm_not_stale, today=date(2026, 7, 29)) is False
    assert is_stale(fm_stale, today=date(2026, 7, 29)) is True
