"""Intent parity: each piece of planner intent the deleted renderer rendered, asserted on
the current renderer.

`baselines/mh_intent_parity.json` records, per intent, what the old renderer (tag
`mh-last-with-legacy-renderer`, mode `legacy_v1`) did with it on synthetic inputs and the
parity target the current renderer must meet, in renderer-independent terms; it is
written by `scripts/extract_mh_intent_parity.py`. Each test renders the row's intent on
the current renderer (through `RenderingPipeline`; `twinklr run`'s
`MovingHeadRenderingStage` where the song's macro palette matters; for the show rows, the
show stage's moving-head render method, `CombinedShowRenderStage._render_moving_heads`)
and checks the target against the encoded frames alone: which channel holds which named
state when, and whether the head is commanded dark.

Every row the current renderer does not meet yet is a strict xfail naming the task of
`changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md` that renders it: the test
turns red the moment the intent starts rendering, and that task removes its entry from
`PENDING`. `test_neutral_intent_renders_the_pinned_bytes` is the regression anchor: a
plan with all intent neutral renders the bytes `test_mh_pins.py` pins.

Everything that knows the planner contract or a stage's call shape is in the block
"Plans and calls" below; W2 (and W4/W9 where they thread the macro plan) rewrite that
block only.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from itertools import pairwise
import json
import math
from pathlib import Path
from typing import Any

from defusedxml import ElementTree
import pytest

from tests.regression.test_mh_pins import HEADS, PINS, _frames_sha256
from tests.support import moving_heads as m
from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.agents.sequencer.moving_heads.moment_cues import bind_lyric_moment_cues
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import MovingHeadRenderingStage
from twinklr.core.config.fixtures import AxisCapability, FixtureCapabilities, FixtureGroup
from twinklr.core.config.fixtures.state_tags import nearest_color_state
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.pipeline.show_stages import CombinedShowRenderStage
from twinklr.core.sequencer.moving_heads.export.frame_encoder import EncodedFixtureFrame
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.planning.models import (
    FocalAssignment,
    FocalRole,
    MacroPlan,
    MacroSection,
    PaletteRef,
    PaletteRoleRef,
    PaletteStop,
    PaletteTransition,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.theming.catalog import get_palette
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EnergyTarget,
    MotionDensity,
)
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag, TargetType

REFERENCE = json.loads((Path(__file__).parent / "baselines" / "mh_intent_parity.json").read_text())
ROWS: dict[str, dict[str, Any]] = {row["id"]: row for row in REFERENCE["rows"]}
FRAME = EFFECT_GRID_MS
GRID = m.bars_grid(*([500.0] * 8))
"""The reference grid: eight bars of 500 ms beats, the first beat 15 ms off the frame grid."""
BEAT = 500.0
SECTION = (GRID.bar_boundaries[0], GRID.bar_boundaries[4])
"""Bars 1-4, the section every single-section row renders."""
TEMPLATE = "mirror_wings"
"""Lit throughout once revealed, white, gobo open, a held full dimmer."""
HOLD_TEMPLATE = "parity_partial_hold"
"""Test-only: one held aim, the dimmer held at half, so a raised level can show."""
PULSE_TEMPLATE = "parity_authored_pulse"
"""Test-only: one held aim with its own dimmer pulse, 0.3-0.8 over two beats."""

PREFIXES = (
    "intensity",
    "color",
    "shutter_closed",
    "shutter_strobe",
    "shutter_pulse",
    "gobo",
    "cue_bound",
    "transition",
    "show_focal",
    "show_palette",
)
"""Row-id prefix of each test below; together they cover every regression row."""

PENDING: dict[str, tuple[str, str]] = {
    "intensity_dramatic": ("W5", "intensity DRAMATIC"),
    "intensity_intense": ("W5", "intensity INTENSE"),
    "intensity_dramatic_on_authored_pulse": ("W5", "intensity DRAMATIC on an authored pulse"),
    "intensity_intense_on_authored_pulse": ("W5", "intensity INTENSE on an authored pulse"),
    "color_explicit_blue": ("W4", "section colour (explicit)"),
    "color_palette_primary": ("W4", "section colour (palette role PRIMARY)"),
    "color_palette_accent": ("W4", "section colour (palette role ACCENT)"),
    "color_palette_warm": ("W4", "section colour (palette role WARM)"),
    "color_palette_cool": ("W4", "section colour (palette role COOL)"),
    "shutter_closed_open": ("W6", "shutter CLOSED/OPEN events"),
    "shutter_strobe_slow": ("W6", "shutter STROBE_SLOW event"),
    "shutter_strobe_medium": ("W6", "shutter STROBE_MEDIUM event"),
    "shutter_strobe_fast": ("W6", "shutter STROBE_FAST event"),
    "shutter_pulse": ("W6", "shutter PULSE event"),
    "cue_bound_shutter_event": ("W6", "lyric-cue-bound shutter event"),
    "gobo_event": ("W7", "gobo event"),
    "gobo_two_events": ("W7", "successive gobo events"),
    "cue_bound_gobo_event": ("W7", "lyric-cue-bound gobo event"),
    "transition_in_crossfade": ("W8", "transition_in CROSSFADE"),
    "transition_in_morph": ("W8", "transition_in MORPH"),
    "transition_in_sweep": ("W8", "transition_in SWEEP"),
    "transition_in_fade_via_black": ("W8", "transition_in FADE_VIA_BLACK"),
    "show_focal_lead": ("W9", "show macro focal role"),
    "show_palette_color": ("W9", "show macro palette colour"),
}
"""Rows not rendered yet: (task that renders it, intent). A task deletes its entries."""

_USED: set[str] = set()


def _rows(prefix: str) -> list[Any]:
    """The fixture's regression rows whose id starts with `prefix`, pending ones as strict
    xfails. Each prefix of `PREFIXES` is used by exactly one test."""
    assert prefix in PREFIXES and prefix not in _USED, prefix
    _USED.add(prefix)
    params = []
    for row_id, row in ROWS.items():
        if not row_id.startswith(prefix) or row["status"] != "regression":
            continue
        marks = []
        if row_id in PENDING:
            task, intent = PENDING[row_id]
            marks.append(
                pytest.mark.xfail(
                    strict=True,
                    reason=f"{task}: {intent} not rendered yet — plan/song-intent-rendering.md",
                )
            )
        params.append(pytest.param(row_id, marks=marks, id=row_id))
    return params


# --- Plans and calls: the one block that knows the planner contract and stage calls -------


def parity_rig() -> FixtureGroup:
    """`m.family_rig` with a green colour state added, so a palette's first two stops can
    land on different states, and every colour state tagged with the colour it is named
    for (white, red, blue, green: W1's `hex` tags)."""
    payload = m.family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        states = fixture["config"]["physical_profile"]["discrete"]["color"]["states"]
        states["green"] = {"range_min": 30, "range_max": 39, "value": 34, "settle_ms": 120}
        for name, state in states.items():
            state["hex"] = name
    return FixtureGroup.model_validate(payload)


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    hold = m.hold_step(
        "hold", 10.0, dimmer={"period_beats": 4.0, "duty_cycle": 1.0, "low": 0.0, "high": 0.5}
    )
    pulse = m.hold_step(
        "pulse", 10.0, dimmer={"period_beats": 2.0, "duty_cycle": 0.5, "low": 0.3, "high": 0.8}
    )
    with (
        m.family_catalog(),
        m.registered_templates(
            m.loop_template_doc(HOLD_TEMPLATE, [hold]),
            m.loop_template_doc(PULSE_TEMPLATE, [pulse]),
        ),
    ):
        yield


_LENGTHS = {
    0.25: "BEAT",
    0.5: "HALF_BAR",
    1.0: "BAR",
    1.5: "ONE_AND_HALF_BARS",
    2.0: "TWO_BARS",
    3.0: "THREE_BARS",
    4.0: "FOUR_BARS",
    6.0: "SIX_BARS",
    8.0: "EIGHT_BARS",
}
"""The transition lengths by their bars on the reference grid's 4/4."""

_SPLITS = {
    1 / 4: "QUARTER",
    1 / 3: "THIRD",
    1 / 2: "HALF",
    2 / 3: "TWO_THIRDS",
    3 / 4: "THREE_QUARTERS",
}
"""The transition splits by the fade-out share they name."""


def _nearest(table: dict[float, str], value: float) -> str:
    return table[min(table, key=lambda key: abs(key - value))]


def _transition(edge: str, hint: dict[str, Any]) -> dict[str, Any]:
    """A fixture row's old-renderer `TransitionHint` as the contract's categorical
    transition: the same mode and curve, the nearest length and the nearest split."""
    return {
        "edge": edge,
        "mode": hint["mode"],
        "length": _nearest(_LENGTHS, hint["duration_bars"]),
        "curve": hint["curve"],
        "split": _nearest(_SPLITS, hint["fade_out_ratio"]),
        "channels": [],
    }


def plan_section(
    intent: dict[str, Any],
    *,
    name: str = "s1",
    bars: tuple[int, int] = (1, 4),
    template_id: str = TEMPLATE,
) -> PlanSection:
    """The planner contract's section for a fixture row's renderer-neutral `intent`.

    `intent` keys: `intensity`, `color` (`{"explicit": preset}` or `{"palette_role":
    role}`), `shutter_events` and `gobo_events` (`bar`, `beat`, `pattern`, optional
    `moment_cue_id`), `transition_in` (a hint). `{}` is the neutral plan: every song
    intent null or empty, the template as authored.
    """
    color = intent.get("color")
    events = [
        {
            "bar": event["bar"],
            "beat": event["beat"],
            "moment_cue_id": event.get("moment_cue_id"),
            "action": "gobo" if key == "gobo_events" else event["pattern"],
            "color": None,
            "gobo": event["pattern"] if key == "gobo_events" else None,
        }
        for key in ("shutter_events", "gobo_events")
        for event in intent.get(key, [])
    ]
    cues = sorted({event["moment_cue_id"] for event in events} - {None})
    hint = intent.get("transition_in")
    return PlanSection.model_validate(
        {
            "section_id": name,
            "start_bar": bars[0],
            "end_bar": bars[1],
            "section_role": None,
            "energy_level": None,
            "parts": [
                {
                    "start_bar": bars[0],
                    "template_id": template_id,
                    "preset_id": None,
                    "modifiers": [],
                    "label": None,
                    "reasoning": "",
                }
            ],
            "intensity": intent.get("intensity"),
            "color": (
                None
                if color is None
                else color["explicit"]
                if "explicit" in color
                else f"PALETTE_{color['palette_role']}"
            ),
            "gobo": None,
            "moment_cues": cues,
            "events": events,
            "motif_id": None,
            "variation": "NONE",
            "density": "BALANCED",
            "transitions": [] if hint is None else [_transition("ENTRY", hint)],
            "reasoning": "",
        }
    )


def single_plan(intent: dict[str, Any], template_id: str = TEMPLATE) -> ChoreographyPlan:
    return ChoreographyPlan(
        sections=[plan_section(intent, template_id=template_id)], overall_strategy=""
    )


def bound_plan(intent: dict[str, Any]) -> ChoreographyPlan:
    """`single_plan(intent)` bound to the reference lyric cue by the planner's binder."""
    cue = REFERENCE["setup"]["cue"]
    lyrics = LyricContextModel(
        has_lyrics=True,
        vocal_coverage_pct=0.25,
        moment_cues=[
            MomentCue(**cue, emphasis="HIGH", text="light the way", visual_hint="Accent the hook.")
        ],
    )
    song = [SongSectionRef(section_id="s1", name="s1", start_ms=0, end_ms=int(SECTION[1]))]
    return bind_lyric_moment_cues(single_plan(intent), lyrics, GRID, song)


def transition_plan(intent: dict[str, Any]) -> ChoreographyPlan:
    """Two sections: a held aim (`finite_snap_hold`), then `TEMPLATE` from another aim. The
    old contract carried the transition as the second section's `transition_in`; the
    contract carries it as the second section's ENTRY transition."""
    first, second = REFERENCE["setup"]["transition_sections"]
    return ChoreographyPlan(
        sections=[
            plan_section({}, name="s1", bars=tuple(first), template_id="finite_snap_hold"),
            plan_section(intent, name="s2", bars=tuple(second)),
        ],
        overall_strategy="",
    )


def macro_plan(palette_id: str, heads_role: str = "SUPPORT") -> MacroPlan:
    """One macro section over bars 1-4 on `palette_id`, the heads in `heads_role`."""
    heads = PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")
    tree = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    roles = [FocalRole(target=heads, role=heads_role)]
    if heads_role != "LEAD":
        roles.append(FocalRole(target=tree, role="LEAD"))
    section = MacroSection(
        section=SongSectionRef(section_id="s1", name="s1", start_ms=0, end_ms=int(SECTION[1])),
        energy_target=EnergyTarget.HIGH,
        motion_density=MotionDensity.BUSY,
        choreography_style=ChoreographyStyle.HYBRID,
        palette_role=PaletteRoleRef(stop_id="p", override=None),
        theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
        motif_ids=[],
        focal_roles=roles,
        call_response_pairs=[],
        coordination_intent=CoordinationMode.UNIFIED,
        notes="Synthetic single-section macro plan.",
    )
    return MacroPlan(
        sections=[section],
        palette_arc=[
            PaletteStop(
                stop_id="p",
                palette=PaletteRef(palette_id=palette_id),
                applies_from_section_id="s1",
                transition=PaletteTransition.CUT,
            )
        ],
        motif_continuity=[],
        focal_arc=[
            FocalAssignment(section_id="s1", lead_target=heads if heads_role == "LEAD" else tree)
        ],
    )


class _Context:
    """The pipeline context surface the render stages read."""

    def __init__(self, **state: Any) -> None:
        self.state = state
        self.job_config = m.family_job(HEADS)
        self.output_dir = None

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def set_state(self, key: str, value: Any) -> None:
        self.state[key] = value

    def add_metric(self, key: str, value: Any) -> None:
        del key, value


def render(plan: ChoreographyPlan) -> Frames:
    rig = parity_rig()
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=GRID,
        fixture_group=rig,
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
    )
    pipeline.render()
    return Frames(pipeline.frames, rig)


