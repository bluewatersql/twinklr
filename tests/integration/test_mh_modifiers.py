"""W10e: a part's `modifiers` render (`modifiers`).

The closed set (spread, direction, aim) is checked on its own, then through the gate's
offer, the render's bytes and trace, and the plan repair, which resolves modifiers with
the render's own function. Every rig a render runs on here is also run narrowed to its
allowed ranges with 150 degree/s heads (`allowed_rig`), where defects hid before.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import pairwise
from typing import Any

import pytest

from tests.integration.test_mh_variant_fitting import slow_rig
from tests.support import moving_heads as m
from tests.unit.sequencer.moving_heads.test_events_render import Frames, assert_wheels_turn_dark
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanModifier,
    PlanSection,
    RepairAction,
)
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.sequencer.moving_heads.modifiers import (
    AIM_OFFSET_DEG,
    MODIFIERS,
    candidates,
    modify,
    resolve_modifiers,
)
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    TemplateAdmission,
    admit_templates,
)
from twinklr.core.sequencer.moving_heads.song_intent import describe_look, offer_for_prompt
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

HEADS = ("MH1", "MH2", "MH3", "MH4")
WAVED = ("unison", "wide_wave", "reversed")
"""The spreads of a template whose heads move in a wave."""
AIMS = ("low", "high")

OFFERED: dict[str, dict[str, tuple[str, ...]]] = {
    "finite_snap_hold": {"spread": ("wave",), "direction": ("reverse",), "aim": AIMS},
    "fly_in_cascade": {"spread": WAVED, "aim": AIMS},
    "fly_out_cascade": {"spread": WAVED, "aim": AIMS},
    "masked_wheel_flick": {"spread": ("wave",), "direction": ("reverse",), "aim": AIMS},
    "mirror_wings": {"spread": WAVED, "direction": ("reverse",), "aim": AIMS},
    "target_orbit": {"spread": ("wave",), "direction": ("reverse",), "aim": AIMS},
    "zoom_wave": {"spread": WAVED, "direction": ("reverse",), "aim": AIMS},
}
"""What each family takes, and so what a rig offers where nothing else stops it."""

WHY_NOT = {
    "spread=wave": "its heads already move in a wave",
    "spread=unison": "its heads already move together (no wave to unify)",
    "spread=wide_wave": "its heads move together (no wave to widen)",
    "spread=reversed": "its heads move together (no wave to reverse)",
    "direction=reverse": "it has no path that runs differently backwards (a periodic sweep "
    "runs the same both ways)",
}
"""Why a family does not take each value it does not (`OFFERED`): the cascades sweep, the
orbit, snap and flick move every head together, the others in a wave."""


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with m.family_catalog():
        yield


def grid(bpm: float, *, bars: int = 16, per_bar: int = 4) -> BeatGrid:
    return m.pickup_grid(60_000 / bpm, bars, pickup=0, beats_per_bar=per_bar)


def zoomed(family: str) -> bool:
    return family == m.ZOOM_FAMILY_ID


RIGS = ("720dps", "allowed_150dps")


def rig(
    name: str, family: str = "", *, heads: Sequence[str] = HEADS, topology: bool = True
) -> FixtureGroup:
    """The family rig (the zoom rig for `zoom_wave`), or it narrowed to its allowed ranges
    with 150 degree/s heads."""
    base = (
        m.zoom_rig(heads, topology=topology)
        if zoomed(family)
        else m.family_rig(heads, topology=topology)
    )
    if name == "720dps":
        return base
    return m.allowed_rig(slow_rig(150.0, base), zoom=(10.0, 38.0))


def job(family: str = "") -> JobConfig:
    return m.zoom_job(HEADS) if zoomed(family) else m.family_job(HEADS)


_GATES: dict[tuple[Any, ...], TemplateAdmission] = {}


def gate(fg: FixtureGroup, beat_grid: BeatGrid, family: str = "") -> TemplateAdmission:
    """The gate's result over the family catalog (the zoom family alone on the zoom rig),
    computed once per rig and grid."""
    ids = [m.ZOOM_FAMILY_ID] if zoomed(family) else list(m.FAMILY_IDS)
    key = (fg.model_dump_json(), beat_grid.model_dump_json(), tuple(ids))
    if key not in _GATES:
        config = job(family)
        _GATES[key] = admit_templates(
            ids,
            beat_grid=beat_grid,
            fixture_group=fg,
            initial_states=config.moving_heads.initial_states,
            failure_mode=config.moving_heads.reposition_fallback,
            on_unplayable=config.moving_heads.on_unplayable,
            excludable=ids,
        )
    return _GATES[key]


def section(
    section_id: str,
    bars: tuple[int, int],
    family: str,
    *modifiers: tuple[str, str],
    preset: str | None = None,
    **fields: Any,
) -> PlanSection:
    built = m.plan_section(section_id, bars[0], bars[1], family, preset, **fields)
    return with_modifiers(built, *modifiers)


def with_modifiers(built: PlanSection, *modifiers: tuple[str, str]) -> PlanSection:
    asked = [PlanModifier(key=key, value=value) for key, value in modifiers]
    return built.model_copy(
        update={"parts": [part.model_copy(update={"modifiers": asked}) for part in built.parts]}
    )


def render(
    sections: Sequence[PlanSection],
    fg: FixtureGroup,
    beat_grid: BeatGrid,
    admission: TemplateAdmission | None,
    family: str = "",
) -> RenderingPipeline:
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=list(sections), overall_strategy=""),
        beat_grid=beat_grid,
        fixture_group=fg,
        job_config=job(family),
        media_file="silence.wav",
        admission=admission,
    )
    pipeline.render()
    return pipeline


def traced(pipeline: RenderingPipeline) -> dict[str, dict[str, Any]]:
    """Per placed part with modifiers, its trace's `arrangement.modifiers`."""
    assert pipeline.render_record is not None
    return {
        look["section_id"]: look["arrangement"]["modifiers"]
        for look in pipeline.render_record["section_looks"]
        if "modifiers" in look.get("arrangement", {})
    }


