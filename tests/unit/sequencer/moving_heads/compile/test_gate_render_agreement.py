"""Differential fuzz: a plan over templates the pre-planning gate admits always renders.

Since the render keeps a cue it cannot play honestly dark (`on_unplayable="dark"`, the
default), the gate checks the placements a template plays at whatever the plan, and the
render degrades the rest. Random templates (every P2.3 path shape, envelopes, overlays,
distributions, rig presets, `ONCE` and repeating cycles, both remainder policies, mixed
per-step fallbacks) on random 8- and 16-bit rigs and steady, variable, jittered and
block-tempo grids, under each fallback policy, with random plans of 1 to 12 consecutive
sections over the admitted templates. Under `dark`: every plan renders; replanning its
cues gives the same segments; every fixture passes `assert_honest_transactions` from its
bytes; every cue kept dark for being unplayable is commanded dark over its frames and
covered by no played cue, and the trace's totals count them; removing a head changes no
other head's frames. Under `error`, the seeds known to fail after admission still fail.

Two generators reproduce the reviewers' seeds: the P2.4b reviewer's (`_check_seed`) and
the gate-coverage reviewer's (`_check_target_seed`, whose `target` arm draws short cycles,
slow rigs, tempo blocks and `drop_accent`). The default run takes their known seeds and a
short sweep of each; set `TWINKLR_GATE_FUZZ=full` for a long one. `degrade_rate` reports
the share of authored cue frames a run kept dark.
"""

from __future__ import annotations

import os
import random
from typing import Any

from pydantic import ValidationError
import pytest