def render_run(plan: ChoreographyPlan, macro: MacroPlan, directory: Path) -> Frames:
    """`twinklr run`'s render stage with the song's macro plan in the pipeline state, read
    back from the `.xsq` it delivers."""
    rig = parity_rig()
    output = directory / "song.xsq"
    stage = MovingHeadRenderingStage(xsq_output_path=output)
    context = _Context(beat_grid=GRID, live_fixture_group=rig, macro_plan=macro)
    result = asyncio.run(stage.execute({"moving_heads": plan}, context))
    assert result.success, result.error
    return Frames(_xsq_frames(output), rig)


def render_show(plan: ChoreographyPlan, macro: MacroPlan) -> Frames:
    """The show stage's moving-head render method (`twinklr show`'s moving-head half)."""
    rig = parity_rig()
    graph = ChoreographyGraph(
        graph_id="combined",
        groups=[
            ChoreoGroup(id=group_id, role=group_id, tags=[ChoreoTag.YARD])
            for group_id in ("MOVING_HEADS", "MEGA_TREE")
        ],
    )
    stage = CombinedShowRenderStage(
        fixture_group=rig,
        choreo_graph=graph,
        display_graph=graph,
        xlights_mapping=None,  # the display half is not run
        recipe_catalog=None,
        moving_head_target_ids={"MOVING_HEADS"},
    )
    _, output = stage._render_moving_heads(
        plan,
        macro,
        GRID,
        _Context(macro_plan=macro),
        markers=[],
        media_file="silence.wav",
        song="",
        artist="",
        timeline_tracks=[],
    )
    frames = [
        EncodedFixtureFrame(time_ms, run.frame.fixture_id, run.frame.channels)
        for run in output["moving_head_runs"]
        for time_ms in range(run.start_ms, run.end_ms, FRAME)
    ]
    return Frames(frames, rig)


