"""W10b/W10c: the planner's motif and variation, resolved to the variant each part plays.

The resolver (`arrangement`) is checked on its own, then through the render (bytes and
trace) and against the plan repair, which reads the same resolution. Frames are read
through the rig's profile (`test_events_render.Frames`).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.unit.sequencer.moving_heads.test_events_render import (
    HEADS,
    Frames,
    grid,
    looks,
    render,
    rig,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.moving_heads.arrangement import (
    BASE,
    VARIATION_PRESETS,
    VariantOptions,
    grid_position,
    grid_variant,
    motif_relations,
    resolve_arrangement,
)
from twinklr.core.sequencer.moving_heads.pipeline import TemplateAdmission, admit_templates
from twinklr.core.sequencer.moving_heads.song_intent import rig_offer
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

ALL = frozenset({BASE, "narrow", "slow", *VARIATION_PRESETS})


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with m.family_catalog():
        yield


def plan(*sections: PlanSection) -> ChoreographyPlan:
    return ChoreographyPlan(sections=list(sections), overall_strategy="")


def section(
    section_id: str,
    bars: tuple[int, int],
    template_id: str,
    *,
    preset: str | None = None,
    motif: str | None = None,
    variation: str = "NONE",
    parts: Sequence[tuple[int, str]] = (),
    **fields: Any,
) -> PlanSection:
    built = m.plan_section(
        section_id,
        bars[0],
        bars[1],
        template_id,
        preset,
        motif_id=motif,
        variation=variation,
        **fields,
    )
    if parts:
        built = built.model_copy(
            update={
                "parts": [
                    built.parts[0].model_copy(update={"start_bar": start, "template_id": t})
                    for start, t in parts
                ]
            }
        )
    return built


def everything(_: str) -> VariantOptions:
    return VariantOptions(effective=BASE, admitted=ALL)


def gate(
    beat_grid: BeatGrid, fixture_group: FixtureGroup | None = None, job: Any = None
) -> TemplateAdmission:
    fg = fixture_group or rig()
    job = job or m.family_job(HEADS)
    return admit_templates(
        list(m.FAMILY_IDS),
        beat_grid=beat_grid,
        fixture_group=fg,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=list(m.FAMILY_IDS),
    )


def arranged(pipeline: Any) -> dict[str, dict[str, Any]]:
    return {
        section_id: look["arrangement"]
        for section_id, look in looks(pipeline).items()
        if "arrangement" in look
    }


# --- the grid and the resolver ---------------------------------------------------------


def test_the_grid_names_every_variant_once() -> None:
    names = {grid_variant(reach, rate) for reach in range(3) for rate in range(3)}
    assert names == ALL
    for name in names:
        position = grid_position(name)
        assert position is not None and grid_variant(*position) == name
    assert grid_position("sweep") is None


def test_equal_motifs_relate_by_plan_order_and_a_macro_thread_names_the_relation() -> None:
    the_plan = plan(
        section("a", (1, 2), "mirror_wings", motif="m"),
        section("b", (3, 4), "mirror_wings", motif="m"),
        section("c", (5, 6), "mirror_wings", motif="m", variation="WIDEN"),
        section("d", (7, 8), "target_orbit"),
    )

    assert motif_relations(the_plan) == {
        "a": ("INTRODUCE", None),
        "b": ("RESTATE", "a"),
        "c": ("VARY", "a"),
    }
    threaded = motif_relations(the_plan, {"m": (["a", "b", "c"], "RESOLVE")})
    assert threaded["b"] == ("RESOLVE", "a") and threaded["c"] == ("RESOLVE", "a")
    assert motif_relations(the_plan, {"m": (["a", "b"], "INTRODUCE")})["b"] == ("RESTATE", "a")


def test_writing_the_relations_records_what_the_macro_threads_do_not_say() -> None:
    from twinklr.core.sequencer.moving_heads.arrangement import with_motif_relations

    the_plan = plan(
        section("a", (1, 2), "mirror_wings", motif="m"),
        section("b", (3, 4), "mirror_wings", motif="m"),
        section("c", (5, 6), "mirror_wings", motif="n"),
    )
    written = with_motif_relations(the_plan, {"m": (["a", "b"], "INTRODUCE")})

    assert [(s.motif_relation, s.motif_source_id) for s in written.sections] == [
        ("INTRODUCE", None),
        ("RESTATE", "a"),
        ("INTRODUCE", None),
    ]
    said = {(r.section_id, r.item): r.reason for r in written.repairs}
    assert set(said) == {("b", "motif m"), ("c", "motif n")}
    assert "already introduced: this section restates it" in said["b", "motif m"]
    assert "no macro motif thread lists section 'c'" in said["c", "motif n"]
    assert with_motif_relations(written, {"m": (["a", "b"], "INTRODUCE")}) == written
    assert with_motif_relations(the_plan).repairs == []


def test_relations_arriving_on_the_plan_are_overwritten() -> None:
    """The reviewer's repro: whatever relation or source arrives (from the planner or an
    injected file) is replaced by the derived one; a bogus source never plays."""
    from twinklr.core.sequencer.moving_heads.arrangement import with_motif_relations

    def the_plan(**s3: Any) -> ChoreographyPlan:
        return plan(
            section("s1", (1, 4), "mirror_wings", motif="m1"),
            section("s2", (5, 8), "mirror_wings", motif="m1", variation="WIDEN"),
            section("s3", (9, 12), "mirror_wings", motif="m1", **s3),
        )

    derived = with_motif_relations(the_plan())
    for supplied in (
        {"motif_relation": "RESTATE", "motif_source_id": "s2"},
        {"motif_relation": "INTRODUCE"},
        {"motif_relation": "RESOLVE", "motif_source_id": "zzz"},
    ):
        written = with_motif_relations(the_plan(**supplied))
        assert written.sections == derived.sections, supplied
    bogus = the_plan(motif_relation="VARY", motif_source_id="zzz", variation="FASTER")
    (s3,) = [p for p in resolve_arrangement(bogus, everything)["s3"].parts if p]
    assert s3.relative_to.startswith("motif 'm1' as section 's1' introduced it")
    assert s3.plays == "fast"
    plain = with_motif_relations(
        plan(section("x", (1, 2), "mirror_wings", motif_relation="VARY", motif_source_id="y"))
    )
    assert plain.sections[0].motif_relation is None and plain.sections[0].motif_source_id is None


def test_every_carrier_varies_the_introduced_look_by_one_step() -> None:
    """Each carrier steps from the introducing section's variant, not from the carrier
    before it: two WIDEN choruses play the same variant, and a restatement returns to the
    introduced look."""
    resolved = resolve_arrangement(
        plan(
            section("a", (1, 2), "mirror_wings", preset="slow", motif="m"),
            section("b", (3, 4), "mirror_wings", motif="m", variation="WIDEN"),
            section("c", (5, 6), "fly_in_cascade", motif="m", variation="FASTER"),
            section("d", (7, 8), "fly_in_cascade", motif="m"),
        ),
        everything,
    )

    plays = {sid: a.parts[0].plays for sid, a in resolved.items() if a.parts[0]}
    assert plays == {"a": "slow", "b": "wide+slow", "c": "base", "d": "slow"}
    assert resolved["c"].parts[0].relative_to.startswith("motif 'm' as section 'a' introduced it")
    assert all(a.source_id == "a" for sid, a in resolved.items() if sid != "a")
    twice = resolve_arrangement(
        plan(
            section("v", (1, 2), "target_orbit", motif="m"),
            section("c1", (3, 4), "fly_out_cascade", motif="m", variation="WIDEN"),
            section("br", (5, 6), "fly_in_cascade", motif="m", variation="FASTER"),
            section("c2", (7, 8), "mirror_wings", motif="m", variation="WIDEN"),
        ),
        everything,
    )
    assert [twice[s].parts[0].plays for s in ("v", "c1", "br", "c2")] == [  # type: ignore[union-attr]
        "base",
        "wide",
        "fast",
        "wide",
    ]


def test_an_introducing_section_with_a_variation_steps_from_its_own_preset() -> None:
    resolved = resolve_arrangement(
        plan(
            section("a", (1, 2), "mirror_wings", preset="wide"),
            section("b", (3, 4), "mirror_wings", preset="slow", motif="m", variation="NARROW"),
        ),
        everything,
    )

    (b,) = [p for p in resolved["b"].parts if p]
    assert (b.source, b.plays, b.relative_to) == ("slow", "narrow+slow", "its own preset")


def test_without_a_motif_a_variation_steps_from_the_previous_section_on_its_family() -> None:
    resolved = resolve_arrangement(
        plan(
            section("a", (1, 2), "mirror_wings", preset="narrow"),
            section("b", (3, 4), "target_orbit", variation="SLOWER"),
            section("c", (5, 6), "mirror_wings", variation="WIDEN"),
        ),
        everything,
    )

    assert "a" not in resolved  # no motif, no variation: plays as before
    assert resolved["b"].parts[0].plays == "slow"
    assert resolved["b"].parts[0].relative_to == "its effective variant"
    assert resolved["c"].parts[0].plays == BASE  # narrow, one step wider
    assert resolved["c"].parts[0].relative_to.startswith("the previous section on mirror_wings")


def test_a_step_that_cannot_play_plays_its_source_and_says_why() -> None:
    def no_wide(_: str) -> VariantOptions:
        return VariantOptions(effective=BASE, admitted=ALL - {"wide"})

    resolved = resolve_arrangement(
        plan(
            section("a", (1, 2), "mirror_wings", preset="wide+fast", motif="m"),
            section("b", (3, 4), "mirror_wings", motif="m", variation="FASTER"),
            section("c", (5, 6), "target_orbit", variation="WIDEN"),
        ),
        no_wide,
    )

    off = resolved["b"].parts[0]
    assert off is not None and off.plays == "wide+fast"  # the source's variant
    assert "already the fastest" in (off.reason or "")
    missing = resolved["c"].parts[0]
    assert missing.plays == BASE and "'wide' of target_orbit is not admitted" in (
        missing.reason or ""
    )


def test_resolve_slows_else_narrows_else_restates() -> None:
    def no_slow(_: str) -> VariantOptions:
        return VariantOptions(effective=BASE, admitted=ALL - {"slow"})

    the_plan = plan(
        section("a", (1, 2), "mirror_wings", motif="m"),
        section(
            "b", (3, 4), "mirror_wings", motif="m", motif_relation="RESOLVE", motif_source_id="a"
        ),
    )

    assert resolve_arrangement(the_plan, everything)["b"].parts[0].plays == "slow"
    assert resolve_arrangement(the_plan, no_slow)["b"].parts[0].plays == "narrow"


def test_each_part_steps_from_the_sources_part_at_the_same_index() -> None:
    """A three-part restatement of a two-part source: parts 1 and 2 step from the
    source's parts 1 and 2, part 3 from its last."""
    resolved = resolve_arrangement(
        plan(
            section(
                "a",
                (1, 4),
                "mirror_wings",
                motif="m",
                parts=[(1, "mirror_wings"), (3, "target_orbit")],
                preset="slow",
            ),
            section(
                "b",
                (5, 10),
                "mirror_wings",
                motif="m",
                variation="WIDEN",
                parts=[(5, "mirror_wings"), (7, "target_orbit"), (9, "fly_in_cascade")],
            ),
        ),
        everything,
    )

    assert [p.plays for p in resolved["b"].parts if p] == ["wide+slow", "wide+slow", "wide+slow"]
    assert [p.relative_to[-6:] for p in resolved["b"].parts if p] == [
        "part 1",
        "part 2",
        "part 2",
    ]