from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    assert_honest_transactions,
    hold_step,
    path_step,
    physical_job,
    physical_sections,
    physical_template_doc,
    registered_templates,
    sine_step,
    sweep_step,
    topology_payload,
    topology_rig,
)
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.moving_heads.physical import PhysicalChannelError
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import PhysicalCompileError
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import frame_times
from twinklr.core.sequencer.moving_heads.pipeline import (
    PhysicalRenderError,
    RenderingPipeline,
    check_physical_templates,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

_FULL = os.environ.get("TWINKLR_GATE_FUZZ") == "full"
GATE_FUZZ_SEEDS = 2000 if _FULL else 15
TARGET_FUZZ_SEEDS = 1000 if _FULL else 6
_KNOWN = (437, 1892, 3283, 2431, 5391, 5440, 5846)
"""P2.4b-generator seeds admitted and then refused at render by an earlier gate: a
`drop_accent` cascade entered at another cue (437, 1892, 3283), a remainder after the
last cycle (2431), a cycle started on another bar (5391, 5846) and a ONCE cycle a section
is too short for (5440)."""
_KNOWN_TARGET = (163, 540, 1427)
"""Target-arm seeds whose last cue, cut to one frame at the song end, opens a shutter
state too short to take effect before the park (review G2): refused under `error`."""
_ONCE_CUT = 5440
_RENDER_ERRORS = (PhysicalRenderError, PhysicalCompileError, PhysicalChannelError, ValueError)

_SHAPES = [
    "sine_pan",
    "sine_tilt",
    "circle",
    "lissajous",
    "sweep",
    "sweep_finite",
    "linear",
    "hold",
]


def _grid(rng: random.Random) -> BeatGrid:
    beats = [rng.choice([15.0, 7.3, 0.0])]
    bars = rng.randint(4, 9)
    steady = rng.random() < 0.4
    base = rng.choice([400.0, 500.0, 600.0])
    for _ in range(4 * bars):
        if steady:
            beats.append(beats[-1] + base)
        else:
            fast = rng.random() < 0.08
            beats.append(
                beats[-1] + rng.choice([300.0, 380.0] if fast else [430.0, 500.0, 610.0, 700.0])
            )
    return BeatGrid(
        bar_boundaries=beats[::4],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=beats[-1] + 15.0,
    )


def _presets(ids: tuple[str, ...]) -> dict[str, Any]:
    colors, gobos = ["red", "blue", "white"], ["dots", "star", "open"]
    return {
        "positions": {},
        "attributes": {
            "flk": {
                "fixtures": {
                    fixture_id: {"gobo": gobos[index % 3], "color": colors[index % 3]}
                    for index, fixture_id in enumerate(ids)
                }
            }
        },
    }


def _rig(rng: random.Random) -> tuple[FixtureGroup, tuple[str, ...]]:
    count = rng.choice([2, 3, 4])
    ids = tuple(f"MH{index}" for index in range(1, count + 1))
    presets = _presets(ids) if rng.random() < 0.3 else None
    rig = topology_rig(ids, topology=topology_payload(ids), presets=presets)
    kind = rng.choice(["16", "8bit", "lat", "shutter", "nodim", "lat8"])
    speed = rng.choice([90.0, 180.0, 360.0, 720.0])
    state = rng.getstate()

    def edit(profile: dict[str, Any]) -> None:
        draws = random.Random()
        draws.setstate(state)  # the same draws for every head
        for axis in ("pan", "tilt"):
            profile["axes"][axis]["travel_speed_per_s"] = speed
        if kind in ("8bit", "lat8"):
            for axis in ("pan", "tilt"):
                profile["axes"][axis].pop("fine_offset", None)
        if kind in ("lat", "lat8"):
            for axis in ("pan", "tilt"):
                profile["axes"][axis]["latency_ms"] = draws.choice([10, 30, 60])
                profile["axes"][axis]["settle_ms"] = draws.choice([0, 40, 90])
            profile["visibility"]["close_latency_ms"] = draws.choice([20, 40])
            profile["visibility"]["open_latency_ms"] = 20
            profile["discrete"]["shutter"]["states"]["closed"]["settle_ms"] = draws.choice([0, 30])
        if kind == "shutter":
            profile["visibility"]["dimmer_zero_extinguishes"] = False
            profile["visibility"]["close_latency_ms"] = draws.choice([0, 20])
            profile["discrete"]["shutter"]["states"]["closed"]["settle_ms"] = draws.choice(
                [0, 30, 50]
            )
        if kind == "nodim":
            profile["axes"].pop("dimmer")
            profile["visibility"]["dimmer_zero_extinguishes"] = False

    payload = rig.model_dump(mode="json")
    for fixture in payload["fixtures"]:
        edit(fixture["config"]["physical_profile"])
    return FixtureGroup.model_validate(payload), ids


def _step(rng: random.Random, step_id: str, start: float, duration: float, once: bool) -> dict:
    shape = rng.choice(["sweep_finite", "linear"] if once else _SHAPES)
    period = rng.choice([1.0, 2.0, 4.0, 3.0])
    extent = round(rng.uniform(5.0, 60.0), 1)
    pan = round(rng.uniform(-100, 100), 1)
    tilt = round(rng.uniform(-40, 40), 1)
    timing = {"start": start, "duration": duration}
    color = rng.choice([None, None, "white", "red", "blue"])
    gobo = rng.choice([None, None, "open", "dots", "star"])
    extra: dict[str, Any] = {}
    if color:
        extra["physical_color"] = color
    if gobo:
        extra["physical_gobo"] = gobo
    if shape in ("sine_pan", "sine_tilt"):
        step = sine_step(step_id, pan, extent, period_beats=period, tilt=tilt, **timing, **extra)
        step["movement"]["physical"]["shape"] = shape
        if shape == "sine_tilt":
            step["movement"]["physical"].update(
                pan_extent_deg=0.0, tilt_extent_deg=min(extent, 30.0)
            )
    elif shape == "linear":
        step = sweep_step(step_id, pan, extent, period_beats=period, tilt=tilt, **timing, **extra)
    elif shape == "hold":
        step = hold_step(step_id, pan, tilt=tilt, **timing, **extra)
    else:
        mode = "finite" if shape == "sweep_finite" else "periodic"
        kernel = "sweep" if shape.startswith("sweep") else shape
        transform = None
        if rng.random() < 0.5:
            transform = {"phase_cycles": rng.choice([0.0, 0.25, 0.5, -0.3])}
            if not (kernel == "sweep" and mode == "periodic") and rng.random() < 0.5:
                transform["reverse"] = True
        step = path_step(
            step_id,
            kernel,
            pan=pan,
            tilt=tilt,
            pan_extent=extent,
            period_beats=period,
            mode=mode,
            transform=transform,
            **timing,
            **extra,
        )
    if shape != "hold" and rng.random() < 0.8:
        low = rng.choice([0.0, 0.0, 0.1, 0.25, 0.5, 0.75])
        width = rng.choice([0.05, 0.1, 0.25, 0.5, 1.0])
        high = min(1.0, low + width)
        if rng.random() < 0.1:
            low, high = 0.0, 1.0
        lit_beats = (high - low) * period
        attack = rng.choice([0.0, 0.0, 0.25, 0.5])
        release = rng.choice([0.0, 0.0, 0.25, 0.5])
        if attack + release > lit_beats:
            attack = release = 0.0
        step["dimmer"] = {}
        step["physical_visibility"] = {
            "visible_phase_start": low,
            "visible_phase_end": high,
            "attack_beats": attack,
            "release_beats": release,
            "level": rng.choice([1.0, 1.0, 0.5, 0.3]),
        }
        draw = rng.random()
        if draw < 0.25:
            step.pop("physical_shutter_state")
        elif draw < 0.3:
            step["physical_shutter_state"] = "closed"
    if rng.random() < 0.5 and shape != "hold":
        domains = (
            ["pan", "tilt"]
            if "physical_visibility" in step
            else rng.choice([["pan", "tilt"], ["pan"]])
        )
        distribution: dict[str, Any] = {
            "domains": domains,
            "spread_cycles": rng.choice([0.1, 0.25, 0.5, 1.0]),
            "wings": rng.choice([1, 2]),
        }
        if rng.random() < 0.3:
            distribution["direction"] = "reverse"
        step["physical_distribution"] = [distribution]
    if rng.random() < 0.4:
        step["physical_reposition_fallback"] = rng.choice(["drop_accent", "preserve_aim"])
    return step


def _document(rng: random.Random, template_id: str, use_preset: bool) -> TemplateDoc:
    once = rng.random() < 0.2
    cycle = rng.choice([1.0, 1.0, 2.0])
    if rng.random() < 0.5:
        steps = [_step(rng, "a", 0.0, cycle, once)]
    else:
        cut = cycle / 2
        steps = [_step(rng, "a", 0.0, cut, once), _step(rng, "b", cut, cycle - cut, once)]
    overlays = []
    beats = cycle * 4
    for channel, states in (
        ("color", ["red", "blue", "white"]),
        ("gobo", ["dots", "star", "open"]),
    ):
        if rng.random() < 0.5:
            mask = rng.choice([0.25, 0.5, 0.5, 1.0])
            start = rng.choice([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.5, 6.0])
            end = start + 2 * mask + rng.choice([0.25, 0.5, 1.0, 2.0])
            if end > beats and rng.random() < 0.85:
                start = max(0.0, beats - (end - start))
                end = start + 2 * mask + 0.25
                if end > beats:
                    continue
            entry: dict[str, Any] = {
                "channel": channel,
                "start_beats": start,
                "end_beats": end,
                "mask_beats": mask,
            }
            if use_preset and rng.random() < 0.5:
                entry["attribute_preset_id"] = "flk"
            else:
                entry["state"] = rng.choice(states)
            overlays.append(entry)
    policy = rng.choice(["HOLD_LAST_POSE", "TRUNCATE"])
    return physical_template_doc(
        template_id,
        steps,
        cycle_bars=cycle,
        mode="ONCE" if once else "JOINER",
        remainder_policy=policy,
        overlays=overlays,
    )


# --- The gate-coverage reviewer's generator (round 6) --------------------------------


def _target_grid(rng: random.Random, target: bool) -> BeatGrid:
    beats = [rng.choice([0.0, 7.3, 15.0, 11.0])]
    bars = rng.randint(6, 12)
    kind = "blocks" if target else rng.choice(["steady", "blocks", "jitter"])
    tempo = rng.choice([380.0, 450.0, 500.0, 560.0, 650.0])
    for _ in range(bars):
        if kind == "blocks" and rng.random() < 0.35:
            tempo = rng.choice([330.0, 400.0, 470.0, 520.0, 600.0, 700.0])
        for _ in range(4):
            jitter = 0.0 if kind != "jitter" else rng.choice([0.0, 0.0, -40.0, 30.0, 60.0])
            beats.append(beats[-1] + tempo + jitter)
    return BeatGrid(
        bar_boundaries=beats[::4],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=beats[-1] + rng.choice([0.0, 15.0, 7.3]),
    )


def _target_rig(rng: random.Random, target: bool) -> tuple[FixtureGroup, tuple[str, ...], bool]:
    count = rng.choice([1, 2, 3, 4])
    ids = tuple(f"MH{index}" for index in range(1, count + 1))
    presets = None
    if rng.random() < 0.3:
        positions = {
            i: {"pan_deg": rng.uniform(-90, 90), "tilt_deg": rng.uniform(-20, 20)} for i in ids
        }
        attributes = {
            i: {"color": rng.choice(["red", "blue", "white"]), "gobo": "open"} for i in ids
        }
        presets = {
            "positions": {"pp": {"fixtures": positions}},
            "attributes": {"aa": {"fixtures": attributes}},
        }
    payload = topology_rig(ids, topology=topology_payload(ids), presets=presets).model_dump(
        mode="json"
    )
    eight = rng.random() < 0.35
    speed = rng.choice([45.0, 60.0, 90.0, 120.0] if target else [120.0, 240.0, 450.0, 720.0])
    latency = rng.choice([0, 0, 15, 45])
    settle = rng.choice([0, 25, 60])
    close = rng.choice([0, 0, 25, 60])
    opening = rng.choice([0, 20])
    shutter_only = rng.random() < 0.2
    closed_settle = rng.choice([0, 0, 40])
    open_settle = rng.choice([0, 0, 30])
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        for name in ("pan", "tilt"):
            axis = profile["axes"][name]
            axis.update(travel_speed_per_s=speed, latency_ms=latency, settle_ms=settle)
            if eight:
                axis.pop("fine_offset", None)
        profile["visibility"].update(close_latency_ms=close, open_latency_ms=opening)
        if shutter_only:
            profile["visibility"]["dimmer_zero_extinguishes"] = False
        profile["discrete"]["shutter"]["states"]["closed"]["settle_ms"] = closed_settle
        profile["discrete"]["shutter"]["states"]["open"]["settle_ms"] = open_settle
    return FixtureGroup.model_validate(payload), ids, presets is not None


def _target_step(
    rng: random.Random,
    step_id: str,
    start: float,
    duration: float,
    once: bool,
    presets: bool,
    target: bool,
) -> dict[str, Any]:
    fallback = (
        rng.choice([None, "drop_accent"])
        if target
        else rng.choice([None, None, "drop_accent", "preserve_aim"])
    )
    extra: dict[str, Any] = {"start": start, "duration": duration}
    if fallback:
        extra["physical_reposition_fallback"] = fallback
    color = rng.choice([None, None, "red", "blue", "white"])
    if color:
        extra["physical_color"] = color
    shapes = (
        ["linear", "hold", "sweepf"]
        if once
        else ["hold", "sine", "linear", "circle", "lissajous", "sweep", "sweepf"]
    )
    shape = rng.choice(shapes)
    pan = round(rng.uniform(-90, 90), 1)
    tilt = round(rng.uniform(-30, 30), 1)
    period = rng.choice([0.5, 1.0, 2.0, 4.0, 3.0])
    extent = round(rng.uniform(4, 50), 1)
    if shape == "hold":
        step = hold_step(step_id, pan, tilt=tilt, **extra)
    elif shape == "sine":
        step = sine_step(step_id, pan, extent, period_beats=period, tilt=tilt, **extra)
    elif shape == "linear":
        signed = extent * rng.choice([1, -1])
        step = sweep_step(step_id, pan, signed, period_beats=period, tilt=tilt, **extra)
    else:
        step = path_step(
            step_id,
            "sweep" if shape.startswith("sweep") else shape,
            pan=pan,
            tilt=tilt,
            pan_extent=extent,
            period_beats=period,
            mode="finite" if shape == "sweepf" else "periodic",
            **extra,
        )
    if presets and rng.random() < 0.3:
        step["component_refs"] = {"position_id": None, "attribute_preset_ids": ["aa"]}
        step.pop("physical_color", None)
    draw = rng.random()
    if draw < 0.25 and not once:
        pulse_period = rng.choice([0.5, 1.0, 2.0])
        duty = rng.choice([0.25, 0.5, 0.75])
        step["dimmer"]["physical"] = {
            "period_beats": pulse_period,
            "duty_cycle": duty,
            "low": 0.0,
            "high": 1.0,
            "phase_cycles": rng.choice([0.0, 0.3, 0.9]),
        }
    elif draw < 0.45 and not once:
        step.pop("physical_shutter_state", None)
        shutter_period = rng.choice([1.0, 2.0])
        duty = rng.choice([0.25, 0.5])
        step["physical_shutter"] = {
            "period_beats": shutter_period,
            "duty_cycle": duty,
            "phase_cycles": rng.choice([0.0, 0.45]),
            "low_state": "closed",
            "high_state": "open",
        }
    elif draw < 0.7 and shape != "hold":
        low = rng.choice([0.0, 0.2, 0.5])
        high = min(1.0, low + rng.choice([0.2, 0.3, 0.5, 1.0]))
        step["dimmer"] = {}
        step["physical_visibility"] = {
            "visible_phase_start": low,
            "visible_phase_end": high,
            "attack_beats": 0.0,
            "release_beats": 0.0,
            "level": 1.0,
        }
    if shape != "hold" and rng.random() < 0.35:
        domains = (
            ["pan", "tilt"]
            if "physical_visibility" in step
            else rng.choice([["pan"], ["pan", "tilt"], ["pan", "dimmer"]])
        )
        if "physical_shutter" in step and "dimmer" in domains:
            domains = ["pan"]
        spread = rng.choice([0.25, 0.5, 1.0])
        step["physical_distribution"] = [
            {"domains": domains, "spread_cycles": spread, "wings": rng.choice([1, 2])}
        ]
    return step


def _target_document(
    rng: random.Random, template_id: str, presets: bool, target: bool
) -> TemplateDoc:
    once = rng.random() < 0.2
    cycles = [0.25, 0.5, 0.25, 0.75] if target else [0.5, 0.75, 1.0, 1.0, 1.5, 2.0, 3.0]
    cycle = rng.choice(cycles)
    beats = round(cycle * 4)
    count = rng.choice([1, 1, 2, 3]) if beats >= 3 else 1
    cuts = sorted(rng.sample(range(1, beats), min(count - 1, beats - 1))) if beats > 1 else []
    edges = [0, *cuts, beats]
    steps = [
        _target_step(
            rng, "abc"[i], edges[i] / 4, (edges[i + 1] - edges[i]) / 4, once, presets, target
        )
        for i in range(len(edges) - 1)
    ]
    overlays = []
    if rng.random() < 0.3 and beats >= 2:
        mask = rng.choice([0.25, 0.5])
        start = rng.choice([0.0, 0.5, 1.0])
        end = start + 2 * mask + 0.25
        if end <= beats:
            overlays.append(
                {
                    "channel": "gobo",
                    "start_beats": start,
                    "end_beats": end,
                    "mask_beats": mask,
                    "state": rng.choice(["dots", "star"]),
                }
            )
    return physical_template_doc(
        template_id,
        steps,
        cycle_bars=cycle,
        mode="ONCE" if once else "JOINER",
        remainder_policy=rng.choice(["HOLD_LAST_POSE", "TRUNCATE"]),
        overlays=overlays,
    )


# --- Checks ---------------------------------------------------------------------------


def _job(ids: tuple[str, ...], policy: str, on_unplayable: str) -> JobConfig:
    states = dict.fromkeys(ids, PHYSICAL_INITIAL_STATE)
    fallback = {} if policy == "error" else {"reposition_fallback": policy}
    return physical_job(initial_states=states, on_unplayable=on_unplayable, **fallback)


def _admitted(
    documents: tuple[TemplateDoc, ...],
    grid: BeatGrid,
    rig: FixtureGroup,
    job: JobConfig,
    gate: str | None = None,
) -> list[str]:
    """The templates the gate admits, gating as `on_unplayable` (or `gate`) scopes it."""
    admitted = []
    for document in documents:
        try:
            check_physical_templates(
                [document.template.template_id],
                beat_grid=grid,
                fixture_group=rig,
                initial_states=job.moving_heads.initial_states,
                failure_mode=job.moving_heads.reposition_fallback,
                on_unplayable=gate or job.moving_heads.on_unplayable,
            )
        except UnsupportedRenderModeError:
            continue
        admitted.append(document.template.template_id)
    return admitted


def _render(
    sections: list[tuple[str, int, int]], grid: BeatGrid, rig: FixtureGroup, job: JobConfig
) -> tuple[RenderingPipeline, list[FixtureSegment]]:
    pipeline = RenderingPipeline(
        choreography_plan=physical_sections(*sections),
        beat_grid=grid,
        fixture_group=rig,
        job_config=job,
        output_path=None,
    )
    return pipeline, pipeline.render()


def _commanded_dark(frame: dict[int, int], profile: FixtureCapabilities) -> bool:
    dimmer = profile.axes.get("dimmer")
    if profile.visibility.dimmer_zero_extinguishes and dimmer is not None:
        word = frame[dimmer.coarse_offset]
        if dimmer.fine_offset is not None:
            word = word << 8 | frame[dimmer.fine_offset]
        if word == dimmer.dmx_word(0):
            return True
    shutter = profile.discrete.get("shutter")
    if shutter is None:
        return False
    state = next(n for n, s in shutter.states.items() if s.value == frame[shutter.offset])
    return state in profile.visibility.extinguishing_shutter_states


def _verify(
    pipeline: RenderingPipeline,
    segments: list[FixtureSegment],
    rig: FixtureGroup,
    job: JobConfig,
    where: str,
) -> tuple[int, int]:
    """Check one dark render; return (frames kept dark as unplayable, authored frames)."""
    grid = pipeline.beat_grid
    cues = [s for s in segments if TRANSACTION_METADATA_KEY not in s.metadata]
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    replanned = plan_prepositions(
        cues,
        profiles,  # type: ignore[arg-type]
        initial_states=job.moving_heads.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(grid.duration_ms))) * EFFECT_GRID_MS,
        failure_mode=job.moving_heads.reposition_fallback,
    )
    assert list(replanned.segments) == segments, where
    for fixture_id, profile in profiles.items():
        assert profile is not None
        if any(cue.fixture_id == fixture_id for cue in cues):
            initial = job.moving_heads.initial_states[fixture_id]
            assert_honest_transactions(replanned, cues, profile, initial, fixture_id=fixture_id)
    record = pipeline.render_record
    assert record is not None
    unplayable = [r for r in record["dropped_cues"] if r["reason"] == "unplayable"]
    frames = {(f.fixture_id, f.time_ms): dict(f.channels) for f in pipeline.frames}
    for dark in unplayable:
        profile = profiles[dark["fixture_id"]]
        assert profile is not None
        for time_ms in range(dark["start_ms"], dark["end_ms"], EFFECT_GRID_MS):
            if (dark["fixture_id"], time_ms) not in frames:
                continue  # past the sequence's frames
            assert _commanded_dark(frames[dark["fixture_id"], time_ms], profile), (where, dark)
            assert not any(
                c.fixture_id == dark["fixture_id"] and c.t0_ms <= time_ms < c.t1_ms for c in cues
            ), (where, dark)
    totals: dict[str, dict[str, int]] = {}
    for dark in unplayable:
        total = totals.setdefault(dark["code"], {"cues": 0, "frames": 0})
        total["cues"] += 1
        total["frames"] += dark["frames"]
    assert record["unplayable_totals"] == totals, where
    assert (pipeline.unplayable_warning is not None) == bool(unplayable), where
    # `quantized_cues` lists each cue entering the transaction pass as its start then
    # its end (then any moved discrete cue).
    bounds = [q for q in record["quantized_cues"] if q["kind"] in ("segment_start", "segment_end")]
    entered = sum(
        (end["actual_ms"] - start["actual_ms"]) // EFFECT_GRID_MS
        for start, end in zip(bounds[::2], bounds[1::2], strict=True)
    )
    others = sum(
        (r["end_ms"] - r["start_ms"]) // EFFECT_GRID_MS
        for r in record["dropped_cues"]
        if r["reason"] != "unplayable" or r["code"] in ("compile_refused", "once_section_too_short")
    )
    degraded = sum(r["frames"] for r in unplayable)
    return degraded, entered + others