# --- reading the frames -------------------------------------------------------------------


class Frames:
    """Every head's encoded frames, read through the rig's physical profile."""

    def __init__(self, frames: Sequence[EncodedFixtureFrame], rig: FixtureGroup) -> None:
        ordered = sorted(frames, key=lambda frame: frame.time_ms)
        self.by_head = {
            head: [dict(frame.channels) for frame in ordered if frame.fixture_id == head]
            for head in HEADS
        }
        profile = rig.fixtures[0].config.physical_profile
        assert isinstance(profile, FixtureCapabilities)
        self.profile = profile
        self.count = len(self.by_head[HEADS[0]])

    def dimmer(self, head: str) -> list[int]:
        offset = self.profile.axes["dimmer"].coarse_offset
        return [frame[offset] for frame in self.by_head[head]]

    def word(self, head: str, axis_name: str) -> list[int]:
        axis = self.profile.axes[axis_name]
        return [_word(frame, axis) for frame in self.by_head[head]]

    def state(self, head: str, wheel: str) -> list[str]:
        capability = self.profile.discrete[wheel]
        names = {state.value: name for name, state in capability.states.items()}
        return [names[frame[capability.offset]] for frame in self.by_head[head]]

    def dark(self, head: str) -> list[bool]:
        """Commanded dark: a zero dimmer the profile declares extinguishing, or an
        extinguishing shutter state."""
        visibility = self.profile.visibility
        zero = self.profile.axes["dimmer"].dmx_word(0)
        shutter = self.state(head, "shutter")
        return [
            (visibility.dimmer_zero_extinguishes and level == zero)
            or state in visibility.extinguishing_shutter_states
            for level, state in zip(self.dimmer(head), shutter, strict=True)
        ]

    def raw(self, head: str) -> list[dict[int, int]]:
        return self.by_head[head]


