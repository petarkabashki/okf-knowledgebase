from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from okf_kb.document import OKFDocument


class IngestionPipeline:
    """Generic ingestion pipeline for any OKF concept document."""

    def __init__(self, target_dir: str | Path):
        self.target_dir = Path(target_dir).resolve()
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def ingest_file(
        self,
        source_path: str | Path,
        concept_type: str,
        slug: str,
        subfolder: str | None = None,
        archive_dir: str | Path | None = None,
    ) -> Path:
        source_p = Path(source_path).resolve()
        if not source_p.exists():
            raise FileNotFoundError(f"Source file not found: {source_p}")

        content = source_p.read_text(encoding="utf-8")
        doc = OKFDocument.parse(content)

        # Set default concept type if missing
        if "type" not in doc.frontmatter:
            doc.frontmatter["type"] = concept_type

        target_subfolder = subfolder or (concept_type.lower() + "s")
        out_dir = self.target_dir / target_subfolder
        out_dir.mkdir(parents=True, exist_ok=True)

        out_path = out_dir / f"{slug}.md"
        out_path.write_text(doc.serialize(), encoding="utf-8")

        if archive_dir:
            arc_path = Path(archive_dir).resolve()
            arc_path.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = arc_path / f"{ts}_{source_p.name}"
            shutil.move(str(source_p), str(dest))

        return out_path