def frame_index(beat_grid: BeatGrid, bar: int) -> int:
    """The frame at bar `bar`'s downbeat (bar `len + 1`: the song's last frame)."""
    bars = beat_grid.bar_boundaries
    at = bars[bar - 1] if bar <= len(bars) else beat_grid.duration_ms
    return int(at // 20)


def assert_within_limits(pipeline: RenderingPipeline) -> None:
    """Every frame: each head's pan and tilt inside its operable range, no step between
    frames faster than the head travels (one word's rounding aside), and every wheel turn
    inside darkness that covers its settle."""
    frames = Frames(pipeline)
    profile = frames.profile
    for name in ("pan", "tilt"):
        axis = profile.axes[name]
        assert axis.travel_speed_per_s is not None
        low, high = axis.operable_range
        word = (axis.physical_max - axis.physical_min) / axis.full_word
        for head in HEADS:
            degrees = []
            for frame in frames.raw(head):
                value = frame[axis.coarse_offset]
                if axis.fine_offset is not None:
                    value = value << 8 | frame[axis.fine_offset]
                degrees.append(float(axis.word_center(value)))
            assert all(low - word <= d <= high + word for d in degrees), (head, name)
            fastest = max(abs(b - a) for a, b in pairwise(degrees))
            assert fastest <= axis.travel_speed_per_s * 0.020 + word + 1e-6, (head, name, fastest)
    assert_wheels_turn_dark(frames)


# --- the closed set ------------------------------------------------------------------------


@pytest.mark.parametrize("family", m.CATALOG_IDS)
def test_each_family_takes_what_changes_it_and_says_why_not_the_rest(family: str) -> None:
    taken = candidates(get_template(family).template)
    offered = {f"{key}={value}" for key, values in OFFERED[family].items() for value in values}

    assert {name for name, why in taken.items() if why is None} == offered
    for name, why in taken.items():
        if why is not None:
            assert why == f"{family} cannot: {WHY_NOT[name]}", name


def test_each_modifier_changes_only_what_it_names() -> None:
    wings = get_template("mirror_wings").template
    (wave,) = wings.steps[0].distribution
    unison = modify(wings, [("spread", "unison")]).steps[0].distribution[0]
    assert (unison.spread_cycles, unison.wings, unison.direction) == (0.0, 2, wave.direction)
    assert modify(wings, [("spread", "wide_wave")]).steps[0].distribution[0].spread_cycles == 0.5
    assert modify(wings, [("spread", "reversed")]).steps[0].distribution[0].direction == "forward"
    reversed_ = modify(wings, [("direction", "reverse")]).steps[0].movement
    assert reversed_.transform is not None and reversed_.transform.reverse
    orbit = get_template("target_orbit").template
    (added,) = modify(orbit, [("spread", "wave")]).steps[0].distribution
    assert (added.spread_cycles, added.wings, set(added.domains)) == (0.25, 1, {"pan", "tilt"})
    snap = modify(get_template("finite_snap_hold").template, [("direction", "reverse")])
    movement = snap.steps[0].movement
    assert (movement.start_tilt_deg, movement.tilt_extent_deg) == (55.0, -45.0)
    zoom = modify(get_template("zoom_wave").template, [("direction", "reverse")]).steps[0]
    assert (zoom.movement.pan_extent_deg, zoom.zoom and zoom.zoom.extent_deg) == (-15.0, -10.0)
    for family in m.CATALOG_IDS:
        template = get_template(family).template
        for value, sign in (("low", -1), ("high", 1)):
            aimed = modify(template, [("aim", value)])
            for step, before in zip(aimed.steps, template.steps, strict=True):
                assert before.movement.start_tilt_deg is not None
                assert step.movement.start_tilt_deg == pytest.approx(
                    before.movement.start_tilt_deg + sign * AIM_OFFSET_DEG
                )
    # Applied in the order of `MODIFIERS`, whatever order they are asked in.
    asked = [("aim", "high"), ("direction", "reverse")]
    assert modify(get_template("finite_snap_hold").template, asked) == modify(
        get_template("finite_snap_hold").template, asked[::-1]
    )
    assert list(MODIFIERS) == ["spread", "direction", "aim"]


# --- the offer -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "bpm", "per_bar"),
    [
        ("720dps", 120, 4),
        ("allowed_150dps", 79.5, 4),
        ("allowed_150dps", 120, 4),
        ("720dps", 170, 3),
    ],
)
def test_the_gate_offers_what_plays_unlike_the_variant_here(
    name: str, bpm: float, per_bar: int
) -> None:
    """On each rig and tempo every admitted family offers what it takes (nothing stops a
    modifier on these rigs), and names why it does not offer the rest; the zoom family on
    the zoom rig likewise."""
    for family in (m.FAMILY_IDS[0], m.ZOOM_FAMILY_ID):
        admission = gate(rig(name, family), grid(bpm, per_bar=per_bar), family)
        for template_id, offered in admission.offer.templates.items():
            assert offered.modifiers == OFFERED[template_id], (template_id, name, bpm)
            refused = set(offered.modifier_refusals)
            assert refused == set(candidates(get_template(template_id).template)) - {
                f"{key}={value}" for key, values in offered.modifiers.items() for value in values
            }


