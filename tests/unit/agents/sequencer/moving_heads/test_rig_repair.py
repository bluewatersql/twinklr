"""Repair of the planner's colours and gobos against the rig's offer (song-intent W3, and
the review fix round: missing palette roles, colour changes that may not play)."""

from __future__ import annotations

from typing import Any

from tests.support import moving_heads as m
from tests.support.moving_heads import discrete_profile_payload, plan_section
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    EventAction,
    PlanColor,
    PlanEvent,
    RepairAction,
)
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureCapabilities
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.song_intent import (
    DarkPhases,
    HeadWheels,
    RigOffer,
    SectionPalette,
    TemplateOffer,
    gobo_offer,
)

RGB_PRIMARY = SectionPalette(
    palette_id="core.rgb_primary", stops=("#FF1744", "#00E676", "#2979FF", "#FFFFFF")
)
MAGMA = SectionPalette(palette_id="core.magma", stops=("#FF1744", "#FF3D00", "#FF9100", "#FFD600"))
TAGGED = {"white": "white", "red": "red", "blue": "blue"}


def _profile(colors: dict[str, str], gobos: dict[str, str] | None = None) -> FixtureCapabilities:
    payload = discrete_profile_payload()
    for name, color in colors.items():
        payload["discrete"]["color"]["states"][name]["hex"] = color
    for name, pattern in (gobos or {}).items():
        payload["discrete"]["gobo"]["states"][name]["pattern"] = pattern
    return FixtureCapabilities.model_validate(payload)


def _offer(*profiles: FixtureCapabilities, **fields: Any) -> RigOffer:
    heads = tuple(HeadWheels.from_profile(f"MH{i + 1}", p) for i, p in enumerate(profiles))
    return RigOffer(
        heads=heads,
        gobos={pattern.value: gobo_offer(heads, pattern) for pattern in GoboPattern},
        strobes={},
        hit="all",
        **{"wheel_change_ms": None, "beat_ms": None, "templates": {}} | fields,
    )


def _slow() -> FixtureCapabilities:
    """`_profile(TAGGED)` with close latency 20 ms and every colour settling in 150 ms: a
    180 ms wheel change, more than half a beat at 170 BPM."""
    payload = _profile(TAGGED).model_dump(mode="json")
    payload["visibility"]["close_latency_ms"] = 20
    for state in payload["discrete"]["color"]["states"].values():
        state["settle_ms"] = 150
    return FixtureCapabilities.model_validate(payload)


def _section(section_id: str = "s1", bars: tuple[int, int] = (1, 4), **intent: Any) -> Any:
    template = intent.pop("template", "mirror_wings")
    return plan_section(section_id, *bars, template).model_copy(update=intent)


def _event(action: EventAction, **values: Any) -> PlanEvent:
    return PlanEvent(
        **{"bar": 2, "beat": 1, "moment_cue_id": None, "color": None, "gobo": None} | values,
        action=action,
    )


def test_repair_clears_what_no_head_shows_and_records_what_some_cannot() -> None:
    offer = _offer(_profile(TAGGED, {"star": "stars"}), _profile({"red": "red"}))
    plan = ChoreographyPlan(
        sections=[
            _section(
                color=PlanColor.GREEN,
                gobo=GoboPattern.STARS,
                events=[
                    _event(EventAction.COLOR, color=PlanColor.YELLOW),
                    _event(EventAction.COLOR, color=PlanColor.BLUE),
                    _event(EventAction.GOBO, gobo=GoboPattern.FLAME),
                    _event(EventAction.HIT),
                ],
            )
        ],
        overall_strategy="",
    )

    repaired = repair_rig_intent(plan, offer, {})

    (section,) = repaired.sections
    assert section.color is None  # green: no head shows anything like it
    assert section.gobo is GoboPattern.STARS  # MH1 has it; MH2 keeps its own
    assert [event.action for event in section.events] == [EventAction.COLOR, EventAction.HIT]
    assert [(r.item.split(" (")[0], r.action) for r in repaired.repairs] == [
        ("colour green", RepairAction.ADJUSTED),
        ("gobo stars", RepairAction.RECORDED),
        ("event at bar 2 beat 1: color yellow", RepairAction.DROPPED),
        ("event at bar 2 beat 1: color blue", RepairAction.RECORDED),
        ("event at bar 2 beat 1: gobo flame", RepairAction.DROPPED),
    ]
    assert "keeps its authored colour (as_authored)" in repaired.repairs[0].reason
    assert repaired.repairs[1].reason == (
        "plays on MH1; MH2 cannot show it and keep their authored look"
    )


