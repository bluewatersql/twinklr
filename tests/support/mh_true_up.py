"""Adversarial synthetic moving-head cases for the true-up (P0-T3).

Eight named cases, built entirely in memory: no environment variables, no local
config files (`config.json`, `job_config.json`, `fixture_config.json`), no audio.
Later phases use them to prove precision, timing and state behavior.

A case marked `legacy_runnable` is a single-section plan naming one builtin template,
and `legacy_outcomes` records what the current legacy `RenderingPipeline` produces
for each of its fixture groups. That is a baseline, not a statement of desired output.

`physical_inputs` are input definitions only. They describe behavior no renderer
implements yet; their speed, range and timing values are synthetic test inputs, not
calibration facts. They are plain typed values so P1 can convert them into its own
models without this module depending on any of them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Literal

from tests.golden.harness import PLAN_BPM, RIGS, RigSpec, build_fixture_group
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
    ShutterEvent,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.fixtures.dmx import ChannelInversions, DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig, FixtureInstance
from twinklr.core.sequencer.moving_heads.libraries.shutter import ShutterPattern
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

LegacyOutcome = Literal["rendered", "unsupported_rig_shape"]
"""`unsupported_rig_shape` is the compiler's `UnsupportedRigShapeError`."""

PhysicalInput = bool | int | float | str | tuple[object, ...]


@dataclass(frozen=True)
class SyntheticMHCase:
    """One synthetic moving-head case and its expected-case metadata."""

    case_id: str
    exposes: str
    """What the case is built to expose."""
    plan: ChoreographyPlan | None
    """None for an input-only case: a plan section must name a template, and an
    input-only case runs none."""
    beat_grid: BeatGrid
    fixture_groups: tuple[FixtureGroup, ...]
    """One group per rig; only `counts` has more than one."""
    template_id: str | None
    """The builtin template the plan names; None for an input-only case."""
    legacy_runnable: bool
    legacy_outcomes: tuple[LegacyOutcome, ...]
    """Legacy baseline per fixture group; empty when the case is not legacy-runnable."""
    physical_inputs: Mapping[str, PhysicalInput]


def _single_section_plan(
    *, end_bar: int, template_id: str, shutter_events: list[ShutterEvent] | None = None
) -> ChoreographyPlan:
    fields: dict[str, object] = {
        "section_name": "section",
        "start_bar": 1,
        "end_bar": end_bar,
        "template_id": template_id,
        "preset_id": None,
    }
    if shutter_events is not None:
        fields["shutter_events"] = shutter_events
    return ChoreographyPlan(sections=[PlanSection.model_validate(fields)])


def _even_grid(*, bars: int, beats_per_bar: int = 4) -> BeatGrid:
    """A metronomic grid one bar longer than the section, as the harness builds it."""
    return BeatGrid.from_tempo(tempo_bpm=PLAN_BPM, total_bars=bars + 1, beats_per_bar=beats_per_bar)


def _counts() -> SyntheticMHCase:
    head_counts = (1, 2, 3, 4, 6, 8)
    template_id = "split_lr_sweep_counter"
    return SyntheticMHCase(
        case_id="counts",
        exposes="Role/topology and subset behavior across 1, 2, 3, 4, 6 and 8 heads",
        plan=_single_section_plan(end_bar=4, template_id=template_id),
        beat_grid=_even_grid(bars=4),
        fixture_groups=tuple(
            build_fixture_group(replace(RIGS["mh4_minimal"], fixture_count=count))
            for count in head_counts
        ),
        template_id=template_id,
        legacy_runnable=True,
        # The template addresses LEFT and RIGHT; a single head is CENTER only.
        legacy_outcomes=(
            "unsupported_rig_shape",
            "rendered",
            "rendered",
            "rendered",
            "rendered",
            "rendered",
        ),
        physical_inputs={"head_counts": head_counts},
    )


def _fine_carry() -> SyntheticMHCase:
    # Each fine channel sits below its coarse channel and is not adjacent to it.
    mapping = {
        "pan_channel": 11,
        "pan_fine_channel": 2,
        "tilt_channel": 13,
        "tilt_fine_channel": 9,
        "dimmer_channel": 15,
        "use_16bit_pan_tilt": True,
    }
    group = FixtureGroup(group_id="MOVING_HEADS", xlights_group="GROUP - MOVING HEADS")
    for fixture_id, inverted in (("MH1", False), ("MH2", True)):
        group.add_fixture(
            FixtureInstance(
                fixture_id=fixture_id,
                config=FixtureConfig(
                    fixture_id=fixture_id,
                    dmx_mapping=DmxMapping.model_validate(mapping),
                    inversions=ChannelInversions(pan=inverted, tilt=inverted),
                ),
                xlights_model_name=f"Dmx {fixture_id}",
            )
        )
    template_id = "sweep_lr_fan_hold"
    return SyntheticMHCase(
        case_id="fine_carry",
        exposes="255->256 coarse/fine word carry and inversion on nonadjacent channels",
        plan=_single_section_plan(end_bar=4, template_id=template_id),
        beat_grid=_even_grid(bars=4),
        fixture_groups=(group,),
        template_id=template_id,
        legacy_runnable=True,
        legacy_outcomes=("rendered",),
        physical_inputs={
            # 16-bit words and their (coarse, fine) bytes, plain then inverted.
            "carry_words": (255, 256),
            "carry_bytes": ((0, 255), (1, 0)),
            "inverted_carry_bytes": ((255, 0), (254, 255)),
        },
    )