@pytest.mark.parametrize("name", RIGS)
def test_a_rig_without_a_topology_offers_no_wave(name: str) -> None:
    admission = gate(rig(name, topology=False), grid(120))

    for template_id in ("target_orbit", "finite_snap_hold", "masked_wheel_flick"):
        offered = admission.offer.templates[template_id]
        assert "spread" not in offered.modifiers
        assert "topology" in offered.modifier_refusals["spread=wave"]
        assert offered.modifiers["aim"] == AIMS


@pytest.mark.parametrize("name", RIGS)
def test_a_modifier_that_plays_like_the_variant_is_not_offered(name: str) -> None:
    """On two heads a two-winged template's wave has one slot: every head already moves
    together, so no spread changes a frame there."""
    two = ("MH1", "MH2")
    fg = rig(name, heads=two)
    config = m.family_job(two)
    admission = admit_templates(
        ["mirror_wings"],
        beat_grid=grid(120),
        fixture_group=fg,
        initial_states=config.moving_heads.initial_states,
        failure_mode=config.moving_heads.reposition_fallback,
        on_unplayable=config.moving_heads.on_unplayable,
        excludable=["mirror_wings"],
    )
    offered = admission.offer.templates["mirror_wings"]

    assert "spread" not in offered.modifiers
    for value in WAVED:
        assert "plays like the template without it" in offered.modifier_refusals[f"spread={value}"]