def test_repair_leaves_an_approximate_colour_and_a_plan_it_need_not_touch() -> None:
    plan = ChoreographyPlan(sections=[_section(color=PlanColor.MAGENTA)], overall_strategy="")

    assert repair_rig_intent(plan, _offer(_profile(TAGGED)), {}) is plan


def test_repair_resolves_a_palette_role_through_the_section_palette() -> None:
    offer = _offer(_profile({"white": "white", "red": "red"}))
    plan = ChoreographyPlan(
        sections=[_section(color=PlanColor.PALETTE_ACCENT)], overall_strategy=""
    )

    with_palette = repair_rig_intent(plan, offer, {"s1": RGB_PRIMARY})  # green: not shown
    fixed = repair_rig_intent(plan, offer, {})  # magenta: shown as red

    assert with_palette.sections[0].color is None
    assert "palette 'core.rgb_primary' stop 2" in with_palette.repairs[0].item
    assert fixed is plan


def test_a_role_the_palette_lacks_becomes_primary_and_is_recorded() -> None:
    """`core.magma` has no cool stop and no white: COOL and NEUTRAL play PRIMARY there."""
    offer = _offer(_profile(TAGGED))
    plan = ChoreographyPlan(
        sections=[
            _section(color=PlanColor.PALETTE_COOL),
            _section(
                "s2",
                (5, 8),
                color=PlanColor.PALETTE_NEUTRAL,
                events=[_event(EventAction.COLOR, bar=6, color=PlanColor.PALETTE_COOL)],
            ),
        ],
        overall_strategy="",
    )

    repaired = repair_rig_intent(plan, offer, {"s1": MAGMA, "s2": MAGMA})

    assert [s.color for s in repaired.sections] == [PlanColor.PALETTE_PRIMARY] * 2
    assert repaired.sections[1].events[0].color is PlanColor.PALETTE_PRIMARY
    assert [(r.section_id, r.item, r.action) for r in repaired.repairs] == [
        ("s1", "colour PALETTE_COOL", RepairAction.ADJUSTED),
        ("s2", "colour PALETTE_NEUTRAL", RepairAction.ADJUSTED),
        ("s2", "event at bar 6 beat 1: color PALETTE_COOL", RepairAction.ADJUSTED),
    ]
    assert "has no stop for this role" in repaired.repairs[0].reason


def test_repair_on_a_rig_without_tags_says_so() -> None:
    plan = ChoreographyPlan(sections=[_section(color=PlanColor.RED)], overall_strategy="")

    (repair,) = repair_rig_intent(plan, m.untagged_offer(), {}).repairs

    assert repair.reason.startswith("this rig's colour wheel offers no colour")


def test_a_state_a_template_cannot_hold_counts_as_not_shown_for_its_sections() -> None:
    offer = _offer(
        _profile(TAGGED),
        templates={
            "masked_wheel_flick": TemplateOffer(variants={}, excluded={"MH1": {"color": ("blue",)}})
        },
    )
    plan = ChoreographyPlan(
        sections=[
            _section(color=PlanColor.BLUE, template="masked_wheel_flick"),
            _section("s2", (5, 8), color=PlanColor.BLUE),
        ],
        overall_strategy="",
    )

    with m.family_catalog():
        repaired = repair_rig_intent(plan, offer, {})

    assert [s.color for s in repaired.sections] == [None, PlanColor.BLUE]
    (repair,) = repaired.repairs
    assert repair.reason.startswith(
        "template 'masked_wheel_flick' cannot turn the color wheel to it and back in time: "
        "its overlay masks are too short for that state's settle"
    )