# --- the render ------------------------------------------------------------------------


def test_with_no_motif_and_no_variation_the_render_is_unchanged() -> None:
    plain = plan(section("a", (1, 4), "mirror_wings"), section("b", (5, 8), "target_orbit"))
    pipeline = render(plain.sections)

    assert arranged(pipeline) == {}
    assert all("arrangement" not in look for look in looks(pipeline).values())


def test_an_introduced_motif_without_a_variation_plays_its_own_preset() -> None:
    resolved = resolve_arrangement(
        plan(
            section("a", (1, 2), "mirror_wings", preset="wide"),
            section("b", (3, 4), "mirror_wings", preset="narrow", motif="m"),
        ),
        everything,
    )

    assert resolved["b"].parts[0].plays == "narrow"
    assert resolved["b"].parts[0].relative_to == "its own preset"
    assert resolved["b"].parts[0].reason is None


def test_an_introduced_motif_plays_as_planned() -> None:
    planned = plan(section("a", (1, 4), "mirror_wings", preset="narrow"))
    introduced = plan(section("a", (1, 4), "mirror_wings", preset="narrow", motif="m"))
    pipeline = render(introduced.sections)

    assert Frames(render(planned.sections)).by_head == Frames(pipeline).by_head
    trace = arranged(pipeline)["a"]
    assert trace["motif"] == {"id": "m", "relation": "INTRODUCE"}
    assert trace["variation"]["plays"] == "narrow"