# --- the render ----------------------------------------------------------------------------


@pytest.mark.parametrize("name", RIGS)
@pytest.mark.parametrize("family", m.CATALOG_IDS)
def test_every_offered_modifier_changes_the_bytes_within_the_limits(name: str, family: str) -> None:
    """One section with each offered value, each after a section without; against the same
    plan without modifiers, each modified section's frames differ, it plays its value, and
    every frame stays inside the heads' range, speed and wheel darkness."""
    fg = rig(name, family)
    beat_grid = grid(120, bars=24)
    admission = gate(fg, beat_grid, family)
    values = [(k, v) for k, vs in admission.offer.templates[family].modifiers.items() for v in vs]
    assert values
    modified: list[PlanSection] = []
    plain: list[PlanSection] = []
    for index, value in enumerate(values):
        start = 4 * index + 1
        modified += [
            section(f"p{index}", (start, start + 1), family),
            section(f"m{index}", (start + 2, start + 3), family, value),
        ]
        plain += [
            section(f"p{index}", (start, start + 1), family),
            section(f"m{index}", (start + 2, start + 3), family),
        ]
    played, without = (
        render(modified, fg, beat_grid, admission, family),
        render(plain, fg, beat_grid, admission, family),
    )
    frames, before = Frames(played), Frames(without)
    trace = traced(played)

    for index, (key, value) in enumerate(values):
        assert trace[f"m{index}"] == {"asked": [f"{key}={value}"], "applied": [f"{key}={value}"]}
        lo, hi = frame_index(beat_grid, 4 * index + 3), frame_index(beat_grid, 4 * index + 5)
        assert any(frames.raw(h)[lo:hi] != before.raw(h)[lo:hi] for h in HEADS), (key, value)
    assert_within_limits(played)


@pytest.mark.parametrize("name", RIGS)
@pytest.mark.parametrize("family", m.CATALOG_IDS)
def test_modifiers_combine_with_every_variant_the_part_plays(name: str, family: str) -> None:
    """At 79.5 BPM a section on every admitted variant with one value of each key, and a
    motif carrier widened from it: each plays what the gate lets it there, repair says the
    same, and every frame stays inside the limits. On the 150 degree/s heads the gate
    fits the cascades' `fast` to them."""
    fg = rig(name, family)
    beat_grid = grid(79.5, bars=24)
    admission = gate(fg, beat_grid, family)
    offered = admission.offer.templates[family]
    if name == "allowed_150dps" and family in ("fly_in_cascade", "fly_out_cascade"):
        assert "fast" in offered.fitted  # a fitted variant among them
    chosen = [(key, values[-1]) for key, values in offered.modifiers.items()]
    sections = [
        section(f"v{index}", (2 * index + 1, 2 * index + 2), family, *chosen, preset=variant)
        for index, variant in enumerate(v for v in offered.variants if v != "base")
    ]
    start = 2 * len(sections) + 1
    sections += [
        section("intro", (start, start + 1), family, motif_id="m"),
        section("wider", (start + 2, start + 3), family, *chosen, motif_id="m", variation="WIDEN"),
    ]
    plan = ChoreographyPlan(sections=sections, overall_strategy="")
    repaired = repair_rig_intent(plan, admission.offer, {}, beat_grid)
    pipeline = render(repaired.sections, fg, beat_grid, admission, family)

    assert_repair_says_what_plays(repaired, pipeline)
    for part in traced(pipeline).values():
        assert part["applied"], part
    assert_within_limits(pipeline)


