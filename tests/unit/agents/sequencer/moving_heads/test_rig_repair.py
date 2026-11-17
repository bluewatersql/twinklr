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
    offer = _offer(_profile(TAGGED), wheel_change_ms=180, beat_ms=beat, templates=templates)
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
        slow = repair_rig_intent(plan, offer.model_copy(update={"wheel_change_ms": 160}), {}, grid)

    assert [(r.section_id, r.item, r.action) for r in repaired.repairs] == [
        ("s2", "colour change from section 's1'", RepairAction.RECORDED),
        ("s4", "colour change from section 's3'", RepairAction.RECORDED),
    ]
    assert "keep the previous section's colour" in repaired.repairs[0].reason
    assert "beat 10 of its cycle, past half the section" in repaired.repairs[1].reason
    assert slow.repairs == []  # 160 ms fits half a beat: every change dips before