def _check_subset(
    sections: list[tuple[str, int, int]],
    grid: BeatGrid,
    rig: FixtureGroup,
    ids: tuple[str, ...],
    job: JobConfig,
    pipeline: RenderingPipeline,
    gone: str,
) -> None:
    """Removing `gone` from the rig changes no other head's frames."""
    payload = rig.model_dump(mode="json")
    payload["fixtures"] = [f for f in payload["fixtures"] if f["fixture_id"] != gone]
    for kind in ("positions", "attributes"):
        for preset in ((payload.get("presets") or {}).get(kind) or {}).values():
            preset["fixtures"].pop(gone, None)
    present = tuple(i for i in ids if i != gone)
    policy = job.moving_heads
    subset_job = physical_job(
        initial_states={i: policy.initial_states[i] for i in present},
        reposition_fallback=policy.reposition_fallback,
        on_unplayable=policy.on_unplayable,
    )
    subset, _ = _render(sections, grid, FixtureGroup.model_validate(payload), subset_job)
    for fixture_id in present:
        whole = [f for f in pipeline.frames if f.fixture_id == fixture_id]
        assert [f for f in subset.frames if f.fixture_id == fixture_id] == whole, (gone, fixture_id)


def _plan(rng: random.Random, admitted: list[str], bars: int) -> list[tuple[str, int, int]]:
    sections = []
    bar = 1
    while bar <= bars:
        length = rng.randint(1, max(1, bars - bar + 1))
        sections.append((rng.choice(admitted), bar, bar + length - 1))
        bar += length
    return sections