def test_aim_gives_way_on_a_variant_whose_tilt_reaches_the_heads_limit() -> None:
    """Heads allowed to tilt only to 80 degrees: the snap's `wide` lifts to 77.5, so aiming
    it 10 degrees higher would leave the range; its base (to 55) takes it. The gate
    excludes it on `wide` alone; the render plays it on the base, not on `wide`, and says
    why, as repair does."""
    payload = m.allowed_rig(slow_rig(150.0)).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        fixture["config"]["physical_profile"]["axes"]["tilt"].update(allowed_max=80.0)
    fg = FixtureGroup.model_validate(payload)
    beat_grid = grid(120)
    admission = gate(fg, beat_grid)
    snap = admission.offer.templates["finite_snap_hold"]

    assert "wide" in snap.variants and "aim=high" not in snap.modifier_exclusions.get("base", {})
    assert "outside its operable range" in snap.modifier_exclusions["wide"]["aim=high"]
    plan = ChoreographyPlan(
        sections=[
            section("a", (1, 4), "finite_snap_hold", ("aim", "high")),
            section("b", (5, 8), "finite_snap_hold", ("aim", "high"), preset="wide"),
        ],
        overall_strategy="",
    )
    repaired = repair_rig_intent(plan, admission.offer, {}, beat_grid)
    pipeline = render(repaired.sections, fg, beat_grid, admission)
    trace = traced(pipeline)

    assert trace["a"]["applied"] == ["aim=high"]
    assert trace["b"]["applied"] == []
    (why,) = trace["b"]["not_applied"]
    assert why["reason"].startswith("it does not fit wide: aim high would take MH1's tilt to")
    assert_repair_says_what_plays(repaired, pipeline)
    assert_within_limits(pipeline)


@pytest.mark.parametrize("name", RIGS)
def test_a_section_of_several_parts_plays_each_parts_own_modifiers(name: str) -> None:
    fg = rig(name)
    beat_grid = grid(120)
    admission = gate(fg, beat_grid)
    built = m.plan_section("s", 1, 8, "mirror_wings", label="first")
    first = built.parts[0].model_copy(
        update={"modifiers": [PlanModifier(key="spread", value="unison")]}
    )
    second = first.model_copy(
        update={
            "start_bar": 5,
            "template_id": "target_orbit",
            "label": "second",
            "modifiers": [
                PlanModifier(key="direction", value="reverse"),
                PlanModifier(key="spread", value="unison"),
            ],
        }
    )
    plan = ChoreographyPlan(
        sections=[built.model_copy(update={"parts": [first, second]})], overall_strategy=""
    )
    repaired = repair_rig_intent(plan, admission.offer, {}, beat_grid)
    pipeline = render(repaired.sections, fg, beat_grid, admission)
    trace = traced(pipeline)

    assert trace["s|first"]["applied"] == ["spread=unison"]
    assert trace["s|second"]["applied"] == ["direction=reverse"]
    (refused,) = trace["s|second"]["not_applied"]
    assert refused["modifier"] == "spread=unison"
    assert refused["reason"].startswith(
        "not offered for target_orbit here: target_orbit cannot: its heads already move "
        "together (no wave to unify); target_orbit takes spread=wave, direction=reverse, "
        "aim=low, aim=high here"
    )
    assert_repair_says_what_plays(repaired, pipeline)


# --- repair says what the render plays -----------------------------------------------------


