from __future__ import annotations

from pathlib import Path
from okf_kb.document import OKFDocument


def generate_index_markdown(dir_path: str | Path, bundle_root: str | Path | None = None) -> str:
    dir_p = Path(dir_path).resolve()
    bundle_p = Path(bundle_root).resolve() if bundle_root else dir_p

    lines = []
    if dir_p == bundle_p:
        lines.append('---')
        lines.append('okf_version: "0.2"')
        lines.append('---')
        lines.append('')
        lines.append(f'# {dir_p.name.title()} Bundle Index')
    else:
        lines.append(f'# {dir_p.name.title()} Directory Index')

    lines.append('')

    # Subdirectories
    subdirs = [d for d in dir_p.iterdir() if d.is_dir() and not d.name.startswith('.')]
    if subdirs:
        lines.append('## Subdirectories')
        lines.append('')
        for sd in sorted(subdirs, key=lambda x: x.name):
            rel = sd.relative_to(dir_p)
            lines.append(f'* [{sd.name}/]({rel}/)')
        lines.append('')

    # Concepts
    files = [f for f in dir_p.glob('*.md') if f.name not in ('index.md', 'log.md', 'README.md')]
    if files:
        lines.append('## Concepts')
        lines.append('')
        for f in sorted(files, key=lambda x: x.name):
            try:
                doc = OKFDocument.parse(f.read_text(encoding='utf-8'))
                title = doc.frontmatter.get('title') or f.stem
                desc = doc.frontmatter.get('description', '')
                desc_str = f" - {desc}" if desc else ""
                lines.append(f'* [{title}]({f.name}){desc_str}')
            except Exception:
                lines.append(f'* [{f.stem}]({f.name})')
        lines.append('')

    return '\n'.join(lines)


def build_bundle_indices(bundle_root: str | Path) -> list[Path]:
    root_p = Path(bundle_root).resolve()
    generated = []

    for d in [root_p] + [p for p in root_p.rglob('*') if p.is_dir() and not p.name.startswith('.')]:
        idx_content = generate_index_markdown(d, bundle_root=root_p)
        idx_path = d / 'index.md'
        idx_path.write_text(idx_content, encoding='utf-8')
        generated.append(idx_path)

    return generated
