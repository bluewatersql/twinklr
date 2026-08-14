"""Fixture-backed proof for the owner mining command's rerun protocol."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_fixture_corpus(tmp_path: Path) -> Path:
    profile = tmp_path / "profile"
    _write_json(
        profile / "sequence_metadata.json",
        {
            "package_id": "content-hash-pkg",
            "sequence_file_id": "content-hash-seq",
            "sequence_sha256": "sha256-sequence",
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
                "effect_event_id": "event-1",
                "target_name": "MegaTree",
                "target_kind": "model",
                "target_semantic_tags": ["tree", "main"],
                "target_pixel_count": 800,
                "layer_index": 0,
                "effect_type": "On",
                "start_ms": 0,
                "end_ms": 1000,
            },
            {
                "effect_event_id": "event-2",
                "target_name": "MegaTree",
                "target_kind": "model",
                "target_semantic_tags": ["tree", "main"],
                "target_pixel_count": 800,
                "layer_index": 0,
                "effect_type": "On",
                "start_ms": 1000,
                "end_ms": 2000,
            },
        ],
    )
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "sequence_index.jsonl").write_text(
        json.dumps(
            {
                "profile_path": str(profile),
                "package_id": "content-hash-pkg",
                "sequence_file_id": "content-hash-seq",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return corpus


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_mining_command_twice_preserves_store_and_live_catalog(tmp_path: Path) -> None:
    root = Path(__file__).parents[3]
    corpus = _seed_fixture_corpus(tmp_path)
    output = tmp_path / "staged-run"
    store = output / "feature-store.sqlite"
    live_catalog = root / "catalog" / "templates"
    catalog_before = _tree_hash(live_catalog)
    command = [
        sys.executable,
        "scripts/demo_feature_engineering.py",
        "--corpus-dir",
        str(corpus),
        "--output-dir",
        str(output),
        "--feature-store-db",
        str(store),
        "--template-min-instance-count",
        "1",
        "--template-min-distinct-pack-count",
        "1",
    ]

    subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
    first = json.loads((output / "mining_run_manifest.json").read_text())
    first_stats = first["feature_store_snapshots"]["after"]["stats"]
    assert store.exists()
    assert first["content_hash_identity"]["verification"]["status"] == (
        "needs_identical_second_run"
    )

    subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
    second = json.loads((output / "mining_run_manifest.json").read_text())
    verification = second["content_hash_identity"]["verification"]

    assert second["feature_store_snapshots"]["before"]["stats"] == first_stats
    assert second["feature_store_snapshots"]["after"]["stats"] == first_stats
    assert verification["before_matches_previous_after"] is True
    assert verification["after_matches_before"] is True
    assert verification["verified_unchanged_rerun"] is True
    assert verification["status"] == "verified"
    assert second["live_catalog_immutability"]["unchanged"] is True
    assert _tree_hash(live_catalog) == catalog_before
    artifact_paths = {
        row["path"] for row in second["candidate_staging"]["recursive_artifacts"]["files"]
    }
    assert "content-hash-pkg/content-hash-seq/feature_bundle.json" in artifact_paths
    assert second["invocation"]["exact_command"] == second["invocation"]["exact_rerun_command"]
    assert second["invocation"]["effective_options"]["recipe_promotion_min_support"] == 2
