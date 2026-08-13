"""Repo-hygiene: no production code defaults to the legacy `data/templates` path.

P1K-T3 repointed every production consumer from the untracked, gitignored
`data/templates/` to the git-tracked `catalog/templates/` catalog. The only
remaining `data/templates` string literals in `packages/`/`scripts/` source
are the *local-extensions overlay* path (see
`TemplateStore.from_catalog_with_local_extensions` and
`catalog/templates/README.md`) — an optional, explicitly-named, untracked
overlay a developer may populate locally. This test allows only those,
labeled overlay references and fails on any other `data/templates` literal.
"""

from __future__ import annotations

from pathlib import Path
import re

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PATTERN = re.compile(r'"data"\s*/\s*"templates"|data/templates')
_ALLOWED_LABEL = re.compile(r"local_extension|overlay", re.IGNORECASE)


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root_name in ("packages", "scripts"):
        root = _REPO_ROOT / root_name
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def test_no_unlabeled_legacy_templates_path_literal() -> None:
    """Every `data/templates` literal in packages/scripts is a labeled local-extensions overlay."""
    offenders: list[str] = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _PATTERN.search(line) and not _ALLOWED_LABEL.search(line):
                offenders.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Found data/templates literal(s) not labeled as the local-extensions overlay "
        "(see catalog/templates/README.md and TemplateStore."
        "from_catalog_with_local_extensions):\n" + "\n".join(offenders)
    )
