"""Fixture-backed proof for the owner mining command's rerun protocol."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
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
            "sequence_sha256": "a" * 64,
            "media_file": "",
            "song": "Synthetic",
            "artist": "Fixture",
        },
    )
    _write_json(profile / "lineage_index.json", {"sequence_file": {"filename": "fixture.xsq"}})
    _write_json(profile / "base_effect_events.json", {"events": []})
    _write_json(profile / "effect_statistics.json", {"total_events": 2})
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
                "sequence_sha256": "a" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        corpus / "corpus_manifest.json",
        {
            "manifest_schema_version": "corpus_manifest_v1",
            "corpus_id": "corpus:fixture",
            "source_profile_paths": [str(profile)],
        },
    )
    (corpus / "lineage_index.jsonl").write_text(
        json.dumps(
            {
                "package_id": "content-hash-pkg",
                "sequence_file_id": "content-hash-seq",
                "zip_sha256": "sha256-archive",
                "sequence_sha256": "a" * 64,
                "profile_path": str(profile),
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
        "--owner-mining-run",
        "--no-music-library-index",
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
    provenance = second["provenance"]
    assert provenance["source"]["git_commit"]
    assert provenance["source"]["tracked_diff_sha256"]
    assert provenance["tools"]["scripts/demo_feature_engineering.py"]["sha256"]
    assert provenance["corpus"]["input_fingerprint_sha256"]
    assert provenance["corpus"]["files"]["corpus_manifest.json"]["sha256"]
    assert provenance["corpus"]["files"]["lineage_index.jsonl"]["sha256"]
    assert provenance["profiles"][0]["tree_sha256"]
    assert provenance["music_library_index"]["exists"] is False
    assert verification["input_fingerprint_matches_previous"] is True
    assert verification["source_provenance_matches_previous"] is True
    assert verification["entity_key_digests_match"] is True
    assert verification["entity_content_digests_match"] is True
    assert verification["duplicate_identity_count"] == 0
    assert verification["status"] == "verified"

    external = tmp_path / "outside-owned-output.txt"
    external.write_text("must survive", encoding="utf-8")
    (output / "injected-link").symlink_to(external)
    escaped = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True)
    assert escaped.returncode != 0
    assert "refusing symbolic link in owned output" in escaped.stderr
    assert external.read_text(encoding="utf-8") == "must survive"


def test_mining_command_rejects_non_unified_corpus_without_global_fallback(
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[3]
    incomplete = tmp_path / "not-a-unified-corpus"
    incomplete.mkdir()
    output = tmp_path / "must-not-exist"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/demo_feature_engineering.py",
            "--owner-mining-run",
            "--no-music-library-index",
            "--corpus-dir",
            str(incomplete),
            "--output-dir",
            str(output),
            "--feature-store-db",
            str(output / "feature-store.sqlite"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "explicit unified corpus" in completed.stderr
    assert "sequence_index.jsonl" in completed.stderr
    assert not output.exists()


def test_owner_mining_requires_explicit_music_index_disposition(tmp_path: Path) -> None:
    root = Path(__file__).parents[3]
    corpus = _seed_fixture_corpus(tmp_path)
    output = tmp_path / "must-not-exist"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/demo_feature_engineering.py",
            "--owner-mining-run",
            "--corpus-dir",
            str(corpus),
            "--output-dir",
            str(output),
            "--feature-store-db",
            str(output / "feature-store.sqlite"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "--music-library-index or --no-music-library-index" in completed.stderr
    assert not output.exists()


def test_mining_command_rejects_unowned_existing_output_directory(tmp_path: Path) -> None:
    root = Path(__file__).parents[3]
    corpus = _seed_fixture_corpus(tmp_path)
    output = tmp_path / "existing-output"
    output.mkdir()
    sentinel = output / "owner-data.txt"
    sentinel.write_text("preserve me", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/demo_feature_engineering.py",
            "--owner-mining-run",
            "--no-music-library-index",
            "--corpus-dir",
            str(corpus),
            "--output-dir",
            str(output),
            "--feature-store-db",
            str(output / "feature-store.sqlite"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "dedicated new output directory" in completed.stderr
    assert sentinel.read_text(encoding="utf-8") == "preserve me"


def test_mining_command_rejects_output_inside_live_catalog(tmp_path: Path) -> None:
    root = Path(__file__).parents[3]
    corpus = _seed_fixture_corpus(tmp_path)
    output = root / "catalog" / "templates" / "forbidden-owner-staging"
    assert not output.exists()

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/demo_feature_engineering.py",
            "--owner-mining-run",
            "--no-music-library-index",
            "--corpus-dir",
            str(corpus),
            "--output-dir",
            str(output),
            "--feature-store-db",
            str(output / "feature-store.sqlite"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "owner output overlaps protected root" in completed.stderr
    assert not output.exists()


def test_mining_command_rejects_duplicate_sequence_content_identity(tmp_path: Path) -> None:
    root = Path(__file__).parents[3]
    corpus = _seed_fixture_corpus(tmp_path)
    index_path = corpus / "sequence_index.jsonl"
    duplicate = {
        "profile_path": str(tmp_path / "profile"),
        "package_id": "other-package",
        "sequence_file_id": "other-sequence",
        "sequence_sha256": "a" * 64,
    }
    index_path.write_text(index_path.read_text() + json.dumps(duplicate) + "\n", encoding="utf-8")
    output = tmp_path / "duplicate-output"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/demo_feature_engineering.py",
            "--owner-mining-run",
            "--no-music-library-index",
            "--corpus-dir",
            str(corpus),
            "--output-dir",
            str(output),
            "--feature-store-db",
            str(output / "feature-store.sqlite"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "duplicate sequence content identity" in completed.stderr
    assert not output.exists()


def test_mining_rerun_detects_entity_content_tampering_without_count_change(
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[3]
    corpus = _seed_fixture_corpus(tmp_path)
    output = tmp_path / "tampered-run"
    store = output / "feature-store.sqlite"
    command = [
        sys.executable,
        "scripts/demo_feature_engineering.py",
        "--owner-mining-run",
        "--no-music-library-index",
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
    with sqlite3.connect(store) as connection:
        connection.execute("UPDATE profiles SET song = ?", ("tampered",))
        connection.commit()

    subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
    manifest = json.loads((output / "mining_run_manifest.json").read_text())
    verification = manifest["content_hash_identity"]["verification"]

    assert verification["entity_key_digests_match"] is True
    assert verification["entity_content_digests_match"] is False
    assert verification["verified_unchanged_rerun"] is False
    assert verification["status"] == "changed"