def assert_repair_says_what_plays(repaired: ChoreographyPlan, pipeline: RenderingPipeline) -> None:
    """Every modifier repair records as not playing is one the render's trace says does
    not play, with the same reason, and the other way round."""
    said = {
        (r.section_id, r.item.split(" modifier ", 1)[1], r.reason)
        for r in repaired.repairs
        if " modifier " in r.item
    }
    assert all(
        r.action is RepairAction.RECORDED for r in repaired.repairs if " modifier " in r.item
    )
    played = {
        (part_id.split("|")[0], entry["modifier"], f"{entry['reason']}; the part plays without it")
        for part_id, part in traced(pipeline).items()
        for entry in part.get("not_applied", [])
        # Giving way is the render's to decide; repair says only that it may.
        if not entry["reason"].startswith("the modifier gave way")
    }
    assert said == played


AGREEMENT: dict[str, list[tuple[str, tuple[int, int], str, list[tuple[str, str]], Any]]] = {
    "mixed": [
        ("a", (1, 2), "fly_out_cascade", [("spread", "unison"), ("aim", "low")], {}),
        ("b", (3, 4), "fly_in_cascade", [("direction", "reverse"), ("tilt", "up")], {}),
        ("c", (5, 6), "mirror_wings", [("Aim", "HIGH"), ("aim", "low"), ("spread", "far")], {}),
        ("d", (7, 8), "target_orbit", [("spread", "wave"), ("spread", "unison")], {}),
    ],
    "arranged": [
        ("a", (1, 2), "mirror_wings", [("spread", "reversed")], {"motif_id": "m"}),
        ("b", (3, 4), "mirror_wings", [("aim", "high")], {"motif_id": "m", "variation": "WIDEN"}),
        ("c", (5, 6), "finite_snap_hold", [("direction", "reverse"), ("aim", "high")], {}),
        ("d", (7, 8), "masked_wheel_flick", [("spread", "wave")], {"variation": "SLOWER"}),
    ],
}


@pytest.mark.parametrize("plan_name", sorted(AGREEMENT))
@pytest.mark.parametrize(("bpm", "per_bar"), [(79.5, 4), (170, 4), (140, 3)])
@pytest.mark.parametrize("name", RIGS)
def test_repair_says_what_the_render_plays(
    plan_name: str, bpm: float, per_bar: int, name: str
) -> None:
    """Unknown keys and values, a second entry for a key, values a template is not offered
    and values that do not fit the variant the part plays: repair records each with the
    render's own reason, the part plays without it, and every other plays."""
    fg = rig(name)
    beat_grid = grid(bpm, per_bar=per_bar)
    admission = gate(fg, beat_grid)
    plan = ChoreographyPlan(
        sections=[
            section(sid, bars, family, *modifiers, **fields)
            for sid, bars, family, modifiers, fields in AGREEMENT[plan_name]
        ],
        overall_strategy="",
    )
    repaired = repair_rig_intent(plan, admission.offer, {}, beat_grid)
    pipeline = render(repaired.sections, fg, beat_grid, admission)

    assert_repair_says_what_plays(repaired, pipeline)
    assert repaired.sections == plan.sections
    if plan_name == "mixed":
        trace = traced(pipeline)
        assert trace["a"]["applied"] == ["spread=unison", "aim=low"]
        assert [e["reason"].split(";")[0] for e in trace["b"]["not_applied"]] == [
            "not offered for fly_in_cascade here: fly_in_cascade cannot: it has no path that "
            "runs differently backwards (a periodic sweep runs the same both ways)",
            "the renderer knows no modifier 'tilt' (it knows spread, direction, aim)",
        ]
        assert trace["c"]["applied"] == ["aim=high"]
        assert [e["reason"].split(";")[0] for e in trace["c"]["not_applied"]] == [
            "the part already sets aim (high)",
            "spread takes unison or wave or wide_wave or reversed, not 'far'",
        ]
        assert trace["d"]["applied"] == ["spread=wave"]
        assert trace["d"]["not_applied"][0]["reason"].startswith("the part already sets spread")
    assert_within_limits(pipeline)


