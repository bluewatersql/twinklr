"""Ground-truth tests for deterministic effect/grid scoring."""

from pathlib import Path

import pytest

from twinklr.core.reporting.evaluation.sync_metrics import (
    EffectInterval,
    StructureSection,
    beat_grid_from_xsq,
    effect_intervals_from_xsq,
    score_sync_metrics,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _grid() -> BeatGrid:
    return BeatGrid.from_tempo(tempo_bpm=120.0, total_bars=3)


def test_sync_metrics_on_known_grid() -> None:
    """A fixed +40ms phase shift has a known rate, mean and zero variance."""
    effects = [
        EffectInterval(start_ms=40, end_ms=500),
        EffectInterval(start_ms=540, end_ms=1000),
        EffectInterval(start_ms=1040, end_ms=1500),
    ]

    metrics = score_sync_metrics(
        beat_grid=_grid(),
        effects=effects,
        sections=[StructureSection(name="intro", start_ms=0, end_ms=2000, bars=1)],
        tolerance_ms=50,
    )

    assert metrics.beat_starts.on_grid_rate == 1.0
    assert metrics.beat_starts.offsets.mean_absolute_ms == pytest.approx(40.0)
    assert metrics.beat_starts.offsets.standard_deviation_ms == pytest.approx(0.0)
    assert metrics.beat_starts.offsets.signed_offsets_ms == [40.0, 40.0, 40.0]


def test_sync_metrics_detect_empty_section() -> None:
    metrics = score_sync_metrics(
        beat_grid=_grid(),
        effects=[EffectInterval(start_ms=100, end_ms=300)],
        sections=[
            StructureSection(name="intro", start_ms=0, end_ms=2000, bars=1),
            StructureSection(name="empty", start_ms=2000, end_ms=4000, bars=1),
        ],
    )

    by_name = {density.section_name: density for density in metrics.section_density}
    assert by_name["empty"].effect_count == 0
    assert by_name["empty"].effects_per_bar == 0.0


def test_sync_metrics_do_not_invent_alignment_without_effect_evidence() -> None:
    metrics = score_sync_metrics(
        beat_grid=_grid(),
        effects=[],
        sections=[StructureSection(name="silent", start_ms=0, end_ms=2000, bars=1)],
    )

    assert metrics.beat_starts.effect_count == 0
    assert metrics.beat_starts.on_grid_rate is None
    assert metrics.beat_starts.offsets.count == 0
    assert metrics.beat_starts.offsets.mean_absolute_ms is None
    assert metrics.section_boundaries.boundary_count == 2
    assert metrics.section_boundaries.aligned_count == 0
    assert metrics.section_boundaries.alignment_rate == 0.0
    assert metrics.section_boundaries.offsets.count == 0


def test_effect_intervals_are_read_from_rendered_xsq(tmp_path: Path) -> None:
    xsq = tmp_path / "fixture.xsq"
    xsq.write_text(
        """<?xml version="1.0"?><xsequence>
        <head><version>2026.15</version><mediaFile>song.mp3</mediaFile>
        <sequenceDuration>4.000</sequenceDuration></head><nextid>1</nextid>
        <ElementEffects>
        <Element type="timing" name="Twinklr Beats"><EffectLayer>
        <Effect label="1.1" startTime="0" endTime="1" />
        <Effect label="1.2" startTime="500" endTime="501" />
        <Effect label="1.3" startTime="1000" endTime="1001" />
        <Effect label="1.4" startTime="1500" endTime="1501" />
        <Effect label="2.1" startTime="2000" endTime="2001" />
        </EffectLayer></Element>
        <Element type="timing" name="Twinklr Bars"><EffectLayer>
        <Effect label="Bar 1" startTime="0" endTime="1" />
        <Effect label="Bar 2" startTime="2000" endTime="2001" />
        </EffectLayer></Element>
        <Element type="model" name="Head 1"><EffectLayer>
        <Effect name="On" startTime="40" endTime="500" palette="0" />
        </EffectLayer></Element></ElementEffects></xsequence>""",
        encoding="utf-8",
    )

    assert effect_intervals_from_xsq(xsq) == [
        EffectInterval(start_ms=40, end_ms=500, element_name="Head 1", layer_index=0)
    ]
    delivered_grid = beat_grid_from_xsq(xsq)
    assert delivered_grid.beat_boundaries == [0.0, 500.0, 1000.0, 1500.0, 2000.0]
    assert delivered_grid.bar_boundaries == [0.0, 2000.0]
    assert delivered_grid.beats_per_bar == 4
