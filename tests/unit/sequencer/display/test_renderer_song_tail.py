"""The display renderer keeps rendering after the last detected beat."""

from __future__ import annotations

from twinklr.core.sequencer.display.renderer import DisplayRenderer
from twinklr.core.sequencer.planning import GroupPlanSet
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import EffectDuration

from .test_renderer_overlay import (
    _load_recipe_compiler,
    _make_choreo_graph,
    _make_plan_set,
    _make_sequence,
    _make_xlights_mapping,
)

_DETECTED_END_MS = 16_000.0
_SONG_END_MS = 24_300.0


def _grid_that_stops_early() -> BeatGrid:
    """120 BPM grid whose detected beats stop 8.3 s before the audio ends."""
    beats = [i * 500.0 for i in range(int(_DETECTED_END_MS / 500.0) + 1)]
    return BeatGrid(
        bar_boundaries=[i * 2000.0 for i in range(int(_DETECTED_END_MS / 2000.0) + 1)],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=_SONG_END_MS,
    )


def _section_long_plan_set() -> GroupPlanSet:
    plan_set = _make_plan_set()
    section = plan_set.section_plans[0]
    coordination = section.lane_plans[0].coordination_plans[0]
    placement = coordination.placements[0].model_copy(update={"duration": EffectDuration.SECTION})
    return plan_set.model_copy(
        update={
            "section_plans": [
                section.model_copy(
                    update={
                        "lane_plans": [
                            section.lane_plans[0].model_copy(
                                update={
                                    "coordination_plans": [
                                        coordination.model_copy(update={"placements": [placement]})
                                    ]
                                }
                            )
                        ]
                    }
                )
            ]
        }
    )


def test_section_past_the_last_detected_beat_renders_to_the_song_end() -> None:
    renderer = DisplayRenderer(
        beat_grid=_grid_that_stops_early(),
        choreo_graph=_make_choreo_graph(),
        template_compiler=_load_recipe_compiler(),
        xlights_mapping=_make_xlights_mapping(),
    )

    result = renderer.render(
        _section_long_plan_set(),
        _make_sequence(),
        section_boundaries=[("intro", 8_000, int(_SONG_END_MS))],
    )

    events = [
        event
        for group in result.render_plan.groups
        for layer in group.layers
        for event in layer.events
    ]
    assert events
    assert min(event.start_ms for event in events) == 8_000
    assert max(event.end_ms for event in events) == 24_300 // 20 * 20
