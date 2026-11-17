#!/usr/bin/env python3
"""Record what the deleted moving-head renderer did with each piece of planner intent.

Extracts `git archive mh-last-with-legacy-renderer` into a temporary directory, runs that
tag's own renderer (`legacy_v1`) on synthetic inputs only (no owner data, network,
provider or xLights) and writes, per intent, renderer-independent facts: which fixture
channel changed, when relative to the beat grid, to which named state, for how long.
Each row also carries its parity target, the task that restores it and the old
behaviour that is a defect rather than intent. `tests/regression/test_mh_intent_parity.py`
asserts the targets on the current renderer. Usage: `scripts/README.md`.

Facts are read from the old renderer's own output: every fixture segment is serialised
by the old exporter (`DmxSettingsBuilder`) and the slider and value-curve settings it
writes are sampled on the 20 ms frame grid, per xLights layer, before emission
quantisation. Which layer xLights actually showed is a separate finding (`LAYER_PLAYBACK`),
transcribed from `layer_playback.py` in the W0 evidence folder.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import importlib
import io
from itertools import pairwise
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

TAG = "mh-last-with-legacy-renderer"
FRAME_MS = 20
SHIFT_MS = 15.0
BEAT_MS = 500.0
BARS = 8
HEADS = ("MH1", "MH2", "MH3", "MH4")
TEMPLATE = "fan_pulse"
"""Old built-in: a held fan pose with a PULSE dimmer authored DRAMATIC, and no colour,
shutter or gobo."""
BREATHE_TEMPLATE = "hold_center_out_breathe"
"""Old built-in: a held pose with a PULSE dimmer authored SMOOTH (a slow breathe)."""
SECOND_TEMPLATE = "wave_fan_hold"
"""Old built-in: the incoming section of the transition rows (another aim, HOLD dimmer)."""
CHANNELS = {"pan": 1, "tilt": 3, "dimmer": 5, "shutter": 6, "color": 7, "gobo": 8}
SHUTTER_MAP = {
    "closed": 64,
    "open": 8,
    "strobe_slow": 100,
    "strobe_medium": 140,
    "strobe_fast": 190,
}
COLOR_MAP = {"white": 0, "red": 14, "blue": 26, "magenta": 40, "amber": 52, "cyan": 66}
GOBO_MAP = {"open": 0, "dots": 10, "stars": 20}
RUN_PALETTE = "core.rgb_primary"
"""The macro palette the current-side palette-role rows supply (first stop #FF1744,
second #00E676)."""
SHOW_PALETTE = "spec.cosmic_night"
"""The show rows' palette: its first stop #0D47A1 is nearest blue, not red."""
CUE = {"cue_id": "hook", "timestamp_ms": 2_690, "section_id": "s1"}
"""A lyric moment 175 ms after bar 2 beat 2 (2515 ms): nearer that beat than beat 3."""
OLD = "packages/twinklr/core/"
"""Prefix of every code citation below; paths and lines are at the tag."""


def _extract_tag(repo: Path, into: Path) -> str:
    """Extract the tag's tree into `into`; return the commit `git get-tar-commit-id` reads
    from the archive itself."""
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", TAG], check=True, capture_output=True
    ).stdout
    commit = (
        subprocess.run(["git", "get-tar-commit-id"], input=archive, check=True, capture_output=True)
        .stdout.decode()
        .strip()
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(into, filter="data")
    return commit


def _bootstrap(archive: Path) -> None:
    """Import `twinklr` from `archive`, not from the editable install of this tree."""
    sys.meta_path[:] = [
        finder for finder in sys.meta_path if not type(finder).__module__.startswith("__editable__")
    ]
    sys.path.insert(0, str(archive / "packages"))
    core = importlib.import_module("twinklr.core")
    if not Path(core.__file__ or "").resolve().is_relative_to(archive):
        raise SystemExit(f"twinklr.core was not imported from {archive}: {core.__file__}")


def _mod(name: str) -> Any:
    return importlib.import_module(name)


# --- inputs -------------------------------------------------------------------------


def _grid() -> Any:
    """Eight 4/4 bars of 500 ms beats, the first beat 15 ms off the frame grid."""
    beat_grid = _mod("twinklr.core.sequencer.timing.beat_grid").BeatGrid
    beats = [SHIFT_MS + BEAT_MS * index for index in range(BARS * 4 + 1)]
    return beat_grid(
        bar_boundaries=beats[::4],
        beat_boundaries=beats,
        eighth_boundaries=beat_grid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=beat_grid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=60_000 / BEAT_MS,
        beats_per_bar=4,
        duration_ms=beats[-1] + SHIFT_MS,
    )


def _rig(shutter_channel: int = CHANNELS["shutter"]) -> Any:
    """Four heads with dimmer, shutter, colour and gobo channels and explicit wheel maps."""
    fixtures = _mod("twinklr.core.config.fixtures")
    instances = _mod("twinklr.core.config.fixtures.instances")
    dmx = _mod("twinklr.core.config.fixtures.dmx")
    group = fixtures.FixtureGroup(group_id="MOVING_HEADS")
    for fixture_id in HEADS:
        mapping = dmx.DmxMapping(
            pan_channel=CHANNELS["pan"],
            tilt_channel=CHANNELS["tilt"],
            dimmer_channel=CHANNELS["dimmer"],
            shutter_channel=shutter_channel,
            shutter_default=SHUTTER_MAP["open"],
            shutter_map=SHUTTER_MAP,
            color_channel=CHANNELS["color"],
            color_map=COLOR_MAP,
            gobo_channel=CHANNELS["gobo"],
            gobo_map=GOBO_MAP,
        )
        group.add_fixture(
            instances.FixtureInstance(
                fixture_id=fixture_id,
                config=instances.FixtureConfig(fixture_id=fixture_id, dmx_mapping=mapping),
                xlights_model_name=f"Dmx {fixture_id}",
            )
        )
    return group


def _old_intent(intent: dict[str, Any] | None) -> dict[str, Any]:
    """The old planner model's fields for a row's renderer-neutral `intent`.

    `None` leaves every intent field out, which the old renderer read as "the template as
    authored" (`legacy_intent_omitted`). Any dict is an explicit plan carrying the old
    model's neutral values (SMOOTH, palette role PRIMARY, no events) wherever `intent`
    sets nothing: that model could not leave one intent unset while setting another.
    """
    if intent is None:
        return {}
    color = intent.get("color", {"palette_role": "PRIMARY"})
    selection = (
        {"kind": "EXPLICIT", "palette_role": None, "explicit_color": color["explicit"]}
        if "explicit" in color
        else {"kind": "PALETTE_ROLE", "palette_role": color["palette_role"], "explicit_color": None}
    )
    events = {
        key: [{"moment_cue_id": None, **event} for event in intent.get(key, [])]
        for key in ("shutter_events", "gobo_events")
    }
    cues = sorted({event["moment_cue_id"] for items in events.values() for event in items} - {None})
    return {
        "intensity": intent.get("intensity", "SMOOTH"),
        "color_intent": {"selection": selection},
        **events,
        "moment_cues": [{"cue_id": cue_id} for cue_id in cues],
        "transition_in": intent.get("transition_in"),
    }


def _section(
    name: str, bars: tuple[int, int], template_id: str, intent: dict[str, Any] | None
) -> dict[str, Any]:
    return {
        "section_name": name,
        "start_bar": bars[0],
        "end_bar": bars[1],
        "template_id": template_id,
        **_old_intent(intent),
    }


def _plan(*sections: dict[str, Any]) -> Any:
    models = _mod("twinklr.core.agents.sequencer.moving_heads.models")
    return models.ChoreographyPlan(
        sections=[models.PlanSection.model_validate(section) for section in sections]
    )


def _bind_cues(plan: Any) -> Any:
    """The old binder: move cue-bound events to the cue's snapped beat."""
    lyrics = _mod("twinklr.core.agents.audio.lyrics.models")
    profile = _mod("twinklr.core.agents.audio.profile.models")
    binder = _mod("twinklr.core.agents.sequencer.moving_heads.moment_cues")
    grid = _grid()
    context = lyrics.LyricContextModel(
        has_lyrics=True,
        vocal_coverage_pct=0.25,
        moment_cues=[
            lyrics.MomentCue(
                **CUE, emphasis="HIGH", text="light the way", visual_hint="Accent the hook."
            )
        ],
    )
    end_ms = int(grid.get_bar_start_ms(4))
    sections = [profile.SongSectionRef(section_id="s1", name="s1", start_ms=0, end_ms=end_ms)]
    return binder.bind_lyric_moment_cues(plan, context, grid, sections)


# --- the old renderer's output, sampled -----------------------------------------------


class Render:
    """One `legacy_v1` render: per fixture and xLights layer, the exported effects."""

    def __init__(self, plan: Any, *, rig: Any | None = None, transitions: bool = True) -> None:
        config = _mod("twinklr.core.config.models")
        pipeline_module = _mod("twinklr.core.sequencer.moving_heads.pipeline")
        builder = _mod("twinklr.core.sequencer.moving_heads.export.dmx_settings_builder")
        self.grid = _grid()
        job = config.JobConfig.model_validate({"transitions": {"enabled": transitions}})
        if job.moving_heads.mode != "legacy_v1":
            raise SystemExit(f"the archive's default render mode is {job.moving_heads.mode}")
        pipeline = pipeline_module.RenderingPipeline(
            choreography_plan=plan,
            beat_grid=self.grid,
            fixture_group=rig or _rig(),
            job_config=job,
        )
        self.segments = pipeline.render()
        self.effects: dict[tuple[str, int], list[tuple[int, int, dict[int, Any]]]] = {}
        for segment in self.segments:
            fixture = pipeline.fixture_group.get_fixture(segment.fixture_id)
            settings = builder.DmxSettingsBuilder(fixture).build_settings_string(segment)
            # The old exporter placed transition segments on layer 1, over layer 0.
            layer = 1 if segment.metadata.get("is_transition") == "true" else 0
            self.effects.setdefault((segment.fixture_id, layer), []).append(
                (segment.t0_ms, segment.t1_ms, _parse_settings(settings))
            )
        self.end_ms = int(self.grid.duration_ms)

    def frames(self, channel: int, *, fixture_id: str = "MH1", layer: int = 0) -> list[int | None]:
        """The byte each frame sends on `channel`: from the effect covering the frame's
        start (the last placed when effects overlap), or None outside every effect."""
        out: list[int | None] = []
        for time_ms in range(0, self.end_ms, FRAME_MS):
            found = None
            for t0, t1, values in self.effects.get((fixture_id, layer), []):
                if t0 <= time_ms < t1 and channel in values:
                    found = _sample(values[channel], (time_ms - t0) / (t1 - t0))
            out.append(found)
        return out

    def same_on_every_head(self, channel: int) -> bool:
        first = self.frames(channel)
        return all(self.frames(channel, fixture_id=head) == first for head in HEADS[1:])


def _parse_settings(settings: str) -> dict[int, Any]:
    """`E_SLIDER_DMXn` bytes and `E_VALUECURVE_DMXn` curves of one exported effect."""
    values: dict[int, Any] = {}
    for part in settings.split(","):
        key, _, raw = part.partition("=")
        if key.startswith("E_SLIDER_DMX"):
            values.setdefault(int(key.removeprefix("E_SLIDER_DMX")), int(raw))
        elif key.startswith("E_VALUECURVE_DMX"):
            fields = dict(item.split("=", 1) for item in raw.strip("|").split("|"))
            low, high = float(fields["Min"]), float(fields["Max"])
            values[int(key.removeprefix("E_VALUECURVE_DMX"))] = [
                (float(t), low + float(v) * (high - low))
                for t, v in (pair.split(":") for pair in fields["Values"].split(";"))
            ]
    return values


def _sample(value: Any, position: float) -> int:
    """A slider byte, or a value curve interpolated linearly as xLights plays it."""
    if isinstance(value, int):
        return value
    for (t0, v0), (t1, v1) in pairwise(value):
        if position <= t1:
            ratio = 0.0 if t1 == t0 else (position - t0) / (t1 - t0)
            return round(v0 + ratio * (v1 - v0))
    return round(value[-1][1])


# --- facts ----------------------------------------------------------------------------


def _beat(grid: Any, time_ms: float) -> str:
    """`bar.beat` (1-based) of the latest beat at or before `time_ms`, plus the offset."""
    beats = grid.beat_boundaries
    index = max(i for i, beat in enumerate(beats) if beat <= time_ms)
    offset = time_ms - beats[index]
    return f"{index // 4 + 1}.{index % 4 + 1}" + (f"+{offset:g}ms" if offset else "")


def _runs(frames: Sequence[int | None], names: dict[int, str]) -> list[list[Any]]:
    """`[start_ms, end_ms, state]` for each run of equal frames, bytes named by `names`."""
    out: list[list[Any]] = []
    for index, value in enumerate(frames):
        shown = None if value is None else names.get(value, value)
        if out and out[-1][2] == shown:
            out[-1][1] = (index + 1) * FRAME_MS
        else:
            out.append([index * FRAME_MS, (index + 1) * FRAME_MS, shown])
    return out


def _in(frames: Sequence[int | None], start_ms: float, end_ms: float) -> list[int]:
    return [
        value
        for index, value in enumerate(frames)
        if value is not None and start_ms <= index * FRAME_MS < end_ms
    ]


def _dimmer(render: Render, start_ms: float, end_ms: float) -> dict[str, Any]:
    """Dimmer range over `[start_ms, end_ms)` and the frames where it rises to its peak."""
    frames = render.frames(CHANNELS["dimmer"])
    window = _in(frames, start_ms, end_ms)
    peak = max(window)
    onsets = [
        index * FRAME_MS
        for index in range(1, len(frames))
        if start_ms <= index * FRAME_MS < end_ms
        and frames[index] == peak
        and (frames[index - 1] or 0) < peak
    ]
    return {
        "dimmer_min": min(window),
        "dimmer_max": peak,
        "dimmer_distinct_levels": len(set(window)),
        "peak_onsets_ms": onsets,
        "peak_onset_beats": [_beat(render.grid, time_ms) for time_ms in onsets],
        "peak_spacing_ms": sorted({b - a for a, b in pairwise(onsets)}),
        "same_on_every_head": render.same_on_every_head(CHANNELS["dimmer"]),
    }


def _channel(
    render: Render, channel: str, names: dict[int, str], *, number: int | None = None
) -> dict[str, Any]:
    """A wheel or shutter channel's named runs over the section, when each change lands
    against the beat grid, and the dimmer byte at that frame (nonzero: turned while lit)."""
    start, end = render.grid.get_bar_start_ms(0), render.grid.get_bar_start_ms(4)
    frames = render.frames(number or CHANNELS[channel])
    runs = [run for run in _runs(frames, names) if run[1] > start and run[0] < end]
    dimmer = render.frames(CHANNELS["dimmer"])
    return {
        "channel": number or CHANNELS[channel],
        "runs": runs,
        "changes": [
            {
                "ms": run[0],
                "after_beat": _beat(render.grid, run[0]),
                "to": run[2],
                "dimmer": dimmer[run[0] // FRAME_MS],
            }
            for run in runs[1:]
        ],
        "same_on_every_head": render.same_on_every_head(number or CHANNELS[channel]),
    }


def _names(mapping: dict[str, int]) -> dict[int, str]:
    return {byte: name for name, byte in reversed(mapping.items())}


def _section_window(render: Render) -> tuple[float, float]:
    return render.grid.get_bar_start_ms(0), render.grid.get_bar_start_ms(4)


def _one(
    intent: dict[str, Any] | None,
    *,
    bind: bool = False,
    rig: Any | None = None,
    template_id: str = TEMPLATE,
) -> Render:
    plan = _plan(_section("s1", (1, 4), template_id, intent))
    return Render(_bind_cues(plan) if bind else plan, rig=rig)


# --- rows -----------------------------------------------------------------------------


def _intensity_rows() -> list[dict[str, Any]]:
    neutral = _one({})
    window = _section_window(neutral)
    authored = _dimmer(_one(None), *window)
    rows = []
    for level in ("SLOW", "FAST", "DRAMATIC", "INTENSE"):
        facts = {
            "set": _dimmer(_one({"intensity": level}), *window),
            "neutral": _dimmer(neutral, *window),
            "template_as_authored": authored,
        }
        if level == "INTENSE":
            long = Render(_plan(_section("s1", (1, 8), TEMPLATE, {"intensity": level})))
            facts["set_over_8_bars"] = _dimmer(long, 15, 16_015)
        rows.append(
            {
                "id": f"intensity_{level.lower()}",
                "intent": {"intensity": level},
                "neutral_intent": {},
                "facts": facts,
            }
        )
    # A template that authors its own pulse: the level against the template as authored.
    for row_id, level, template_id in (
        ("intensity_dramatic_on_authored_pulse", "DRAMATIC", BREATHE_TEMPLATE),
        ("intensity_intense_on_authored_pulse", "INTENSE", TEMPLATE),
        ("intensity_smooth_on_energetic_template", "SMOOTH", TEMPLATE),
    ):
        rows.append(
            {
                "id": row_id,
                "intent": {"intensity": level},
                "neutral_intent": None,
                "old_template": template_id,
                "facts": {
                    "set": _dimmer(_one({"intensity": level}, template_id=template_id), *window),
                    "template_as_authored": _dimmer(_one(None, template_id=template_id), *window),
                },
            }
        )
    return rows


def _color_rows() -> list[dict[str, Any]]:
    names = _names(COLOR_MAP)
    neutral = _channel(_one(None), "color", names)
    rows = []
    for row_id, color in [
        ("color_explicit_blue", {"explicit": "blue"}),
        *[
            (f"color_palette_{role.lower()}", {"palette_role": role})
            for role in ("PRIMARY", "ACCENT", "WARM", "COOL", "NEUTRAL")
        ],
    ]:
        intent: dict[str, Any] = {"color": color}
        if "palette_role" in color:
            # The current side's input: the song's macro palette. The old `run` path had
            # no palette input; its fixed role table gave the same colour for any song.
            intent["macro_palette"] = RUN_PALETTE
        rows.append(
            {
                "id": row_id,
                "intent": intent,
                "neutral_intent": None,
                "facts": {
                    "set": _channel(_one({"color": color}), "color", names),
                    "neutral": neutral,
                },
            }
        )
    # Two sections with different colours: where the wheel turns between them.
    render = Render(
        _plan(
            _section("s1", (1, 4), TEMPLATE, {"color": {"explicit": "red"}}),
            _section("s2", (5, 8), TEMPLATE, {"color": {"explicit": "blue"}}),
        ),
        transitions=False,
    )
    frames = render.frames(CHANNELS["color"])
    dimmer = render.frames(CHANNELS["dimmer"])
    runs = _runs(frames, names)
    rows.append(
        {
            "id": "color_change_between_sections",
            "intent": {
                "sections": [{"color": {"explicit": "red"}}, {"color": {"explicit": "blue"}}]
            },
            "neutral_intent": None,
            "facts": {
                "runs": runs,
                "changes": [
                    {
                        "ms": run[0],
                        "after_beat": _beat(render.grid, run[0]),
                        "to": run[2],
                        "dimmer": dimmer[run[0] // FRAME_MS],
                        "dimmer_frame_before": dimmer[run[0] // FRAME_MS - 1],
                    }
                    for run in runs[1:]
                    if run[2] is not None
                ],
            },
        }
    )
    return rows


def _event(
    row_id: str,
    intent: dict[str, Any],
    channel: str,
    *,
    bind: bool = False,
    rig: Any | None = None,
    number: int | None = None,
) -> dict[str, Any]:
    names = _names(SHUTTER_MAP if channel == "shutter" else GOBO_MAP)
    render = _one(intent, bind=bind, rig=rig)
    facts: dict[str, Any] = {
        "set": _channel(render, channel, names, number=number),
        "neutral": _channel(_one({}, rig=rig), channel, names, number=number),
    }
    traces = sorted(
        {
            value
            for segment in render.segments
            for key, value in segment.metadata.items()
            if key.endswith("_trace")
        }
    )
    facts["handler_traces"] = traces
    if bind:
        section = _bind_cues(_plan(_section("s1", (1, 4), TEMPLATE, intent))).sections[0]
        event = (section.shutter_events or section.gobo_events)[0]
        facts["bound_event"] = {"bar": event.bar, "beat": event.beat}
        facts["cue_snapped_beat_ms"] = render.grid.snap_to_nearest_beat(float(CUE["timestamp_ms"]))
    return {"id": row_id, "intent": intent, "neutral_intent": {}, "facts": facts}


def _pulse_row() -> dict[str, Any]:
    intent = {"shutter_events": [{"bar": 2, "beat": 1, "pattern": "pulse"}]}
    render = _one(intent)
    start = render.grid.get_beat_time_ms(4)
    t0, t1, values = next(
        effect
        for effect in render.effects[("MH1", 0)]
        if effect[0] == round(start) and CHANNELS["shutter"] in effect[2]
    )
    curve = values[CHANNELS["shutter"]]
    after = _in(render.frames(CHANNELS["shutter"]), start, render.grid.get_bar_start_ms(4))
    return {
        "id": "shutter_pulse",
        "intent": intent,
        "neutral_intent": {},
        "facts": {
            "set": {
                "channel": CHANNELS["shutter"],
                "curve_effect_ms": [t0, t1],
                "curve_points": len(curve),
                "curve_point_bytes": sorted({round(v) for _, v in curve}),
                "alternation_period_ms": round(2 * (t1 - t0) / (len(curve) - 1), 1),
                "frames_after_event": len(after),
                "frames_on_a_byte_naming_no_state": sum(
                    value not in SHUTTER_MAP.values() for value in after
                ),
            },
            "neutral": _channel(_one({}), "shutter", _names(SHUTTER_MAP)),
        },
    }


def _event_rows() -> list[dict[str, Any]]:
    rows = [
        _event(
            "shutter_closed_open",
            {
                "shutter_events": [
                    {"bar": 2, "beat": 1, "pattern": "closed"},
                    {"bar": 2, "beat": 3, "pattern": "open"},
                ]
            },
            "shutter",
        )
    ]
    rows += [
        _event(
            f"shutter_strobe_{speed}",
            {"shutter_events": [{"bar": 2, "beat": 1, "pattern": f"strobe_{speed}"}]},
            "shutter",
        )
        for speed in ("slow", "medium", "fast")
    ]
    rows.append(_pulse_row())
    rows.append(
        _event(
            "shutter_event_on_channel_17",
            {"shutter_events": [{"bar": 2, "beat": 1, "pattern": "closed"}]},
            "shutter",
            rig=_rig(shutter_channel=17),
            number=17,
        )
    )
    rows.append(
        _event("gobo_event", {"gobo_events": [{"bar": 2, "beat": 3, "pattern": "dots"}]}, "gobo")
    )
    rows.append(
        _event(
            "gobo_two_events",
            {
                "gobo_events": [
                    {"bar": 2, "beat": 1, "pattern": "dots"},
                    {"bar": 3, "beat": 1, "pattern": "open"},
                ]
            },
            "gobo",
        )
    )
    cue = {"bar": 1, "beat": 1, "moment_cue_id": CUE["cue_id"]}
    rows.append(
        _event(
            "cue_bound_shutter_event",
            {"shutter_events": [{**cue, "pattern": "closed"}]},
            "shutter",
            bind=True,
        )
    )
    rows.append(
        _event(
            "cue_bound_gobo_event",
            {"gobo_events": [{**cue, "pattern": "dots"}]},
            "gobo",
            bind=True,
        )
    )
    return rows


def _transition(render: Render) -> dict[str, Any]:
    """The layer-1 transition effect at the boundary and the layer-0 sections around it."""
    boundary = render.grid.get_bar_start_ms(4)
    spans = sorted({(t0, t1) for t0, t1, _ in render.effects.get(("MH1", 1), [])})
    facts: dict[str, Any] = {
        "boundary_ms": boundary,
        "transition_effect_ms": [list(span) for span in spans],
        "transition_effect_from_boundary_ms": [[t0 - boundary, t1 - boundary] for t0, t1 in spans],
    }
    for channel in ("dimmer", "pan"):
        layer = render.frames(CHANNELS[channel], layer=1)
        values = [value for value in layer if value is not None]
        facts[f"transition_{channel}"] = (
            {
                "first": values[0],
                "last": values[-1],
                "min": min(values),
                "max": max(values),
                "monotonic": values == sorted(values) or values == sorted(values, reverse=True),
                "at_boundary": layer[int(boundary) // FRAME_MS + 1],
            }
            if values
            else None
        )
    base = render.frames(CHANNELS["dimmer"])
    facts["base_dimmer_before_after"] = [
        base[int(boundary - 1_100) // FRAME_MS],
        base[int(boundary + 1_100) // FRAME_MS],
    ]
    facts["base_pan_before_after"] = [
        render.frames(CHANNELS["pan"])[int(boundary - 1_100) // FRAME_MS],
        render.frames(CHANNELS["pan"])[int(boundary + 1_100) // FRAME_MS],
    ]
    return facts


TRANSITION_MODES = ("snap", "crossfade", "morph", "fade_via_black", "sweep")


def _transition_rows() -> list[dict[str, Any]]:
    def render(hint: dict[str, Any] | None, *, enabled: bool = True) -> Render:
        return Render(
            _plan(
                _section("s1", (1, 4), TEMPLATE, {}),
                _section("s2", (5, 8), SECOND_TEMPLATE, {"transition_in": hint}),
            ),
            transitions=enabled,
        )

    default = _transition(render(None))
    rows = [
        {
            "id": "transition_in_null",
            "intent": {"transition_in": None},
            "neutral_intent": {"transitions_enabled": False},
            "facts": {"set": default, "neutral": _transition(render(None, enabled=False))},
        }
    ]
    for mode in TRANSITION_MODES:
        hint = {
            "mode": mode,
            "duration_bars": 0.0 if mode == "snap" else 1.0,
            "curve": "linear",
            "fade_out_ratio": 0.25,
            "per_channel_overrides": None,
        }
        rows.append(
            {
                "id": f"transition_in_{mode}",
                "intent": {"transition_in": hint},
                "neutral_intent": {"transition_in": None},
                "facts": {"set": _transition(render(hint)), "neutral": default},
            }
        )
    return rows


def _show_rows() -> list[dict[str, Any]]:
    """The old show projection (`coordinate_moving_head_plan`) called directly on a
    one-section macro plan, then the old renderer on the projected plan."""
    coordination = _mod("twinklr.core.sequencer.show_coordination")
    planning = _mod("twinklr.core.sequencer.planning.models")
    profile = _mod("twinklr.core.agents.audio.profile.models")
    targets = _mod("twinklr.core.sequencer.templates.group.models.coordination")
    choreography = _mod("twinklr.core.sequencer.templates.group.models.choreography")
    vocabulary = _mod("twinklr.core.sequencer.vocabulary")
    kinds = _mod("twinklr.core.sequencer.vocabulary.choreography")
    theming = _mod("twinklr.core.sequencer.theming")
    grid = _grid()
    heads = targets.PlanTarget(type=kinds.TargetType.GROUP, id="MOVING_HEADS")
    tree = targets.PlanTarget(type=kinds.TargetType.GROUP, id="MEGA_TREE")
    graph = choreography.ChoreographyGraph(
        graph_id="combined",
        groups=[
            choreography.ChoreoGroup(id=target.id, role=target.id, tags=[kinds.ChoreoTag.YARD])
            for target in (heads, tree)
        ],
    )

    def macro(role: str) -> Any:
        lead = heads if role == "LEAD" else tree
        roles = [planning.FocalRole(target=heads, role=role)]
        if role != "LEAD":
            roles.append(planning.FocalRole(target=tree, role="LEAD"))
        section = planning.MacroSection(
            section=profile.SongSectionRef(
                section_id="s1", name="s1", start_ms=0, end_ms=int(grid.get_bar_start_ms(4))
            ),
            energy_target=vocabulary.EnergyTarget.HIGH,
            motion_density=vocabulary.MotionDensity.BUSY,
            choreography_style=vocabulary.ChoreographyStyle.HYBRID,
            palette_role=planning.PaletteRoleRef(stop_id="p", override=None),
            theme=theming.ThemeRef(
                theme_id="theme.holiday.traditional", scope=theming.ThemeScope.SECTION
            ),
            motif_ids=[],
            focal_roles=roles,
            call_response_pairs=[],
            coordination_intent=vocabulary.CoordinationMode.UNIFIED,
            notes="Synthetic single-section macro plan.",
        )
        return planning.MacroPlan(
            sections=[section],
            palette_arc=[
                planning.PaletteStop(
                    stop_id="p",
                    palette=planning.PaletteRef(palette_id=SHOW_PALETTE),
                    applies_from_section_id="s1",
                    transition=planning.PaletteTransition.CUT,
                )
            ],
            motif_continuity=[],
            focal_arc=[planning.FocalAssignment(section_id="s1", lead_target=lead)],
        )

    rows = []
    for role in ("LEAD", "SUPPORT", "REST"):
        macro_plan = macro(role)
        projected = coordination.coordinate_moving_head_plan(
            _plan(_section("s1", (1, 4), TEMPLATE, None)),
            macro_plan,
            grid,
            {"MOVING_HEADS"},
            None,
            graph,
        )
        section = projected.sections[0]
        render = Render(projected)
        rows.append(
            {
                "id": f"show_focal_{role.lower()}",
                "intent": {"show": {"focal_role": role, "palette_id": SHOW_PALETTE}},
                "neutral_intent": None,
                "facts": {
                    "palette_colors": list(coordination._resolved_palette(macro_plan, "s1").colors),
                    "projected_intensity": section.intensity.value,
                    "projected_color": section.color_intent.explicit_color.value,
                    "set": _dimmer(render, *_section_window(render))
                    | {"color": _channel(render, "color", _names(COLOR_MAP))["runs"]},
                },
            }
        )
    return rows


# --- what xLights played: the layer finding --------------------------------------------

LAYER_PLAYBACK: dict[str, Any] = {
    "provenance": (
        "transcribed from the output of layer_playback.py (path below), run 2026-11-17 on "
        "the two files named here; not measured by this extraction script"
    ),
    "question": (
        "the old exporter wrote transitions as a second EffectLayer under each head's "
        "section layer, without a LayerMethod: did xLights play the transition, the "
        "section layer, or a mix?"
    ),
    "scope": (
        "one song: the owner's 2026-11-16 viewing render (Need A Favor) on the owner rig, "
        "the old renderer's reference .xsq produced by the code at commit dcc14ddf, read "
        "under implementation-brief.md row 139 (viewing render and old-renderer reference: "
        "inputs)"
    ),
    "source": {
        "xsq": "~/xlights/_twinklr_verify/p3_view/out/legacy_need_a_favor.xsq",
        "xsq_sha256": "7d75ab25d4f28c0e3811ae67c83c6ce7751e4358c28f9ee029b0bf1b7320df34",
        "fseq": "~/xlights/_twinklr_verify/p3_view/out/legacy_need_a_favor.fseq",
        "fseq_sha256": "b8070827f929c8da80499ccc481cb3edfb6c15da9f10aff1884b363fa005f294",
        "script": "changes/2026_11_12_mh_true_up/evidence/2026-11-17-w0-intent-parity/"
        "layer_playback.py",
    },
    "fseq": "v2.2, zstd, 64 channels in 4 sparse ranges of 16, 9870 frames of 20 ms",
    "head_to_range": (
        "computed, not assumed: each head's agreement with its section layer outside "
        "transitions is 0.972-0.980 on its own range and at most 0.686 on any other"
    ),
    "xsq_layers": (
        "per head: the first EffectLayer holds the 26-28 section effects, the second the 4 "
        "transition effects; no setting names a LayerMethod"
    ),
    "frames_inside_transition_effects": {
        "with_a_section_effect": {
            "played_section_only": 6351,
            "played_either": 4112,
            "played_transition_only": 4,
            "played_neither": 393,
        },
        "neither_resampled": {
            "matches_section_at_t-20_t+20_or_mid_frame": 82,
            "within_the_section_curve_swing_over_those_samples": 240,
            "left": 71,
            "left_on_channel_2": 64,
            "left_on_channels_3_and_11": 7,
            "left_nearer_the_transition_than_the_section": 24,
            "note": (
                "channel 2's section curve moves up to ~75 bytes per frame and its "
                "transition byte is 0, so a low byte there is nearer the transition by "
                "coincidence; none of the 7 others is nearer the transition (3 lie within "
                "3 bytes of a section sample a frame away, 4 are on the last frame before a "
                "section effect ends)"
            ),
        },
        "without_a_section_effect": {
            "played_transition": 1668,
            "other": 144,
            "other_matches_transition_at_t-20_t+20_or_mid_frame": 144,
        },
        "section_byte_zero_under_nonzero_transition": 0,
        "unit": "channel-frames within ±1 of the sampled value",
    },
    "example": {
        "head": "MH2",
        "transition_effect_ms": [128100, 131140],
        "boundary_ms": 129625,
        "channel_11": "played 123 until 129620, then 39 (the section layer's cut); the "
        "transition layer would have glided 123 -> 100",
    },
    "finding": (
        "in the owner's 2026-11-16 viewing render of one song, wherever the section layer's "
        "byte was non-zero, the section layer played: every boundary between two sections "
        "played as a cut. The transition layer showed only where a head had no section "
        "effect (MH1 and MH4, 129620-150900 ms), as a fade to or from nothing. No frame had "
        "a zero section byte under a non-zero transition byte, so that case is unobserved"
    ),
}


# --- annotations: parity targets, tasks, citations, what is not carried over ----------

PENDING = "regression"
"""Rendered by the old renderer, not by the current one: tested, failing until `task`."""
RECORDED = "recorded"
"""A fact with no render-level parity target; the reason is in the row."""

_EVENTS = [
    f"{OLD}sequencer/moving_heads/pipeline.py:2362-2410 (events placed at the bar/beat's grid time)",
    f"{OLD}sequencer/moving_heads/compile/intent_resolution.py:43-117 (segment split at the "
    "event, the event's value held until the next event or the section end)",
]
_WHEELS = f"{OLD}sequencer/moving_heads/handlers/wheels.py"
_DIMMER = [
    f"{OLD}sequencer/moving_heads/compile/intent_resolution.py:21-40 (intensity onto every step)",
    f"{OLD}sequencer/moving_heads/libraries/dimmer.py:50-59 (DEFAULT_DIMMER_PARAMS)",
    f"{OLD}sequencer/moving_heads/handlers/dimmers/default.py:110-123,151-192 (period in "
    "bars to cycles; a pattern with its own table, HOLD or BLACKOUT, ignores intensity)",
    f"{OLD}sequencer/moving_heads/handlers/movement/default.py:80-88 (movement ignores it)",
]
_SAMPLES = (
    "the pulse shape: 64 linearly interpolated samples per segment whatever its length "
    f"({OLD}sequencer/models/context.py:148), here 4 per beat for INTENSE on the 4-bar step"
)
_LIT_TURN = (
    "the wheel byte changes on a frame whose dimmer is nonzero: the old renderer had no "
    "dark transaction; the new path turns wheels only while dark"
)
_COLOR_FIRST_FRAME = (
    "the colour is present from the section's first frame, so inside one section nothing "
    "turns; the wheel turns lit only at a boundary between sections of different colours "
    "(color_change_between_sections)"
)
_TRANSITION = [
    f"{OLD}sequencer/moving_heads/pipeline.py:1760-1763,2428-2513,2515-2563",
    f"{OLD}sequencer/moving_heads/compile/transition_planner.py:130-190 (overlap; only "
    "CROSSFADE splits it by fade_out_ratio), 192-245 (strategies from the job's "
    "per-channel defaults; the mode is read only for SNAP)",
    f"{OLD}sequencer/moving_heads/compile/channel_blender.py:38-80",
    f"{OLD}config/models.py:587-637 (TransitionConfig: enabled, 0.5-bar CROSSFADE default)",
    f"{OLD}sequencer/moving_heads/export/xsq_adapter.py:272-292 (transitions on a second layer)",
]
_NOT_PLAYED = (
    "the transition was written on a second xLights layer under the untrimmed section "
    "layer; in the one render measured (LAYER_PLAYBACK) the section layer played wherever "
    "its byte was non-zero, so the blend in these facts was not what played and the "
    "boundary played as a cut. The target is the planner's intent, a smooth lit change "
    "between sections"
)
_WINDOW = (
    "the test's window is this row's transition_effect_from_boundary_ms (for CROSSFADE "
    "-500...+1500 ms, the old 25% early split); W8 keeps that window or updates the row"
)
_SHOW = [
    f"{OLD}sequencer/show_coordination.py:69-73 (_ROLE_MH_INTENSITY), 83-98 (_PRESET_RGB), "
    "503-553 (_closest_preset, coordinate_moving_head_plan)",
    f"{OLD}pipeline/show_stages.py:224-262 (legacy show render projects the macro plan)",
]
_CODE_OWNED = (
    "the curve, duration_bars and fade_out_ratio numbers are the planner's categories in the "
    "revised plan (Transition{mode, length, curve}); this row fixes none of them"
)
_INTENSITY_TARGET = (
    "Relative to the neutral render of the same section: every frame dark there stays dark "
    "and every frame lit there stays lit; no lit frame is dimmer than the neutral one and "
    "the lowest lit level is higher (a raised floor); the dimmer pulses (at least two "
    "levels) with a period of a whole number of beats, {period}, each pulse peaking within "
    "one frame after a beat; on every head."
)

ANNOTATIONS: dict[str, dict[str, Any]] = {
    "intensity_slow": {
        "status": RECORDED,
        "code": _DIMMER,
        "parity_target": None,
        "not_a_parity_target": [
            "SLOW rendered exactly as SMOOTH: the dimmer table gives SLOW and FAST the SMOOTH "
            "values since the owner reverted P4-F8 on 2026-11-12 (libraries/dimmer.py:51-54); "
            "the revised plan keeps them as the identity"
        ],
    },
    "intensity_fast": {
        "status": RECORDED,
        "code": _DIMMER,
        "parity_target": None,
        "not_a_parity_target": [
            "FAST rendered exactly as SMOOTH (same table entry, reverted P4-F8); movement "
            "ignored intensity, so FAST was not faster either"
        ],
    },
    "intensity_dramatic": {
        "status": PENDING,
        "task": "W5",
        "code": _DIMMER,
        "parity_target": _INTENSITY_TARGET.format(period="longer than INTENSE's"),
        "not_a_parity_target": [
            "the 5-beat period (1.25 bars in the table) is a fact, not pinned: the revised "
            "plan has the W5 table set it, a whole number of beats longer than INTENSE's",
            "the exact bytes (131-255 here) come from the template's 60 floor and min/max_norm "
            "over the table's 100-255; the new path scales its own levels",
            _SAMPLES,
        ],
    },
    "intensity_intense": {
        "status": PENDING,
        "task": "W5",
        "code": _DIMMER,
        "parity_target": _INTENSITY_TARGET.format(period="one beat"),
        "not_a_parity_target": [
            "the exact bytes (171-255 here) come from the template's floor and norms over the "
            "table's 150-255",
            _SAMPLES,
        ],
    },
    "intensity_dramatic_on_authored_pulse": {
        "status": PENDING,
        "task": "W5",
        "code": _DIMMER,
        "parity_target": (
            "On a template that authors its own dimmer pulse, against the template as "
            "authored: dark frames stay dark and lit frames stay lit; no lit frame is dimmer "
            "than as authored and the lowest lit level is higher; the dimmer still pulses "
            "with peaks within one frame after a beat; on every head."
        ),
        "not_a_parity_target": [
            "the old renderer replaced the authored curve with the table's (the breathe's "
            "4-bar swell became a 5-beat pulse); the revised plan raises the authored look "
            "instead, never below it"
        ],
    },
    "intensity_intense_on_authored_pulse": {
        "status": PENDING,
        "task": "W5",
        "code": _DIMMER,
        "parity_target": (
            "On a template that authors its own dimmer pulse, against the template as "
            "authored: dark frames stay dark and lit frames stay lit; no lit frame is dimmer "
            "than as authored and the lowest lit level is higher; the dimmer pulses once per "
            "beat, peaks within one frame after the beat; on every head."
        ),
        "not_a_parity_target": [
            "the old renderer replaced the authored curve with the table's; the revised plan "
            "raises the authored look instead"
        ],
    },
    "intensity_smooth_on_energetic_template": {
        "status": RECORDED,
        "code": _DIMMER,
        "parity_target": None,
        "owner_view": "W5",
        "not_a_parity_target": [
            "an explicit SMOOTH calmed an energetic template: fan_pulse as authored (DRAMATIC) "
            "pulses 131-255 every 5 beats; with SMOOTH it became a 51-153 swell over 4 bars. "
            "The revised plan makes SMOOTH the identity so the accepted look is not dimmed. "
            "For the owner to judge at W5's view, not a target"
        ],
    },
    "color_explicit_blue": {
        "status": PENDING,
        "task": "W4",
        "code": [
            f"{OLD}sequencer/moving_heads/pipeline.py:2362-2373",
            f"{OLD}sequencer/moving_heads/compile/intent_resolution.py:36-37",
            f"{_WHEELS}:31-59 (name through the fixture's color_map; absent name: 'open')",
        ],
        "parity_target": (
            "Every lit frame of the section, on every head, shows the colour wheel state for "
            "blue; the wheel changes only while the head is dark and settles before the "
            "reveal; the dark frames differ from the neutral render's only in the window "
            "before the section's reveal (close latency + wheel settle + half a beat)."
        ),
        "not_a_parity_target": [_COLOR_FIRST_FRAME],
    },
    **{
        f"color_palette_{role.lower()}": {
            "status": PENDING,
            "task": "W4",
            "code": [
                f"{OLD}sequencer/moving_heads/pipeline.py:146-157 (PALETTE_ROLE_TO_COLOR)",
                f"{OLD}sequencer/moving_heads/pipeline.py:2362-2373 (no palette input)",
                f"{_WHEELS}:31-59",
            ],
            "parity_target": (
                f"With the song's macro palette {RUN_PALETTE} in `twinklr run`, every lit frame "
                f"of the section, on every head, shows {target}; the wheel changes only while "
                "dark; dark frames differ from neutral only before the reveal, as for an "
                "explicit colour."
            ),
            "not_a_parity_target": [
                f"the fixed role table ({role} -> {preset}) whatever the song's palette; the "
                "revised plan resolves a role through the macro palette's stops",
                _COLOR_FIRST_FRAME,
            ],
        }
        for role, preset, target in (
            (
                "PRIMARY",
                "red",
                "the rig state nearest the palette's first stop (red), not ACCENT's",
            ),
            (
                "ACCENT",
                "magenta",
                "the rig state nearest the palette's second stop (green), not PRIMARY's",
            ),
            ("WARM", "amber", "one state other than the rig default and other than COOL's"),
            ("COOL", "cyan", "one state other than the rig default and other than WARM's"),
        )
    },
    "color_palette_neutral": {
        "status": RECORDED,
        "code": [f"{OLD}sequencer/moving_heads/pipeline.py:146-157"],
        "parity_target": None,
        "not_a_parity_target": [
            "NEUTRAL resolved to white, which is also the rig's default colour here; nothing "
            "observable distinguishes it from no colour intent on this rig"
        ],
    },
    "color_change_between_sections": {
        "status": RECORDED,
        "code": [f"{_WHEELS}:31-59", f"{OLD}config/models.py:587-637"],
        "parity_target": None,
        "not_a_parity_target": [
            "the wheel turned from red to blue at the boundary with the head lit (dimmer "
            "nonzero on both sides); W4 owns colour changes at boundaries (the revised plan's "
            "timing rule forces a dark dip there)"
        ],
    },
    "shutter_closed_open": {
        "status": PENDING,
        "task": "W6",
        "code": [*_EVENTS, f"{_WHEELS}:62-119"],
        "parity_target": (
            "The head is dark from the frame at bar 2 beat 1 (within one frame) until bar 2 "
            "beat 3, and lit again from then on (within one frame) as in the neutral render; "
            "every frame before the event equals the neutral render; the same on every head."
        ),
        "not_a_parity_target": [],
    },
    **{
        f"shutter_strobe_{speed}": {
            "status": PENDING,
            "task": "W6",
            "code": [*_EVENTS, f"{_WHEELS}:118-119 (shutter_map byte)"],
            "parity_target": (
                "The first dark frame is within one frame of bar 2 beat 1; from then the head "
                "goes dark and lit again at least twice in the following bar and keeps "
                "strobing to the section end; before that it equals the neutral render. "
                "Strobe speeds are ordered: more dark-lit alternations per bar for fast than "
                "medium than slow."
            ),
            "not_a_parity_target": [
                "the strobe rate was the fixture's own (one static shutter byte); the plan of "
                "record renders it as a dimmer or shutter pulse, or a state tagged strobe"
            ],
        }
        for speed in ("slow", "medium", "fast")
    },
    "shutter_pulse": {
        "status": PENDING,
        "task": "W6",
        "code": [*_EVENTS, f"{_WHEELS}:95-112 (closed/open alternate by sample index)"],
        "parity_target": (
            "From the frame at bar 2 beat 1 (within one frame) to the section end the head "
            "pulses with the beat: it is revealed once per beat, each reveal within one frame "
            "after the beat, and dark between reveals; before that it equals the neutral render."
        ),
        "not_a_parity_target": [
            "the period: the curve alternated closed/open by sample index (64 samples over the "
            "remaining segment), not by beat, so its rate depended on the segment's length",
            "xLights interpolates the curve linearly, so most frames sent a byte between the "
            "closed and open values that names no shutter state",
        ],
    },
    "shutter_event_on_channel_17": {
        "status": RECORDED,
        "code": [f"{_WHEELS}:16-22,85-92 (PLAN_INTENT_CHANNEL_WINDOW_MAX = 16)"],
        "parity_target": None,
        "not_a_parity_target": [
            "a shutter above channel 16 dropped every shutter event (handler trace says so); "
            "a limit of the old exporter's 16-slider window, not intent. The rows above hold "
            "on the current rigs, whose shutter is on channel 17 or 6"
        ],
    },
    "gobo_event": {
        "status": PENDING,
        "task": "W7",
        "code": [*_EVENTS, f"{_WHEELS}:122-150"],
        "parity_target": (
            "The head is lit on the frame at bar 2 beat 3 (within one frame) showing gobo "
            "dots, and every lit frame from then to the section end shows dots; the frames lit "
            "in the neutral render before the event stay lit and show the neutral gobo; dark "
            "frames differ from neutral only in the window before the reveal (close latency + "
            "wheel settle + half a beat); the wheel changes only while dark; on every head."
        ),
        "not_a_parity_target": [_LIT_TURN],
    },
    "gobo_two_events": {
        "status": PENDING,
        "task": "W7",
        "code": [*_EVENTS, f"{_WHEELS}:122-150"],
        "parity_target": (
            "Gobo dots from bar 2 beat 1 is held on every lit frame until bar 3 beat 1, then "
            "open from that beat to the section end; each reveal lands within one frame of its "
            "beat; dark frames differ from neutral only in the windows before the two reveals; "
            "the wheel changes only while dark; on every head."
        ),
        "not_a_parity_target": [_LIT_TURN],
    },
    "cue_bound_shutter_event": {
        "status": PENDING,
        "task": "W6",
        "code": [
            f"{OLD}agents/sequencer/moving_heads/moment_cues.py:35-66,151-173",
            *_EVENTS,
        ],
        "parity_target": (
            "With the plan bound to the lyric cues, the CLOSED event bound to cue 'hook' "
            "darkens the head from the cue's snapped beat (bar 2 beat 2, first dark frame "
            "within one frame) to the section end; before that it equals the neutral render."
        ),
        "not_a_parity_target": [],
    },
    "cue_bound_gobo_event": {
        "status": PENDING,
        "task": "W7",
        "code": [
            f"{OLD}agents/sequencer/moving_heads/moment_cues.py:35-66,151-173",
            *_EVENTS,
        ],
        "parity_target": (
            "With the plan bound to the lyric cues, the gobo event bound to cue 'hook' "
            "behaves as gobo_event at the cue's snapped beat (bar 2 beat 2)."
        ),
        "not_a_parity_target": [_LIT_TURN],
    },
    "transition_in_null": {
        "status": RECORDED,
        "code": _TRANSITION,
        "parity_target": None,
        "not_a_parity_target": [
            "with no hint the old renderer still wrote a blend at every boundary (the job's "
            "default 0.5-bar crossfade), which xLights did not show (LAYER_PLAYBACK); null "
            "keeps today's render, the regression anchor"
        ],
    },
    "transition_in_snap": {
        "status": RECORDED,
        "code": _TRANSITION,
        "parity_target": None,
        "not_a_parity_target": [
            "SNAP placed no transition: the outgoing section cut to the incoming one at the "
            "boundary, the aim jumping while lit. The current renderer already starts the "
            "incoming look at the boundary (behind its entry dip); the lit jump is a defect"
        ],
    },
    **{
        f"transition_in_{mode}": {
            "status": PENDING,
            "task": "W8",
            "code": _TRANSITION,
            "parity_target": (
                "Across the transition window (one bar centred on the boundary; for "
                "crossfade, a quarter before and three quarters after) the head is never "
                "dark; on lit frames pan and tilt move no faster than the profile's travel "
                "speed; from the window's end the aim is the neutral render's (the incoming "
                "section's); on every head."
                + (
                    " MORPH and SWEEP render differently from each other (W8 defines how)."
                    if mode != "crossfade"
                    else ""
                )
            ),
            "not_a_parity_target": [
                _NOT_PLAYED,
                _WINDOW,
                *(
                    [
                        "MORPH, SWEEP and FADE_VIA_BLACK wrote the same blend as a symmetric "
                        "CROSSFADE: the mode was read only for SNAP and CROSSFADE's split"
                    ]
                    if mode != "crossfade"
                    else []
                ),
                _CODE_OWNED,
            ],
        }
        for mode in ("crossfade", "morph", "sweep")
    },
    "transition_in_fade_via_black": {
        "status": PENDING,
        "task": "W8",
        "code": _TRANSITION,
        "parity_target": (
            "Across the transition window the dimmer fades down through at least two "
            "intermediate levels to dark at the boundary and up through at least two after "
            "it, on every head."
        ),
        "not_a_parity_target": [
            _NOT_PLAYED,
            _WINDOW,
            "the old renderer ignored the mode and wrote a lit blend like a symmetric "
            "crossfade; the intent (fade through black) is the target, not that blend",
        ],
    },
    "show_focal_lead": {
        "status": PENDING,
        "task": "W9",
        "code": _SHOW,
        "parity_target": (
            "Under `twinklr show`, with the same plan (intensity null), a section whose macro "
            "focal role for the heads is LEAD renders hotter than with SUPPORT: no lit frame "
            "dimmer, some lit frame brighter (a raised floor or a beat pulse, per the W5 "
            "table); with REST no lit frame is brighter than with SUPPORT (as authored); the "
            "dark frames and every channel but the dimmer identical; on every head."
        ),
        "not_a_parity_target": [
            "the old projection overwrote the plan's intensity (LEAD INTENSE, SUPPORT SMOOTH, "
            "REST SLOW) whatever the plan said. The design (integrator decision, 2026-11-17) "
            "applies the macro focal role deterministically in the show render, adjusting "
            "the section's effective intensity and recording it in the trace; this row tests "
            "that render effect"
        ],
    },
    "show_focal_support": {
        "status": RECORDED,
        "code": _SHOW,
        "parity_target": None,
        "not_a_parity_target": ["SUPPORT projected SMOOTH; show_focal_lead tests the roles"],
    },
    "show_focal_rest": {
        "status": RECORDED,
        "code": _SHOW,
        "parity_target": None,
        "not_a_parity_target": [
            "REST projected SLOW, which rendered as SMOOTH; show_focal_lead tests the roles"
        ],
    },
    "show_palette_color": {
        "status": PENDING,
        "task": "W9",
        "code": _SHOW,
        "parity_target": (
            f"Under `twinklr show` with macro palette {SHOW_PALETTE}, a section whose colour "
            "intent is palette role PRIMARY shows, on every lit frame and every head, the rig "
            "state nearest the palette's first stop (#0D47A1: blue on these rigs, not red)."
        ),
        "not_a_parity_target": [
            "the old input carried no colour (plan_color null): the projection overwrote it "
            "with the preset nearest the first stop whatever the plan said; the revised plan "
            "resolves the plan's palette role through the macro palette instead",
            _COLOR_FIRST_FRAME,
        ],
    },
}


def _show_palette_row(show_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The palette half of the show projection, read from the LEAD render's colour runs."""
    lead = show_rows[0]["facts"]
    return {
        "id": "show_palette_color",
        "intent": {"show": {"palette_id": SHOW_PALETTE}, "color": {"palette_role": "PRIMARY"}},
        "neutral_intent": None,
        "facts": {
            "plan_color": None,
            "palette_colors": lead["palette_colors"],
            "projected_color": lead["projected_color"],
            "color_runs": lead["set"]["color"],
            "same_for_every_focal_role": len(
                {json.dumps(row["facts"]["set"]["color"]) for row in show_rows}
            )
            == 1,
        },
    }


def build(commit: str) -> dict[str, Any]:
    """The fixture: provenance, setup and each row's facts with its annotation."""
    show = _show_rows()
    rows = [
        *_intensity_rows(),
        *_color_rows(),
        *_event_rows(),
        *_transition_rows(),
        *show,
        _show_palette_row(show),
    ]
    for row in rows:
        row.update(provenance="rendered", **ANNOTATIONS[row["id"]])
    return {
        "schema": 1,
        "provenance": {
            "tag": TAG,
            "commit": commit,
            "commit_source": "git get-tar-commit-id on the archive the script extracted",
            "script": "scripts/extract_mh_intent_parity.py",
            "renderer": "legacy_v1 RenderingPipeline.render(), DmxSettingsBuilder per segment",
            "sampling": "per layer, before emission quantisation, on the 20 ms frame grid",
            "show": "coordinate_moving_head_plan called directly; no full `twinklr show` run",
            "frame_ms": FRAME_MS,
        },
        "layer_playback": LAYER_PLAYBACK,
        "setup": {
            "grid": {"first_beat_ms": SHIFT_MS, "beat_ms": BEAT_MS, "bars": BARS},
            "section_bars": [1, 4],
            "transition_sections": [[1, 4], [5, 8]],
            "old_template": TEMPLATE,
            "old_second_template": SECOND_TEMPLATE,
            "old_breathe_template": BREATHE_TEMPLATE,
            "old_rig": {
                "heads": list(HEADS),
                "channels": CHANNELS,
                "shutter_map": SHUTTER_MAP,
                "color_map": COLOR_MAP,
                "gobo_map": GOBO_MAP,
            },
            "cue": CUE,
            "run_palette": RUN_PALETTE,
            "show_palette": SHOW_PALETTE,
            "neutral": (
                "neutral_intent {} is the old model's explicit neutral (SMOOTH, palette role "
                "PRIMARY, no events, no transition hint); null leaves every intent field out "
                "(the template as authored)"
            ),
        },
        "rows": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="mh-legacy-") as directory:
        archive = Path(directory).resolve()
        commit = _extract_tag(repo, archive)
        _bootstrap(archive)
        fixture = build(commit)
    args.out.write_text(json.dumps(fixture, indent=1) + "\n")
    print(f"wrote {len(fixture['rows'])} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
