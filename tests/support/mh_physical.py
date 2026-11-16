"""Synthetic physical-renderer inputs: a fixture profile, a known initial state,
physical fixture segments, the P1.6 pipeline case (rig, grid, job, plan and the
test-only template), rig presets with steps that reference them, multi-head rigs
with a topology, steps on relative paths, and visibility envelopes and attribute overlays.

In-memory payloads only; no owner profile or measured data.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import copy
from fractions import Fraction
from pathlib import Path
from typing import Any

from tests.support.mh_true_up import synthetic_case
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.config.fixtures import (
    AxisCapability,
    FixtureCapabilities,
    FixtureGroup,
    InitialFixtureState,
)
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName, SemanticGroupType
from twinklr.core.sequencer.models.moving_heads.physical import (
    AXIS_KEYS,
    DISCRETE_KEYS,
    PhysicalValue,
    RenderLock,
)
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import PrepositionResult
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    encode_fixture_frames,
    frame_times,
)
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    load_template_document,
    load_templates_from_directory,
)
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def physical_segment(
    channels: dict[ChannelName, PhysicalValue],
    *,
    t0_ms: int,
    t1_ms: int,
    fixture_id: str = "MH1",
    segment_id: str = "seg",
    section_id: str = "section",
) -> FixtureSegment:
    """A fixture segment whose channels hold only typed physical values."""
    return FixtureSegment(
        section_id=section_id,
        segment_id=segment_id,
        step_id="step",
        template_id="template",
        fixture_id=fixture_id,
        t0_ms=t0_ms,
        t1_ms=t1_ms,
        channels={
            name: ChannelValue(channel=name, physical=value) for name, value in channels.items()
        },
    )


def profile_payload() -> dict[str, Any]:
    """A synthetic 8-channel spot: 16-bit pan/tilt, dimmer, shutter, color and a spare."""
    return {
        "profile_id": "synthetic_spot",
        "provenance": "synthetic",
        "footprint": 8,
        "defaults": {1: 128, 2: 0, 3: 128, 4: 0, 5: 0, 6: 64, 7: 0, 8: 0},
        "axes": {
            "pan": {
                "unit": "degree",
                "physical_min": -270.0,
                "physical_max": 270.0,
                "coarse_offset": 1,
                "fine_offset": 2,
            },
            "tilt": {
                "unit": "degree",
                "physical_min": -135.0,
                "physical_max": 135.0,
                "coarse_offset": 3,
                "fine_offset": 4,
            },
            "dimmer": {
                "unit": "normalized",
                "physical_min": 0.0,
                "physical_max": 1.0,
                "coarse_offset": 5,
            },
        },
        "discrete": {
            "shutter": {
                "offset": 6,
                "states": {
                    "closed": {"range_min": 64, "range_max": 95, "value": 64},
                    "open": {"range_min": 0, "range_max": 31, "value": 8},
                },
                "default_state": "closed",
                "closed_state": "closed",
                "open_state": "open",
            },
            "color": {
                "offset": 7,
                "states": {
                    "white": {"range_min": 0, "range_max": 9, "value": 0},
                    "red": {"range_min": 10, "range_max": 19, "value": 14},
                },
                "default_state": "white",
            },
        },
        "visibility": {
            "dimmer_zero_extinguishes": True,
            "extinguishing_shutter_states": ["closed"],
            "close_latency_ms": 0,
            "open_latency_ms": 0,
        },
    }


def initial_state_payload() -> dict[str, Any]:
    """A known, settled, dark time-zero state the profile above accepts."""
    return {
        "pan_deg": 0.0,
        "tilt_deg": 0.0,
        "dimmer": 0.0,
        "discrete_states": {"shutter": "closed", "color": "red"},
        "settled": True,
        "dark": True,
    }


def motion_profile_payload() -> dict[str, Any]:
    """`profile_payload` with configured pan/tilt travel speeds and settled shutter states."""
    payload = profile_payload()
    for axis in ("pan", "tilt"):
        payload["axes"][axis]["travel_speed_per_s"] = 720.0
    for state in payload["discrete"]["shutter"]["states"].values():
        state["settle_ms"] = 0
    return payload


def preposition_profile_payload() -> dict[str, Any]:
    """`motion_profile_payload` with every timing the transaction pass reads declared.

    Pan/tilt latency and settle and color settle are explicit zeros, so a test states
    only the timing it is about.
    """
    payload = motion_profile_payload()
    for axis in ("pan", "tilt"):
        payload["axes"][axis].update(latency_ms=0, settle_ms=0)
    for state in payload["discrete"]["color"]["states"].values():
        state["settle_ms"] = 0
    return payload


def discrete_profile_payload() -> dict[str, Any]:
    """`motion_profile_payload` with the shutter on channel 17 and color and gobo wheels.

    Closed is byte 64 and open byte 8, inside ranges whose bounds are not the selected
    bytes; each wheel has a state between its first and last selected bytes.
    """
    payload = motion_profile_payload()
    payload["footprint"] = 18
    payload["defaults"] = {
        **payload["defaults"],
        **dict.fromkeys(range(9, 17), 0),
        17: 64,
        18: 0,
    }
    payload["discrete"]["shutter"].update(
        offset=17,
        states={
            "closed": {"range_min": 60, "range_max": 95, "value": 64, "settle_ms": 0},
            "open": {"range_min": 0, "range_max": 31, "value": 8, "settle_ms": 0},
        },
    )
    payload["discrete"]["color"]["states"] = {
        "white": {"range_min": 0, "range_max": 9, "value": 0, "settle_ms": 120},
        "red": {"range_min": 10, "range_max": 19, "value": 14, "settle_ms": 120},
        "blue": {"range_min": 20, "range_max": 29, "value": 26, "settle_ms": 140},
    }
    payload["discrete"]["gobo"] = {
        "offset": 18,
        "states": {
            "open": {"range_min": 0, "range_max": 7, "value": 0, "settle_ms": 150},
            "dots": {"range_min": 8, "range_max": 15, "value": 10, "settle_ms": 150},
            "star": {"range_min": 16, "range_max": 23, "value": 20, "settle_ms": 160},
        },
        "default_state": "open",
    }
    return payload


def discrete_step_payload() -> dict[str, Any]:
    """A physical step holding its pose with static shutter, color and gobo states."""
    return {
        "step_id": "look",
        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 0.5}},
        "geometry": {},
        "movement": {
            "physical": {
                "shape": "hold",
                "mode": "periodic",
                "start_pan_deg": 0.0,
                "start_tilt_deg": 0.0,
            }
        },
        "dimmer": {},
        "physical_shutter_state": "open",
        "physical_color": "white",
        "physical_gobo": "open",
    }


def physical_step_payload() -> dict[str, Any]:
    """A physical-only template step: finite linear pan/tilt plus dimmer and shutter pulses."""
    return {
        "step_id": "main",
        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 0.5}},
        "geometry": {},
        "movement": {
            "physical": {
                "shape": "linear",
                "mode": "finite",
                "start_pan_deg": 10.0,
                "start_tilt_deg": 20.0,
                "pan_extent_deg": 30.0,
                "tilt_extent_deg": 10.0,
                "period_beats": 1.0,
            }
        },
        "dimmer": {"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}},
        "physical_shutter": {
            "period_beats": 2.0,
            "duty_cycle": 0.5,
            "low_state": "closed",
            "high_state": "open",
        },
    }


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "moving_heads" / "physical_v2"
"""Test-only physical templates, loaded by the data loader and never shipped."""
TEMPLATE_ID = "p1_linear_reveal"
SUBSET_TEMPLATE_ID = "p1_linear_reveal_right"
BUILTIN_TEMPLATE_COUNT = 37
GRID_SHIFT_MS = 15.0
PHYSICAL_INITIAL_STATE = {
    "pan_deg": 0.0,
    "tilt_deg": 0.0,
    "dimmer": 0.0,
    "discrete_states": {"shutter": "closed", "color": "white", "gobo": "open"},
    "settled": True,
    "dark": True,
}


@contextmanager
def physical_test_templates() -> Iterator[None]:
    """Register the test template (and a variant targeting only RIGHT) for one test.

    They are never admitted to the production catalog: the process-wide registry,
    which the pipeline and the deterministic selector read, is restored on exit.
    """
    load_builtin_templates()
    loaded = load_templates_from_directory(TEMPLATE_DIR)
    try:
        document = load_template_document(TEMPLATE_DIR / f"{TEMPLATE_ID}.json")
        template = document.template.model_copy(
            update={"template_id": SUBSET_TEMPLATE_ID, "name": "P1 Linear Reveal Right"}
        )
        template.steps[0].target = SemanticGroupType.RIGHT
        if REGISTRY.register_document(document.model_copy(update={"template": template})):
            loaded.append(SUBSET_TEMPLATE_ID)
        yield
    finally:
        for template_id in loaded:
            REGISTRY._remove_registration(template_id)


def physical_grid() -> BeatGrid:
    """P0's variable-tempo grid (500 ms beats, then 400 ms), moved off the frame grid."""
    tempo = synthetic_case("tempo").beat_grid
    beats = [beat + GRID_SHIFT_MS for beat in tempo.beat_boundaries]
    return BeatGrid(
        bar_boundaries=[bar + GRID_SHIFT_MS for bar in tempo.bar_boundaries],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=tempo.tempo_bpm,
        beats_per_bar=tempo.beats_per_bar,
        duration_ms=tempo.duration_ms + GRID_SHIFT_MS,
    )


