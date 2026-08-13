"""End-to-end idempotency of content-hash corpus identity (P1K-T1).

Profiling the same archive twice must produce byte-identical primary keys, so
the feature store's ``INSERT OR REPLACE`` upsert actually replaces rather than
accumulating a second row per run.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from zipfile import ZipFile

import pytest

from twinklr.core.feature_store.backends.sqlite import SQLiteFeatureStore
from twinklr.core.feature_store.models import FeatureStoreConfig
from twinklr.core.profiling.profiler import SequencePackProfiler

pytestmark = pytest.mark.integration

_SEQUENCE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<xsequence BaseChannel="0" ChanCtrlBasic="0" ChanCtrlColor="0">
  <head>
    <version>2025.1</version>
    <mediaFile>song.mp3</mediaFile>
    <sequenceDuration>10.0</sequenceDuration>
    <song>Synthetic Song</song>
    <artist>Synthetic Artist</artist>
  </head>
  <EffectDB>
    <Effect>E_TEXTCTRL_Eff_speed=10</Effect>
  </EffectDB>
  <ElementEffects>
    <Element type="model" name="Arch 1">
      <EffectLayer>
        <Effect ref="0" name="Bars" startTime="100" endTime="200" palette="0"/>
        <Effect ref="0" name="On" startTime="300" endTime="500" palette="0"/>
      </EffectLayer>
    </Element>
  </ElementEffects>
</xsequence>
"""


def _write_pack(path: Path) -> None:
    """Build a minimal synthetic .xsqz pack (no vendor content)."""
    with ZipFile(path, "w") as archive:
        archive.writestr("sequence.xsq", _SEQUENCE_XML)
        archive.writestr("song.mp3", b"synthetic-audio-bytes")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SQLiteFeatureStore]:
    backend = SQLiteFeatureStore(
        FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "store.db")
    )
    backend.initialize()
    yield backend
    backend.close()


def test_reprofiling_same_archive_upserts_one_row(
    tmp_path: Path, store: SQLiteFeatureStore
) -> None:
    zip_path = tmp_path / "pack.xsqz"
    _write_pack(zip_path)

    profiler = SequencePackProfiler(store=store)
    first = profiler.profile(zip_path, tmp_path / "profile", force=True)
    second = profiler.profile(zip_path, tmp_path / "profile", force=True)

    assert first.manifest.package_id == second.manifest.package_id
    assert first.sequence_metadata.sequence_file_id == second.sequence_metadata.sequence_file_id
    assert tuple(e.effect_event_id for e in first.base_events.events) == tuple(
        e.effect_event_id for e in second.base_events.events
    )

    profiles = store.query_profiles()
    assert len(profiles) == 1
    assert store.get_corpus_stats().profile_count == 1
    expected_profile_id = f"{first.manifest.package_id}/{first.sequence_metadata.sequence_file_id}"
    assert profiles[0].profile_id == expected_profile_id


def test_distinct_archives_produce_distinct_profile_rows(
    tmp_path: Path, store: SQLiteFeatureStore
) -> None:
    first_zip = tmp_path / "first.xsqz"
    second_zip = tmp_path / "second.xsqz"
    _write_pack(first_zip)
    with ZipFile(second_zip, "w") as archive:
        archive.writestr("sequence.xsq", _SEQUENCE_XML)
        archive.writestr("song.mp3", b"different-audio-bytes")

    profiler = SequencePackProfiler(store=store)
    first = profiler.profile(first_zip, tmp_path / "profile_first", force=True)
    second = profiler.profile(second_zip, tmp_path / "profile_second", force=True)

    assert first.manifest.package_id != second.manifest.package_id
    assert store.get_corpus_stats().profile_count == 2
