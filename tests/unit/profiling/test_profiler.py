"""Unit tests for SequencePackProfiler orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from twinklr.core.formats.xlights.sequence.models.xsq import SequenceHead, XSequence
from twinklr.core.profiling.models.enums import FileKind
from twinklr.core.profiling.models.events import BaseEffectEventsFile
from twinklr.core.profiling.models.layout import LayoutMetadata, LayoutProfile, LayoutStatistics
from twinklr.core.profiling.models.pack import FileEntry, PackageManifest
from twinklr.core.profiling.profiler import SequencePackProfiler


def _manifest() -> PackageManifest:
    return PackageManifest(
        package_id="pkg",
        zip_sha256="zipsha",
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


def test_profiler_orchestration_and_writer_boundary(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_ingest_zip(_path: Path):
        calls.append("ingest")
        extracted = tmp_path / "extracted"
        extracted.mkdir(exist_ok=True)
        (extracted / "sequence.xsq").write_text("<xsequence></xsequence>", encoding="utf-8")
        (extracted / "xlights_rgbeffects.xml").write_text("<xrgb></xrgb>", encoding="utf-8")
        return _manifest(), extracted

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

    layout_profiler = MagicMock()

    def fake_layout_profile(_path: Path) -> LayoutProfile:
        calls.append("layout")
        return _layout_profile()

    layout_profiler.profile.side_effect = fake_layout_profile

    xsq_parser = MagicMock()
    xsq_parser.parse.return_value = XSequence(
        head=SequenceHead(version="2025.1", media_file="song.mp3", sequence_duration_ms=1000)
    )

    writer = MagicMock()

    profiler = SequencePackProfiler(
        layout_profiler=layout_profiler,
        xsq_parser=xsq_parser,
        artifact_writer=writer,
    )

    profile = profiler.profile(tmp_path / "pack.zip", tmp_path / "out")

    assert profile.sequence_metadata.sequence_file_id == "seq"
    assert profile.sequence_metadata.song == "song"
    assert "ingest" in calls
    assert "extract" in calls
    assert "enrich" in calls
    assert "layout" in calls
    assert calls.index("layout") < calls.index("extract")
    assert calls.index("extract") < calls.index("enrich")
    layout_profiler.profile.assert_called_once()
    assert (
        layout_profiler.profile.call_args[0][0] == tmp_path / "extracted" / "xlights_rgbeffects.xml"
    )
    writer.write_json_bundle.assert_called_once()
    writer.write_markdown_bundle.assert_called_once()