def physical_edge_grid(
    *, lead_in_ms: float, tail_ms: float, grid: BeatGrid | None = None
) -> BeatGrid:
    """`grid` (default `physical_grid()`) with silent song edges: its beats and bars move
    `lead_in_ms` later and the song ends `tail_ms` after its last beat."""
    grid = grid or physical_grid()
    beats = [beat + lead_in_ms for beat in grid.beat_boundaries]
    return grid.model_copy(
        update={
            "bar_boundaries": [bar + lead_in_ms for bar in grid.bar_boundaries],
            "beat_boundaries": beats,
            "eighth_boundaries": BeatGrid._calculate_eighth_boundaries(beats),
            "sixteenth_boundaries": BeatGrid._calculate_sixteenth_boundaries(beats),
            "duration_ms": beats[-1] + tail_ms,
        }
    )


def physical_bars_grid(*beat_ms: float) -> BeatGrid:
    """A 4/4 grid moved `GRID_SHIFT_MS` off the frame grid, whose nth bar has four beats of
    `beat_ms[n]`; the song ends `GRID_SHIFT_MS` after its last beat."""
    beats = [GRID_SHIFT_MS]
    for interval in beat_ms:
        beats += [beats[-1] + interval * (index + 1) for index in range(4)]
    return BeatGrid(
        bar_boundaries=beats[::4],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=60_000 / beat_ms[0],
        beats_per_bar=4,
        duration_ms=beats[-1] + GRID_SHIFT_MS,
    )


