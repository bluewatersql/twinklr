"""Synthetic end-to-end proof for the owner style-group mining command."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _profile(root: Path, *, package_id: str, sequence_id: str) -> Path:
    profile = root / package_id
    _write_json(
        profile / "sequence_metadata.json",
        {
            "package_id": package_id,
            "sequence_file_id": sequence_id,
            "sequence_sha256": f"sha256-{sequence_id}",
            "media_file": "",
            "song": "Synthetic",
            "artist": "Fixture",
        },
    )
    _write_json(profile / "lineage_index.json", {"sequence_file": {"filename": "fixture.xsq"}})
    _write_json(
        profile / "enriched_effect_events.json",
        [
            {
                "effect_event_id": f"{sequence_id}-{index}",
                "target_name": "MegaTree",
                "target_kind": "model",
                "target_semantic_tags": ["tree"],
                "target_pixel_count": 800,
                "layer_index": 0,
                "effect_type": "On",
                "start_ms": index * 1000,
                "end_ms": (index + 1) * 1000,
            }
            for index in range(3)
        ],
    )
    return profile


def test_mining_command_writes_one_grouped_fingerprint_per_owner_declaration(
    tmp_path: Path,
) -> None:
    """The command keeps propensity corpus-wide while partitioning style artifacts."""
    profile_a = _profile(tmp_path, package_id="hash-pack-a", sequence_id="hash-seq-a")
    profile_b = _profile(tmp_path, package_id="hash-pack-b", sequence_id="hash-seq-b")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "sequence_index.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "profile_path": str(profile),
                    "package_id": package_id,
                    "sequence_file_id": sequence_id,
                }
            )
            for profile, package_id, sequence_id in (
                (profile_a, "hash-pack-a", "hash-seq-a"),
                (profile_b, "hash-pack-b", "hash-seq-b"),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    declaration = tmp_path / "owner-style-groups.json"
    _write_json(
        declaration,
        {
            "schema_version": "twinklr.style-groups.v1",
            "groups": [
                {"style_name": "Style A", "selector": {"package_ids": ["hash-pack-a"]}},
                {"style_name": "Style B", "selector": {"package_ids": ["hash-pack-b"]}},
            ],
        },
    )
    output = tmp_path / "staged"
    root = Path(__file__).parents[3]
    subprocess.run(
        [
            sys.executable,
            "scripts/demo_feature_engineering.py",
            "--corpus-dir",
            str(corpus),
            "--output-dir",
            str(output),
            "--style-groups",
            str(declaration),
            "--template-min-instance-count",
            "1",
            "--template-min-distinct-pack-count",
            "1",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    manifest = json.loads((output / "feature_store_manifest.json").read_text())
    assert set(manifest["style_fingerprints"]) == {"Style A", "Style B"}
    assert (output / "style_fingerprint_style_a.json").exists()
    assert (output / "style_fingerprint_style_b.json").exists()
    assert (output / "propensity_index.json").exists()
    report = json.loads((output / "style_fingerprint_report.json").read_text())
    assert all(row["corpus_sequence_count"] == 1 for row in report["styles"])


def test_style_groups_is_the_only_build_action_and_rejects_skip_build(tmp_path: Path) -> None:
    """Help and argument semantics expose one unambiguous grouped-refresh action."""
    root = Path(__file__).parents[3]
    help_result = subprocess.run(
        [sys.executable, "scripts/demo_feature_engineering.py", "--help"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--style-groups" in help_result.stdout
    assert "--refresh-style-fingerprints" not in help_result.stdout

    declaration = tmp_path / "owner-style-groups.json"
    _write_json(
        declaration,
        {
            "schema_version": "twinklr.style-groups.v1",
            "groups": [{"style_name": "Style A", "selector": {"package_ids": ["hash-pack-a"]}}],
        },
    )
    rejected = subprocess.run(
        [
            sys.executable,
            "scripts/demo_feature_engineering.py",
            "--skip-build",
            "--style-groups",
            str(declaration),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 2
    assert "cannot be used with --skip-build" in rejected.stderr