NOT_SHOWN = {("finite_snap_hold", "FASTER")}
"""The one step the gate does not offer at 120 BPM: the snap's `fast` plays as its base
after its own base (`test_a_variant_playing_the_same_as_base_is_not_offered`)."""


@pytest.mark.parametrize("variation", ["NARROW", "WIDEN", "SLOWER", "FASTER"])
@pytest.mark.parametrize("family", m.CATALOG_IDS)
def test_every_variation_changes_the_bytes_of_every_family_or_says_why(
    family: str, variation: str
) -> None:
    """Two sections on one family, the second varied: its frames differ from the same plan
    unvaried, and the trace names the variant it plays; the one step the gate does not
    offer here plays its source's variant, and the trace says why."""
    beat_grid = grid(120)
    zoom = family == m.ZOOM_FAMILY_ID
    fg = m.zoom_rig(HEADS) if zoom else rig()
    job = m.zoom_job(HEADS) if zoom else m.family_job(HEADS)
    admission = admit_templates(
        [family],
        beat_grid=beat_grid,
        fixture_group=fg,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=[],
    )
    varied = plan(
        section("a", (1, 4), family),
        section("b", (5, 8), family, variation=variation),
    )
    unvaried = plan(section("a", (1, 4), family), section("b", (5, 8), family))
    kwargs: dict[str, Any] = {
        "beat_grid": beat_grid,
        "fixture_group": fg,
        "job_config": job,
        "admission": admission,
    }
    pipeline = render(varied.sections, **kwargs)
    same = render(unvaried.sections, **kwargs)
    trace = arranged(pipeline)["b"]["variation"]

    assert bool(trace.get("reason")) == ((family, variation) in NOT_SHOWN), trace
    warned = [
        d["message"]
        for d in pipeline.render_record["diagnostics"]
        if d["section_id"] == "b" and "does not play" in d["message"]
    ]
    assert warned == (
        [f"section 'b': its variation {variation} does not play ({trace['reason']})"]
        if trace.get("reason")
        else []
    )
    if trace.get("reason"):
        assert trace["plays"] == trace["from"]
        assert Frames(pipeline).by_head == Frames(same).by_head
    else:
        assert trace["plays"] != trace["from"]
        assert Frames(pipeline).by_head != Frames(same).by_head