def _word(frame: dict[int, int], axis: AxisCapability) -> int:
    if axis.fine_offset is None:
        return frame[axis.coarse_offset]
    return frame[axis.coarse_offset] << 8 | frame[axis.fine_offset]


def _xsq_frames(path: Path) -> list[EncodedFixtureFrame]:
    """The constant DMX effects of a delivered `.xsq`, expanded to 20 ms frames."""
    root = ElementTree.parse(path).getroot()
    database = [effect.text or "" for effect in root.iterfind("EffectDB/Effect")]
    frames = []
    for element in root.iterfind("ElementEffects/Element"):
        if element.get("type") != "model":
            continue
        fixture_id = (element.get("name") or "").removeprefix("Dmx ")
        for effect in element.iter("Effect"):
            settings = database[int(effect.get("ref", "0"))]
            channels = tuple(
                (int(key.removeprefix("E_SLIDER_DMX")), int(value))
                for key, _, value in (part.partition("=") for part in settings.split(","))
                if key.startswith("E_SLIDER_DMX")
            )
            start, end = int(effect.get("startTime", "0")), int(effect.get("endTime", "0"))
            frames += [
                EncodedFixtureFrame(time_ms, fixture_id, channels)
                for time_ms in range(start, end, FRAME)
            ]
    return frames


def nearest_state(hex_color: str) -> str:
    """The `parity_rig` colour state nearest `hex_color`, by its `hex` tags."""
    profile = parity_rig().expand_fixtures()[0].config.physical_profile
    match = None if profile is None else nearest_color_state(profile, hex_color)
    assert match is not None
    return match.state


