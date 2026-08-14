"""P1P-T4: the renderer's bar->ms conversion resolves through detected downbeats.

`TemplateCompileContext` is where a plan's bar numbers become the millisecond
positions effects are written at. Before this task it multiplied by a song-wide
average anchored at 0 ms while the `.xsq`'s own "Twinklr Bars" track used the
detected downbeats, so the effects sat off the markers the user sees.
"""

from __future__ import annotations

import logging

import pytest

from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

# Bars of 2000 / 2500 / 1500 / 2500 ms starting at 1500 ms; average 2125 ms.
UNEVEN_BARS = [1500.0, 3500.0, 6000.0, 7500.0, 10000.0]


def make_grid(bar_boundaries: list[float]) -> BeatGrid:
    return BeatGrid(
        bar_boundaries=bar_boundaries,
        beat_boundaries=list(bar_boundaries),
        eighth_boundaries=[],
        sixteenth_boundaries=[],
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=bar_boundaries[-1],
    )


def make_context(
    beat_grid: BeatGrid, *, start_bar: int = 1, duration_bars: int = 2
) -> TemplateCompileContext:
    registries = create_default_registries()
    return TemplateCompileContext(
        section_id="section",
        template_id="template",
        fixtures=[],
        beat_grid=beat_grid,
        start_bar=start_bar,
        duration_bars=duration_bars,
        curve_registry=CurveRegistry(),
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
    )


@pytest.fixture
def uneven() -> BeatGrid:
    return make_grid(UNEVEN_BARS)


def test_bar_to_ms_uses_detected_boundaries(uneven: BeatGrid) -> None:
    """Bar 1 renders at the first detected downbeat, not at 0 ms."""
    context = make_context(uneven)
    assert context._bar_to_ms(1) == 1500
    assert context.start_ms == 1500


def test_bar_to_ms_does_not_multiply_the_average(uneven: BeatGrid) -> None:
    """Bar 3 is at 6000ms; two average bars from zero would be 4250ms."""
    context = make_context(uneven)
    assert context._bar_to_ms(3) == 6000


def test_section_duration_is_the_real_span(uneven: BeatGrid) -> None:
    """Bars 1-2 span 1500-6000ms (4500ms), not 2 x the 2125ms average."""
    context = make_context(uneven, start_bar=1, duration_bars=2)
    assert context.start_ms == 1500
    assert context.end_ms == 6000
    assert context.duration_ms == 4500


def test_bar_offset_to_ms_interpolates_inside_the_real_bar(uneven: BeatGrid) -> None:
    """A step half a bar into bar 3 lands 750ms in — half of *that* bar."""
    context = make_context(uneven, start_bar=3, duration_bars=1)
    assert context.bar_offset_to_ms(0.0) == 6000
    assert context.bar_offset_to_ms(0.5) == 6750
    assert context.bar_offset_to_ms(1.0) == 7500


def test_out_of_range_bar_falls_back_to_average(
    uneven: BeatGrid, caplog: pytest.LogCaptureFixture
) -> None:
    """A section past the detected grid still renders, on the average, with a log."""
    context = make_context(uneven, start_bar=5, duration_bars=4)
    with caplog.at_level(logging.DEBUG, logger="twinklr.core.sequencer.timing.beat_grid"):
        end_ms = context.end_ms

    assert context.start_ms == 10000
    assert end_ms == pytest.approx(10000 + 4 * uneven.ms_per_bar, abs=1)
    assert "past the detected grid" in caplog.text


def test_bar_round_trip_is_identity(uneven: BeatGrid) -> None:
    """Renderer and planner agree: ms -> bar -> ms returns the same bar."""
    context = make_context(uneven)
    for bar in range(1, len(UNEVEN_BARS) + 1):
        assert uneven.nearest_bar_index(float(context._bar_to_ms(bar))) + 1 == bar
