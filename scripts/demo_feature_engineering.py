#!/usr/bin/env python3
"""Run a feature-engineering demo with human-readable summaries."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
from dataclasses import fields
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
import time
from typing import Any, Literal, cast

from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.feature_engineering.models import MusicLibraryIndex
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)
from twinklr.core.feature_engineering.style_groups import load_style_group_declaration
from twinklr.core.profiling.unify import CorpusBuildOptions, ProfileCorpusBuilder

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "features" / "demo_feature_engineering"
_MUSIC_INDEX_PATH = ROOT / "data" / "music" / "music_library_index.json"
_UNIFIED_CORPUS_FILES = ("sequence_index.jsonl", "corpus_manifest.json", "lineage_index.jsonl")
_PROFILE_IDENTITY_FILES = (
    "sequence_metadata.json",
    "lineage_index.json",
    "base_effect_events.json",
    "enriched_effect_events.json",
    "effect_statistics.json",
)
_TOOL_PATHS = (
    "scripts/demo_feature_engineering.py",
    "scripts/report_quality_gate_distributions.py",
    "packages/twinklr/core/feature_engineering/quality_gate_distributions.py",
)


def _load_music_library_index(path: Path | None = _MUSIC_INDEX_PATH) -> MusicLibraryIndex | None:
    """Load the pre-built music library index if available."""
    if path is None:
        print("  [info] Music library index explicitly disabled.")
        return None
    if not path.exists():
        print(
            f"  [info] No music library index at {path}\n"
            "         Run: uv run python scripts/build/build_music_library_index.py"
        )
        return None
    index = MusicLibraryIndex.model_validate_json(path.read_text())
    tagged = sum(1 for e in index.entries if e.title)
    print(
        f"  [info] Loaded music library index: {len(index.entries)} files ({tagged} with metadata)"
    )
    return index


def _ensure_corpus(corpus_dir: Path) -> Path:
    """Build the profile corpus if sequence_index.jsonl is missing.

    Returns the resolved corpus directory (which may differ from *corpus_dir*
    when the builder auto-detects a schema version).
    """
    index_path = corpus_dir / "sequence_index.jsonl"
    if index_path.exists():
        return corpus_dir

    profiles_root = ROOT / "data" / "profiles"
    if not profiles_root.exists():
        raise FileNotFoundError(
            f"Neither corpus ({corpus_dir}) nor profiles root ({profiles_root}) exist. "
            "Run sequence profiling first: python scripts/demo_profiling.py"
        )

    print(f"  [auto] Corpus index missing at {corpus_dir.relative_to(ROOT)}")
    print(f"  [auto] Building corpus from {profiles_root.relative_to(ROOT)} ...")
    builder = ProfileCorpusBuilder(CorpusBuildOptions())
    corpus_output_root = profiles_root / "corpus"
    results = builder.build(profiles_root=profiles_root, output_root=corpus_output_root)
    if not results:
        raise RuntimeError("Corpus build produced no results — check data/profiles/ for profiles.")
    for result in results:
        print(
            f"  [auto] Built corpus: {result.schema_version} "
            f"({result.sequence_count} sequences) → {result.output_dir}"
        )
    best = results[0]
    if corpus_dir.name in {r.schema_version for r in results}:
        return corpus_dir
    print(f"  [auto] Using corpus: {best.output_dir.relative_to(ROOT)}")
    return cast("Path", best.output_dir)


def _require_explicit_unified_corpus(corpus_dir: Path) -> list[dict[str, Any]]:
    """Validate the owner-run corpus contract without falling back to global data."""
    missing = [name for name in _UNIFIED_CORPUS_FILES if not (corpus_dir / name).is_file()]
    if missing:
        raise ValueError(
            "--owner-mining-run requires an explicit unified corpus containing "
            + ", ".join(_UNIFIED_CORPUS_FILES)
            + f"; missing {', '.join(missing)} under {corpus_dir}"
        )
    rows = _read_jsonl(corpus_dir / "sequence_index.jsonl")
    if not rows:
        raise ValueError("explicit unified corpus sequence_index.jsonl is empty")
    lineage_rows = _read_jsonl(corpus_dir / "lineage_index.jsonl")
    if not lineage_rows:
        raise ValueError("explicit unified corpus lineage_index.jsonl is empty")
    logical: set[tuple[str, str]] = set()
    content: set[str] = set()
    for row in rows:
        key = (str(row.get("package_id", "")), str(row.get("sequence_file_id", "")))
        if not all(key):
            raise ValueError("unified corpus row is missing package_id or sequence_file_id")
        if key in logical:
            raise ValueError(f"duplicate logical sequence identity: {key[0]}/{key[1]}")
        logical.add(key)
        sequence_sha = str(row.get("sequence_sha256", ""))
        if not sequence_sha:
            raise ValueError(f"unified corpus row {key[0]}/{key[1]} lacks sequence_sha256")
        if sequence_sha in content:
            raise ValueError(f"duplicate sequence content identity: {sequence_sha}")
        content.add(sequence_sha)
        profile_path = Path(str(row.get("profile_path", ""))).resolve()
        if not profile_path.is_dir():
            raise ValueError(f"profile path does not exist for {key[0]}/{key[1]}: {profile_path}")
        missing_profile = [
            name for name in _PROFILE_IDENTITY_FILES if not (profile_path / name).is_file()
        ]
        if missing_profile:
            raise ValueError(
                f"profile {profile_path} is incomplete; missing {', '.join(missing_profile)}"
            )
        metadata = _read_json(profile_path / "sequence_metadata.json")
        metadata_identity = (
            str(metadata.get("package_id", "")),
            str(metadata.get("sequence_file_id", "")),
            str(metadata.get("sequence_sha256", "")),
        )
        if metadata_identity != (*key, sequence_sha):
            raise ValueError(f"profile identity disagrees with unified index for {key[0]}/{key[1]}")
    lineage_identities = {
        (str(row.get("package_id", "")), str(row.get("sequence_file_id", "")))
        for row in lineage_rows
    }
    if len(lineage_rows) != len(lineage_identities):
        raise ValueError("lineage_index.jsonl contains duplicate logical identities")
    if lineage_identities != logical:
        raise ValueError("lineage_index.jsonl identities disagree with sequence_index.jsonl")
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run feature-engineering demo with reporting.")
    parser.add_argument(
        "--owner-mining-run",
        action="store_true",
        help=(
            "Enable the fail-closed P2K-T2 owner evidence contract: explicit unified corpus, "
            "dedicated output, SQLite identity verification, and complete provenance."
        ),
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("data/profiles/corpus/v0_effectdb_structured_1"),
        help="Unified profile corpus dir (required unless --skip-build).",
    )
    music_group = parser.add_mutually_exclusive_group()
    music_group.add_argument(
        "--music-library-index",
        type=Path,
        default=None,
        help="Explicit music-library index used by owner mode.",
    )
    music_group.add_argument(
        "--no-music-library-index",
        action="store_true",
        help="Explicitly declare that the owner run has no music-library index.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--style-groups",
        type=Path,
        default=None,
        help=(
            "Owner-authored JSON declaration that runs per-style fingerprint extraction; "
            "requires a build (incompatible with --skip-build)."
        ),
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip pipeline run and report from existing artifacts in output-dir.",
    )
    parser.add_argument(
        "--run-audio-analysis",
        action="store_true",
        help="Run audio analysis during build (off by default for faster demo).",
    )
    parser.add_argument(
        "--template-min-instance-count",
        type=int,
        default=2,
        help="Minimum phrase instances per mined template.",
    )
    parser.add_argument(
        "--template-min-distinct-pack-count",
        type=int,
        default=1,
        help="Minimum distinct packs per mined template.",
    )
    parser.add_argument(
        "--quality-max-unknown-effect-family-ratio",
        type=float,
        default=0.02,
        help="Maximum unknown effect-family ratio quality threshold.",
    )
    parser.add_argument(
        "--quality-max-unknown-motion-ratio",
        type=float,
        default=0.02,
        help="Maximum unknown motion-class ratio quality threshold.",
    )
    parser.add_argument(
        "--quality-max-single-unknown-effect-type-ratio",
        type=float,
        default=0.01,
        help="Maximum ratio allowed for any one unknown effect type.",
    )
    parser.add_argument(
        "--quality-max-low-support-template-ratio",
        type=float,
        default=None,
        help="Maximum low-support template ratio quality threshold (None = off).",
    )
    parser.add_argument(
        "--quality-max-high-concentration-template-ratio",
        type=float,
        default=None,
        help="Maximum high-concentration template ratio quality threshold (None = off).",
    )
    parser.add_argument(
        "--quality-max-high-variance-template-ratio",
        type=float,
        default=None,
        help="Maximum high-variance template ratio quality threshold (None = off).",
    )
    parser.add_argument(
        "--quality-max-over-generic-template-ratio",
        type=float,
        default=None,
        help="Maximum over-generic template ratio quality threshold (None = off).",
    )
    parser.add_argument(
        "--quality-diagnostics-gate-mode",
        choices=["enforce", "warn"],
        default="warn",
        help="Gate mode for diagnostics-based quality checks (default: warn).",
    )
    parser.add_argument("--top-n", type=int, default=10, help="Top-N rows to show in summaries.")
    parser.add_argument(
        "--feature-store-db",
        type=Path,
        default=None,
        help="SQLite feature store path (enables store).",
    )
    parser.add_argument(
        "--feature-store-backend",
        type=str,
        default=None,
        help="Feature store backend (default: sqlite when --feature-store-db set).",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        value = json.loads(stripped)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _json_ready(value: object) -> object:
    """Convert nested option values into deterministic JSON-compatible data."""
    if isinstance(value, Path):
        return str(value.resolve())
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_ready(model_dump(mode="json"))
    return value


def _effective_options(options: FeatureEngineeringPipelineOptions) -> dict[str, object]:
    """Serialize every effective FE dataclass option, including defaults."""
    return {
        field.name: _json_ready(getattr(options, field.name))
        for field in fields(FeatureEngineeringPipelineOptions)
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_snapshot(root: Path) -> dict[str, object]:
    """Measure a recursive tree using both per-file and aggregate content hashes."""
    if not root.exists():
        return {"root": str(root), "exists": False, "file_count": 0, "sha256": None, "files": []}
    files: list[dict[str, object]] = []
    aggregate = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root).as_posix()
        digest = _sha256_file(path)
        size = path.stat().st_size
        files.append({"path": relative, "size_bytes": size, "sha256": digest})
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\0")
    return {
        "root": str(root),
        "exists": True,
        "file_count": len(files),
        "sha256": aggregate.hexdigest(),
        "files": files,
    }


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=False
    )
    return completed.stdout.decode("utf-8", errors="strict").strip()


def _source_provenance() -> dict[str, object]:
    tracked_diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    tools: dict[str, object] = {}
    for relative in _TOOL_PATHS:
        path = ROOT / relative
        tools[relative] = {
            "path": str(path),
            "exists": path.is_file(),
            "sha256": _sha256_file(path) if path.is_file() else None,
        }
    return {
        "source": {
            "git_commit": _git_output("rev-parse", "HEAD"),
            "git_tree": _git_output("rev-parse", "HEAD^{tree}"),
            "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        },
        "tools": tools,
    }


def _input_provenance(
    corpus_dir: Path,
    rows: Sequence[dict[str, Any]],
    music_index_path: Path | None,
) -> dict[str, object]:
    corpus_files = {
        name: {
            "path": str((corpus_dir / name).resolve()),
            "size_bytes": (corpus_dir / name).stat().st_size,
            "sha256": _sha256_file(corpus_dir / name),
        }
        for name in _UNIFIED_CORPUS_FILES
    }
    profiles: list[dict[str, object]] = []
    for row in sorted(
        rows, key=lambda item: (str(item["package_id"]), str(item["sequence_file_id"]))
    ):
        profile_path = Path(str(row["profile_path"])).resolve()
        snapshot = _tree_snapshot(profile_path)
        profiles.append(
            {
                "package_id": str(row["package_id"]),
                "sequence_file_id": str(row["sequence_file_id"]),
                "sequence_sha256": str(row["sequence_sha256"]),
                "path": str(profile_path),
                "tree_sha256": snapshot["sha256"],
                "file_count": snapshot["file_count"],
                "files": snapshot["files"],
            }
        )
    music = {
        "path": str(music_index_path) if music_index_path is not None else None,
        "exists": music_index_path is not None,
        "size_bytes": music_index_path.stat().st_size if music_index_path is not None else None,
        "sha256": _sha256_file(music_index_path) if music_index_path is not None else None,
        "explicitly_disabled": music_index_path is None,
    }
    fingerprint_material = {
        "corpus_tree_sha256": _tree_snapshot(corpus_dir)["sha256"],
        "corpus_files": corpus_files,
        "profiles": profiles,
        "music_library_index": music,
    }
    return {
        "corpus": {
            "path": str(corpus_dir),
            "tree_sha256": fingerprint_material["corpus_tree_sha256"],
            "files": corpus_files,
            "input_fingerprint_sha256": _canonical_sha256(fingerprint_material),
        },
        "profiles": profiles,
        "music_library_index": music,
    }


def _validate_owner_output_dir(
    *,
    output_dir: Path,
    feature_store_db: Path | None,
    previous_manifest: dict[str, Any] | None,
    input_fingerprint: str,
) -> None:
    if feature_store_db is None:
        raise ValueError("--owner-mining-run requires --feature-store-db")
    try:
        feature_store_db.resolve().relative_to(output_dir.resolve())
    except ValueError as exc:
        raise ValueError(
            "--owner-mining-run requires the SQLite store inside its dedicated output directory"
        ) from exc
    if not output_dir.exists():
        return
    if previous_manifest is None:
        raise ValueError(
            "--owner-mining-run requires a dedicated new output directory; refusing to clean "
            f"unowned existing path {output_dir}"
        )
    prior_output = previous_manifest.get("output_dir")
    prior_provenance = previous_manifest.get("provenance")
    prior_corpus = prior_provenance.get("corpus") if isinstance(prior_provenance, dict) else None
    prior_fingerprint = (
        prior_corpus.get("input_fingerprint_sha256") if isinstance(prior_corpus, dict) else None
    )
    if prior_output != str(output_dir.resolve()) or prior_fingerprint != input_fingerprint:
        raise ValueError(
            "existing owner mining output is not an exact rerun of the same input fingerprint"
        )


_STORE_TABLES = (
    "phrases",
    "templates",
    "template_assignments",
    "stacks",
    "transitions",
    "recipes",
    "taxonomy",
    "propensity",
    "profiles",
)
_VOLATILE_STORE_COLUMNS = {"profiled_at", "fe_completed_at", "updated_at"}


def _store_entity_integrity(db_path: Path) -> dict[str, object]:
    """Hash stable entity keys and row content from a closed SQLite feature store."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        result: dict[str, object] = {}
        for table in _STORE_TABLES:
            columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
            names = [str(row[1]) for row in columns]
            key_names = [
                str(row[1]) for row in sorted(columns, key=lambda item: int(item[5])) if int(row[5])
            ]
            content_names = [name for name in names if name not in _VOLATILE_STORE_COLUMNS]
            query_names = list(dict.fromkeys([*key_names, *content_names]))
            rows = connection.execute(
                f"SELECT {', '.join(query_names)} FROM {table} ORDER BY {', '.join(key_names)}"
            ).fetchall()
            key_indexes = [query_names.index(name) for name in key_names]
            content_indexes = [query_names.index(name) for name in content_names]
            keys = [[row[index] for index in key_indexes] for row in rows]
            content = [[row[index] for index in content_indexes] for row in rows]
            result[table] = {
                "row_count": len(rows),
                "key_columns": key_names,
                "key_sha256": _canonical_sha256(keys),
                "content_sha256": _canonical_sha256(content),
            }
        duplicates = connection.execute(
            "SELECT package_id, sequence_file_id, COUNT(*) FROM profiles "
            "GROUP BY package_id, sequence_file_id HAVING COUNT(*) > 1"
        ).fetchall()
    finally:
        connection.close()
    return {
        "tables": result,
        "duplicate_identity_count": len(duplicates),
        "aggregate_key_sha256": _canonical_sha256(
            {name: value["key_sha256"] for name, value in result.items()}  # type: ignore[index]
        ),
        "aggregate_content_sha256": _canonical_sha256(
            {name: value["content_sha256"] for name, value in result.items()}  # type: ignore[index]
        ),
    }