def test_a_multi_part_section_judges_a_template_exclusion_per_part() -> None:
    """Blue is excluded only on `masked_wheel_flick`: a section whose second part is
    `mirror_wings` keeps blue, recorded as not playing in the first part."""
    offer = _offer(
        _profile(TAGGED),
        templates={
            "masked_wheel_flick": TemplateOffer(variants={}, excluded={"MH1": {"color": ("blue",)}})
        },
    )
    section = _section(color=PlanColor.BLUE, template="masked_wheel_flick")
    second = section.parts[0].model_copy(update={"start_bar": 3, "template_id": "mirror_wings"})
    section = section.model_copy(update={"parts": [section.parts[0], second]})

    with m.family_catalog():
        repaired = repair_rig_intent(
            ChoreographyPlan(sections=[section], overall_strategy=""), offer, {}
        )

    assert repaired.sections[0].color is PlanColor.BLUE
    (repair,) = repaired.repairs
    assert repair.action is RepairAction.RECORDED
    assert repair.reason.startswith(
        "plays in the parts on mirror_wings; not in those on masked_wheel_flick "
        "(template 'masked_wheel_flick' cannot turn the color wheel"
    )


def test_a_colour_change_a_fast_tempo_may_not_play_is_recorded_for_the_planner() -> None:
    """At 170 BPM a 180 ms wheel change does not fit half a beat (176 ms): a change into a
    section whose template has no dark moment long enough is recorded (the heads that
    play straight in keep the previous colour), one into a template with a dark phase in
    its first half is not, and one whose first dark phase lies past half the section is
    recorded as late."""
    beat = 60_000 / 170
    grid = m.bars_grid(*([beat] * 12))
    templates = {
        "mirror_wings": TemplateOffer(
            variants={"base": DarkPhases(cycle_beats=8.0, heads={"MH1": ((0.0, 0.25),)})}
        ),
        "masked_wheel_flick": TemplateOffer(
            variants={"base": DarkPhases(cycle_beats=8.0, heads={"MH1": ((2.0, 3.0),)})}
        ),
        "finite_snap_hold": TemplateOffer(
            variants={"base": DarkPhases(cycle_beats=8.0, heads={"MH1": ((10.0, 11.0),)})}
        ),
    }
    offer = _offer(_slow(), wheel_change_ms=180, beat_ms=beat, templates=templates)
    plan = ChoreographyPlan(
        sections=[
            _section("s1", (1, 3), color=PlanColor.RED),
            _section("s2", (4, 6), color=PlanColor.BLUE),
            _section("s3", (7, 9), color=PlanColor.RED, template="masked_wheel_flick"),
            _section("s4", (10, 12), color=PlanColor.BLUE, template="finite_snap_hold"),
        ],
        overall_strategy="",
    )

    with m.family_catalog():
        repaired = repair_rig_intent(plan, offer, {}, grid)
        quick = repair_rig_intent(
            plan, _offer(_profile(TAGGED), beat_ms=beat, templates=templates), {}, grid
        )

    assert [(r.section_id, r.item, r.action) for r in repaired.repairs] == [
        ("s2", "colour change from section 's1'", RepairAction.RECORDED),
        ("s4", "colour change from section 's3'", RepairAction.RECORDED),
    ]
    assert "keep the previous section's colour" in repaired.repairs[0].reason
    assert "beat 10 of its cycle, past half the section" in repaired.repairs[1].reason
    # Each head is judged on its own wheel: a 140 ms change fits half a beat, so every
    # change dips before its section.
    assert quick.repairs == []


def test_a_colour_change_into_a_template_that_always_enters_dark_is_not_recorded() -> None:
    """The gate found `mirror_wings` always enters dark after itself (`dark_entries`):
    the wheel turns in its entry, so the change at 170 BPM is not recorded. Each head is
    judged on its own change: only the slow head is named."""
    beat = 60_000 / 170
    grid = m.bars_grid(*([beat] * 6))
    templates = {
        "mirror_wings": TemplateOffer(variants={"base": DarkPhases(cycle_beats=8.0, heads={})})
    }
    plan = ChoreographyPlan(
        sections=[
            _section("s1", (1, 3), color=PlanColor.RED),
            _section("s2", (4, 6), color=PlanColor.BLUE),
        ],
        overall_strategy="",
    )

    with m.family_catalog():
        dark = repair_rig_intent(
            plan,
            _offer(
                _slow(),
                templates=templates,
                dark_entries={"mirror_wings": {"mirror_wings": ("MH1",)}},
            ),
            {},
            grid,
        )
        lit = repair_rig_intent(
            plan, _offer(_slow(), _profile(TAGGED), templates=templates), {}, grid
        )

    assert dark.repairs == []
    (repair,) = lit.repairs
    assert "the wheel change of MH1 (180 ms dark)" in repair.reason
    assert "where MH1 play straight into the section" in repair.reason


