"""Filesystem safety at the public owner-run staging boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from twinklr.core.feature_engineering.evidence import (
    clean_owned_output_dir,
    validate_owner_run_paths,
)


def test_owner_output_rejects_live_catalog_child_and_protected_root_overlap(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalog" / "templates"
    corpus = tmp_path / "private-corpus"
    profile = tmp_path / "private-profiles"
    catalog.mkdir(parents=True)
    corpus.mkdir()
    profile.mkdir()

    with pytest.raises(ValueError, match="overlaps protected root"):
        validate_owner_run_paths(
            output_dir=catalog / "candidate-child",
            feature_store_db=catalog / "candidate-child" / "store.sqlite",
            protected_roots=(catalog, corpus, profile),
        )
    with pytest.raises(ValueError, match="overlaps protected root"):
        validate_owner_run_paths(
            output_dir=tmp_path,
            feature_store_db=tmp_path / "store.sqlite",
            protected_roots=(corpus,),
        )


def test_cleanup_rejects_injected_symlink_without_touching_escape_target(tmp_path: Path) -> None:
    output = tmp_path / "owned-output"
    external = tmp_path / "owner-private"
    output.mkdir()
    external.mkdir()
    sentinel = external / "must-survive.txt"
    sentinel.write_text("owner data", encoding="utf-8")
    (output / "escape").symlink_to(external, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        clean_owned_output_dir(output, preserved_paths=())

    assert sentinel.read_text(encoding="utf-8") == "owner data"
    assert (output / "escape").is_symlink()