def test_a_motif_on_another_template_carries_its_variant_and_never_its_colour() -> None:
    beat_grid = grid(120)
    pipeline = render(
        plan(
            section("a", (1, 4), "mirror_wings", preset="slow", motif="m", color="red"),
            section("b", (5, 8), "target_orbit", motif="m", color="blue"),
        ).sections,
        beat_grid=beat_grid,
        fixture_group=m.tagged_family_rig(HEADS),
    )
    trace = arranged(pipeline)["b"]

    assert trace["motif"] == {"id": "m", "relation": "RESTATE", "source": "a"}
    assert trace["variation"]["plays"] == "slow"
    frames = Frames(pipeline)
    middle = int(beat_grid.bar_boundaries[5] // 20)  # inside section b
    lit = [h for h in HEADS if not frames.dark(h)[middle]]
    assert lit and all(frames.state(h, "color")[middle] == "blue" for h in lit)
    repaired = repair_rig_intent(
        plan(
            section("a", (1, 4), "mirror_wings", preset="slow", motif="m", color="red"),
            section("b", (5, 8), "target_orbit", motif="m", color="blue"),
        ),
        rig_offer(m.tagged_family_rig(HEADS), beat_grid),
        {},
        beat_grid,
    )
    said = [r.reason for r in repaired.repairs if r.section_id == "b" and r.item == "motif m"]
    assert any("only its reach and rate (slow) carry the motif" in why for why in said)
    assert any("its color (blue) differs from its source 'a''s (red)" in why for why in said)


# --- repair agrees with the render ------------------------------------------------------


AGREEMENT_PLANS = {
    "chain": [
        ("a", (1, 2), "mirror_wings", {"motif": "m", "preset": "slow"}),
        ("b", (3, 4), "fly_in_cascade", {"motif": "m", "variation": "WIDEN"}),
        ("c", (5, 6), "fly_out_cascade", {"motif": "m", "variation": "FASTER"}),
        ("d", (7, 8), "mirror_wings", {"variation": "NARROW"}),
    ],
    "offgrid": [
        ("a", (1, 2), "target_orbit", {"motif": "m", "preset": "wide"}),
        ("b", (3, 4), "target_orbit", {"motif": "m", "variation": "WIDEN"}),
        ("c", (5, 6), "masked_wheel_flick", {"variation": "SLOWER", "preset": "narrow"}),
        ("d", (7, 8), "finite_snap_hold", {"variation": "FASTER"}),
    ],
}


def _slow_heads(speed: float = 300.0) -> FixtureGroup:
    payload = rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = speed
    return FixtureGroup.model_validate(payload)


@pytest.mark.parametrize("name", sorted(AGREEMENT_PLANS))
@pytest.mark.parametrize("bpm", [120, 170])
@pytest.mark.parametrize("slow", [False, True], ids=["720dps", "300dps"])
def test_repair_reads_the_variant_the_render_plays(name: str, bpm: int, slow: bool) -> None:
    """Repair resolves each part as the render does, over the same gate, and records every
    step that cannot play, every named preset the resolution replaces, every motif on
    another template than its source's, and every colour that differs from the source."""
    beat_grid = grid(bpm)
    fg = _slow_heads() if slow else rig()
    admission = gate(beat_grid, fg)
    sections = [
        section(sid, bars, template, **fields)
        for sid, bars, template, fields in AGREEMENT_PLANS[name]
    ]
    repaired = repair_rig_intent(plan(*sections), admission.offer, {}, beat_grid)
    pipeline = render(repaired.sections, beat_grid=beat_grid, fixture_group=fg, admission=admission)
    traced = arranged(pipeline)
    recorded = {(r.section_id, r.item): r.reason for r in repaired.repairs}

    for sid, trace in traced.items():
        variant = trace.get("variation")
        if variant is None:
            continue
        cannot = [
            reason
            for (section_id, item), reason in recorded.items()
            if section_id == sid and " variation " in item
        ]
        assert bool(variant.get("reason")) == bool(cannot), (sid, variant, cannot)
        if cannot:
            assert cannot[0].endswith(f"it plays {variant['plays']}")
        if "named" in variant:
            assert any(section_id == sid and " preset " in item for section_id, item in recorded), (
                sid
            )


def test_repair_feeds_back_a_named_preset_the_gate_did_not_admit() -> None:
    """On 150-degree heads at 170 BPM the cascades' `fast` is not admitted at any fitted
    strength: a section naming it plays its effective variant, and repair says so."""
    beat_grid = grid(170)
    fg = _slow_heads(150.0)
    admission = gate(beat_grid, fg)
    assert "fast" not in admission.offer.templates["fly_in_cascade"].variants
    repaired = repair_rig_intent(
        plan(section("a", (1, 4), "fly_in_cascade", preset="fast")),
        admission.offer,
        {},
        beat_grid,
    )

    (said,) = [r.reason for r in repaired.repairs if r.item.endswith("preset fast")]
    assert "did not admit fly_in_cascade's 'fast'" in said and "effective variant" in said


@pytest.mark.parametrize("bpm", [78, 120, 170])
def test_a_variant_playing_the_same_as_base_is_not_offered(bpm: int) -> None:
    """`finite_snap_hold` snaps and holds: its `fast` plays the same frames as its base
    in a section after its own base, so the gate leaves it out (and a FASTER step from
    base plays base, saying why); every other variant of every family shows."""
    admission = gate(grid(bpm))
    same = [
        (e["template_id"], e["preset_id"])
        for e in admission.preset_exclusions
        if "plays the same as base here" in str(e["reason"])
    ]

    assert same == [("finite_snap_hold", "fast")]
    assert "fast" not in admission.offer.templates["finite_snap_hold"].variants


# --- a plan playing no variation variant sees the ladder's numbers (W10a review) ---------


def _without_variations(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate's catalog with every variation variant removed (the ladder alone)."""
    from twinklr.core.sequencer.moving_heads import pipeline

    real = pipeline.get_template

    def ladder_only(template_id: str) -> Any:
        document = real(template_id)
        return document.model_copy(
            update={
                "presets": [p for p in document.presets if p.preset_id not in VARIATION_PRESETS]
            }
        )

    monkeypatch.setattr(pipeline, "get_template", ladder_only)


@pytest.mark.parametrize("bpm", [78, 170])
def test_the_ladder_numbers_are_those_of_a_catalog_without_variations(
    bpm: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Entry dips, dark entries and the prompt's numbers for a plan playing no variation
    variant are exactly those the gate gives without the variation variants; each
    variation variant has its own, published apart."""
    from twinklr.core.sequencer.moving_heads.song_intent import offer_for_prompt

    beat_grid = grid(bpm)
    full = gate(beat_grid)
    with monkeypatch.context() as patch:
        _without_variations(patch)
        ladder = gate(beat_grid)

    assert full.entry_dips == ladder.entry_dips
    assert full.offer.dark_entries == ladder.offer.dark_entries
    shown = offer_for_prompt(full.offer, {}, ["s1", "s2"])
    alone = offer_for_prompt(ladder.offer, {}, ["s1", "s2"])
    assert {k: v for k, v in shown.items() if k not in ("variations", "variant_windows")} == {
        k: v for k, v in alone.items() if k not in ("variations", "variant_windows")
    }
    assert not alone["variations"] and not alone["variant_windows"]
    for template_id, variants in full.variant_entry_dips.items():
        assert set(variants) == set(full.offer.templates[template_id].variants)
    pair = full.offer.variant_dark_entries
    assert pair and all(
        ">" in key for after in pair.values() for keys in after.values() for key in keys
    )


def test_repair_reads_the_dark_entry_of_the_pair_of_variants_played() -> None:
    """`dark_entry_heads` gives the ladder's claim for ladder variants and a variation
    pair's own claim otherwise."""
    admission = gate(grid(170))
    offer = admission.offer

    for successor, after in offer.dark_entries.items():
        for predecessor, heads in after.items():
            assert offer.dark_entry_heads(successor, predecessor) == heads
            assert offer.dark_entry_heads(successor, predecessor, "narrow", "slow") == heads
    for successor, after in offer.variant_dark_entries.items():
        for predecessor, pairs in after.items():
            for key, heads in pairs.items():
                before, played = key.split(">")
                assert offer.dark_entry_heads(successor, predecessor, played, before) == heads


def test_a_ladder_variant_playing_as_base_stays_admitted_but_is_never_a_step() -> None:
    """On 220-degree heads at 240 BPM `finite_snap_hold`'s `slow` plays as its base: a
    section naming it plays it as before (the ladder is unchanged), and a SLOWER step
    from base plays base, saying why."""
    beat_grid = grid(240)
    fg = _slow_heads(220.0)
    admission = gate(beat_grid, fg)
    snap = admission.offer.templates["finite_snap_hold"]

    assert "slow" in snap.variants and snap.plays_as_base == ("slow",)
    assert "slow" in admission.admitted_presets["finite_snap_hold"]
    repaired = repair_rig_intent(
        plan(
            section("a", (1, 4), "finite_snap_hold"),
            section("b", (5, 8), "finite_snap_hold", variation="SLOWER"),
        ),
        admission.offer,
        {},
        beat_grid,
    )
    (said,) = [r.reason for r in repaired.repairs if r.item.endswith("variation SLOWER")]
    assert "'slow' of finite_snap_hold plays the same as base here" in said
    pipeline = render(repaired.sections, beat_grid=beat_grid, fixture_group=fg, admission=admission)
    assert arranged(pipeline)["b"]["variation"]["plays"] == BASE
