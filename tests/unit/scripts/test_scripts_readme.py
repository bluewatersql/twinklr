"""Ensure every maintained script remains discoverable by exact path."""

from pathlib import Path


def test_scripts_readme_indexes_every_tracked_source_and_note() -> None:
    scripts_root = Path("scripts")
    readme = (scripts_root / "README.md").read_text(encoding="utf-8")
    indexed_files = {
        path.relative_to(scripts_root).as_posix()
        for path in scripts_root.rglob("*")
        if path.is_file()
        and path.name != "README.md"
        and path.suffix in {".py", ".md"}
        and "__pycache__" not in path.parts
    }

    missing = sorted(
        path
        for path in indexed_files
        if f"`{path}`" not in readme and f"`scripts/{path}`" not in readme
    )
    assert not missing, f"scripts/README.md is missing: {missing}"