def _channel_edges() -> SyntheticMHCase:
    rig = RigSpec(
        rig_id="channel_edges",
        description="4 heads with shutter on channel 17, one above the plan-intent window",
        fixture_count=4,
        pan_channel=11,
        tilt_channel=13,
        dimmer_channel=15,
        shutter_channel=17,
    )
    template_id = "sweep_lr_fan_hold"
    return SyntheticMHCase(
        case_id="channel_edges",
        exposes="Backend channel ceiling versus the old plan-intent ceiling",
        plan=_single_section_plan(
            end_bar=4,
            template_id=template_id,
            shutter_events=[
                ShutterEvent(bar=1, beat=1, pattern=ShutterPattern.STROBE_FAST, moment_cue_id=None)
            ],
        ),
        beat_grid=_even_grid(bars=4),
        fixture_groups=(build_fixture_group(rig),),
        template_id=template_id,
        legacy_runnable=True,
        legacy_outcomes=("rendered",),
        physical_inputs={"shutter_channel_supported_max": 48, "shutter_channel_unsupported": 49},
    )


def _tempo() -> SyntheticMHCase:
    # 500 ms beats in bar 1, 400 ms beats in bar 2; 3600 is bar 2's closing edge.
    beats = [0.0, 500.0, 1000.0, 1500.0, 2000.0, 2400.0, 2800.0, 3200.0, 3600.0]
    bars = [0.0, 2000.0, 3600.0]
    grid = BeatGrid(
        bar_boundaries=bars,
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=60000.0 * (len(beats) - 1) / (beats[-1] - beats[0]),
        beats_per_bar=4,
        duration_ms=bars[-1],
    )
    # A 2-bar cycle exactly spans the 2-bar section, across the tempo change.
    template_id = "ballyhoo_chaos"
    return SyntheticMHCase(
        case_id="tempo",
        exposes="Exact internal musical phase across a tempo change",
        plan=_single_section_plan(end_bar=2, template_id=template_id),
        beat_grid=grid,
        fixture_groups=(build_fixture_group(RIGS["mh4_minimal"]),),
        template_id=template_id,
        legacy_runnable=True,
        legacy_outcomes=("rendered",),
        physical_inputs={},
    )


def _meter3() -> SyntheticMHCase:
    # Four 3/4 bars hold exactly one 4-bar cycle of a pulsed dimmer.
    template_id = "bounce_fan_pulse"
    return SyntheticMHCase(
        case_id="meter3",
        exposes="No assumed four-beat subdivision",
        plan=_single_section_plan(end_bar=4, template_id=template_id),
        beat_grid=_even_grid(bars=4, beats_per_bar=3),
        fixture_groups=(build_fixture_group(RIGS["mh4_minimal"]),),
        template_id=template_id,
        legacy_runnable=True,
        legacy_outcomes=("rendered",),
        physical_inputs={},
    )


def _finite() -> SyntheticMHCase:
    # A 5-bar section against a 6-bar cycle: the FADE_IN build and ACCENT_SNAP drop
    # play once and the FADE_OUT recover is cut off halfway, so the fade never closes.
    template_id = "build_drop_recover"
    return SyntheticMHCase(
        case_id="finite",
        exposes="End-state/wrap semantics: non-closing fade, one-shot accent, short section",
        plan=_single_section_plan(end_bar=5, template_id=template_id),
        beat_grid=_even_grid(bars=5),
        fixture_groups=(build_fixture_group(RIGS["mh4_minimal"]),),
        template_id=template_id,
        legacy_runnable=True,
        legacy_outcomes=("rendered",),
        physical_inputs={},
    )


def _state() -> SyntheticMHCase:
    return SyntheticMHCase(
        case_id="state",
        exposes="Feasibility honesty: unknown pose, known darkness, too-short dark gap",
        plan=None,
        beat_grid=_even_grid(bars=2),
        fixture_groups=(build_fixture_group(RIGS["mh4_minimal"]),),
        template_id=None,
        legacy_runnable=False,
        legacy_outcomes=(),
        physical_inputs={
            "initial_pose_known": False,
            "initial_dimmer_known": True,
            "initial_dimmer": 0.0,
            # Dark for 100 ms before the bar-2 downbeat, but the reposition across
            # it needs 500 ms at the synthetic speed.
            "dark_gap_start_ms": 1900,
            "dark_gap_end_ms": 2000,
            "gap_pan_from_deg": -90.0,
            "gap_pan_to_deg": 90.0,
            "synthetic_pan_speed_deg_per_s": 360.0,
        },
    )


def _locks() -> SyntheticMHCase:
    return SyntheticMHCase(
        case_id="locks",
        exposes="Motion locked while intensity changes",
        plan=None,
        beat_grid=_even_grid(bars=2),
        fixture_groups=(build_fixture_group(RIGS["mh4_minimal"]),),
        template_id=None,
        legacy_runnable=False,
        legacy_outcomes=(),
        physical_inputs={
            "locked_channels": ("pan", "tilt"),
            "lock_start_ms": 0,
            "lock_end_ms": 4000,
            # (time ms, normalized dimmer level)
            "dimmer_keyframes": ((0, 0.25), (2000, 1.0), (4000, 0.5)),
        },
    )


_BUILDERS: dict[str, Callable[[], SyntheticMHCase]] = {
    "counts": _counts,
    "fine_carry": _fine_carry,
    "channel_edges": _channel_edges,
    "tempo": _tempo,
    "meter3": _meter3,
    "finite": _finite,
    "state": _state,
    "locks": _locks,
}

CASE_IDS: tuple[str, ...] = tuple(_BUILDERS)


def synthetic_case(case_id: str) -> SyntheticMHCase:
    """Build a fresh synthetic case.

    Raises:
        ValueError: If `case_id` is not one of `CASE_IDS`.
    """
    builder = _BUILDERS.get(case_id)
    if builder is None:
        raise ValueError(f"Unknown synthetic moving-head case {case_id!r}; known: {CASE_IDS}")
    return builder()