def _store_snapshot(db_path: Path | None, backend: str) -> dict[str, object]:
    """Read actual feature-store row counts without creating a missing store."""
    if db_path is None or backend != "sqlite":
        return {"enabled": False, "backend": backend, "path": None, "exists": False, "stats": None}
    resolved = db_path.resolve()
    if not resolved.exists():
        return {
            "enabled": True,
            "backend": backend,
            "path": str(resolved),
            "exists": False,
            "stats": None,
        }
    from twinklr.core.feature_store.backends.sqlite import SQLiteFeatureStore
    from twinklr.core.feature_store.models import FeatureStoreConfig

    store = SQLiteFeatureStore(FeatureStoreConfig(backend="sqlite", db_path=resolved))
    store.initialize()
    try:
        stats = store.get_corpus_stats().model_dump(mode="json")
    finally:
        store.close()
    return {
        "enabled": True,
        "backend": backend,
        "path": str(resolved),
        "exists": True,
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256_file(resolved),
        "stats": stats,
        "entity_integrity": _store_entity_integrity(resolved),
    }


def _clean_output_dir(output_dir: Path, feature_store_db: Path | None) -> None:
    """Clear staged output while preserving an embedded SQLite store and sidecars."""
    if output_dir == Path(output_dir.anchor):
        raise ValueError(f"Refusing to clean filesystem root as output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    preserved: set[Path] = set()
    if feature_store_db is not None:
        store = feature_store_db.resolve()
        if store == output_dir:
            raise ValueError("--feature-store-db must name a file, not --output-dir itself")
        preserved.update((store, Path(f"{store}-wal"), Path(f"{store}-shm")))

    def _remove_staged(path: Path) -> None:
        resolved = path.resolve()
        if resolved in preserved:
            return
        if path.is_dir():
            for child in path.iterdir():
                _remove_staged(child)
            if not any(path.iterdir()):
                path.rmdir()
            return
        path.unlink()

    for child in tuple(output_dir.iterdir()):
        _remove_staged(child)


def _stats(snapshot: object) -> object:
    return snapshot.get("stats") if isinstance(snapshot, dict) else None


def _write_mining_run_manifest(
    *,
    output_dir: Path,
    corpus_dir: Path,
    feature_store_db: Path | None,
    feature_store_backend: str,
    sequence_count: int,
    options: FeatureEngineeringPipelineOptions,
    previous_manifest: dict[str, Any] | None,
    store_before: dict[str, object],
    store_after: dict[str, object],
    catalog_before: dict[str, object],
    catalog_after: dict[str, object],
    provenance: dict[str, object],
) -> Path:
    """Record measured reproducibility, idempotency, and catalog-safety evidence."""
    artifact_snapshot = _tree_snapshot(output_dir)
    prior_after: object = None
    if previous_manifest is not None:
        prior_snapshots = previous_manifest.get("feature_store_snapshots")
        if isinstance(prior_snapshots, dict):
            prior_after = prior_snapshots.get("after")
    prior_stats = _stats(prior_after)
    before_stats = _stats(store_before)
    after_stats = _stats(store_after)
    has_prior_measurement = prior_stats is not None
    before_matches_prior = has_prior_measurement and before_stats == prior_stats
    after_matches_before = before_stats is not None and after_stats == before_stats
    prior_integrity = prior_after.get("entity_integrity") if isinstance(prior_after, dict) else None
    before_integrity = store_before.get("entity_integrity")
    after_integrity = store_after.get("entity_integrity")
    prior_provenance = previous_manifest.get("provenance") if previous_manifest else None
    prior_corpus = prior_provenance.get("corpus") if isinstance(prior_provenance, dict) else None
    current_corpus = provenance.get("corpus")
    prior_input_fingerprint = (
        prior_corpus.get("input_fingerprint_sha256") if isinstance(prior_corpus, dict) else None
    )
    current_input_fingerprint = (
        current_corpus.get("input_fingerprint_sha256") if isinstance(current_corpus, dict) else None
    )
    input_fingerprint_matches_previous = (
        prior_input_fingerprint is not None and prior_input_fingerprint == current_input_fingerprint
    )
    prior_source = prior_provenance.get("source") if isinstance(prior_provenance, dict) else None
    prior_tools = prior_provenance.get("tools") if isinstance(prior_provenance, dict) else None
    source_provenance_matches_previous = (
        isinstance(prior_source, dict)
        and prior_source == provenance.get("source")
        and isinstance(prior_tools, dict)
        and prior_tools == provenance.get("tools")
    )
    prior_before_keys = (
        prior_integrity.get("aggregate_key_sha256") if isinstance(prior_integrity, dict) else None
    )
    before_keys = (
        before_integrity.get("aggregate_key_sha256") if isinstance(before_integrity, dict) else None
    )
    after_keys = (
        after_integrity.get("aggregate_key_sha256") if isinstance(after_integrity, dict) else None
    )
    prior_before_content = (
        prior_integrity.get("aggregate_content_sha256")
        if isinstance(prior_integrity, dict)
        else None
    )
    before_content = (
        before_integrity.get("aggregate_content_sha256")
        if isinstance(before_integrity, dict)
        else None
    )
    after_content = (
        after_integrity.get("aggregate_content_sha256")
        if isinstance(after_integrity, dict)
        else None
    )
    entity_key_digests_match = (
        prior_before_keys is not None and prior_before_keys == before_keys == after_keys
    )
    entity_content_digests_match = (
        prior_before_content is not None and prior_before_content == before_content == after_content
    )
    duplicate_identity_count = (
        int(after_integrity.get("duplicate_identity_count", -1))
        if isinstance(after_integrity, dict)
        else -1
    )
    verified_unchanged_rerun = (
        before_matches_prior
        and after_matches_before
        and input_fingerprint_matches_previous
        and source_provenance_matches_previous
        and entity_key_digests_match
        and entity_content_digests_match
        and duplicate_identity_count == 0
    )
    verification_status = (
        "verified"
        if verified_unchanged_rerun
        else "changed"
        if has_prior_measurement
        else "needs_identical_second_run"
    )
    exact_command = shlex.join([sys.executable, *sys.argv])
    payload = {
        "schema_version": "mining_run_manifest_v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "invocation": {
            "exact_command": exact_command,
            "exact_rerun_command": exact_command,
            "effective_options": _effective_options(options),
        },
        "corpus": {
            "path": str(corpus_dir),
            "sequence_index_sha256": _sha256_file(corpus_dir / "sequence_index.jsonl"),
        },
        "output_dir": str(output_dir.resolve()),
        "sequence_count": sequence_count,
        "provenance": provenance,
        "candidate_staging": {
            "recursive_artifacts": artifact_snapshot,
            "note": "FE output is staged under this run directory; promotion into a live catalog is not performed by this command.",
        },
        "content_hash_identity": {
            "required": True,
            "implementation": "P1K-T1 deterministic package/file/profile identifiers",
            "verification": {
                "previous_run_after_stats": prior_stats,
                "current_run_before_stats": before_stats,
                "current_run_after_stats": after_stats,
                "before_matches_previous_after": before_matches_prior,
                "after_matches_before": after_matches_before,
                "input_fingerprint_matches_previous": input_fingerprint_matches_previous,
                "source_provenance_matches_previous": source_provenance_matches_previous,
                "entity_key_digests_match": entity_key_digests_match,
                "entity_content_digests_match": entity_content_digests_match,
                "duplicate_identity_count": duplicate_identity_count,
                "verified_unchanged_rerun": verified_unchanged_rerun,
                "status": verification_status,
            },
        },
        "feature_store": {
            "backend": feature_store_backend,
            "path": str(feature_store_db.resolve()) if feature_store_db else None,
        },
        "feature_store_snapshots": {"before": store_before, "after": store_after},
        "live_catalog_immutability": {
            "before": catalog_before,
            "after": catalog_after,
            "unchanged": catalog_before == catalog_after,
        },
    }
    path = output_dir / "mining_run_manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_dataset_rows(sequence_dir: Path, stem: str) -> list[dict[str, Any]]:
    parquet_path = sequence_dir / f"{stem}.parquet"
    jsonl_path = sequence_dir / f"{stem}.jsonl"

    if parquet_path.exists():
        try:
            import pyarrow.parquet as pq
        except Exception:
            pass
        else:
            table = pq.read_table(parquet_path)
            return [row for row in table.to_pylist() if isinstance(row, dict)]

    if jsonl_path.exists():
        return _read_jsonl(jsonl_path)

    return []