def test_intensity_a_rig_cannot_pulse_is_recorded_not_shaped() -> None:
    """DRAMATIC and INTENSE play on the dimmer: on a rig where no head, or only some, has
    a dimmer axis the choice is kept and recorded, so the planner can give emphasis with
    events or colour; an identity level and a rig with a dimmer everywhere record nothing."""
    profile = _profile(TAGGED)
    plan = ChoreographyPlan(
        sections=[
            plan_section("s1", 1, 4, "mirror_wings", intensity="DRAMATIC"),
            plan_section("s2", 5, 8, "mirror_wings", intensity="INTENSE"),
            plan_section("s3", 9, 12, "mirror_wings", intensity="FAST"),
        ],
        overall_strategy="",
    )

    assert repair_rig_intent(plan, _offer(profile), {}).repairs == []
    none = repair_rig_intent(plan, _offer(profile).model_copy(update={"hit": "none"}), {})
    assert [(r.section_id, r.item, r.action) for r in none.repairs] == [
        ("s1", "intensity DRAMATIC", RepairAction.RECORDED),
        ("s2", "intensity INTENSE", RepairAction.RECORDED),
    ]
    assert none.sections == plan.sections
    assert "no head of this rig has a dimmer axis" in none.repairs[0].reason
    assert "events or colour" in none.repairs[0].reason
    some = repair_rig_intent(plan, _offer(profile).model_copy(update={"hit": "some"}), {})
    assert "only some heads of this rig have a dimmer axis" in some.repairs[0].reason


def test_events_the_render_plays_otherwise_are_recorded_and_kept() -> None:
    """At 120 BPM on a rig whose darkness follows 40 ms phases a fast strobe plays
    sixteenths, recorded; a hit on a beat where the template is dark on every head is
    recorded as moving; a colour change 150 ms after the previous one (a 180 ms wheel
    change) is recorded. The plan keeps every event (the render decides)."""
    grid = m.bars_grid(*([500.0] * 4), *([150.0] * 4))
    templates = {
        "fly_out_cascade": TemplateOffer(
            variants={"base": DarkPhases(cycle_beats=8.0, heads={"MH1": ((6.0, 9.0),)})}
        )
    }
    offer = _offer(_slow(), flash_ms=40, beat_ms=500.0, templates=templates)
    events = [
        _event(EventAction.STROBE_FAST, bar=1, beat=2),
        _event(EventAction.HIT, bar=3, beat=1),
        _event(EventAction.COLOR, bar=6, beat=1, color=PlanColor.RED),
        _event(EventAction.COLOR, bar=6, beat=2, color=PlanColor.BLUE),
    ]
    plan = ChoreographyPlan(
        sections=[_section("s1", (1, 8), template="fly_out_cascade", events=events)],
        overall_strategy="",
    )

    with m.family_catalog():
        repaired = repair_rig_intent(plan, offer, {}, grid)

    assert repaired.sections[0].events == events
    reasons = {r.item: r.reason for r in repaired.repairs if r.action is RepairAction.RECORDED}
    assert reasons == {
        "event at bar 1 beat 2: strobe_fast": "at this tempo it plays 4 flash(es) a beat, not "
        "8: the darkness follows 40 ms phases",
        "event at bar 3 beat 1: hit": "template 'fly_out_cascade' is dark on this beat on every "
        "head (between its cues): the hit moves to the nearest beat the heads show, within a bar",
        "event at bar 6 beat 2: color blue": "it comes 150 ms after the previous color change, "
        "and a wheel change needs 180 ms of darkness: it turns late or does not play; space "
        "wheel changes further apart",
    }
