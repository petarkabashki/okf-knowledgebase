from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from okf_kb.document import OKFDocument, trust_tier, is_stale


class KnowledgeQueryEngine:
    """Generic query engine for any Open Knowledge Format (OKF v0.2) bundle."""

    def __init__(self, root_path: str | Path):
        self.root_path = Path(root_path).resolve()
        if not self.root_path.exists():
            raise FileNotFoundError(f"Knowledge bundle directory not found: {self.root_path}")

    def scan_documents(self, subfolder: str | None = None) -> list[OKFDocument]:
        """Scan and parse all non-reserved .md files in the bundle or subfolder."""
        search_dir = self.root_path / subfolder if subfolder else self.root_path
        if not search_dir.exists():
            return []

        docs = []
        for p in search_dir.rglob("*.md"):
            if p.name in ("index.md", "log.md", "README.md"):
                continue
            try:
                content = p.read_text(encoding="utf-8")
                rel_path = str(p.relative_to(self.root_path)).replace("\\", "/")
                doc = OKFDocument.parse(content, file_path=rel_path)
                docs.append(doc)
            except Exception:
                continue
        return docs

    def query_concepts(
        self,
        concept_type: str | None = None,
        tag: str | None = None,
        search_term: str | None = None,
        status: str | None = None,
        trust_tier_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query generic concepts with optional filtering by type, tag, term, or trust tier."""
        docs = self.scan_documents()
        results = []

        for doc in docs:
            fm = doc.frontmatter
            c_type = str(fm.get("type", "Concept"))
            c_tags = [str(t).lower() for t in fm.get("tags", [])]
            c_status = str(fm.get("status", "stable"))
            t_tier = trust_tier(fm)
            c_stale = is_stale(fm)

            if concept_type and concept_type.lower() != c_type.lower():
                continue
            if tag and tag.lower() not in c_tags:
                continue
            if status and status.lower() != c_status.lower():
                continue
            if trust_tier_filter and trust_tier_filter.lower() != t_tier.lower():
                continue
            if search_term:
                term_lower = search_term.lower()
                in_title = term_lower in str(fm.get("title", "")).lower()
                in_desc = term_lower in str(fm.get("description", "")).lower()
                in_body = term_lower in doc.body.lower()
                in_path = term_lower in (doc.file_path or "").lower()
                if not (in_title or in_desc or in_body or in_path):
                    continue

            results.append({
                "concept_id": (doc.file_path or "").removesuffix(".md"),
                "file_path": doc.file_path,
                "type": c_type,
                "title": fm.get("title") or Path(doc.file_path or "").stem,
                "description": fm.get("description", ""),
                "resource": fm.get("resource"),
                "tags": fm.get("tags", []),
                "status": c_status,
                "trust_tier": t_tier,
                "is_stale": c_stale,
                "frontmatter": fm,
                "body": doc.body,
            })

        return sorted(results, key=lambda x: x["concept_id"])

    def find_by_resource(self, resource_uri: str) -> list[dict[str, Any]]:
        """Find concepts matching a resource URI."""
        concepts = self.query_concepts()
        return [c for c in concepts if str(c.get("resource", "")).lower() == resource_uri.lower()]

    def extract_links(self) -> list[dict[str, str]]:
        """Extract all markdown internal cross-links between concepts (§6.1)."""
        concepts = self.query_concepts()
        concept_ids = {c["concept_id"] for c in concepts}
        edges = []

        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for c in concepts:
            src_id = c["concept_id"]
            for match in link_pattern.finditer(c["body"]):
                target_path = match.group(2).strip()
                if target_path.startswith("http://") or target_path.startswith("https://"):
                    continue
                clean_target = target_path.lstrip("/").removesuffix(".md")
                if clean_target in concept_ids:
                    edges.append({"source": src_id, "target": clean_target, "label": match.group(1)})

        return edges
