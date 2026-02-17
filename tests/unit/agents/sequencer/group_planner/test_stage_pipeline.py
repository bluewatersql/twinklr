"""Unit tests for GroupPlannerStage pipeline timing context behavior."""

from __future__ import annotations

from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage
from twinklr.core.audio.models import SongBundle, SongTiming
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)


def _make_stage() -> GroupPlannerStage:
    return GroupPlannerStage(
        choreo_graph=ChoreographyGraph(
            graph_id="test",
            groups=[ChoreoGroup(id="G1", role="OUTLINE")],
        ),
        template_catalog=TemplateCatalog(entries=[]),
    )


def _make_bundle(features: dict[str, object]) -> SongBundle:
    return SongBundle(
        schema_version="3.0",
        audio_path="/tmp/test.mp3",
        recording_id="rec_1",
        features=features,
        timing=SongTiming(sr=22050, hop_length=512, duration_s=30.0, duration_ms=30000),
    )


def test_build_timing_context_uses_derived_beats_per_bar() -> None:
    """Timing context should honor derived meter from analysis features."""
    stage = _make_stage()
    bundle = _make_bundle({"tempo_bpm": 120.0, "assumptions": {"beats_per_bar": 3}})

    timing_context = stage._build_timing_context(
        bundle, section_id="sec_1", section_start_ms=0, section_end_ms=6000
    )

    assert timing_context.beats_per_bar == 3


def test_build_timing_context_warns_and_falls_back_to_4_4(caplog) -> None:
    """Missing derived meter should emit warning and fallback to 4/4."""
    stage = _make_stage()
    bundle = _make_bundle({"tempo_bpm": 120.0})

    with caplog.at_level("WARNING"):
        timing_context = stage._build_timing_context(
            bundle, section_id="sec_1", section_start_ms=0, section_end_ms=6000
        )

    assert timing_context.beats_per_bar == 4
    assert "falling back to 4/4" in caplog.text
