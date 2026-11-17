"""A section's colour and gobo rendered (song-intent rendering W4): the resolved wheel
state plays on every lit frame, the wheel turns only in the dark, a colour change at a
boundary the heads play lit through gets a dark dip of at most half a beat before the
section (or the head keeps the previous colour), and as-authored intent renders the bytes
it always did."""

from __future__ import annotations

from collections.abc import Iterator
import math
from typing import Any

import pytest

from tests.support import moving_heads as m
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanColor
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline, admit_templates
from twinklr.core.sequencer.moving_heads.song_intent import SectionPalette, darkness_ms

HEADS = ("MH1", "MH2", "MH3", "MH4")
GRID = m.bars_grid(*([500.0] * 8))
BOUNDARY = GRID.bar_boundaries[4]
"""Where the second section (bars 5-8) starts."""
FRAME = EFFECT_GRID_MS


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with m.family_catalog():
        yield


def rig(
    *,
    close_latency_ms: int = 40,
    blue_settle_ms: int = 140,
    untagged: tuple[str, ...] = (),
    settle_ms: int | None = None,
    shutter_only: bool = False,
    green_settle_ms: int | None = None,
) -> FixtureGroup:
    """`tagged_family_rig(HEADS)` with a close latency, so darkness takes effect after a
    delay, a chosen settle for its blue state (or `settle_ms` for every wheel state), the
    `untagged` heads' tags removed and, with `shutter_only`, darkness only through the
    closed shutter."""
    payload = m.tagged_family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        profile["visibility"]["close_latency_ms"] = close_latency_ms
        profile["discrete"]["color"]["states"]["blue"]["settle_ms"] = blue_settle_ms
        if settle_ms is not None:
            for channel in ("color", "gobo"):
                for state in profile["discrete"][channel]["states"].values():
                    state["settle_ms"] = settle_ms
        if shutter_only:
            profile["visibility"]["dimmer_zero_extinguishes"] = False
        if green_settle_ms is not None:
            profile["discrete"]["color"]["states"]["green"] = {
                "range_min": 30,
                "range_max": 39,
                "value": 34,
                "settle_ms": green_settle_ms,
                "hex": "green",
            }
        if fixture["fixture_id"] in untagged:
            for channel in ("color", "gobo"):
                for state in profile["discrete"][channel]["states"].values():
                    state.pop("hex", None)
                    state.pop("pattern", None)
    return FixtureGroup.model_validate(payload)


def render(
    *sections: dict[str, Any],
    fixture_group: FixtureGroup | None = None,
    template_id: str = "mirror_wings",
    palettes: dict[str, SectionPalette] | None = None,
    grid: Any = GRID,
    **pipeline_fields: Any,
) -> RenderingPipeline:
    """Two sections, bars 1-4 and 5-8, each with the song intent given."""
    plan = ChoreographyPlan(
        sections=[
            m.plan_section(name, first, first + 3, template_id, **intent)
            for (name, first), intent in zip((("s1", 1), ("s2", 5)), sections, strict=True)
        ],
        overall_strategy="",
    )
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=grid,
        fixture_group=fixture_group or rig(),
        job_config=pipeline_fields.pop("job_config", m.family_job(HEADS)),
        media_file="silence.wav",
        palettes=palettes,
        **pipeline_fields,
    )
    pipeline.render()
    return pipeline