@pytest.mark.parametrize("name", RIGS)
def test_a_spread_that_darkens_a_hit_gives_way_and_repair_says_it_may(name: str) -> None:
    """The cascades are lit only on a stretch of each head's own phase: under `unison`
    every head is dark on the same beats (the gate publishes them,
    `TemplateOffer.modifier_phases`). A hit on a beat every head is dark on under
    `unison`, where some heads are lit without it: repair reads that darkness and says the
    modifiers may give way; the render's arrangement unit gives way (the song outranks
    the arrangement), tracing the event, and the hit plays as without the spread. With
    `aim` beside it, only the spread gives way."""
    fg = rig(name)
    beat_grid = grid(120)
    admission = gate(fg, beat_grid)
    unison = admission.offer.templates["fly_out_cascade"].modifier_phases["base"]["spread=unison"]
    assert len({tuple(windows) for windows in unison.heads.values()}) == 1

    def plan(bar: int, beat: int, *modifiers: tuple[str, str]) -> ChoreographyPlan:
        hit = {
            "bar": bar,
            "beat": beat,
            "moment_cue_id": None,
            "action": "hit",
            "color": None,
            "gobo": None,
        }
        return ChoreographyPlan(
            sections=[
                section("a", (1, 4), "fly_out_cascade"),
                section("b", (5, 8), "fly_out_cascade", *modifiers, events=[hit]),
            ],
            overall_strategy="",
        )

    def said(repaired: ChoreographyPlan, suffix: str = ": hit") -> list[str]:
        return [r.reason for r in repaired.repairs if r.item.endswith(suffix)]

    found = None
    for bar, beat in ((bar, beat) for bar in (5, 6) for beat in range(1, 5)):
        with_ = said(
            repair_rig_intent(plan(bar, beat, ("spread", "unison")), admission.offer, {}, beat_grid)
        )
        without = said(repair_rig_intent(plan(bar, beat), admission.offer, {}, beat_grid))
        if any("on every head" in r for r in with_) and any(
            "only the other heads play it" in r for r in without
        ):
            found = bar, beat
            break
    assert found is not None

    def rendered(*modifiers: tuple[str, str]) -> tuple[ChoreographyPlan, RenderingPipeline]:
        repaired = repair_rig_intent(plan(*found, *modifiers), admission.offer, {}, beat_grid)
        return repaired, render(repaired.sections, fg, beat_grid, admission)

    def hit(pipeline: RenderingPipeline) -> dict[str, Any]:
        assert pipeline.render_record is not None
        (look,) = [x for x in pipeline.render_record["section_looks"] if x["section_id"] == "b"]
        (entry,) = look["events"]
        outcomes: dict[str, Any] = entry["heads"]
        return outcomes

    repaired, unified = rendered(("spread", "unison"))
    (may,) = said(repaired, "modifiers")
    assert may.startswith("the modifiers may make the song's events worse than without them")
    assert "they may give way" in may
    _, plain = rendered()
    trace = traced(unified)["b"]
    assert trace["applied"] == []
    (why,) = trace["not_applied"]
    assert why["reason"].startswith("the modifier gave way to ")
    assert hit(unified) == hit(plain)
    assert unified.frames == plain.frames
    assert any(
        "its modifier spread=unison does not play" in d["message"] for d in diagnostics(unified)
    )
    (reason,) = said(repair_rig_intent(plan(*found), admission.offer, {}, beat_grid))
    dark = sorted(h for h, outcome in hit(plain).items() if "not_played" in outcome)
    assert reason == (
        f"template 'fly_out_cascade' is dark on this beat on {', '.join(dark)} (between its "
        "cues): only the other heads play it"
    )
    _, aimed = rendered(("spread", "unison"), ("aim", "high"))
    trace = traced(aimed)["b"]
    assert trace["applied"] == ["aim=high"]
    (why,) = trace["not_applied"]
    assert why["modifier"] == "spread=unison"
    assert why["reason"].startswith("the modifier gave way to the song")
    assert hit(aimed) == hit(plain)


def diagnostics(pipeline: RenderingPipeline) -> list[dict[str, Any]]:
    assert pipeline.render_record is not None
    found: list[dict[str, Any]] = pipeline.render_record["diagnostics"]
    return found


# --- identity, the arrangement unit and what is said -------------------------------------------