def stops(palette_id: str) -> list[str]:
    return [stop.hex[:7].upper() for stop in get_palette(palette_id).stops]


# --- frame-time helpers -------------------------------------------------------------------


def frames_in(start_ms: float, end_ms: float) -> range:
    """Frames starting in `[start_ms, end_ms)`."""
    return range(max(0, math.ceil(start_ms / FRAME)), math.ceil(end_ms / FRAME))


def beat_ms(bar: int, beat: int) -> float:
    return GRID.beat_boundaries[(bar - 1) * 4 + beat - 1]


def near_beat(time_ms: int) -> bool:
    """The frame at `time_ms` contains a beat or starts within one frame after one."""
    return any(-FRAME < time_ms - beat <= FRAME for beat in GRID.beat_boundaries)


def local_peaks(values: Sequence[int], frames: Sequence[int]) -> list[int]:
    """Start times of the local peaks among `frames` (consecutive lit frames): a rise
    followed, after any plateau, by a fall, all inside `frames`."""
    inside = set(frames)
    peaks = []
    for i in frames:
        if i - 1 not in inside or values[i] <= values[i - 1]:
            continue
        j = i
        while j + 1 in inside and values[j + 1] == values[i]:
            j += 1
        if j + 1 in inside and values[j + 1] < values[i]:
            peaks.append(i * FRAME)
    return peaks


def lit_frames(frames: Frames, head: str, window: range) -> list[int]:
    dark = frames.dark(head)
    return [i for i in window if not dark[i]]


def dark_runs(dark: Sequence[bool], window: range) -> int:
    """How many times the head goes dark (lit to dark) inside `window`."""
    return sum(1 for i in window if i and dark[i] and not dark[i - 1])


def first_dark(dark: Sequence[bool], from_ms: float) -> float:
    """The start of the first dark frame at or after the frame containing `from_ms`."""
    start = math.floor(from_ms / FRAME)
    return next((i * FRAME for i in range(start, len(dark)) if dark[i]), math.inf)


def assert_equal_before(frames: Frames, neutral: Frames, time_ms: float) -> None:
    """Every frame before the one containing `time_ms` equals the neutral render's."""
    before = range(math.floor(time_ms / FRAME))
    for head in HEADS:
        assert [frames.raw(head)[i] for i in before] == [neutral.raw(head)[i] for i in before]


def assert_wheel_turns_dark(frames: Frames, wheel: str) -> None:
    """The wheel changes state only on a dark frame and stays dark until it settles."""
    capability = frames.profile.discrete[wheel]
    for head in HEADS:
        states, dark = frames.state(head, wheel), frames.dark(head)
        for i in range(1, frames.count):
            if states[i] != states[i - 1]:
                settle = capability.states[states[i]].settle_ms or 0
                busy = range(i, min(frames.count, i + max(1, math.ceil(settle / FRAME))))
                assert all(dark[j] for j in busy), f"{head} {wheel} turns lit at {i * FRAME} ms"


def assert_dark_only_before_reveals(
    frames: Frames, neutral: Frames, wheel: str, reveals: Sequence[tuple[float, str]]
) -> None:
    """The dark frames differ from the neutral render's only in the window before each
    reveal `(time_ms, state)`: close latency + the state's settle + half a beat (the
    revised plan's bound on the dark lead), ending one frame after the reveal."""
    visibility = frames.profile.visibility
    states = frames.profile.discrete[wheel].states
    allowed: set[int] = set()
    for time_ms, state in reveals:
        lead = (visibility.close_latency_ms or 0) + (states[state].settle_ms or 0) + BEAT / 2
        allowed.update(frames_in(time_ms - lead, time_ms + FRAME))
    for head in HEADS:
        changed = {
            i
            for i, (a, b) in enumerate(zip(frames.dark(head), neutral.dark(head), strict=True))
            if a != b
        }
        assert changed <= allowed, f"{head} darkness changes at {sorted(changed - allowed)[:5]}"


# --- the anchor and the guard -------------------------------------------------------------


def test_neutral_intent_renders_the_pinned_bytes() -> None:
    """All intent neutral: the bytes `test_mh_pins.py` pins for this template and grid."""
    plan = ChoreographyPlan(sections=[plan_section({}, bars=(1, 8))], overall_strategy="")
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=GRID,
        fixture_group=m.family_rig(HEADS),
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
    )
    pipeline.render()

    assert _frames_sha256(pipeline.frames) == PINS[f"steady/{TEMPLATE}/base"][1]


def test_every_regression_row_is_tested_once_and_pending_rows_name_their_task() -> None:
    assert set(PREFIXES) == _USED
    for row_id, row in ROWS.items():
        assert (row["parity_target"] is None) == (row["status"] != "regression"), row_id
        if row["status"] == "regression":
            assert len([p for p in PREFIXES if row_id.startswith(p)]) == 1, row_id
    for row_id, (task, _) in PENDING.items():
        assert ROWS[row_id]["status"] == "regression"
        assert ROWS[row_id]["task"] == task


