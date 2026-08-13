#!/usr/bin/env python3
"""Verify all version declaration sites in the workspace agree.

Twinklr's version is declared independently in five places (root workspace,
two sub-package `pyproject.toml` files, and two sub-package `__init__.py`
modules) with no automated sync. This script reads all five and fails loudly
if they disagree, so drift is caught rather than silently ignored.

See build/specs/phase-0-foundation/P0-T4-minimal-ci.md for the task that
added this check, and the file's evidence section for why fixing existing
drift is explicitly out of scope here — this only detects and reports it.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

# (label, file relative to ROOT, regex with one capture group for the version)
SITES: list[tuple[str, str, str]] = [
    ("root pyproject.toml", "pyproject.toml", r'^version\s*=\s*"([^"]+)"'),
    (
        "packages/twinklr/core/pyproject.toml",
        "packages/twinklr/core/pyproject.toml",
        r'^version\s*=\s*"([^"]+)"',
    ),
    (
        "packages/twinklr/cli/pyproject.toml",
        "packages/twinklr/cli/pyproject.toml",
        r'^version\s*=\s*"([^"]+)"',
    ),
    (
        "packages/twinklr/core/__init__.py",
        "packages/twinklr/core/__init__.py",
        r'^__version__\s*=\s*"([^"]+)"',
    ),
    (
        "packages/twinklr/cli/__init__.py",
        "packages/twinklr/cli/__init__.py",
        r'^__version__\s*=\s*"([^"]+)"',
    ),
]


def _read_version(label: str, relpath: str, pattern: str) -> str:
    path = ROOT / relpath
    if not path.is_file():
        print(f"ERROR: version site missing: {label} ({relpath})", file=sys.stderr)
        sys.exit(2)
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        print(
            f"ERROR: could not find a version declaration in {label} ({relpath})",
            file=sys.stderr,
        )
        sys.exit(2)
    return match.group(1)


def main() -> int:
    versions = [
        (label, relpath, _read_version(label, relpath, pattern))
        for label, relpath, pattern in SITES
    ]

    distinct = sorted({version for _, _, version in versions})
    if len(distinct) == 1:
        print(f"OK: all {len(versions)} version declaration sites agree on {distinct[0]!r}")
        return 0

    print(
        f"FAIL: version declaration sites disagree ({len(distinct)} distinct values):",
        file=sys.stderr,
    )
    for label, relpath, version in versions:
        print(f"  {version!r:>10}  {label} ({relpath})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