@pytest.mark.parametrize("name", RIGS)
def test_modifiers_that_do_not_play_change_no_frame(name: str) -> None:
    fg = rig(name)
    beat_grid = grid(120)
    admission = gate(fg, beat_grid)
    asked = [("spread", "wave"), ("colour", "red"), ("aim", "sideways")]
    with_ = render([section("a", (1, 8), "fly_out_cascade", *asked)], fg, beat_grid, admission)
    without = render([section("a", (1, 8), "fly_out_cascade")], fg, beat_grid, admission)

    assert with_.frames == without.frames
    assert traced(with_)["a"]["applied"] == []
    assert len(traced(with_)["a"]["not_applied"]) == 3


@pytest.mark.parametrize("name", RIGS)
def test_what_plays_is_render_identity(name: str) -> None:
    fg = rig(name)
    beat_grid = grid(120)
    admission = gate(fg, beat_grid)
    sections = [section("a", (1, 8), "target_orbit", ("direction", "reverse"))]
    offered = render(sections, fg, beat_grid, admission)
    offer = admission.offer.model_copy(
        update={
            "templates": {
                t: o.model_copy(update={"modifiers": {}})
                for t, o in admission.offer.templates.items()
            }
        }
    )
    from dataclasses import replace

    refused = render(sections, fg, beat_grid, replace(admission, offer=offer))

    assert offered.frames != refused.frames
    assert offered.fingerprint() != refused.fingerprint()


def test_a_parts_modifiers_are_one_arrangement_unit() -> None:
    """One unit per placed part whose modifiers play, after its section's variation and
    density; a spread playing with others may go alone first."""
    from twinklr.core.sequencer.moving_heads.pipeline import WITHOUT_SPREAD, _modifier_units

    fg = rig("720dps")
    beat_grid = grid(120)
    admission = gate(fg, beat_grid)
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(
            sections=[
                section("a", (1, 4), "mirror_wings", ("spread", "unison"), ("aim", "high")),
                section("b", (5, 6), "target_orbit", ("aim", "low")),
                section("c", (7, 8), "target_orbit", ("spread", "unison")),
            ],
            overall_strategy="",
        ),
        beat_grid=beat_grid,
        fixture_group=fg,
        job_config=job(),
        media_file="silence.wav",
        admission=admission,
    )

    assert [(u.key, u.order, u.candidates) for u in _modifier_units(pipeline)] == [
        ("modifier:a", (0, 2), ("planned", WITHOUT_SPREAD)),
        ("modifier:b", (1, 2), ("planned",)),
    ]


def test_the_planner_and_the_report_are_told_what_plays() -> None:
    admission = gate(rig("720dps"), grid(120))
    shown = offer_for_prompt(admission.offer, {}, ["a"])["modifiers"]

    assert {t["template_id"]: t["offered"] for t in shown}["fly_out_cascade"] == [
        "spread unison|wide_wave|reversed",
        "aim low|high",
    ]
    from tests.unit.agents.sequencer.moving_heads.test_prompts import (
        TestPlannerUserPromptRendering,
    )

    prompt = TestPlannerUserPromptRendering._render(rig_offer=admission.offer)
    assert "- **Modifiers** that play here (any other is ignored, and repair says so): " in prompt
    assert "`fly_out_cascade`: spread unison|wide_wave|reversed, aim low|high;" in prompt
    lines = describe_look(
        {
            "arrangement": {
                "modifiers": {
                    "asked": ["aim=high", "tilt=up"],
                    "applied": ["aim=high"],
                    "not_applied": [{"modifier": "tilt=up", "reason": "unknown"}],
                }
            }
        }
    )
    assert lines == ["modifiers: aim=high play", "modifier tilt=up does not play: unknown"]
    play = resolve_modifiers(
        [PlanModifier(key=" Spread ", value="Wide-Wave")],
        get_template("mirror_wings").template,
        admission.offer.templates["mirror_wings"],
        "base",
    )
    assert play.applied == (("spread", "wide_wave"),)