# --- rows ---------------------------------------------------------------------------------


@pytest.mark.parametrize("row_id", _rows("intensity"))
def test_intensity_raises_the_floor_and_pulses_on_the_beat(row_id: str) -> None:
    row = ROWS[row_id]
    level = row["intent"]["intensity"]
    template_id = PULSE_TEMPLATE if row_id.endswith("_on_authored_pulse") else HOLD_TEMPLATE
    frames = render(single_plan(row["intent"], template_id))
    neutral = render(single_plan({}, template_id))
    section = frames_in(*SECTION)

    for head in HEADS:
        dark, neutral_dark = frames.dark(head), neutral.dark(head)
        assert [dark[i] for i in section] == [neutral_dark[i] for i in section]
        lit = lit_frames(neutral, head, section)
        dimmer, authored = frames.dimmer(head), neutral.dimmer(head)
        assert all(dimmer[i] >= authored[i] for i in lit), f"{head} dims below the authored look"
        assert min(dimmer[i] for i in lit) > min(authored[i] for i in lit), f"{head} floor"
        assert len({dimmer[i] for i in lit}) >= 2, f"{head} does not pulse"
        # Peaks of the level above the authored one, so an accent that scales with the
        # template's own alternating level still shows as a peak on its beat.
        peaks = local_peaks(
            [value - base for value, base in zip(dimmer, authored, strict=True)], lit
        )
        assert len(peaks) >= 2, f"{head} peaks {peaks}"
        assert all(near_beat(peak) for peak in peaks), f"{head} peaks off the beat: {peaks}"
        if level == "INTENSE":
            # A peak on every beat the head is lit across, whatever level the template
            # itself is at on that beat.
            lit_set = set(lit)
            beats = [
                beat
                for beat in GRID.beat_boundaries
                if set(frames_in(beat - 2 * FRAME, beat + 3 * FRAME)) <= lit_set
            ]
            missing = [b for b in beats if not any(-FRAME < p - b <= FRAME for p in peaks)]
            assert beats and not missing, f"{head} no peak on beats {missing}"
            continue
        if template_id == PULSE_TEMPLATE:
            continue  # DRAMATIC on an authored pulse: the template sets the period
        gaps = {b - a for a, b in pairwise(peaks)}
        whole = {round(gap / BEAT) for gap in gaps}
        assert all(abs(gap - round(gap / BEAT) * BEAT) <= FRAME for gap in gaps), gaps
        assert len(whole) == 1 and min(whole) >= 2, gaps  # longer than INTENSE's beat


@pytest.mark.parametrize("row_id", _rows("color"))
def test_section_colour_holds_on_every_lit_frame(row_id: str, tmp_path: Path) -> None:
    """An explicit colour shows its own state; a palette role the rig state nearest its
    macro-palette stop (PRIMARY the first, ACCENT the second; WARM and COOL two different
    non-default states)."""
    intent = ROWS[row_id]["intent"]

    def run(color: dict[str, str]) -> Frames:
        if "macro_palette" not in intent:
            return render(single_plan({"color": color}))
        macro = macro_plan(intent["macro_palette"])
        return render_run(single_plan({"color": color}), macro, tmp_path)

    def shown(result: Frames) -> set[str]:
        return {
            result.state(head, "color")[i]
            for head in HEADS
            for i in lit_frames(result, head, frames_in(*SECTION))
        }

    frames, neutral = run(intent["color"]), render(single_plan({}))
    default = frames.profile.discrete["color"].default_state
    states = shown(frames)
    role = intent["color"].get("palette_role")
    if role is None:
        assert states == {intent["color"]["explicit"]}, states
    elif role in ("PRIMARY", "ACCENT"):
        first, second = (nearest_state(stop) for stop in stops(intent["macro_palette"])[:2])
        assert first != second
        assert states == {first if role == "PRIMARY" else second}, states
    else:
        other = shown(run({"palette_role": "COOL" if role == "WARM" else "WARM"}))
        assert len(states) == 1 and default not in states and states != other, (states, other)
    reveal = next(i for i in frames_in(*SECTION) if not neutral.dark("MH1")[i]) * FRAME
    (state,) = states
    assert_dark_only_before_reveals(frames, neutral, "color", [(reveal, state)])
    assert_wheel_turns_dark(frames, "color")


@pytest.mark.parametrize("row_id", _rows("shutter_closed"))
def test_shutter_closed_then_open_darkens_between_the_events(row_id: str) -> None:
    row = ROWS[row_id]
    closed, opened = (beat_ms(e["bar"], e["beat"]) for e in row["intent"]["shutter_events"])
    frames, neutral = render(single_plan(row["intent"])), render(single_plan({}))

    assert_equal_before(frames, neutral, closed)
    for head in HEADS:
        dark, neutral_dark = frames.dark(head), neutral.dark(head)
        assert first_dark(dark, closed) <= closed + FRAME, f"{head} darkens late"
        assert all(dark[i] for i in frames_in(closed + FRAME, opened - FRAME))
        assert all(dark[i] == neutral_dark[i] for i in frames_in(opened + FRAME, SECTION[1]))