class Heads:
    """Each head's frames read through its profile: wheel states and commanded darkness."""

    def __init__(self, pipeline: RenderingPipeline) -> None:
        self.profiles: dict[str, FixtureCapabilities] = {}
        for fixture in pipeline.fixture_group.expand_fixtures():
            assert fixture.config.physical_profile is not None
            self.profiles[fixture.fixture_id] = fixture.config.physical_profile
        self.frames = {
            head: [dict(f.channels) for f in pipeline.frames if f.fixture_id == head]
            for head in HEADS
        }

    def state(self, head: str, wheel: str) -> list[str]:
        capability = self.profiles[head].discrete[wheel]
        names = {state.value: name for name, state in capability.states.items()}
        return [names[frame[capability.offset]] for frame in self.frames[head]]

    def dark(self, head: str) -> list[bool]:
        """Commanded dark: a zero dimmer the profile declares extinguishing, or an
        extinguishing shutter state."""
        profile = self.profiles[head]
        dimmer = profile.axes["dimmer"].coarse_offset
        shutter = self.state(head, "shutter")
        visibility = profile.visibility
        return [
            (visibility.dimmer_zero_extinguishes and frame[dimmer] == 0)
            or state in visibility.extinguishing_shutter_states
            for frame, state in zip(self.frames[head], shutter, strict=True)
        ]

    def shown(self, head: str, wheel: str, start_ms: float, end_ms: float) -> set[str]:
        """The states `wheel` shows on the head's lit frames in `[start_ms, end_ms)`."""
        states = self.state(head, wheel)
        return {states[i] for i in self.lit(head, start_ms, end_ms)}

    def lit(self, head: str, start_ms: float, end_ms: float) -> list[int]:
        dark = self.dark(head)
        return [i for i in range(math.ceil(start_ms / FRAME), int(end_ms // FRAME)) if not dark[i]]


def assert_wheels_turn_dark(heads: Heads, wheel: str) -> None:
    """Every state change of `wheel` lies inside a dark window covering the time darkness
    takes to set in before it (close latency, plus the closed shutter's settle where only
    the shutter extinguishes) and the new state's settle after it."""
    for head in HEADS:
        profile = heads.profiles[head]
        latency = darkness_ms(profile) or 0
        states, dark = heads.state(head, wheel), heads.dark(head)
        for i in range(1, len(states)):
            if states[i] == states[i - 1]:
                continue
            settle = profile.discrete[wheel].states[states[i]].settle_ms or 0
            window = range(i - math.ceil(latency / FRAME), i + math.ceil(settle / FRAME))
            assert all(dark[j] for j in window), f"{head} {wheel} turns lit at {i * FRAME} ms"


def changed_darkness(a: Heads, b: Heads, head: str) -> list[int]:
    return [
        i * FRAME for i, (x, y) in enumerate(zip(a.dark(head), b.dark(head), strict=True)) if x != y
    ]


def test_a_colour_change_at_a_lit_boundary_dips_dark_just_before_the_section() -> None:
    neutral = Heads(render({}, {}))
    pipeline = render({"color": PlanColor.RED}, {"color": PlanColor.BLUE})
    heads = Heads(pipeline)

    assert pipeline.render_record is not None
    looks = {look["section_id"]: look for look in pipeline.render_record["section_looks"]}
    boundaries = looks["s2"]["boundaries"]
    assert [b["fixture_id"] for b in boundaries] == list(HEADS)
    for head, boundary in zip(HEADS, boundaries, strict=True):
        assert heads.shown(head, "color", 0, BOUNDARY) == {"red"}
        assert heads.shown(head, "color", BOUNDARY, GRID.duration_ms) == {"blue"}
        lead = boundary["dark_dip"]["lead_ms"]
        reveal = boundary["boundary_ms"]
        # Darkness: the neutral render's, plus at most half a beat just before the reveal.
        assert 0 < lead <= 250
        assert changed_darkness(heads, neutral, head) == list(range(reveal - lead, reveal, FRAME))
        assert boundary["wheels"] == {"color": {"from": "red", "to": "blue"}}
    assert_wheels_turn_dark(heads, "color")


def test_no_dip_where_the_colour_does_not_change() -> None:
    neutral = Heads(render({}, {}))
    pipeline = render({"color": PlanColor.RED}, {"color": PlanColor.RED})
    heads = Heads(pipeline)

    assert pipeline.render_record is not None
    assert all("boundaries" not in look for look in pipeline.render_record["section_looks"])
    for head in HEADS:
        assert changed_darkness(heads, neutral, head) == []
        assert heads.shown(head, "color", 0, GRID.duration_ms) == {"red"}
    assert_wheels_turn_dark(heads, "color")


def test_a_head_keeps_the_previous_colour_when_the_dip_does_not_fit_half_a_beat() -> None:
    """Blue settles in 300 ms: with the close latency that is more than half the 500 ms
    beat, so the heads play blue's section in red, and the trace says why."""
    slow = rig(blue_settle_ms=300)
    neutral = Heads(render({}, {}, fixture_group=slow))
    pipeline = render({"color": PlanColor.RED}, {"color": PlanColor.BLUE}, fixture_group=slow)
    heads = Heads(pipeline)

    assert pipeline.render_record is not None
    _, s2 = pipeline.render_record["section_looks"]
    for boundary in s2["boundaries"]:
        assert "dark_dip" not in boundary
        assert "do not fit half the beat" in boundary["kept_previous"]["reason"]
    for head in HEADS:
        assert changed_darkness(heads, neutral, head) == []
        assert heads.shown(head, "color", 0, GRID.duration_ms) == {"red"}


def test_as_authored_intent_on_a_tagged_rig_renders_the_untagged_bytes() -> None:
    tagged = render({}, {}, fixture_group=m.tagged_family_rig(HEADS))
    untagged = render({}, {}, fixture_group=m.family_rig(HEADS))

    assert tagged.frames == untagged.frames
    assert tagged.render_record is not None
    assert "section_looks" not in tagged.render_record
    assert "palettes" not in tagged.render_record


def test_a_section_gobo_plays_its_pattern_and_turns_in_the_dark() -> None:
    pipeline = render({"gobo": GoboPattern.STARS}, {})
    heads = Heads(pipeline)

    for head in HEADS:
        assert heads.shown(head, "gobo", 0, BOUNDARY) == {"star"}
        assert heads.shown(head, "gobo", BOUNDARY, GRID.duration_ms) == {"open"}
    assert_wheels_turn_dark(heads, "gobo")


def test_a_head_that_cannot_show_the_colour_keeps_its_authored_colour() -> None:
    pipeline = render({"color": PlanColor.BLUE}, {}, fixture_group=rig(untagged=("MH3",)))
    heads = Heads(pipeline)

    assert heads.shown("MH1", "color", 0, BOUNDARY) == {"blue"}
    assert heads.shown("MH3", "color", 0, GRID.duration_ms) == {"white"}
    assert pipeline.render_record is not None
    first, second = pipeline.render_record["section_looks"]
    assert first["color"]["kept_authored"] == ["MH3"]
    # Back to the authored white in the next section: a dip on the heads that played blue.
    assert [b["fixture_id"] for b in second["boundaries"]] == ["MH1", "MH2", "MH4"]


def test_an_overlay_keeps_its_state_and_returns_to_the_section_colour() -> None:
    """`masked_wheel_flick` flicks to the rig's `flick` preset (red on MH1 and MH3, blue
    on MH2 and MH4) and back: with a white section it returns to white, with a blue one
    to blue; a head whose flick is the section's colour plays it throughout, unmasked."""
    pipeline = render(
        {"color": PlanColor.BLUE},
        {"color": PlanColor.BLUE},
        template_id="masked_wheel_flick",
        fixture_group=rig(close_latency_ms=40),
    )
    heads = Heads(pipeline)

    assert heads.shown("MH1", "color", 0, GRID.duration_ms) == {"red", "blue"}
    assert heads.shown("MH2", "color", 0, GRID.duration_ms) == {"blue"}
    assert "white" not in heads.shown("MH1", "color", 0, GRID.duration_ms)
    assert_wheels_turn_dark(heads, "color")


def test_palettes_are_render_identity_only_where_a_section_reads_one() -> None:
    first = {"s1": SectionPalette(palette_id="a", stops=("#FF0000", "#0000FF"))}
    second = {"s1": SectionPalette(palette_id="b", stops=("#0000FF", "#FF0000"))}

    role_a = render({"color": PlanColor.PALETTE_PRIMARY}, {}, palettes=first)
    role_b = render({"color": PlanColor.PALETTE_PRIMARY}, {}, palettes=second)
    named_a = render({"color": PlanColor.RED}, {}, palettes=first)
    named = render({"color": PlanColor.RED}, {})

    assert role_a.fingerprint() != role_b.fingerprint()
    assert role_a.frames != role_b.frames  # red, then blue
    assert role_a.render_record is not None
    assert role_a.render_record["palettes"] == {"s1": first["s1"].model_dump(mode="json")}
    assert named_a.fingerprint() == named.fingerprint()
    assert named_a.frames == role_a.frames


def test_the_gate_bounds_entry_dips_with_every_offered_wheel_state() -> None:
    """A section's colour can turn the wheel at any entry, so a tagged rig's dips allow
    for its slowest offered state's settle (here the star gobo's 160 ms) where an untagged
    rig's need only a frame; admission is the same."""
    job = m.family_job(HEADS)

    def gate(fixture_group: FixtureGroup) -> Any:
        return admit_templates(
            ["finite_snap_hold"],
            beat_grid=GRID,
            fixture_group=fixture_group,
            initial_states=job.moving_heads.initial_states,
            failure_mode="error",
        )

    tagged, untagged = gate(m.tagged_family_rig(HEADS)), gate(m.family_rig(HEADS))

    assert tagged.admitted == untagged.admitted
    assert (
        tagged.entry_dips["finite_snap_hold"]["bound_ms"]
        - untagged.entry_dips["finite_snap_hold"]["bound_ms"]
        == 160 - FRAME
    )
    assert tagged.offer.offers_colors() and not untagged.offer.offers_colors()


FAST = m.bars_grid(*([60_000 / 170] * 8))
"""170 BPM: half a beat (176 ms) is shorter than the owner-like 180 ms wheel change."""


def owner_like(**fields: Any) -> FixtureGroup:
    """Close latency 20 ms and every wheel state settling in 150 ms: a 180 ms change."""
    return rig(close_latency_ms=20, settle_ms=150, **fields)


def test_at_170_bpm_a_change_into_an_overlay_family_turns_in_its_mask() -> None:
    """The dip does not fit half a beat; `masked_wheel_flick`'s first mask is the first
    dark window long enough, so every head plays red until it and blue from it. Heads
    whose flick colour is the new colour turn there too (held at the old colour, their
    overlay opens a mask)."""
    neutral = Heads(
        render({}, {}, template_id="masked_wheel_flick", grid=FAST, fixture_group=owner_like())
    )
    pipeline = render(
        {"color": PlanColor.RED},
        {"color": PlanColor.BLUE},
        template_id="masked_wheel_flick",
        grid=FAST,
        fixture_group=owner_like(),
    )
    heads = Heads(pipeline)

    assert pipeline.render_record is not None
    s2 = pipeline.render_record["section_looks"][1]
    turns = {b["fixture_id"]: b["deferred"]["turn_ms"] for b in s2["boundaries"]}
    assert set(turns) == set(HEADS) and len(set(turns.values())) == 1
    (turn,) = set(turns.values())
    boundary = FAST.bar_boundaries[4]
    assert boundary < turn < boundary + (FAST.duration_ms - boundary) / 2
    assert s2["color"]["heads"] == {}
    assert set(s2["color"]["deferred"]) == set(HEADS)
    for head in HEADS:
        assert heads.shown(head, "color", boundary, turn) == {"red"}
        added = [
            i
            for i, (x, y) in enumerate(zip(heads.dark(head), neutral.dark(head), strict=True))
            if x and not y
        ]
        assert added == []  # the turn uses a mask the template is dark in anyway
    assert_wheels_turn_dark(heads, "color")
    (message,) = [
        d["message"] for d in pipeline.render_record["diagnostics"] if "turns late" in d["message"]
    ]
    assert "turns late on 4 head(s)" in message


def test_at_170_bpm_a_family_without_a_dark_moment_keeps_the_previous_colour() -> None:
    neutral = Heads(render({}, {}, grid=FAST, fixture_group=owner_like()))
    pipeline = render(
        {"color": PlanColor.RED}, {"color": PlanColor.BLUE}, grid=FAST, fixture_group=owner_like()
    )
    heads = Heads(pipeline)

    assert pipeline.render_record is not None
    s2 = pipeline.render_record["section_looks"][1]
    assert s2["color"]["kept_previous"] == dict.fromkeys(HEADS, "red")
    assert s2["color"]["heads"] == {}
    for boundary in s2["boundaries"]:
        assert "no dark window long enough" in boundary["kept_previous"]["reason"]
    for head in HEADS:
        assert heads.shown(head, "color", 0, FAST.duration_ms) == {"red"}
        assert changed_darkness(heads, neutral, head) == []
    assert any(
        "keep the previous section's colour" in d["message"]
        for d in pipeline.render_record["diagnostics"]
    )


def test_on_a_shutter_darkened_rig_the_dip_closes_the_shutter_long_enough() -> None:
    """Darkness only through the closed shutter: the dip covers its close latency and
    settle before the turn, and the wheel settles before the reveal."""
    shutter_rig = rig(shutter_only=True)
    neutral = Heads(render({}, {}, fixture_group=shutter_rig))
    pipeline = render(
        {"color": PlanColor.RED}, {"color": PlanColor.BLUE}, fixture_group=shutter_rig
    )
    heads = Heads(pipeline)

    assert pipeline.render_record is not None
    for boundary in pipeline.render_record["section_looks"][1]["boundaries"]:
        dip = boundary["dark_dip"]
        head = boundary["fixture_id"]
        assert dip["lead_ms"] <= 250
        changed = changed_darkness(heads, neutral, head)
        assert changed and min(changed) >= dip["from_ms"] and max(changed) < boundary["boundary_ms"]
    assert_wheels_turn_dark(heads, "color")


def test_a_dip_adds_no_darkness_where_the_head_is_already_dark_before_the_boundary() -> None:
    """A dark span (a show's rest) over the last beat before the boundary already holds
    the head dark for the whole lead: the wheel turns in it and nothing is added."""
    boundary = GRID.bar_boundaries[4]
    span = ((int(boundary) - 500, int(boundary)),)
    neutral = Heads(render({}, {}, dark_spans=span))
    pipeline = render({"color": PlanColor.RED}, {"color": PlanColor.BLUE}, dark_spans=span)
    heads = Heads(pipeline)

    assert pipeline.render_record is not None
    for record in pipeline.render_record["section_looks"][1]["boundaries"]:
        assert record["dark_dip"]["added_ms"] == 0
    for head in HEADS:
        assert changed_darkness(heads, neutral, head) == []
    assert_wheels_turn_dark(heads, "color")


def test_a_slow_state_an_overlay_mask_cannot_turn_to_is_left_out_and_never_refuses() -> None:
    """A green settling in 470 ms does not fit `masked_wheel_flick`'s one-beat masks at
    120 BPM (the turn back from the flick). The gate leaves green out of that template's
    offer (and keeps it for others); a render without the gate's result plays the
    authored colour on those heads, recorded, and does not refuse even under
    `on_unplayable: error`."""
    slow = rig(green_settle_ms=470)
    job = m.family_job(HEADS)
    admission = admit_templates(
        ["masked_wheel_flick", "mirror_wings"],
        beat_grid=GRID,
        fixture_group=slow,
        initial_states=job.moving_heads.initial_states,
        failure_mode="error",
    )
    strict = m.family_job(HEADS, on_unplayable="error")

    pipeline = render(
        {"color": PlanColor.GREEN},
        {},
        template_id="masked_wheel_flick",
        fixture_group=slow,
        job_config=strict,
    )
    gated = render(
        {"color": PlanColor.GREEN},
        {},
        template_id="masked_wheel_flick",
        fixture_group=slow,
        job_config=strict,
        admission=admission,
    )

    flick = admission.offer.templates["masked_wheel_flick"]
    assert flick.excluded == {head: {"color": ("green",)} for head in HEADS}
    assert admission.offer.templates["mirror_wings"].excluded == {}
    assert admission.offer.for_templates({"masked_wheel_flick"}).color("green").status == (
        "unavailable"
    )
    assert admission.offer.for_templates({"mirror_wings"}).color("green").status == "faithful"
    assert pipeline.render_record is not None
    s1 = pipeline.render_record["section_looks"][0]["color"]
    assert set(s1["kept_authored_unplayable"]) == set(HEADS)
    assert s1["heads"] == {}
    assert any(
        "keep the template's colour" in d["message"] for d in pipeline.render_record["diagnostics"]
    )
    assert gated.render_record is not None
    gated_look = gated.render_record["section_looks"][0]["color"]
    assert gated_look["heads"] == {} and gated_look["kept_authored"] == list(HEADS)


def test_a_wheel_with_a_state_of_unknown_settle_costs_no_admission() -> None:
    """Tags on a wheel whose untagged default state has no settle: nothing is offered for
    that wheel, so the gate admits exactly what it admits untagged."""

    def partial(tagged: bool) -> FixtureGroup:
        payload = m.family_rig(HEADS).model_dump(mode="json")
        for fixture in payload["fixtures"]:
            wheel = fixture["config"]["physical_profile"]["discrete"]["color"]
            if tagged:
                wheel["states"]["red"]["hex"] = "red"
                wheel["states"]["blue"]["hex"] = "blue"
            del wheel["states"]["white"]["settle_ms"]
            wheel.pop("settle_ms", None)
        return FixtureGroup.model_validate(payload)

    job = m.family_job(HEADS)

    def gate(fixture_group: FixtureGroup) -> Any:
        return admit_templates(
            list(m.CATALOG_IDS),
            beat_grid=GRID,
            fixture_group=fixture_group,
            initial_states=job.moving_heads.initial_states,
            failure_mode="error",
            excludable=list(m.CATALOG_IDS),
        )

    untagged, tagged = gate(partial(tagged=False)), gate(partial(tagged=True))

    assert tagged.admitted == untagged.admitted
    assert tagged.entry_dips == untagged.entry_dips
    assert not tagged.offer.offers_colors()
    assert {h.unsettled.get("color") for h in tagged.offer.heads} == {("white",)}


def test_the_gate_publishes_each_admitted_variants_dark_phases() -> None:
    """`masked_wheel_flick`'s two masks (beats 2-3 and 5-6 of its 8-beat cycle) on every
    head; `mirror_wings` lit throughout."""
    job = m.family_job(HEADS)
    admission = admit_templates(
        ["masked_wheel_flick", "mirror_wings"],
        beat_grid=GRID,
        fixture_group=rig(),
        initial_states=job.moving_heads.initial_states,
        failure_mode="error",
    )

    flick = admission.offer.templates["masked_wheel_flick"].variants["base"]
    assert flick.cycle_beats == 8.0
    for head in HEADS:
        windows = flick.heads[head]
        assert len(windows) == 2
        assert all(end - start >= 0.9 for start, end in windows)
        assert windows[0][0] == pytest.approx(2.0, abs=0.05)
    wings = admission.offer.templates["mirror_wings"].variants
    assert all(not windows for phases in wings.values() for windows in phases.heads.values())
