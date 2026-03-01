"""Unit tests for SequencePackProfiler store-integration (Phase 02)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock
import zipfile

import pytest

from twinklr.core.feature_store.backends.null import NullFeatureStore
from twinklr.core.feature_store.factory import create_feature_store
from twinklr.core.feature_store.models import FeatureStoreConfig

# ---------------------------------------------------------------------------
# Shared fake pipeline helpers
# ---------------------------------------------------------------------------
from twinklr.core.formats.xlights.sequence.models.xsq import SequenceHead, XSequence
from twinklr.core.profiling.models.enums import FileKind
from twinklr.core.profiling.models.events import BaseEffectEventsFile
from twinklr.core.profiling.models.layout import LayoutMetadata, LayoutProfile, LayoutStatistics
from twinklr.core.profiling.models.pack import FileEntry, PackageManifest
from twinklr.core.profiling.profiler import SequencePackProfiler


def _manifest(zip_sha: str = "zipsha") -> PackageManifest:
    return PackageManifest(
        package_id="pkg",
        zip_sha256=zip_sha,
        source_extensions=frozenset({".zip"}),
        files=(
            FileEntry(
                file_id="seq",
                filename="sequence.xsq",
                ext=".xsq",
                size=1,
                sha256="seqsha",
                kind=FileKind.SEQUENCE,
            ),
            FileEntry(
                file_id="rgb",
                filename="xlights_rgbeffects.xml",
                ext=".xml",
                size=1,
                sha256="rgbsha",
                kind=FileKind.RGB_EFFECTS,
            ),
        ),
        sequence_file_id="seq",
        rgb_effects_file_id="rgb",
    )


def _layout_profile() -> LayoutProfile:
    return LayoutProfile(
        metadata=LayoutMetadata(
            source_file="xlights_rgbeffects.xml",
            source_path="/tmp/xlights_rgbeffects.xml",
            file_sha256="rgbsha",
            file_size_bytes=1,
        ),
        statistics=LayoutStatistics(
            total_models=0,
            display_models=0,
            dmx_fixtures=0,
            auxiliary_models=0,
            inactive_models=0,
            total_submodels=0,
            model_chained_count=0,
            address_chained_count=0,
            chain_sequences=(),
            model_families={},
            model_type_distribution={},
            string_type_distribution={},
            semantic_tag_distribution={},
            protocol_distribution={},
            layout_group_distribution={},
        ),
        models=(),
        groups=(),
    )


def _make_fake_pipeline(monkeypatch, tmp_path: Path, zip_sha: str = "zipsha") -> list[str]:
    """Wire up monkeypatched pipeline stubs; return a shared call-log list."""
    calls: list[str] = []

    def fake_ingest_zip(_path: Path):
        calls.append("ingest")
        extracted = tmp_path / "extracted"
        extracted.mkdir(exist_ok=True)
        (extracted / "sequence.xsq").write_text("<xsequence></xsequence>", encoding="utf-8")
        (extracted / "xlights_rgbeffects.xml").write_text("<xrgb></xrgb>", encoding="utf-8")
        return _manifest(zip_sha), extracted

    def fake_extract_effect_events(*_args, **_kwargs):
        calls.append("extract")
        return BaseEffectEventsFile(
            package_id="pkg",
            sequence_file_id="seq",
            sequence_sha256="seqsha",
            events=(),
        )

    def fake_enrich_events(*_args, **_kwargs):
        calls.append("enrich")
        return ()

    monkeypatch.setattr("twinklr.core.profiling.profiler.ingest_zip", fake_ingest_zip)
    monkeypatch.setattr(
        "twinklr.core.profiling.profiler.extract_effect_events", fake_extract_effect_events
    )
    monkeypatch.setattr("twinklr.core.profiling.profiler.enrich_events", fake_enrich_events)
    return calls


def _make_xsq_parser() -> MagicMock:
    parser = MagicMock()
    parser.parse.return_value = XSequence(
        head=SequenceHead(version="2025.1", media_file="song.mp3", sequence_duration_ms=60000)
    )
    return parser


def _make_layout_profiler() -> MagicMock:
    lp = MagicMock()
    lp.profile.return_value = _layout_profile()
    return lp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_minimal_zip(tmp_path: Path, name: str = "pack") -> Path:
    """Create minimal zip with sequence + rgbeffects for profiling."""
    zip_path = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "sequence.xsq",
            '<?xml version="1.0"?><xsequence version="2025.1">'
            "<head><mediafile/><sequenceduration>60000</sequenceduration></head>"
            "<models/><effects/></xsequence>",
        )
        zf.writestr("xlights_rgbeffects.xml", "<xrgb></xrgb>")
    return zip_path


@pytest.fixture
def synthetic_zip(tmp_path: Path) -> Path:
    return _make_minimal_zip(tmp_path)


@pytest.fixture
def tmp_sqlite_store(tmp_path: Path):
    db_path = tmp_path / "store.db"
    config = FeatureStoreConfig(backend="sqlite", db_path=db_path)
    store = create_feature_store(config)
    store.initialize()
    try:
        yield store
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_profile_without_store(monkeypatch, tmp_path: Path) -> None:
    """store=None: full pipeline runs and NullFeatureStore is used internally."""
    calls = _make_fake_pipeline(monkeypatch, tmp_path)
    writer = MagicMock()

    profiler = SequencePackProfiler(
        layout_profiler=_make_layout_profiler(),
        xsq_parser=_make_xsq_parser(),
        artifact_writer=writer,
        store=None,
    )
    profile = profiler.profile(tmp_path / "pack.zip", tmp_path / "out")

    assert "ingest" in calls
    assert "extract" in calls
    assert "enrich" in calls
    assert profile.sequence_metadata.sequence_file_id == "seq"
    # Internal store must be NullFeatureStore when none is supplied
    assert isinstance(profiler._store, NullFeatureStore)
    writer.write_json_bundle.assert_called_once()


def test_profile_registers_in_store(monkeypatch, tmp_path: Path, tmp_sqlite_store) -> None:
    """After profiling with a real SQLite store, a ProfileRecord exists in the store."""
    calls = _make_fake_pipeline(monkeypatch, tmp_path)
    monkeypatch.setattr("twinklr.core.profiling.profiler.sha256_file", lambda p: "zipsha")
    writer = MagicMock()

    profiler = SequencePackProfiler(
        layout_profiler=_make_layout_profiler(),
        xsq_parser=_make_xsq_parser(),
        artifact_writer=writer,
        store=tmp_sqlite_store,
    )
    profiler.profile(tmp_path / "pack.zip", tmp_path / "out")

    assert "ingest" in calls
    records = tmp_sqlite_store.query_profiles()
    assert len(records) == 1
    record = records[0]
    assert record.package_id == "pkg"
    assert record.sequence_file_id == "seq"
    assert record.fe_status == "pending"


def test_profile_skip_sha_match(monkeypatch, tmp_path: Path, tmp_sqlite_store) -> None:
    """Second call with same zip SHA skips full pipeline (no re-ingest)."""
    calls = _make_fake_pipeline(monkeypatch, tmp_path)
    # sha256_file must return the same value as the manifest's zip_sha256 ("zipsha")
    monkeypatch.setattr("twinklr.core.profiling.profiler.sha256_file", lambda p: "zipsha")
    writer = MagicMock()
    output_dir = tmp_path / "out"

    profiler = SequencePackProfiler(
        layout_profiler=_make_layout_profiler(),
        xsq_parser=_make_xsq_parser(),
        artifact_writer=writer,
        store=tmp_sqlite_store,
    )

    # First call — full pipeline runs, artifacts written to disk
    profiler.profile(tmp_path / "pack.zip", output_dir)
    ingest_count_after_first = calls.count("ingest")
    assert ingest_count_after_first == 1

    # The profile_dir in the store must exist for skip to trigger.
    # Writer is mocked, so write all artifacts manually.
    _write_minimal_artifacts(output_dir)

    # Second call — should skip because SHA matches and profile_dir exists
    profiler.profile(tmp_path / "pack.zip", output_dir)
    assert calls.count("ingest") == 1  # ingest was NOT called again


def test_profile_skip_file_fallback(monkeypatch, tmp_path: Path) -> None:
    """NullFeatureStore + sequence_metadata.json on disk → skip, return loaded profile."""
    calls = _make_fake_pipeline(monkeypatch, tmp_path)
    writer = MagicMock()
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write the artifacts that _load_existing_profile needs
    _write_minimal_artifacts(output_dir)

    profiler = SequencePackProfiler(
        layout_profiler=_make_layout_profiler(),
        xsq_parser=_make_xsq_parser(),
        artifact_writer=writer,
        store=None,  # NullFeatureStore
    )

    profile = profiler.profile(tmp_path / "pack.zip", output_dir)

    # No ingest because file fallback triggered
    assert "ingest" not in calls
    assert profile.sequence_metadata.sequence_file_id == "seq"


def test_profile_force_overrides_skip(monkeypatch, tmp_path: Path, tmp_sqlite_store) -> None:
    """force=True when SHA match exists → full pipeline runs anyway."""
    calls = _make_fake_pipeline(monkeypatch, tmp_path)
    monkeypatch.setattr("twinklr.core.profiling.profiler.sha256_file", lambda p: "zipsha")
    writer = MagicMock()
    output_dir = tmp_path / "out"

    profiler = SequencePackProfiler(
        layout_profiler=_make_layout_profiler(),
        xsq_parser=_make_xsq_parser(),
        artifact_writer=writer,
        store=tmp_sqlite_store,
    )

    # First call — registers record in store
    profiler.profile(tmp_path / "pack.zip", output_dir)
    assert calls.count("ingest") == 1

    # Make profile_dir appear to exist so the skip would normally trigger
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_minimal_artifacts(output_dir)

    # Second call with force=True — must run full pipeline
    profiler.profile(tmp_path / "pack.zip", output_dir, force=True)
    assert calls.count("ingest") == 2


def test_profile_new_sha_processes(monkeypatch, tmp_path: Path, tmp_sqlite_store) -> None:
    """Different zip (different SHA) → full profiling runs for new zip."""
    calls: list[str] = []

    def fake_extract(*_args, **_kwargs):
        return BaseEffectEventsFile(
            package_id="pkg", sequence_file_id="seq", sequence_sha256="seqsha", events=()
        )

    def fake_enrich(*_args, **_kwargs):
        return ()

    monkeypatch.setattr("twinklr.core.profiling.profiler.extract_effect_events", fake_extract)
    monkeypatch.setattr("twinklr.core.profiling.profiler.enrich_events", fake_enrich)

    # First zip with sha "sha_a" and distinct package_id
    def fake_ingest_a(_path: Path):
        calls.append("ingest_a")
        extracted = tmp_path / "extracted_a"
        extracted.mkdir(exist_ok=True)
        (extracted / "sequence.xsq").write_text("<xsequence></xsequence>", encoding="utf-8")
        (extracted / "xlights_rgbeffects.xml").write_text("<xrgb></xrgb>", encoding="utf-8")
        return _manifest("sha_a"), extracted

    monkeypatch.setattr("twinklr.core.profiling.profiler.ingest_zip", fake_ingest_a)

    sha_counter = {"value": "sha_a"}
    monkeypatch.setattr(
        "twinklr.core.profiling.profiler.sha256_file", lambda p: sha_counter["value"]
    )
    writer = MagicMock()

    profiler = SequencePackProfiler(
        layout_profiler=_make_layout_profiler(),
        xsq_parser=_make_xsq_parser(),
        artifact_writer=writer,
        store=tmp_sqlite_store,
    )

    # First profiling run (sha_a)
    profiler.profile(tmp_path / "pack_a.zip", tmp_path / "out_a")
    assert calls.count("ingest_a") == 1
    assert len(tmp_sqlite_store.query_profiles()) == 1

    # Now change SHA to sha_b — different zip; still same profile_id so upsert replaces
    sha_counter["value"] = "sha_b"

    def fake_ingest_b(_path: Path):
        calls.append("ingest_b")
        extracted = tmp_path / "extracted_b"
        extracted.mkdir(exist_ok=True)
        (extracted / "sequence.xsq").write_text("<xsequence></xsequence>", encoding="utf-8")
        (extracted / "xlights_rgbeffects.xml").write_text("<xrgb></xrgb>", encoding="utf-8")
        return _manifest("sha_b"), extracted

    monkeypatch.setattr("twinklr.core.profiling.profiler.ingest_zip", fake_ingest_b)

    profiler.profile(tmp_path / "pack_b.zip", tmp_path / "out_b")
    assert calls.count("ingest_b") == 1  # new SHA → full profiling ran
    # Same profile_id ("pkg/seq"), so upsert replaces — still 1 record, but with updated SHA
    records = tmp_sqlite_store.query_profiles()
    assert len(records) == 1
    assert records[0].zip_sha256 == "sha_b"


def test_profile_registers_correct_metadata(monkeypatch, tmp_path: Path, tmp_sqlite_store) -> None:
    """ProfileRecord has correct package_id, sequence_file_id, song, duration_ms."""
    _make_fake_pipeline(monkeypatch, tmp_path)
    monkeypatch.setattr("twinklr.core.profiling.profiler.sha256_file", lambda p: "zipsha")
    writer = MagicMock()

    profiler = SequencePackProfiler(
        layout_profiler=_make_layout_profiler(),
        xsq_parser=_make_xsq_parser(),
        artifact_writer=writer,
        store=tmp_sqlite_store,
    )
    profiler.profile(tmp_path / "pack.zip", tmp_path / "out")

    records = tmp_sqlite_store.query_profiles()
    assert len(records) == 1
    rec = records[0]
    assert rec.package_id == "pkg"
    assert rec.sequence_file_id == "seq"
    assert rec.song == "song"
    assert rec.duration_ms == 60000
    assert rec.effect_total_events == 0
    assert rec.fe_status == "pending"
    assert rec.profile_id == "pkg/seq"


def test_profile_skip_with_missing_dir(monkeypatch, tmp_path: Path, tmp_sqlite_store) -> None:
    """Store has record but profile_dir deleted → re-profiles (no skip)."""
    calls = _make_fake_pipeline(monkeypatch, tmp_path)
    monkeypatch.setattr("twinklr.core.profiling.profiler.sha256_file", lambda p: "zipsha")
    writer = MagicMock()
    output_dir = tmp_path / "out"

    profiler = SequencePackProfiler(
        layout_profiler=_make_layout_profiler(),
        xsq_parser=_make_xsq_parser(),
        artifact_writer=writer,
        store=tmp_sqlite_store,
    )

    # First call — registers record; output_dir is NOT created because writer is mocked
    profiler.profile(tmp_path / "pack.zip", output_dir)
    assert calls.count("ingest") == 1

    # Verify record exists in store
    records = tmp_sqlite_store.query_profiles()
    assert len(records) == 1

    # profile_dir does NOT exist (writer was mocked, nothing written to disk)
    assert not output_dir.exists()

    # Second call — record exists in store but dir missing → must re-profile
    profiler.profile(tmp_path / "pack.zip", output_dir)
    assert calls.count("ingest") == 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_minimal_artifacts(output_dir: Path) -> None:
    """Write the JSON files that _load_existing_profile reads."""
    output_dir.mkdir(parents=True, exist_ok=True)

    seq_meta = {
        "package_id": "pkg",
        "sequence_file_id": "seq",
        "sequence_sha256": "seqsha",
        "xlights_version": "2025.1",
        "sequence_duration_ms": 60000,
        "media_file": "song.mp3",
        "image_dir": "",
        "song": "song",
        "artist": "",
        "album": "",
        "author": "",
    }
    (output_dir / "sequence_metadata.json").write_text(json.dumps(seq_meta), encoding="utf-8")

    manifest_data = {
        "package_id": "pkg",
        "zip_sha256": "zipsha",
        "source_extensions": [".zip"],
        "files": [
            {
                "file_id": "seq",
                "filename": "sequence.xsq",
                "ext": ".xsq",
                "size": 1,
                "sha256": "seqsha",
                "kind": "sequence",
            }
        ],
        "sequence_file_id": "seq",
        "rgb_effects_file_id": None,
    }
    (output_dir / "package_manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

    base_events = {
        "package_id": "pkg",
        "sequence_file_id": "seq",
        "sequence_sha256": "seqsha",
        "events": [],
    }
    (output_dir / "base_effect_events.json").write_text(json.dumps(base_events), encoding="utf-8")

    (output_dir / "enriched_effect_events.json").write_text(json.dumps([]), encoding="utf-8")

    effect_stats = {
        "total_events": 0,
        "distinct_effect_types": 0,
        "total_effect_duration_ms": 0,
        "avg_effect_duration_ms": 0.0,
        "total_targets_with_effects": 0,
        "effect_type_counts": {},
        "effect_type_durations_ms": {},
        "effect_type_profiles": {},
        "effects_per_target": {},
        "layers_per_target": {},
    }
    (output_dir / "effect_statistics.json").write_text(json.dumps(effect_stats), encoding="utf-8")

    empty_classifications = {
        "monochrome": [],
        "warm": [],
        "cool": [],
        "primary_only": [],
        "by_color_family": {},
    }
    color_palettes = {
        "unique_colors": [],
        "single_colors": [],
        "color_palettes": [],
        "classifications": empty_classifications,
    }
    (output_dir / "color_palettes.json").write_text(json.dumps(color_palettes), encoding="utf-8")

    (output_dir / "asset_inventory.json").write_text(json.dumps([]), encoding="utf-8")
    (output_dir / "shader_inventory.json").write_text(json.dumps([]), encoding="utf-8")

    lineage = {
        "package_id": "pkg",
        "zip_sha256": "zipsha",
        "sequence_file": {"file_id": "seq", "filename": "sequence.xsq"},
        "rgb_effects_file": None,
        "layout_id": None,
        "rgb_sha256": None,
    }
    (output_dir / "lineage_index.json").write_text(json.dumps(lineage), encoding="utf-8")