def _strobe_flashes() -> dict[str, int]:
    """How often MH1 goes dark in the bar after the event, per strobe speed."""
    counts = {}
    for speed in ("slow", "medium", "fast"):
        intent = ROWS[f"shutter_strobe_{speed}"]["intent"]
        event = intent["shutter_events"][0]
        start = beat_ms(event["bar"], event["beat"])
        frames = render(single_plan(intent))
        counts[speed] = dark_runs(frames.dark("MH1"), frames_in(start - FRAME, start + 2_000))
    return counts


@pytest.mark.parametrize("row_id", _rows("shutter_strobe"))
def test_shutter_strobe_flashes_from_the_event(row_id: str) -> None:
    row = ROWS[row_id]
    event = row["intent"]["shutter_events"][0]
    start = beat_ms(event["bar"], event["beat"])
    frames, neutral = render(single_plan(row["intent"])), render(single_plan({}))

    assert_equal_before(frames, neutral, start)
    for head in HEADS:
        dark = frames.dark(head)
        assert first_dark(dark, start) <= start + FRAME, f"{head} strobe starts late"
        bar_after = frames_in(start - FRAME, start + 2_000)
        assert dark_runs(dark, bar_after) >= 2, f"{head} does not strobe"
        assert not all(dark[i] for i in bar_after)
        assert dark_runs(dark, frames_in(start + 2_000, SECTION[1] - FRAME)) >= 1, "strobe stops"
    if row_id == "shutter_strobe_fast":
        counts = _strobe_flashes()
        assert counts["fast"] > counts["medium"] > counts["slow"], counts


@pytest.mark.parametrize("row_id", _rows("shutter_pulse"))
def test_shutter_pulse_reveals_on_each_beat(row_id: str) -> None:
    row = ROWS[row_id]
    event = row["intent"]["shutter_events"][0]
    start = beat_ms(event["bar"], event["beat"])
    frames, neutral = render(single_plan(row["intent"])), render(single_plan({}))
    window = frames_in(start - FRAME, SECTION[1] - FRAME)
    beats = [b for b in GRID.beat_boundaries if start <= b < SECTION[1] - FRAME]

    assert_equal_before(frames, neutral, start)
    for head in HEADS:
        dark = frames.dark(head)
        reveals = [i * FRAME for i in window if i and dark[i - 1] and not dark[i]]
        # The head is already lit when the event's beat arrives, so the pulse on that first
        # beat can be a lit frame followed by a dark gap rather than a reveal: one fewer
        # reveal than beats is allowed.
        assert len(reveals) >= len(beats) - 1, f"{head} reveals {reveals}"
        assert all(near_beat(reveal) for reveal in reveals), f"{head} off the beat: {reveals}"


def _assert_gobo_events(
    frames: Frames, neutral: Frames, events: Sequence[tuple[float, str]]
) -> None:
    """Each `(time_ms, state)` is revealed within one frame of its time and held on every lit
    frame until the next; lit frames before the first show the neutral gobo, and darkness
    differs from the neutral render only before the reveals."""
    ends = [time_ms for time_ms, _ in events[1:]] + [SECTION[1]]
    neutral_state = neutral.state("MH1", "gobo")[0]
    for head in HEADS:
        states, dark = frames.state(head, "gobo"), frames.dark(head)
        for (time_ms, state), end in zip(events, ends, strict=True):
            assert any(
                not dark[i] and states[i] == state
                for i in frames_in(time_ms - FRAME, time_ms + 2 * FRAME)
            ), f"{head} not revealed with {state} at {time_ms} ms"
            held = lit_frames(frames, head, frames_in(time_ms + FRAME, end))
            assert all(states[i] == state for i in held), f"{head} {state} not held"
        before = lit_frames(frames, head, frames_in(0, events[0][0] - FRAME))
        assert all(states[i] == neutral_state for i in before)
    assert_dark_only_before_reveals(frames, neutral, "gobo", events)
    assert_wheel_turns_dark(frames, "gobo")


@pytest.mark.parametrize("row_id", _rows("gobo"))
def test_gobo_events_reveal_on_their_beats(row_id: str) -> None:
    intent = ROWS[row_id]["intent"]
    events = [(beat_ms(e["bar"], e["beat"]), e["pattern"]) for e in intent["gobo_events"]]

    _assert_gobo_events(render(single_plan(intent)), render(single_plan({})), events)