def _render_table(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    header_line = " | ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers))
    divider = "-+-".join("-" * widths[idx] for idx in range(len(headers)))
    body = [" | ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)) for row in rows]
    return "\n".join([header_line, divider, *body])


def _render_markdown_table(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _collect_sequence_dirs(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    dirs: list[Path] = []
    for package_dir in sorted(path for path in output_dir.iterdir() if path.is_dir()):
        for sequence_dir in sorted(path for path in package_dir.iterdir() if path.is_dir()):
            if (sequence_dir / "feature_bundle.json").exists():
                dirs.append(sequence_dir)
    return dirs


def _sequence_summary(
    sequence_dirs: list[Path],
) -> tuple[
    list[tuple[str, ...]], Counter[str], Counter[str], int, dict[str, list[tuple[str, str, str]]]
]:
    rows: list[tuple[str, ...]] = []
    taxonomy_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    total_phrases = 0
    by_sha: dict[str, list[tuple[str, str, str]]] = {}

    for sequence_dir in sequence_dirs:
        feature_bundle = _read_json(sequence_dir / "feature_bundle.json")
        phrases = _read_dataset_rows(sequence_dir, "effect_phrases")
        taxonomy = _read_dataset_rows(sequence_dir, "phrase_taxonomy")
        roles = _read_dataset_rows(sequence_dir, "target_roles")

        total_phrases += len(phrases)
        package_id = str(feature_bundle.get("package_id", "-"))
        sequence_file_id = str(feature_bundle.get("sequence_file_id", "-"))
        sequence_name = str(feature_bundle.get("song", "") or sequence_file_id)
        sequence_sha = str(feature_bundle.get("sequence_sha256", ""))
        if sequence_sha:
            by_sha.setdefault(sequence_sha, []).append(
                (package_id, sequence_file_id, sequence_name)
            )

        for row in taxonomy:
            labels = row.get("labels", [])
            if isinstance(labels, list):
                taxonomy_counts.update(str(label) for label in labels)

        for row in roles:
            role = row.get("role")
            if isinstance(role, str):
                role_counts.update([role])

        rows.append(
            (
                package_id,
                sequence_name,
                sequence_file_id,
                str(len(phrases)),
                str(len(taxonomy)),
                str(len(roles)),
                str(feature_bundle.get("audio", {}).get("audio_status", "-")),
                sequence_sha[:12] if sequence_sha else "-",
            )
        )

    return rows, taxonomy_counts, role_counts, total_phrases, by_sha


def _top_rows(counter: Counter[str], top_n: int) -> list[tuple[str, str]]:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:top_n]
    return [(label, str(count)) for label, count in ordered]


def _template_rows(path: Path, top_n: int) -> list[tuple[str, ...]]:
    if not path.exists():
        return []
    payload = _read_json(path)
    templates = payload.get("templates", [])
    if not isinstance(templates, list):
        return []

    rows: list[tuple[str, ...]] = []
    ranked = sorted(
        [row for row in templates if isinstance(row, dict)],
        key=lambda row: (-int(row.get("support_count", 0)), str(row.get("template_id", ""))),
    )
    for row in ranked[:top_n]:
        rows.append(
            (
                str(row.get("template_id", "")),
                str(row.get("support_count", 0)),
                str(row.get("distinct_pack_count", 0)),
                str(row.get("effect_family", "")),
            )
        )
    return rows


def _write_markdown(
    output_dir: Path,
    sequence_rows: list[tuple[str, ...]],
    taxonomy_rows: list[tuple[str, str]],
    role_rows: list[tuple[str, str]],
    content_template_rows: list[tuple[str, ...]],
    orchestration_template_rows: list[tuple[str, ...]],
    transition_graph: dict[str, Any] | None,
    quality_report: dict[str, Any] | None,
    unknown_diagnostics: dict[str, Any] | None,
    template_retrieval_index: dict[str, Any] | None,
    template_diagnostics: dict[str, Any] | None,
    total_phrases: int,
    duplicate_groups: list[tuple[str, list[tuple[str, str, str]]]],
    color_arc: dict[str, Any] | None = None,
    propensity_index: dict[str, Any] | None = None,
    style_fingerprint: dict[str, Any] | None = None,
) -> Path:
    lines: list[str] = []
    lines.append("# Feature Engineering Demo Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total sequences: {len(sequence_rows)}")
    lines.append(f"- Total phrases: {total_phrases}")
    lines.append("")

    if sequence_rows:
        lines.append("## Sequence Coverage")
        lines.append("")
        lines.append(
            _render_markdown_table(
                (
                    "package_id",
                    "sequence_name",
                    "sequence_file_id",
                    "phrases",
                    "taxonomy",
                    "target_roles",
                    "audio_status",
                    "sequence_sha12",
                ),
                sequence_rows,
            )
        )
        lines.append("")

    if duplicate_groups:
        lines.append("## Duplicate Sequence Warning")
        lines.append("")
        lines.append(
            "Detected sequences sharing the same `sequence_sha256` (likely duplicated source sequence content)."
        )
        lines.append("")
        for sha, items in duplicate_groups:
            lines.append(f"- SHA `{sha}`")
            for package_id, sequence_file_id, sequence_name in items:
                lines.append(f"  - `{package_id}` / `{sequence_file_id}` / `{sequence_name}`")
        lines.append("")

    if taxonomy_rows:
        lines.append("## Top Taxonomy Labels")
        lines.append("")
        lines.append(_render_markdown_table(("label", "count"), taxonomy_rows))
        lines.append("")

    if role_rows:
        lines.append("## Target Role Distribution")
        lines.append("")
        lines.append(_render_markdown_table(("role", "count"), role_rows))
        lines.append("")

    if content_template_rows:
        lines.append("## Content Templates")
        lines.append("")
        lines.append(
            _render_markdown_table(
                ("template_id", "support", "packs", "effect_family"), content_template_rows
            )
        )
        lines.append("")

    if orchestration_template_rows:
        lines.append("## Orchestration Templates")
        lines.append("")
        lines.append(
            _render_markdown_table(
                ("template_id", "support", "packs", "effect_family"),
                orchestration_template_rows,
            )
        )
        lines.append("")

    if transition_graph:
        lines.append("## Transition Graph")
        lines.append("")
        lines.append(f"- Transitions: {transition_graph.get('total_transitions', 0)}")
        lines.append(f"- Nodes: {transition_graph.get('total_nodes', 0)}")
        lines.append(f"- Edges: {transition_graph.get('total_edges', 0)}")
        anomalies = transition_graph.get("anomalies", [])
        lines.append(f"- Anomalies: {len(anomalies) if isinstance(anomalies, list) else 0}")
        lines.append("")

    if quality_report:
        lines.append("## Quality Gates")
        lines.append("")
        lines.append(f"- Passed: {quality_report.get('passed', False)}")
        checks = quality_report.get("checks", [])
        check_rows: list[tuple[str, str, str, str]] = []
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict):
                    continue
                check_rows.append(
                    (
                        str(check.get("check_id", "")),
                        str(check.get("passed", False)),
                        str(check.get("value", "")),
                        str(check.get("threshold", "")),
                    )
                )
        if check_rows:
            lines.append("")
            lines.append(
                _render_markdown_table(("check", "passed", "value", "threshold"), check_rows)
            )
            lines.append("")

    if color_arc:
        lines.append("## Color Arc")
        lines.append("")
        palettes = color_arc.get("palette_library", [])
        assignments = color_arc.get("section_assignments", [])
        transitions = color_arc.get("transition_rules", [])
        lines.append(f"- Palettes: {len(palettes)}")
        lines.append(f"- Assignments: {len(assignments)}")
        lines.append(f"- Transitions: {len(transitions)}")
        if isinstance(assignments, list) and assignments:
            arc_rows: list[tuple[str, str, str, str]] = []
            for a in assignments:
                if not isinstance(a, dict):
                    continue
                arc_rows.append(
                    (
                        str(a.get("section_label", "")),
                        str(a.get("palette_id", "")),
                        str(a.get("shift_timing", "")),
                        str(a.get("contrast_target", "")),
                    )
                )
            if arc_rows:
                lines.append("")
                lines.append(
                    _render_markdown_table(
                        ("section", "palette_id", "shift_timing", "contrast"), arc_rows
                    )
                )
        lines.append("")

    if propensity_index:
        lines.append("## Propensity Index")
        lines.append("")
        affinities = propensity_index.get("affinities", [])
        anti_affinities = propensity_index.get("anti_affinities", [])
        lines.append(f"- Affinities: {len(affinities)}")
        lines.append(f"- Anti-affinities: {len(anti_affinities)}")
        if isinstance(affinities, list) and affinities:
            prop_rows: list[tuple[str, str, str, str, str]] = []
            sorted_aff = sorted(
                [a for a in affinities if isinstance(a, dict)],
                key=lambda a: (-float(a.get("frequency", 0)), str(a.get("effect_family", ""))),
            )
            for a in sorted_aff[:20]:
                prop_rows.append(
                    (
                        str(a.get("effect_family", "")),
                        str(a.get("model_type", "")),
                        str(a.get("frequency", "")),
                        str(a.get("exclusivity", "")),
                        str(a.get("corpus_support", "")),
                    )
                )
            if prop_rows:
                lines.append("")
                lines.append(
                    _render_markdown_table(
                        ("effect_family", "model_type", "frequency", "exclusivity", "support"),
                        prop_rows,
                    )
                )
        lines.append("")

    if style_fingerprint:
        lines.append("## Style Fingerprint")
        lines.append("")
        lines.append(f"- Creator: {style_fingerprint.get('creator_id', '-')}")
        lines.append(f"- Corpus sequences: {style_fingerprint.get('corpus_sequence_count', 0)}")
        recipe_prefs = style_fingerprint.get("recipe_preferences", {})
        if isinstance(recipe_prefs, dict) and recipe_prefs:
            style_pref_rows: list[tuple[str, str]] = []
            for family, weight in sorted(recipe_prefs.items(), key=lambda x: -float(x[1])):
                style_pref_rows.append((str(family), str(weight)))
            lines.append("")
            lines.append("### Recipe Preferences")
            lines.append("")
            lines.append(_render_markdown_table(("effect_family", "weight"), style_pref_rows))
        transition = style_fingerprint.get("transition_style", {})
        color = style_fingerprint.get("color_tendencies", {})
        timing = style_fingerprint.get("timing_style", {})
        layering = style_fingerprint.get("layering_style", {})
        if isinstance(transition, dict) and transition:
            lines.append("")
            lines.append("### Sub-Profiles")
            lines.append("")
            sub_rows: list[tuple[str, str]] = [
                ("transition.preferred_gap_ms", str(transition.get("preferred_gap_ms", ""))),
                ("transition.overlap_tendency", str(transition.get("overlap_tendency", ""))),
                ("transition.variety_score", str(transition.get("variety_score", ""))),
                ("color.palette_complexity", str(color.get("palette_complexity", ""))),
                ("color.contrast_preference", str(color.get("contrast_preference", ""))),
                ("color.temperature_preference", str(color.get("temperature_preference", ""))),
                ("timing.beat_alignment", str(timing.get("beat_alignment_strictness", ""))),
                ("timing.density_preference", str(timing.get("density_preference", ""))),
                (
                    "timing.section_change_aggression",
                    str(timing.get("section_change_aggression", "")),
                ),
                ("layering.mean_layers", str(layering.get("mean_layers", ""))),
                ("layering.max_layers", str(layering.get("max_layers", ""))),
                ("layering.blend_mode", str(layering.get("blend_mode_preference", ""))),
            ]
            lines.append(_render_markdown_table(("metric", "value"), sub_rows))
        lines.append("")

    if unknown_diagnostics:
        lines.append("## Unknown Diagnostics")
        lines.append("")
        lines.append(
            f"- Unknown effect-family ratio: {unknown_diagnostics.get('unknown_effect_family_ratio', 0)}"
        )
        lines.append(
            f"- Unknown motion ratio: {unknown_diagnostics.get('unknown_motion_ratio', 0)}"
        )
        top_unknown = unknown_diagnostics.get("top_unknown_effect_types", [])
        if isinstance(top_unknown, list) and top_unknown:
            unknown_rows: list[tuple[str, str, str, str]] = []
            for row in top_unknown[:10]:
                if not isinstance(row, dict):
                    continue
                unknown_rows.append(
                    (
                        str(row.get("effect_type", "")),
                        str(row.get("normalized_key", "")),
                        str(row.get("count", 0)),
                        str(row.get("distinct_sequence_count", 0)),
                    )
                )
            if unknown_rows:
                lines.append("")
                lines.append("### Top Unknown Effect Types")
                lines.append("")
                lines.append(
                    _render_markdown_table(
                        ("effect_type", "normalized_key", "count", "sequences"),
                        unknown_rows,
                    )
                )
                lines.append("")

        alias_groups = unknown_diagnostics.get("alias_candidate_groups", [])
        if isinstance(alias_groups, list) and alias_groups:
            alias_rows: list[tuple[str, str]] = []
            for group in alias_groups[:10]:
                if not isinstance(group, dict):
                    continue
                values = group.get("raw_effect_types", [])
                alias_values = (
                    ", ".join(str(value) for value in values[:6])
                    if isinstance(values, list)
                    else ""
                )
                alias_rows.append((str(group.get("normalized_key", "")), alias_values))
            if alias_rows:
                lines.append("### Alias Candidate Groups")
                lines.append("")
                lines.append(
                    _render_markdown_table(("normalized_key", "raw_effect_types"), alias_rows)
                )
                lines.append("")

    if template_retrieval_index:
        recommendations = template_retrieval_index.get("recommendations", [])
        retrieval_rows: list[tuple[str, str, str, str, str]] = []
        if isinstance(recommendations, list):
            for row in recommendations[:10]:
                if not isinstance(row, dict):
                    continue
                retrieval_rows.append(
                    (
                        str(row.get("rank", "")),
                        str(row.get("template_kind", "")),
                        str(row.get("retrieval_score", "")),
                        str(row.get("effect_family", "")),
                        str(row.get("template_id", "")),
                    )
                )
        if retrieval_rows:
            lines.append("## Template Retrieval Baseline")
            lines.append("")
            lines.append(
                _render_markdown_table(
                    ("rank", "kind", "score", "effect_family", "template_id"),
                    retrieval_rows,
                )
            )
            lines.append("")

    if template_diagnostics:
        lines.append("## Template Diagnostics")
        lines.append("")
        lines.append(
            f"- Flagged templates: {template_diagnostics.get('flagged_template_count', 0)} / "
            f"{template_diagnostics.get('total_templates', 0)}"
        )
        lines.append(f"- Low support: {len(template_diagnostics.get('low_support_templates', []))}")
        lines.append(
            f"- High concentration: {len(template_diagnostics.get('high_concentration_templates', []))}"
        )
        lines.append(
            f"- High variance: {len(template_diagnostics.get('high_variance_templates', []))}"
        )
        lines.append(
            f"- Over generic: {len(template_diagnostics.get('over_generic_templates', []))}"
        )

        diagnostic_source_rows = template_diagnostics.get("rows", [])
        diagnostic_rows: list[tuple[str, str, str, str, str, str]] = []
        if isinstance(diagnostic_source_rows, list):
            candidates = [
                row for row in diagnostic_source_rows if isinstance(row, dict) and row.get("flags")
            ]
            candidates.sort(
                key=lambda row: (
                    -int(row.get("support_count", 0)),
                    str(row.get("template_id", "")),
                )
            )
            for row in candidates[:10]:
                flags = row.get("flags", [])
                diagnostic_rows.append(
                    (
                        str(row.get("template_id", "")),
                        str(row.get("template_kind", "")),
                        str(row.get("support_count", 0)),
                        str(row.get("concentration_ratio", 0)),
                        str(row.get("variance_score", 0)),
                        ",".join(str(flag) for flag in flags) if isinstance(flags, list) else "",
                    )
                )
        if diagnostic_rows:
            lines.append("")
            lines.append(
                _render_markdown_table(
                    (
                        "template_id",
                        "kind",
                        "support",
                        "concentration",
                        "variance",
                        "flags",
                    ),
                    diagnostic_rows,
                )
            )
        lines.append("")

    report_path = output_dir / "feature_engineering_demo.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.owner_mining_run and args.skip_build:
        print("ERROR: --owner-mining-run cannot be combined with --skip-build", file=sys.stderr)
        return 2
    if args.owner_mining_run and not (
        args.music_library_index is not None or args.no_music_library_index
    ):
        print(
            "ERROR: --owner-mining-run requires either --music-library-index or "
            "--no-music-library-index",
            file=sys.stderr,
        )
        return 2
    if args.skip_build and args.style_groups is not None:
        print(
            "ERROR: --style-groups cannot be used with --skip-build; grouped fingerprint "
            "extraction requires a build.",
            file=sys.stderr,
        )
        return 2
    try:
        style_groups = (
            load_style_group_declaration(args.style_groups.resolve())
            if args.style_groups is not None
            else None
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not args.skip_build:
        if args.corpus_dir is None:
            print("ERROR: --corpus-dir is required unless --skip-build is set.")
            return 2
        requested_corpus_dir = args.corpus_dir.resolve()
        owner_corpus_rows: list[dict[str, Any]] | None = None
        if args.owner_mining_run:
            try:
                owner_corpus_rows = _require_explicit_unified_corpus(requested_corpus_dir)
            except ValueError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 2
            corpus_dir = requested_corpus_dir
        else:
            corpus_dir = _ensure_corpus(requested_corpus_dir)
        feature_store_db = (
            args.feature_store_db.resolve() if args.feature_store_db is not None else None
        )
        feature_store_backend: Literal["sqlite", "null"]
        if args.feature_store_backend is None:
            feature_store_backend = "sqlite" if feature_store_db is not None else "null"
        elif args.feature_store_backend == "sqlite":
            feature_store_backend = "sqlite"
        elif args.feature_store_backend == "null":
            feature_store_backend = "null"
        else:
            raise ValueError(f"Unsupported feature-store backend: {args.feature_store_backend}")
        previous_manifest_path = output_dir / "mining_run_manifest.json"
        previous_manifest = (
            _read_json(previous_manifest_path) if previous_manifest_path.exists() else None
        )
        source_provenance = _source_provenance()
        if owner_corpus_rows is not None:
            music_index_path = (
                args.music_library_index.resolve() if args.music_library_index is not None else None
            )
            if music_index_path is not None and not music_index_path.is_file():
                print(
                    f"ERROR: explicit music-library index does not exist: {music_index_path}",
                    file=sys.stderr,
                )
                return 2
            input_provenance = _input_provenance(corpus_dir, owner_corpus_rows, music_index_path)
        else:
            music_index_path = _MUSIC_INDEX_PATH
            input_provenance = {
                "corpus": {
                    "path": str(corpus_dir),
                    "sequence_index_sha256": _sha256_file(corpus_dir / "sequence_index.jsonl"),
                    "input_fingerprint_sha256": _sha256_file(corpus_dir / "sequence_index.jsonl"),
                },
                "profiles": [],
                "music_library_index": {
                    "path": str(_MUSIC_INDEX_PATH),
                    "exists": _MUSIC_INDEX_PATH.is_file(),
                    "sha256": (
                        _sha256_file(_MUSIC_INDEX_PATH) if _MUSIC_INDEX_PATH.is_file() else None
                    ),
                },
            }
        provenance = {**source_provenance, **input_provenance}
        if args.owner_mining_run:
            if feature_store_backend != "sqlite":
                print("ERROR: --owner-mining-run requires the sqlite backend", file=sys.stderr)
                return 2
            try:
                _validate_owner_output_dir(
                    output_dir=output_dir,
                    feature_store_db=feature_store_db,
                    previous_manifest=previous_manifest,
                    input_fingerprint=str(
                        cast("dict[str, object]", provenance["corpus"])["input_fingerprint_sha256"]
                    ),
                )
            except ValueError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 2
        live_catalog_dir = ROOT / "catalog" / "templates"
        catalog_before = _tree_snapshot(live_catalog_dir)
        store_before = _store_snapshot(feature_store_db, feature_store_backend)
        _clean_output_dir(output_dir, feature_store_db)
        analyzer = None
        if args.run_audio_analysis:
            from twinklr.core.audio.analyzer import AudioAnalyzer

            analyzer = AudioAnalyzer(AppConfig(), JobConfig())

        from twinklr.core.feature_store.models import FeatureStoreConfig

        feature_store_config = None
        if feature_store_db is not None:
            feature_store_config = FeatureStoreConfig(
                backend=feature_store_backend,
                db_path=feature_store_db,
            )

        music_index = _load_music_library_index(music_index_path)
        effective_options = FeatureEngineeringPipelineOptions(
            template_min_instance_count=args.template_min_instance_count,
            template_min_distinct_pack_count=args.template_min_distinct_pack_count,
            quality_max_unknown_effect_family_ratio=args.quality_max_unknown_effect_family_ratio,
            quality_max_unknown_motion_ratio=args.quality_max_unknown_motion_ratio,
            quality_max_single_unknown_effect_type_ratio=args.quality_max_single_unknown_effect_type_ratio,
            quality_max_low_support_template_ratio=args.quality_max_low_support_template_ratio,
            quality_max_high_concentration_template_ratio=args.quality_max_high_concentration_template_ratio,
            quality_max_high_variance_template_ratio=args.quality_max_high_variance_template_ratio,
            quality_max_over_generic_template_ratio=args.quality_max_over_generic_template_ratio,
            quality_diagnostics_gate_mode=args.quality_diagnostics_gate_mode,
            feature_store_config=feature_store_config,
            style_groups=style_groups,
        )
        pipeline = FeatureEngineeringPipeline(
            options=effective_options,
            analyzer=analyzer,
            music_library_index=music_index,
        )
        build_start = time.perf_counter()

        def _progress(msg: str) -> None:
            elapsed = time.perf_counter() - build_start
            print(f"  [{elapsed:5.1f}s] {msg}")

        bundles = pipeline.run_corpus(corpus_dir, output_dir, progress_fn=_progress)
        build_elapsed = time.perf_counter() - build_start
        print(
            f"  Built feature-engineering artifacts for {len(bundles)} sequences"
            f" in {build_elapsed:.1f}s."
        )
        store_after = _store_snapshot(feature_store_db, feature_store_backend)
        if owner_corpus_rows is not None:
            after_input = _input_provenance(corpus_dir, owner_corpus_rows, music_index_path)
            if (
                cast("dict[str, object]", after_input["corpus"])["input_fingerprint_sha256"]
                != cast("dict[str, object]", provenance["corpus"])["input_fingerprint_sha256"]
            ):
                raise RuntimeError("owner mining input changed while the run was executing")
        catalog_after = _tree_snapshot(live_catalog_dir)
        manifest_path = _write_mining_run_manifest(
            output_dir=output_dir,
            corpus_dir=corpus_dir,
            feature_store_db=feature_store_db,
            feature_store_backend=feature_store_backend,
            sequence_count=len(bundles),
            options=effective_options,
            previous_manifest=previous_manifest,
            store_before=store_before,
            store_after=store_after,
            catalog_before=catalog_before,
            catalog_after=catalog_after,
            provenance=provenance,
        )
        print(f"  Wrote staged mining-run manifest: {manifest_path}")
        if catalog_before != catalog_after:
            raise RuntimeError(
                f"Live catalog changed during staged mining run; inspect {manifest_path}"
            )

    sequence_dirs = _collect_sequence_dirs(output_dir)
    if not sequence_dirs:
        print("No feature-engineering sequence outputs found.")
        return 1

    sequence_rows, taxonomy_counts, role_counts, total_phrases, by_sha = _sequence_summary(
        sequence_dirs
    )
    duplicate_groups = [
        (sha, items)
        for sha, items in sorted(by_sha.items(), key=lambda item: item[0])
        if len(items) > 1
    ]

    taxonomy_rows = _top_rows(taxonomy_counts, args.top_n)
    role_rows = _top_rows(role_counts, args.top_n)
    content_template_rows = _template_rows(output_dir / "content_templates.json", args.top_n)
    orchestration_template_rows = _template_rows(
        output_dir / "orchestration_templates.json", args.top_n
    )

    transition_graph = None
    transition_graph_path = output_dir / "transition_graph.json"
    if transition_graph_path.exists():
        transition_graph = _read_json(transition_graph_path)

    quality_report = None
    quality_report_path = output_dir / "quality_report.json"
    if quality_report_path.exists():
        quality_report = _read_json(quality_report_path)

    unknown_diagnostics = None
    unknown_diagnostics_path = output_dir / "unknown_diagnostics.json"
    if unknown_diagnostics_path.exists():
        unknown_diagnostics = _read_json(unknown_diagnostics_path)

    color_arc = None
    color_arc_path = output_dir / "color_arc.json"
    if color_arc_path.exists():
        color_arc = _read_json(color_arc_path)

    propensity_index = None
    propensity_index_path = output_dir / "propensity_index.json"
    if propensity_index_path.exists():
        propensity_index = _read_json(propensity_index_path)

    style_fingerprint = None
    style_fingerprint_path = output_dir / "style_fingerprint.json"
    if style_fingerprint_path.exists():
        style_fingerprint = _read_json(style_fingerprint_path)

    template_retrieval_index = None
    template_retrieval_index_path = output_dir / "template_retrieval_index.json"
    if template_retrieval_index_path.exists():
        template_retrieval_index = _read_json(template_retrieval_index_path)

    template_diagnostics = None
    template_diagnostics_path = output_dir / "template_diagnostics.json"
    if template_diagnostics_path.exists():
        template_diagnostics = _read_json(template_diagnostics_path)

    print("\nFeature Engineering Summary")
    print("===========================")
    print(f"Output directory : {output_dir}")
    print(f"Sequences        : {len(sequence_rows)}")
    print(f"Total phrases    : {total_phrases}")

    print("\nPer-Sequence Coverage")
    print(
        _render_table(
            (
                "package_id",
                "sequence_name",
                "sequence_file_id",
                "phrases",
                "taxonomy",
                "target_roles",
                "audio_status",
                "sequence_sha12",
            ),
            sequence_rows,
        )
    )

    if duplicate_groups:
        print("\nDuplicate Sequence Warning")
        print(
            "Detected sequences sharing identical sequence_sha256 (likely duplicated source sequence content):"
        )
        for sha, items in duplicate_groups:
            print(f"- {sha}")
            for package_id, sequence_file_id, sequence_name in items:
                print(f"  - {package_id} | {sequence_file_id} | {sequence_name}")

    if taxonomy_rows:
        print("\nTop Taxonomy Labels")
        print(_render_table(("label", "count"), taxonomy_rows))

    if role_rows:
        print("\nTarget Role Distribution")
        print(_render_table(("role", "count"), role_rows))

    if content_template_rows:
        print("\nTop Content Templates")
        print(
            _render_table(
                ("template_id", "support", "packs", "effect_family"), content_template_rows
            )
        )

    if orchestration_template_rows:
        print("\nTop Orchestration Templates")
        print(
            _render_table(
                ("template_id", "support", "packs", "effect_family"),
                orchestration_template_rows,
            )
        )

    if transition_graph is not None:
        print("\nTransition Graph")
        print(f"Transitions : {transition_graph.get('total_transitions', 0)}")
        print(f"Nodes       : {transition_graph.get('total_nodes', 0)}")
        print(f"Edges       : {transition_graph.get('total_edges', 0)}")
        anomalies = transition_graph.get("anomalies", [])
        anomaly_count = len(anomalies) if isinstance(anomalies, list) else 0
        print(f"Anomalies   : {anomaly_count}")

    if quality_report is not None:
        print("\nQuality Gates")
        print(f"Passed: {quality_report.get('passed', False)}")
        checks = quality_report.get("checks", [])
        check_rows: list[tuple[str, str, str, str]] = []
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict):
                    continue
                check_rows.append(
                    (
                        str(check.get("check_id", "")),
                        str(check.get("passed", False)),
                        str(check.get("value", "")),
                        str(check.get("threshold", "")),
                    )
                )
        if check_rows:
            print(_render_table(("check", "passed", "value", "threshold"), check_rows))

    if color_arc is not None:
        print("\nColor Arc")
        palettes = color_arc.get("palette_library", [])
        assignments = color_arc.get("section_assignments", [])
        transitions = color_arc.get("transition_rules", [])
        print(f"Palettes     : {len(palettes)}")
        print(f"Assignments  : {len(assignments)}")
        print(f"Transitions  : {len(transitions)}")
        if isinstance(assignments, list) and assignments:
            arc_rows: list[tuple[str, str, str, str]] = []
            for a in assignments[: args.top_n]:
                if not isinstance(a, dict):
                    continue
                arc_rows.append(
                    (
                        str(a.get("section_label", "")),
                        str(a.get("palette_id", "")),
                        str(a.get("shift_timing", "")),
                        str(a.get("contrast_target", "")),
                    )
                )
            if arc_rows:
                print(
                    _render_table(
                        ("section", "palette_id", "shift_timing", "contrast"),
                        arc_rows,
                    )
                )

    if propensity_index is not None:
        print("\nPropensity Index")
        affinities = propensity_index.get("affinities", [])
        anti_affinities = propensity_index.get("anti_affinities", [])
        print(f"Affinities      : {len(affinities)}")
        print(f"Anti-affinities : {len(anti_affinities)}")
        if isinstance(affinities, list) and affinities:
            prop_rows: list[tuple[str, str, str, str, str]] = []
            sorted_aff = sorted(
                [a for a in affinities if isinstance(a, dict)],
                key=lambda a: (-float(a.get("frequency", 0)), str(a.get("effect_family", ""))),
            )
            for a in sorted_aff[: args.top_n]:
                prop_rows.append(
                    (
                        str(a.get("effect_family", "")),
                        str(a.get("model_type", "")),
                        str(a.get("frequency", "")),
                        str(a.get("exclusivity", "")),
                        str(a.get("corpus_support", "")),
                    )
                )
            if prop_rows:
                print(
                    _render_table(
                        ("effect_family", "model_type", "frequency", "exclusivity", "support"),
                        prop_rows,
                    )
                )

    if style_fingerprint is not None:
        print("\nStyle Fingerprint")
        print(f"Creator          : {style_fingerprint.get('creator_id', '-')}")
        print(f"Corpus sequences : {style_fingerprint.get('corpus_sequence_count', 0)}")
        recipe_prefs = style_fingerprint.get("recipe_preferences", {})
        if isinstance(recipe_prefs, dict) and recipe_prefs:
            style_pref_rows: list[tuple[str, str]] = []
            for family, weight in sorted(recipe_prefs.items(), key=lambda x: -float(x[1])):
                style_pref_rows.append((str(family), str(weight)))
            print(_render_table(("effect_family", "weight"), style_pref_rows))
        transition = style_fingerprint.get("transition_style", {})
        color_t = style_fingerprint.get("color_tendencies", {})
        timing = style_fingerprint.get("timing_style", {})
        layering = style_fingerprint.get("layering_style", {})
        if isinstance(transition, dict) and transition:
            sub_rows: list[tuple[str, str]] = [
                ("transition.preferred_gap_ms", str(transition.get("preferred_gap_ms", ""))),
                ("transition.overlap_tendency", str(transition.get("overlap_tendency", ""))),
                ("transition.variety_score", str(transition.get("variety_score", ""))),
                ("color.palette_complexity", str(color_t.get("palette_complexity", ""))),
                ("color.contrast_preference", str(color_t.get("contrast_preference", ""))),
                ("color.temperature_preference", str(color_t.get("temperature_preference", ""))),
                ("timing.beat_alignment", str(timing.get("beat_alignment_strictness", ""))),
                ("timing.density_preference", str(timing.get("density_preference", ""))),
                ("timing.section_aggression", str(timing.get("section_change_aggression", ""))),
                ("layering.mean_layers", str(layering.get("mean_layers", ""))),
                ("layering.max_layers", str(layering.get("max_layers", ""))),
                ("layering.blend_mode", str(layering.get("blend_mode_preference", ""))),
            ]
            print(_render_table(("metric", "value"), sub_rows))

    if unknown_diagnostics is not None:
        print("\nUnknown Diagnostics")
        print(
            f"Unknown effect-family ratio : {unknown_diagnostics.get('unknown_effect_family_ratio', 0)}"
        )
        print(f"Unknown motion ratio        : {unknown_diagnostics.get('unknown_motion_ratio', 0)}")
        top_unknown = unknown_diagnostics.get("top_unknown_effect_types", [])
        if isinstance(top_unknown, list) and top_unknown:
            unknown_rows: list[tuple[str, str, str, str]] = []
            for row in top_unknown[:10]:
                if not isinstance(row, dict):
                    continue
                unknown_rows.append(
                    (
                        str(row.get("effect_type", "")),
                        str(row.get("normalized_key", "")),
                        str(row.get("count", 0)),
                        str(row.get("distinct_sequence_count", 0)),
                    )
                )
            if unknown_rows:
                print("\nTop Unknown Effect Types")
                print(
                    _render_table(
                        ("effect_type", "normalized_key", "count", "sequences"), unknown_rows
                    )
                )

        alias_groups = unknown_diagnostics.get("alias_candidate_groups", [])
        if isinstance(alias_groups, list) and alias_groups:
            alias_rows: list[tuple[str, str]] = []
            for group in alias_groups[:10]:
                if not isinstance(group, dict):
                    continue
                values = group.get("raw_effect_types", [])
                alias_values = (
                    ", ".join(str(value) for value in values[:6])
                    if isinstance(values, list)
                    else ""
                )
                alias_rows.append((str(group.get("normalized_key", "")), alias_values))
            if alias_rows:
                print("\nAlias Candidate Groups")
                print(_render_table(("normalized_key", "raw_effect_types"), alias_rows))

    if template_retrieval_index is not None:
        recommendations = template_retrieval_index.get("recommendations", [])
        retrieval_rows: list[tuple[str, str, str, str, str]] = []
        if isinstance(recommendations, list):
            for row in recommendations[:10]:
                if not isinstance(row, dict):
                    continue
                retrieval_rows.append(
                    (
                        str(row.get("rank", "")),
                        str(row.get("template_kind", "")),
                        str(row.get("retrieval_score", "")),
                        str(row.get("effect_family", "")),
                        str(row.get("template_id", "")),
                    )
                )
        if retrieval_rows:
            print("\nTemplate Retrieval Baseline")
            print(
                _render_table(
                    ("rank", "kind", "score", "effect_family", "template_id"), retrieval_rows
                )
            )

    if template_diagnostics is not None:
        print("\nTemplate Diagnostics")
        total_templates = int(template_diagnostics.get("total_templates", 0))
        flagged_template_count = int(template_diagnostics.get("flagged_template_count", 0))
        print(f"Flagged templates : {flagged_template_count}/{total_templates}")
        print(f"Low support       : {len(template_diagnostics.get('low_support_templates', []))}")
        print(
            "High concentration: "
            f"{len(template_diagnostics.get('high_concentration_templates', []))}"
        )
        print(f"High variance     : {len(template_diagnostics.get('high_variance_templates', []))}")
        print(f"Over generic      : {len(template_diagnostics.get('over_generic_templates', []))}")

        diagnostic_source_rows = template_diagnostics.get("rows", [])
        diagnostic_rows: list[tuple[str, str, str, str, str, str]] = []
        if isinstance(diagnostic_source_rows, list):
            candidates = [
                row for row in diagnostic_source_rows if isinstance(row, dict) and row.get("flags")
            ]
            candidates.sort(
                key=lambda row: (
                    -int(row.get("support_count", 0)),
                    str(row.get("template_id", "")),
                )
            )
            for row in candidates[:10]:
                flags = row.get("flags", [])
                diagnostic_rows.append(
                    (
                        str(row.get("template_id", "")),
                        str(row.get("template_kind", "")),
                        str(row.get("support_count", 0)),
                        str(row.get("concentration_ratio", 0)),
                        str(row.get("variance_score", 0)),
                        ",".join(str(flag) for flag in flags) if isinstance(flags, list) else "",
                    )
                )
        if diagnostic_rows:
            print(
                _render_table(
                    (
                        "template_id",
                        "kind",
                        "support",
                        "concentration",
                        "variance",
                        "flags",
                    ),
                    diagnostic_rows,
                )
            )

    report_path = _write_markdown(
        output_dir=output_dir,
        sequence_rows=sequence_rows,
        taxonomy_rows=taxonomy_rows,
        role_rows=role_rows,
        content_template_rows=content_template_rows,
        orchestration_template_rows=orchestration_template_rows,
        transition_graph=transition_graph,
        quality_report=quality_report,
        unknown_diagnostics=unknown_diagnostics,
        template_retrieval_index=template_retrieval_index,
        template_diagnostics=template_diagnostics,
        total_phrases=total_phrases,
        duplicate_groups=duplicate_groups,
        color_arc=color_arc,
        propensity_index=propensity_index,
        style_fingerprint=style_fingerprint,
    )
    print(f"\nMarkdown report written: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
