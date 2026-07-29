from __future__ import annotations

from pathlib import Path
from okf_kb.document import OKFDocument
from okf_kb.ingest import IngestionPipeline


class KnowledgeManager:
    """Generic manager for adding, archiving, and updating concepts in an OKF bundle."""

    def __init__(self, root_path: str | Path):
        self.root_path = Path(root_path).resolve()
        self.pipeline = IngestionPipeline(self.root_path)

    def add_concept(self, source_file: str | Path, concept_type: str, slug: str, subfolder: str | None = None) -> Path:
        return self.pipeline.ingest_file(source_file, concept_type, slug, subfolder=subfolder)

    def archive_concept(self, relative_path_or_slug: str) -> Path:
        p = Path(relative_path_or_slug)
        if p.suffix != ".md":
            p = p.with_suffix(".md")

        target = self.root_path / p
        if not target.exists():
            # Try searching in subdirectories
            matches = list(self.root_path.rglob(p.name))
            if matches:
                target = matches[0]
            else:
                raise FileNotFoundError(f"Concept file not found: {relative_path_or_slug}")

        archive_dir = self.root_path / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest = archive_dir / target.name
        target.rename(dest)
        return dest