def hold_step(
    step_id: str,
    pan: float,
    *,
    tilt: float = 0.0,
    start: float = 0.0,
    duration: float = 1.0,
    **fields: Any,
) -> dict[str, Any]:
    """A lit physical step holding one aim over `duration` bars from `start` bars."""
    return {
        "step_id": step_id,
        "timing": {"base_timing": {"start_offset_bars": start, "duration_bars": duration}},
        "geometry": {},
        "movement": {
            "physical": {
                "shape": "hold",
                "mode": "periodic",
                "start_pan_deg": pan,
                "start_tilt_deg": tilt,
            }
        },
        "dimmer": {"physical": {"period_beats": 4.0, "duty_cycle": 1.0, "low": 0.0, "high": 1.0}},
        "physical_shutter_state": "open",
        **fields,
    }


def sweep_step(
    step_id: str, pan: float, extent: float, *, period_beats: float = 4.0, **fields: Any
) -> dict[str, Any]:
    """`hold_step` whose pan moves linearly by `extent` over `period_beats`, then holds."""
    step = hold_step(step_id, pan, **fields)
    step["movement"]["physical"].update(
        shape="linear", mode="finite", pan_extent_deg=extent, period_beats=period_beats
    )
    return step


def path_step(
    step_id: str,
    shape: str,
    *,
    pan: float = 0.0,
    tilt: float = 0.0,
    pan_extent: float = 20.0,
    tilt_extent: float | None = None,
    period_beats: float = 4.0,
    mode: str = "periodic",
    transform: dict[str, Any] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """`hold_step` moving on a relative `circle`, `lissajous` or `sweep` path about its aim,
    with an optional path `transform`. The tilt extent defaults to 10, or 0 for a sweep,
    which moves along pan."""
    step = hold_step(step_id, pan, tilt=tilt, **fields)
    if tilt_extent is None:
        tilt_extent = 0.0 if shape == "sweep" else 10.0
    step["movement"]["physical"].update(
        shape=shape,
        mode=mode,
        pan_extent_deg=pan_extent,
        tilt_extent_deg=tilt_extent,
        period_beats=period_beats,
    )
    if transform is not None:
        step["movement"]["physical"]["transform"] = transform
    return step


def envelope_step(
    step_id: str,
    pan: float,
    extent: float,
    *,
    lit: tuple[float, float],
    attack: float = 0.0,
    release: float = 0.0,
    level: float = 1.0,
    period_beats: float = 4.0,
    **fields: Any,
) -> dict[str, Any]:
    """`sine_step` lit only over the movement phases `lit` by a visibility envelope, which
    replaces its dimmer; the shutter holds `open`."""
    step = sine_step(step_id, pan, extent, period_beats=period_beats, **fields)
    step["dimmer"] = {}
    step["physical_visibility"] = {
        "visible_phase_start": lit[0],
        "visible_phase_end": lit[1],
        "attack_beats": attack,
        "release_beats": release,
        "level": level,
    }
    return step


def overlay(
    channel: str, start: float, end: float, mask: float, state: str | None = None, **fields: Any
) -> dict[str, Any]:
    """An attribute overlay on `channel` over beats `[start, end)` of each cycle."""
    payload = {
        "channel": channel,
        "start_beats": start,
        "end_beats": end,
        "mask_beats": mask,
        **fields,
    }
    if state is not None:
        payload["state"] = state
    return payload


def physical_template_doc(
    template_id: str,
    steps: Sequence[dict[str, Any]],
    *,
    cycle_bars: float = 1.0,
    mode: str = "JOINER",
    remainder_policy: str = "HOLD_LAST_POSE",
    overlays: Sequence[dict[str, Any]] = (),
) -> TemplateDoc:
    """A physical template looping every step once per `cycle_bars` (JOINER by default),
    with optional attribute `overlays`."""
    template: dict[str, Any] = {
        "template_id": template_id,
        "version": 1,
        "name": template_id,
        "category": "low_energy",
        "repeat": {
            "mode": mode,
            "cycle_bars": cycle_bars,
            "loop_step_ids": [step["step_id"] for step in steps],
            "remainder_policy": remainder_policy,
        },
        "steps": list(steps),
        "metadata": {
            "tags": ["test_only", "physical_v2"],
            "recommended_sections": ["verse"],
            "energy_range": [0, 100],
            "description": "Test-only physical template, never in the catalog.",
        },
    }
    if overlays:
        template["physical_overlays"] = list(overlays)
    return TemplateDoc.model_validate({"template": template})


@contextmanager
def registered_templates(*documents: TemplateDoc) -> Iterator[None]:
    """Register test-only template documents for one test, then remove them again."""
    load_builtin_templates()
    added: list[str] = []
    try:
        for document in documents:
            if REGISTRY.register_document(document):
                added.append(document.template.template_id)
        yield
    finally:
        for template_id in added:
            REGISTRY._remove_registration(template_id)


def physical_sections(*sections: tuple[str, int, int]) -> ChoreographyPlan:
    """A plan of `(template_id, start_bar, end_bar)` sections, no planner intent."""
    return ChoreographyPlan(
        sections=[
            PlanSection.model_validate(
                {
                    "section_name": f"s{index}",
                    "start_bar": start,
                    "end_bar": end,
                    "template_id": template_id,
                    "preset_id": None,
                }
            )
            for index, (template_id, start, end) in enumerate(sections, start=1)
        ]
    )


def physical_head_profile(*, inverted: bool, pan_max: float = 270.0) -> dict[str, Any]:
    """Channel-17 shutter, 16-bit pan/tilt, 720°/s travel and 40 ms settle."""
    payload = discrete_profile_payload()
    for axis in ("pan", "tilt"):
        payload["axes"][axis].update(latency_ms=0, settle_ms=40, inverted=inverted)
    payload["axes"]["pan"]["physical_max"] = pan_max
    return payload


def physical_rig(*, mh1_pan_max: float = 270.0) -> FixtureGroup:
    """P0's two-head 16-bit rig with a synthetic physical profile per head."""
    payload = synthetic_case("fine_carry").fixture_groups[0].model_dump(mode="python")
    for fixture in payload["fixtures"]:
        mh1 = fixture["fixture_id"] == "MH1"
        fixture["config"]["physical_profile"] = physical_head_profile(
            inverted=not mh1, pan_max=mh1_pan_max if mh1 else 270.0
        )
    return FixtureGroup.model_validate(payload)


def preset_library_payload() -> dict[str, Any]:
    """Rig presets for `physical_rig`'s two heads, in its profile's state names.

    `front` and `wash` declare MH1 only and fall back to `home` and `wash_all` for MH2;
    `side` and `cool` declare both heads.
    """
    return {
        "positions": {
            "front": {
                "fixtures": {"MH1": {"pan_deg": -30.0, "tilt_deg": 20.0}},
                "fallback": "home",
            },
            "home": {
                "fixtures": {
                    "MH1": {"pan_deg": 0.0, "tilt_deg": 0.0},
                    "MH2": {"pan_deg": 10.0, "tilt_deg": 5.0},
                }
            },
            "side": {
                "fixtures": {
                    "MH1": {"pan_deg": 60.0, "tilt_deg": 30.0},
                    "MH2": {"pan_deg": -60.0, "tilt_deg": 30.0},
                }
            },
        },
        "attributes": {
            "wash": {
                "fixtures": {
                    "MH1": {"shutter": "open", "color": "red", "gobo": "dots", "dimmer": 0.8}
                },
                "fallback": "wash_all",
            },
            "wash_all": {
                "fixtures": {
                    "MH1": {"shutter": "open", "color": "white", "gobo": "open", "dimmer": 1.0},
                    "MH2": {"shutter": "open", "color": "blue", "gobo": "star", "dimmer": 0.6},
                }
            },
            "cool": {"fixtures": {"MH1": {"color": "blue"}, "MH2": {"color": "white"}}},
        },
    }


def physical_preset_rig(presets: dict[str, Any] | None = None) -> FixtureGroup:
    """`physical_rig` carrying `presets` (default `preset_library_payload()`)."""
    payload = physical_rig().model_dump(mode="python")
    payload["presets"] = preset_library_payload() if presets is None else presets
    return FixtureGroup.model_validate(payload)


def referencing_step(
    step_id: str = "look",
    *,
    position_id: str | None = "front",
    attribute_preset_ids: Sequence[str] = ("wash",),
    start: float = 0.0,
    duration: float = 1.0,
    **fields: Any,
) -> dict[str, Any]:
    """A physical hold step whose aim and held states come from rig presets alone."""
    return {
        "step_id": step_id,
        "timing": {"base_timing": {"start_offset_bars": start, "duration_bars": duration}},
        "geometry": {},
        "movement": {"physical": {"shape": "hold", "mode": "periodic"}},
        "dimmer": {},
        "component_refs": {
            "position_id": position_id,
            "attribute_preset_ids": list(attribute_preset_ids),
        },
        **fields,
    }


def topology_payload(
    fixture_ids: Sequence[str], *, rows: Sequence[int] | None = None
) -> dict[str, Any]:
    """A topology listing `fixture_ids` in canonical order: column and ordinal are each
    head's index, row is 0 or `rows[index]`."""
    return {
        "members": [
            {
                "fixture_id": fixture_id,
                "row": 0 if rows is None else rows[index],
                "column": index,
                "ordinal": index,
            }
            for index, fixture_id in enumerate(fixture_ids)
        ]
    }


def topology_rig(
    fixture_ids: Sequence[str],
    *,
    topology: dict[str, Any] | None = None,
    position_indexes: Sequence[int] | None = None,
    presets: dict[str, Any] | None = None,
) -> FixtureGroup:
    """A rig of `fixture_ids` heads, each `physical_rig`'s MH1 (one non-inverted profile),
    with an optional declared `topology`, `position.position_index` per head and presets."""
    payload = physical_rig().model_dump(mode="python")
    head = payload["fixtures"][0]
    fixtures = []
    for index, fixture_id in enumerate(fixture_ids):
        fixture = copy.deepcopy(head)
        fixture["fixture_id"] = fixture["config"]["fixture_id"] = fixture_id
        fixture["xlights_model_name"] = f"Dmx {fixture_id}"
        if position_indexes is not None:
            fixture["config"]["position"] = {"position_index": position_indexes[index]}
        fixtures.append(fixture)
    payload["fixtures"] = fixtures
    if topology is not None:
        payload["topology"] = topology
    if presets is not None:
        payload["presets"] = presets
    return FixtureGroup.model_validate(payload)


def sine_step(
    step_id: str,
    pan: float,
    extent: float,
    *,
    period_beats: float = 4.0,
    distribution: Sequence[dict[str, Any]] = (),
    **fields: Any,
) -> dict[str, Any]:
    """`hold_step` whose pan swings `extent * sin(2*pi*phase)` over `period_beats`, with
    an optional `physical_distribution`."""
    step = hold_step(step_id, pan, **fields)
    step["movement"]["physical"].update(
        shape="sine_pan", mode="periodic", pan_extent_deg=extent, period_beats=period_beats
    )
    if distribution:
        step["physical_distribution"] = list(distribution)
    return step


def physical_job(**policy: Any) -> JobConfig:
    """A schema-3.1 `physical_v2` job with both heads' known dark initial state."""
    return JobConfig.model_validate(
        {
            "schema_version": "3.1",
            "moving_heads": {
                "mode": "physical_v2",
                "initial_states": {"MH1": PHYSICAL_INITIAL_STATE, "MH2": PHYSICAL_INITIAL_STATE},
                **policy,
            },
        }
    )


def physical_plan(template_id: str = TEMPLATE_ID) -> ChoreographyPlan:
    """One two-bar section, no planner intent, naming `template_id`."""
    return ChoreographyPlan(
        sections=[
            PlanSection.model_validate(
                {
                    "section_name": "verse",
                    "start_bar": 1,
                    "end_bar": 2,
                    "template_id": template_id,
                    "preset_id": None,
                }
            )
        ]
    )


def physical_layout_xml(models: dict[str, dict[str, str]] | None = None) -> str:
    """A synthetic `xlights_rgbeffects.xml` with the physical rig's two DMX models.

    Each model carries the attributes xLights 2026.19 writes for an 18-channel DMX
    moving head (`DmxChannelCount`, no `parm1`) unless `models` overrides them (an
    attribute set to "" is left out).
    """
    attributes = {
        name: {
            "DisplayAs": "DmxMovingHeadAdv",
            "StringType": "Single Color White",
            "DmxChannelCount": "18",
            "versionNumber": "8",
            "SourceVersion": "2026.19",
        }
        for name in ("Dmx MH1", "Dmx MH2")
    }
    for name, override in (models or {}).items():
        attributes[name] = {**attributes.get(name, {}), **override}
    rows = "".join(
        f'    <model name="{name}" '
        + " ".join(f'{key}="{value}"' for key, value in attrs.items() if value)
        + " />\n"
        for name, attrs in attributes.items()
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<xrgb>\n  <models>\n{rows}  </models>\n</xrgb>\n'
    )


def assert_honest_transactions(
    result: PrepositionResult,
    inputs: Sequence[FixtureSegment],
    profile: FixtureCapabilities,
    initial: InitialFixtureState,
    *,
    locks: Sequence[RenderLock] = (),
    fixture_id: str = "MH1",
) -> None:
    """Check one fixture of a planned result from its encoded bytes and the profile alone.

    The head follows its commands: a pan/tilt word change at frame time `c` is reached
    at `max(previous arrival, c + latency_ms) + word distance / travel_speed_per_s` and
    settled `settle_ms` later; a wheel change settles its new state's `settle_ms` after
    `c`; an unknown value never settles. A frame is optically lit unless it is
    commanded dark (declared dimmer zero, or an extinguishing shutter state) by a run
    that started at least `close_latency_ms` (plus the shutter state's `settle_ms`) before;
    a run reaching time zero is dark already only through the mechanism the dark initial
    state evidences (its zero dimmer, or its own extinguishing shutter state).

    Asserted: the result encodes with the full footprint and covers every frame up to
    its end; a feasible cue's frames equal the cue encoded alone, a `preserve_aim` cue
    changes only its held pose, a dropped cue is commanded dark; no wheel turns or
    settles in a lit frame, inside a cue or not; no pose change outside a cue's own
    content moves or settles in a lit frame; a cue's own motion still under
    way when light returns after the planner darkened the fixture past its end (a
    transaction, a park or a substituted cue; not a following cue's own dark frames) is a
    leak; back-to-back cues
    step within one frame's travel and keep their wheels; a lit cue after a transaction
    reveals on its own frame; no locked frame differs from the cues alone.
    """
    assert not result.has_errors, result.diagnostics
    outputs = [s for s in result.segments if s.fixture_id == fixture_id]
    cues = [s for s in inputs if s.fixture_id == fixture_id]
    times = frame_times(max(s.t1_ms for s in outputs))
    count = len(times)
    out = [dict(f.channels) for f in encode_fixture_frames(outputs, profile, frame_times_ms=times)]
    alone = [dict(f.channels) for f in encode_fixture_frames(cues, profile, frame_times_ms=times)]
    footprint = list(range(1, profile.footprint + 1))
    assert all(sorted(frame) == footprint for frame in out)
    covered = {t for s in outputs for t in range(s.t0_ms, s.t1_ms, EFFECT_GRID_MS)}
    assert covered >= set(times), f"frames {sorted(set(times) - covered)[:5]} are not authored"

    status = {d.cue_ms: d.status for d in result.diagnostics if d.fixture_id == fixture_id}
    cue_at: list[FixtureSegment | None] = [None] * count
    for cue in cues:
        for index in range(cue.t0_ms // EFFECT_GRID_MS, cue.t1_ms // EFFECT_GRID_MS):
            cue_at[index] = cue

    visibility = profile.visibility
    dimmer = profile.axes.get("dimmer")
    shutter = profile.discrete.get("shutter")
    by_byte = {} if shutter is None else {s.value: n for n, s in shutter.states.items()}
    infinite = Fraction(10**12)
    # The initial state evidences darkness only through the mechanism it names: a dimmer
    # at zero that the profile declares extinguishing, or its own extinguishing shutter.
    initial_dimmer_dark = (
        initial.dark and visibility.dimmer_zero_extinguishes and initial.dimmer == 0
    )
    initial_shutter = initial.discrete_states.get("shutter") if initial.dark else None

    def dimmer_dark(frame: dict[int, int]) -> bool:
        return (
            visibility.dimmer_zero_extinguishes
            and dimmer is not None
            and _word(frame, dimmer) == dimmer.dmx_word(0)
        )

    def shutter_dark(frame: dict[int, int]) -> str | None:
        state = None if shutter is None else by_byte[frame[shutter.offset]]
        return state if state in visibility.extinguishing_shutter_states else None

    commanded_dark = [dimmer_dark(f) or shutter_dark(f) is not None for f in out]
    # A frame is lit if any part of it is; every query below starts on a frame start.
    lit: list[bool] = []
    dimmer_run = shutter_run = Fraction(0)
    for index, frame in enumerate(out):
        start = Fraction(times[index])
        dark_from = infinite
        close = visibility.close_latency_ms
        if dimmer_dark(frame):
            if index == 0 or not dimmer_dark(out[index - 1]):
                dimmer_run = -infinite if index == 0 and initial_dimmer_dark else start
            if dimmer_run == -infinite:  # dark initial state: evidence, no latency needed
                dark_from = -infinite
            elif close is not None:
                dark_from = min(dark_from, dimmer_run + close)
        state = shutter_dark(frame)
        if state is not None:
            if index == 0 or shutter_dark(out[index - 1]) != state:
                shutter_run = -infinite if index == 0 and state == initial_shutter else start
            settle = shutter.states[state].settle_ms if shutter is not None else None
            if shutter_run == -infinite:
                dark_from = -infinite
            elif close is not None and settle is not None:
                dark_from = min(dark_from, shutter_run + close + settle)
        lit.append(not commanded_dark[index] or dark_from > start)

    def lit_between(begin: Fraction, end: Fraction) -> int | None:
        first = max(0, int(begin // EFFECT_GRID_MS))
        for index in range(first, count):
            if times[index] >= end:
                break
            if lit[index] and times[index] + EFFECT_GRID_MS > begin:
                return times[index]
        return None

    def kind(index: int) -> str:
        if index == 0:
            return "transition"
        before, here = cue_at[index - 1], cue_at[index]
        if before is not None and before is here and status.get(here.t0_ms) != "drop_accent":
            return "content"
        if (
            before is not None
            and here is not None
            and before.t1_ms == here.t0_ms
            and status.get(before.t0_ms) == status.get(here.t0_ms) == "feasible"
        ):
            return "continuation"
        return "transition"

    def relit_after(cue: FixtureSegment) -> int | None:
        """The first lit frame after a frame the planner darkened, both at or after the
        cue's end. A frame a cue played as authored commands dark itself hides nothing:
        there the head follows the cues' own path, as it would were the frame lit."""
        seen_dark = False
        for index in range(cue.t1_ms // EFFECT_GRID_MS, count):
            here = cue_at[index]
            if not commanded_dark[index]:
                if seen_dark:
                    return times[index]
            elif here is None or status.get(here.t0_ms) != "feasible":
                seen_dark = True
        return None

    def check_busy(index: int, busy_end: Fraction, what: str) -> None:
        change = Fraction(times[index])
        if kind(index) == "transition":
            hit = lit_between(change, busy_end)
            assert hit is None, f"{what} changes at {change} ms and is lit at {hit} ms while busy"
            return
        cue = cue_at[index]
        assert cue is not None
        relit = relit_after(cue)
        if relit is not None:
            hit = lit_between(max(change, Fraction(relit)), busy_end)
            assert hit is None, f"{what} motion from {change} ms in {cue.segment_id} leaks to {hit}"

    initial_words: dict[int, int] = {}
    for name, axis in profile.axes.items():
        if name in ("pan", "tilt"):
            word = axis.dmx_word(initial.pan_deg if name == "pan" else initial.tilt_deg)
            initial_words |= _split(axis, word)
    for name, wheel in profile.discrete.items():
        initial_words[wheel.offset] = wheel.resolve(initial.discrete_states[name])

    for name, axis in profile.axes.items():
        if name not in ("pan", "tilt"):
            continue
        per_word = (Fraction(axis.physical_max) - Fraction(axis.physical_min)) / axis.full_word
        speed, latency, settle = axis.travel_speed_per_s, axis.latency_ms, axis.settle_ms
        arrival = Fraction(0)
        previous = _word(initial_words, axis)
        for index, frame in enumerate(out):
            word = _word(frame, axis)
            if word == previous:
                continue
            distance = abs(word - previous) * per_word
            previous = word
            if kind(index) == "continuation":
                assert speed is not None and distance <= Fraction(speed) * EFFECT_GRID_MS / 1000, (
                    f"{name} jumps {float(distance):g} across the cue at {times[index]} ms"
                )
            if speed is None or latency is None or settle is None:
                arrival = infinite
            else:
                arrival = max(
                    arrival, Fraction(times[index] + latency)
                ) + distance * 1000 / Fraction(speed)
            check_busy(index, arrival + (settle or 0), name)

    for name, wheel in profile.discrete.items():
        if name == "shutter":
            continue
        previous = initial_words[wheel.offset]
        for index, frame in enumerate(out):
            if frame[wheel.offset] == previous:
                continue
            previous = frame[wheel.offset]
            assert kind(index) != "continuation", f"{name} changes between back-to-back cues"
            selected = next(s for s in wheel.states.values() if s.value == previous)
            # A wheel is masked when it turns, so even an instant one needs a dark frame;
            # that holds inside a cue's own content too.
            settle_at = (
                infinite
                if selected.settle_ms is None
                else Fraction(times[index] + max(selected.settle_ms, 1))
            )
            hit = lit_between(Fraction(times[index]), settle_at)
            assert hit is None, f"{name} turns at {times[index]} ms and is lit at {hit} ms"

    pose_offsets = [o for c in (ChannelName.PAN, ChannelName.TILT) for o in _offsets(profile, c)]
    for cue in cues:
        span = range(cue.t0_ms // EFFECT_GRID_MS, cue.t1_ms // EFFECT_GRID_MS)
        cue_status = status.get(cue.t0_ms)
        if cue_status == "feasible":
            assert all(out[i] == alone[i] for i in span), f"cue {cue.segment_id} was changed"
        elif cue_status == "preserve_aim":
            for i in span:
                assert all(out[i][o] == alone[i][o] for o in footprint if o not in pose_offsets)
                assert all(out[i][o] == out[span[0]][o] for o in pose_offsets)
        elif cue_status == "drop_accent":
            assert all(commanded_dark[i] for i in span), f"dropped {cue.segment_id} is lit"
        else:
            raise AssertionError(f"cue {cue.segment_id} has no diagnostic")
        first = span[0]
        if first and cue_at[first - 1] is None and not commanded_dark[first]:
            assert commanded_dark[first - 1], f"cue {cue.segment_id} is revealed early"

    for lock in locks:
        if fixture_id not in lock.fixture_ids:
            continue
        start = lock.start_ms // EFFECT_GRID_MS * EFFECT_GRID_MS
        end = -(-lock.end_ms // EFFECT_GRID_MS) * EFFECT_GRID_MS
        offsets = [offset for channel in lock.channels for offset in _offsets(profile, channel)]
        for time_ms, frame, cue_frame in zip(times, out, alone, strict=True):
            if start <= time_ms < end:
                assert all(frame[o] == cue_frame[o] for o in offsets), f"lock changed at {time_ms}"


def _word(frame: dict[int, int], axis: AxisCapability) -> int:
    if axis.fine_offset is None:
        return frame[axis.coarse_offset]
    return frame[axis.coarse_offset] << 8 | frame[axis.fine_offset]


def _split(axis: AxisCapability, word: int) -> dict[int, int]:
    if axis.fine_offset is None:
        return {axis.coarse_offset: word}
    return {axis.coarse_offset: word >> 8, axis.fine_offset: word & 0xFF}


def _offsets(profile: FixtureCapabilities, channel: ChannelName) -> list[int]:
    if channel in AXIS_KEYS:
        axis = profile.axes.get(AXIS_KEYS[channel])
        if axis is None:
            return []
        return [axis.coarse_offset] + ([] if axis.fine_offset is None else [axis.fine_offset])
    wheel = profile.discrete.get(DISCRETE_KEYS[channel])
    return [] if wheel is None else [wheel.offset]