def _check_seed(
    seed: int, on_unplayable: str = "dark", gate: str | None = None
) -> tuple[str, int, int]:
    """P2.4b generator: gate two templates, render a random plan of the admitted ones.

    Returns the outcome (`invalid`, `refused`, `rendered`, or under `error` `failed`) and
    the frames kept dark and authored. `gate` scopes the gate as another `on_unplayable`
    would: a known seed draws its plan over the templates the full gate admitted."""
    rng = random.Random(seed)
    grid = _grid(rng)
    rig, ids = _rig(rng)
    use_preset = rig.presets is not None and bool(rig.presets.attributes)
    try:
        documents = (
            _document(rng, f"gf_{seed}_a", use_preset),
            _document(rng, f"gf_{seed}_b", use_preset),
        )
    except ValidationError:
        return "invalid", 0, 0
    policy = rng.choice(["error", "preserve_aim", "drop_accent"])
    job = _job(ids, policy, on_unplayable)
    bars = sum(1 for bar in grid.bar_boundaries if bar < grid.duration_ms)
    with registered_templates(*documents):
        admitted = _admitted(documents, grid, rig, job, gate)
        if not admitted:
            return "refused", 0, 0
        sections = _plan(rng, admitted, bars)
        where = f"seed {seed}: plan {sections} under {policy}"
        if on_unplayable == "error":
            try:
                _render(sections, grid, rig, job)
            except _RENDER_ERRORS:
                return "failed", 0, 0
            return "rendered", 0, 0
        pipeline, segments = _render(sections, grid, rig, job)
        counts = _verify(pipeline, segments, rig, job, where)
        if len(ids) >= 2:
            _check_subset(sections, grid, rig, ids, job, pipeline, rng.choice(ids))
    return "rendered", *counts