@pytest.mark.parametrize("row_id", _rows("cue_bound"))
def test_cue_bound_event_lands_on_the_snapped_beat(row_id: str) -> None:
    row = ROWS[row_id]
    snapped = row["facts"]["cue_snapped_beat_ms"]
    frames, neutral = render(bound_plan(row["intent"])), render(single_plan({}))

    if "gobo_events" in row["intent"]:
        pattern = row["intent"]["gobo_events"][0]["pattern"]
        _assert_gobo_events(frames, neutral, [(snapped, pattern)])
        return
    assert_equal_before(frames, neutral, snapped)
    for head in HEADS:
        dark = frames.dark(head)
        assert first_dark(dark, snapped) <= snapped + FRAME, f"{head} darkens late"
        assert all(dark[i] for i in frames_in(snapped + FRAME, SECTION[1] - FRAME))


@pytest.mark.parametrize("row_id", _rows("transition"))
def test_transition_in_changes_smoothly_across_the_boundary(row_id: str) -> None:
    row = ROWS[row_id]
    mode = row["intent"]["transition_in"]["mode"]
    boundary = GRID.bar_boundaries[4]
    ((before, after),) = row["facts"]["set"]["transition_effect_from_boundary_ms"]
    window = frames_in(boundary + before, boundary + after)
    frames, neutral = render(transition_plan(row["intent"])), render(transition_plan({}))

    for head in HEADS:
        dark, dimmer = frames.dark(head), frames.dimmer(head)
        if mode == "fade_via_black":
            top = max(dimmer[i] for i in window)
            down = [dimmer[i] for i in frames_in(boundary + before, boundary)]
            up = [dimmer[i] for i in frames_in(boundary, boundary + after)]
            assert down == sorted(down, reverse=True) and up == sorted(up)
            assert len({v for v in down if 0 < v < top}) >= 2, f"{head} does not fade out: {down}"
            assert len({v for v in up if 0 < v < top}) >= 2, f"{head} does not fade in: {up}"
            assert any(dark[i] for i in frames_in(boundary - FRAME, boundary + FRAME))
            continue
        assert not any(dark[i] for i in window), f"{head} goes dark at the boundary"
        for name in ("pan", "tilt"):
            axis = frames.profile.axes[name]
            low, high = axis.word_range
            per_word = (axis.physical_max - axis.physical_min) / (high - low)
            step = (axis.travel_speed_per_s or 0) * FRAME / 1000 + per_word
            words, incoming = frames.word(head, name), neutral.word(head, name)
            assert all(abs(words[i] - words[i - 1]) * per_word <= step for i in window), name
            settled = frames_in(boundary + after, GRID.bar_boundaries[8] - FRAME)
            assert all(words[i] == incoming[i] for i in settled), f"{head} {name} off the aim"
    if mode in ("morph", "sweep"):
        other = ROWS["transition_in_sweep" if mode == "morph" else "transition_in_morph"]
        others = render(transition_plan(other["intent"]))
        assert any(frames.raw("MH1")[i] != others.raw("MH1")[i] for i in window), "MORPH = SWEEP"


@pytest.mark.parametrize("row_id", _rows("show_focal"))
def test_show_focal_lead_renders_hotter(row_id: str) -> None:
    """The show render applies the macro focal role to the section's intensity: with one
    plan, LEAD is no dimmer anywhere and hotter somewhere than SUPPORT, REST no hotter than
    SUPPORT, and nothing but the dimmer level differs (same dark frames, same other
    channels)."""
    palette = ROWS[row_id]["intent"]["show"]["palette_id"]
    plan = single_plan({}, HOLD_TEMPLATE)
    lead, support, rest = (
        render_show(plan, macro_plan(palette, role)) for role in ("LEAD", "SUPPORT", "REST")
    )

    for head in HEADS:
        lit = lit_frames(support, head, frames_in(*SECTION))
        hot, base, calm = lead.dimmer(head), support.dimmer(head), rest.dimmer(head)
        assert lead.dark(head) == support.dark(head) == rest.dark(head)
        dimmer_offset = support.profile.axes["dimmer"].coarse_offset
        for other in (lead, rest):
            assert [
                {k: v for k, v in frame.items() if k != dimmer_offset} for frame in other.raw(head)
            ] == [
                {k: v for k, v in frame.items() if k != dimmer_offset}
                for frame in support.raw(head)
            ], f"{head}: the focal role changed more than the dimmer level"
        assert all(hot[i] >= base[i] for i in lit)
        assert any(hot[i] > base[i] for i in lit), f"{head}: LEAD no hotter than SUPPORT"
        assert all(calm[i] <= base[i] for i in lit), f"{head}: REST hotter than as authored"


@pytest.mark.parametrize("row_id", _rows("show_palette"))
def test_show_palette_colours_the_heads(row_id: str) -> None:
    intent = ROWS[row_id]["intent"]
    palette = intent["show"]["palette_id"]
    expected = nearest_state(stops(palette)[0])
    frames = render_show(single_plan({"color": intent["color"]}), macro_plan(palette))

    assert expected != "red"
    for head in HEADS:
        states = frames.state(head, "color")
        lit = lit_frames(frames, head, frames_in(*SECTION))
        assert lit
        assert {states[i] for i in lit} == {expected}
