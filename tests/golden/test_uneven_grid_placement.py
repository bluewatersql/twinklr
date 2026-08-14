"""P1P-T4: effect placement on a real, uneven beat grid.

The rest of the golden suite renders against `build_beat_grid()` — metronomic,
first downbeat at 0 ms — where the song-wide average bar duration and the detected
downbeats coincide exactly. Under that grid, placing effects at
`(bar - 1) x avg_ms_per_bar` and placing them on the detected downbeats produce
identical output, so it cannot show whether the renderer is using the real grid.

`build_uneven_beat_grid()` separates them the way a real recording does: the first
downbeat sits at 1500 ms (intro before the band comes in) and each bar is 12 ms
longer than the last (tempo easing off). These goldens pin placement against that
grid, and `test_effect_start_matches_bars_timing_track` proves the property the
goldens are a consequence of: every section's first effect starts exactly on the
"Twinklr Bars" marker for that section's start bar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.golden.harness import (
    RIGS,
    assert_or_write_golden,
    build_plan,
    build_uneven_beat_grid,
    golden_path,
    render_golden_text,
    render_rig,
)
from twinklr.core.formats.xlights.sequence.timeline import (
    TimelineTracksConfig,
    build_timeline_tracks,
)

if TYPE_CHECKING:
    from tests.golden.harness import RenderResult

GOLDEN_DIR = "mh4_minimal_uneven"
GRID_LABEL = "uneven: first downbeat 1500 ms, bars growing 12 ms each (P1P-T4)"


@pytest.fixture(scope="module")
def uneven_render() -> RenderResult:
    """The 4-head reference rig rendered against the uneven grid."""
    return render_rig(RIGS["mh4_minimal"], beat_grid=build_uneven_beat_grid())


def test_uneven_grid_section_golden(uneven_render: RenderResult, regen_goldens: bool) -> None:
    """Pin the emitted effects for every rendered section on the uneven grid."""
    sections = uneven_render.sections()
    assert sections, "the uneven-grid render produced no effects at all"

    for section_id in sections:
        assert_or_write_golden(
            golden_path(GOLDEN_DIR, section_id),
            render_golden_text(uneven_render, section_id, grid_label=GRID_LABEL),
            regen=regen_goldens,
        )


def test_effect_start_matches_bars_timing_track(uneven_render: RenderResult) -> None:
    """The headline three-way agreement: effects land on the "Twinklr Bars" markers.

    The plan's bar numbers, the rendered effect start times, and the timing track
    written into the same `.xsq` all name the same instants — exactly, with no
    tolerance, for bars inside the detected range.
    """
    grid = build_uneven_beat_grid()
    tracks = build_timeline_tracks(
        TimelineTracksConfig(beats=False, bars=True, sections=False, lyrics=False),
        beat_grid=grid,
    )
    bars_track = next(track for track in tracks if track.name == "Twinklr Bars")
    marker_ms = {marker.name: marker.time_ms for marker in bars_track.markers}

    for section in build_plan().sections:
        effects = uneven_render.for_section(section.section_name)
        assert effects, f"section {section.section_name} rendered nothing"
        first_start = min(effect.t0_ms for effect in effects)
        assert first_start == marker_ms[f"Bar {section.start_bar}"], (
            f"section '{section.section_name}' starts at {first_start}ms but its "
            f"start bar {section.start_bar} is marked at "
            f"{marker_ms[f'Bar {section.start_bar}']}ms in the Twinklr Bars track"
        )


def test_first_effect_is_not_at_zero(uneven_render: RenderResult) -> None:
    """The constant-offset case, stated bluntly.

    Before P1P-T4 the first effect started at t=0 while the first bar marker sat at
    1500 ms. A regression to average-grid placement fails here first.
    """
    assert min(effect.t0_ms for effect in uneven_render.effects) == 1500


def test_later_sections_do_not_drift_from_their_markers(
    uneven_render: RenderResult,
) -> None:
    """Drift, not just offset: the average grid gets further out as the tempo moves.

    The `breakdown` section starts at bar 13. On the song-wide average
    (2090 ms/bar from 0 ms) that is 25080 ms; on the detected grid it is 26292 ms.
    The 1212 ms gap is offset *plus* accumulated drift, which is why correcting the
    anchor alone would not be enough.
    """
    grid = build_uneven_beat_grid()
    average_placement = int(12 * grid.ms_per_bar)
    detected_placement = int(grid.get_bar_start_ms(12))
    assert average_placement != detected_placement

    breakdown_start = min(effect.t0_ms for effect in uneven_render.for_section("breakdown"))
    assert breakdown_start == detected_placement