def _check_target_seed(
    seed: int, target: bool, on_unplayable: str = "dark", gate: str | None = None
) -> tuple[str, int, int]:
    """The gate-coverage reviewer's generator: up to three templates, three random plans."""
    rng = random.Random(seed * 7919 + 13)
    grid = _target_grid(rng, target)
    rig, ids, presets = _target_rig(rng, target)
    try:
        documents = tuple(
            _target_document(rng, f"md{seed}_{i}", presets, target)
            for i in range(rng.choice([1, 2, 3]))
        )
    except ValidationError:
        return "invalid", 0, 0
    policy = (
        "drop_accent" if target else rng.choice(["error", "error", "drop_accent", "preserve_aim"])
    )
    job = _job(ids, policy, on_unplayable)
    bars = sum(1 for bar in grid.bar_boundaries if bar < grid.duration_ms)
    degraded = authored = 0
    with registered_templates(*documents):
        admitted = _admitted(documents, grid, rig, job, gate)
        if not admitted:
            return "refused", 0, 0
        for _ in range(3):
            sections = []
            bar = 1
            while bar <= bars:
                length = min(rng.choice([1, 1, 2, 2, 3, 4, bars]), bars - bar + 1)
                sections.append((rng.choice(admitted), bar, bar + length - 1))
                bar += length
            if on_unplayable == "error":
                try:
                    _render(sections, grid, rig, job)
                except _RENDER_ERRORS:
                    return "failed", 0, 0
                continue
            pipeline, segments = _render(sections, grid, rig, job)
            where = f"seed {seed} (target {target}): plan {sections} under {policy}"
            dark, total = _verify(pipeline, segments, rig, job, where)
            degraded, authored = degraded + dark, authored + total
            if len(ids) >= 2:
                _check_subset(sections, grid, rig, ids, job, pipeline, ids[-1])
    return "rendered", degraded, authored


def degrade_rate(outcomes: list[tuple[str, int, int]]) -> float:
    """The share of authored cue frames kept dark as unplayable over a run."""
    authored = sum(total for _, _, total in outcomes)
    return sum(dark for _, dark, _ in outcomes) / authored if authored else 0.0


@pytest.mark.parametrize("seed", _KNOWN)
def test_a_known_failure_after_admission_renders_dark(seed: int) -> None:
    """Each seed once failed at render after the gate admitted it; now every admitted
    plan renders, honestly."""
    assert _check_seed(seed, gate="error")[0] in ("refused", "rendered", "invalid")


@pytest.mark.parametrize("seed", _KNOWN_TARGET)
def test_a_known_song_end_failure_renders_dark_and_error_still_refuses(seed: int) -> None:
    outcome, dark, _ = _check_target_seed(seed, target=True, gate="error")
    assert outcome == "rendered" and dark > 0
    assert _check_target_seed(seed, target=True, on_unplayable="error")[0] == "failed"


def test_a_once_cycle_cut_short_renders_dark_and_error_still_refuses() -> None:
    # Its short section starts at the song's last frame, so it keeps no frame dark.
    assert _check_seed(_ONCE_CUT, gate="error")[0] == "rendered"
    assert _check_seed(_ONCE_CUT, on_unplayable="error")[0] == "failed"


def test_every_admitted_plan_renders_honestly() -> None:
    outcomes = [_check_seed(seed) for seed in range(GATE_FUZZ_SEEDS)]
    outcomes += [_check_target_seed(seed, target=False) for seed in range(TARGET_FUZZ_SEEDS)]
    outcomes += [_check_target_seed(seed, target=True) for seed in range(TARGET_FUZZ_SEEDS)]
    rendered = [outcome for outcome in outcomes if outcome[0] == "rendered"]
    assert len(rendered) >= len(outcomes) // 4, outcomes
