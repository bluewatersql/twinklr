"""The physical family catalog (P2.4c): admission, section succession and the families' frames.

The six documents in `catalog/templates/moving_heads_physical` load only under
`physical_v2`, after the builtins and before `--template-dir`. Every ordered pair of
families renders back to back at a fast tempo without a fallback, and each family's
frames show what its name claims: fly-out lights outward travel and fly-in inward
travel with every return dark, orbit and wings stay lit across cycles, and the snap
holds its terminal pose. Every render here is checked from its encoded bytes, and each
family is also repeated and rendered without a head. Synthetic rigs and grids only: no
audio, provider, owner data or xLights. How any of it looks is `PENDING-OWNER`.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from functools import cache
from itertools import pairwise
import math
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.support.mh_physical import (
    FAMILY_IDS,
    TEMPLATE_DIR,
    TEMPLATE_ID,
    assert_honest_transactions,
    family_job,
    family_rig,
    hold_step,
    physical_bars_grid,
    physical_catalog,
    physical_job,
    physical_rig,
    physical_sections,
    physical_template_doc,
    registered_templates,
)
from twinklr.cli.main import _run_pipeline_async
from twinklr.core.agents.sequencer.moving_heads.deterministic_selector import (
    DeterministicSelector,
)
from twinklr.core.config.fixtures import AxisCapability, FixtureCapabilities, FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import SemanticGroupType
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import is_physical_template
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.compile.preset import apply_preset
from twinklr.core.sequencer.moving_heads.export.frame_encoder import frame_times
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    TemplateAdmission,
    check_physical_templates,
)
from twinklr.core.sequencer.moving_heads.templates import list_templates
from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    PHYSICAL_TEMPLATE_DIR,
    load_template_document,
)
from twinklr.core.sequencer.moving_heads.templates.library import (
    REGISTRY,
    validate_template_document,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

HEADS = ("MH1", "MH2", "MH3", "MH4")
_STRICT = {"reposition_fallback": "error", "on_unplayable": "error"}


# --- The documents ---------------------------------------------------------------------


def test_catalog_holds_the_six_families_each_physical_explicit_and_degradable() -> None:
    """Each family lints, is physical on every step, sets both start angles (no rig
    position preset is required), authors its dimmer, declares `drop_accent` and
    declares reach and rate variants as presets."""
    paths = sorted(PHYSICAL_TEMPLATE_DIR.glob("*.json"))
    assert tuple(path.stem for path in paths) == FAMILY_IDS
    for path in paths:
        document = load_template_document(path)
        validate_template_document(document)
        template = document.template
        assert template.template_id == path.stem
        assert is_physical_template(template), path.name
        for step in template.steps:
            movement = step.movement.physical
            assert movement is not None
            assert movement.start_pan_deg is not None and movement.start_tilt_deg is not None
            assert step.component_refs is None, path.name
            assert step.dimmer.physical is not None or step.physical_visibility is not None
            assert step.physical_reposition_fallback == "drop_accent", path.name
        assert {preset.preset_id for preset in document.presets} == {"narrow", "slow"}


def test_a_family_preset_keeps_the_flick_overlay() -> None:
    """Applying a preset rebuilds the template; without its overlay a preset would play
    the flick family with no flick."""
    document = load_template_document(PHYSICAL_TEMPLATE_DIR / "masked_wheel_flick.json")
    overlays = document.template.physical_overlays
    assert overlays
    for preset in document.presets:
        assert apply_preset(document.template, preset).physical_overlays == overlays


# --- Admission through the CLI ---------------------------------------------------------


async def _cli_offer(
    tmp_path: Path, job: JobConfig, rig: FixtureGroup, template_dir: Path | None = None
) -> list[str]:
    """Run `twinklr run` up to the pipeline build and return the templates it would
    offer the planner; nothing after template admission and the rig check runs."""
    offered: list[str] = []

    def stop(**kwargs: Any) -> Any:
        offered.extend(kwargs["available_templates"])
        raise ValueError("stopped before the pipeline")

    with (
        patch("twinklr.cli.main.load_app_config", return_value=MagicMock()),
        patch("twinklr.cli.main.validate_llm_provider_config"),
        patch("twinklr.cli.main.load_job_config", return_value=job),
        patch("twinklr.cli.main.load_fixture_group", return_value=rig),
        patch("twinklr.cli.main.build_run_pipeline", side_effect=stop),
    ):
        code = await _run_pipeline_async(
            tmp_path / "song.wav",
            tmp_path / "out",
            tmp_path / "config.json",
            tmp_path / "job_config.json",
            template_dir=template_dir,
        )
    assert code == 1 and offered  # stopped at the build, after admission
    return offered


@pytest.mark.asyncio
async def test_legacy_run_with_the_catalog_on_disk_is_unchanged(tmp_path: Path) -> None:
    """A legacy run never loads the catalog: it offers the 37 builtins, the shared
    registry holds 37 entries, and the deterministic selector's candidates are the same."""
    with physical_catalog(admit=False):
        builtins = [info.template_id for info in list_templates()]
        candidates = set(DeterministicSelector(seed=7)._documents)
        offered = await _cli_offer(tmp_path, JobConfig(), physical_rig())

        assert offered == builtins
        assert len(builtins) == 37
        assert len(REGISTRY.list_all()) == 37
        assert set(DeterministicSelector(seed=7)._documents) == candidates
        assert not set(FAMILY_IDS) & set(offered)


@pytest.mark.asyncio
async def test_physical_run_offers_the_families_and_template_dir_documents(
    tmp_path: Path,
) -> None:
    with physical_catalog(admit=False):
        offered = await _cli_offer(tmp_path, family_job(HEADS), family_rig(HEADS), TEMPLATE_DIR)

    assert sorted(offered) == sorted([*FAMILY_IDS, TEMPLATE_ID])


@pytest.mark.parametrize(
    "spelling",
    [
        pytest.param(PHYSICAL_TEMPLATE_DIR, id="resolved"),
        pytest.param(PHYSICAL_TEMPLATE_DIR / ".." / PHYSICAL_TEMPLATE_DIR.name, id="unresolved"),
    ],
)
@pytest.mark.asyncio
async def test_template_dir_naming_the_physical_catalog_loads_nothing_twice(
    tmp_path: Path, spelling: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with (
        physical_catalog(admit=False),
        patch(
            "twinklr.cli.main.load_templates_from_directory",
            side_effect=AssertionError("--template-dir loaded"),
        ),
    ):
        offered = await _cli_offer(tmp_path, family_job(HEADS), family_rig(HEADS), spelling)

    assert tuple(sorted(offered)) == FAMILY_IDS
    # Rich wraps long paths; the words survive with their spacing normalized.
    assert "already admitted" in " ".join(capsys.readouterr().out.split())


@pytest.mark.asyncio
async def test_runs_in_one_process_admit_the_catalog_once_and_a_legacy_run_withdraws_it(
    tmp_path: Path,
) -> None:
    """A second physical run reuses the catalog the first admitted instead of failing on
    it, and a legacy run after them offers the 37 builtins with the deterministic
    selector's candidates unchanged."""
    with physical_catalog(admit=False):
        builtins = [info.template_id for info in list_templates()]
        candidates = set(DeterministicSelector(seed=7)._documents)
        for _ in range(2):
            offered = await _cli_offer(tmp_path, family_job(HEADS), family_rig(HEADS))
            assert tuple(sorted(offered)) == FAMILY_IDS
        offered = await _cli_offer(tmp_path, JobConfig(), physical_rig())

        assert offered == builtins
        assert len(REGISTRY.list_all()) == 37
        assert set(DeterministicSelector(seed=7)._documents) == candidates


# --- Section succession ----------------------------------------------------------------


def test_template_with_an_unknown_bound_term_is_excluded_naming_fixture_and_term() -> None:
    """A template that plays at every gate placement on a head whose tilt latency is
    unknown still has no worst-case entry bound there, so it is left out of the offer;
    one with no cue on that head is admitted."""
    payload = physical_rig().model_dump(mode="json")
    payload["fixtures"][0]["config"]["physical_profile"]["axes"]["tilt"]["latency_ms"] = None
    rig = FixtureGroup.model_validate(payload)
    still = physical_template_doc("p24c_still", [hold_step("still", 0.0)])
    right = physical_template_doc(
        "p24c_still_right", [hold_step("still", 0.0, target=SemanticGroupType.RIGHT)]
    )
    job = physical_job()
    with registered_templates(still, right):
        admission = check_physical_templates(
            ["p24c_still", "p24c_still_right"],
            beat_grid=physical_bars_grid(500.0, 500.0, 500.0),
            fixture_group=rig,
            initial_states=job.moving_heads.initial_states,
            failure_mode="error",
            excludable=["p24c_still"],
        )

    assert admission.admitted == ("p24c_still_right",)
    [exclusion] = admission.exclusions
    assert exclusion["template_id"] == "p24c_still"
    assert "MH1" in exclusion["reason"] and "axes.tilt.latency_ms" in exclusion["reason"]


def _gate(
    template_ids: Sequence[str], grid: BeatGrid, rig: FixtureGroup, job: JobConfig
) -> TemplateAdmission:
    return check_physical_templates(
        list(template_ids),
        beat_grid=grid,
        fixture_group=rig,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=list(template_ids),
    )


def _late_mh3_rig() -> FixtureGroup:
    """`family_rig` whose MH3 tilt answers 60 ms late, so its entries take longest."""
    payload = family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        if fixture["fixture_id"] == "MH3":
            fixture["config"]["physical_profile"]["axes"]["tilt"]["latency_ms"] = 60
    return FixtureGroup.model_validate(payload)


def test_gate_reports_each_familys_worst_case_entry_dip() -> None:
    """The dip is the largest bound over a family's presets and fixtures (here on MH3,
    whose tilt is late), in whole beats at the song's shortest beat (300 ms, not the
    500 ms of the other bars), from the union of every offered family's poses and wheel
    states and the initial state: beside the wide cascades the orbit dips longer than
    offered alone."""
    grid = physical_bars_grid(500.0, 300.0, 500.0, 500.0)
    rig, job = _late_mh3_rig(), family_job(HEADS)
    with physical_catalog():
        everything = _gate(FAMILY_IDS, grid, rig, job)
        orbit = _gate(["target_orbit"], grid, rig, job)
        beside_cascade = _gate(["target_orbit", "fly_out_cascade"], grid, rig, job)

    assert everything.admitted == FAMILY_IDS
    assert tuple(sorted(everything.entry_dips)) == FAMILY_IDS
    bounds = [dip["bound_ms"] for dip in everything.entry_dips.values()]
    for template_id, dip in everything.entry_dips.items():
        assert dip["fixture_id"] == "MH3", template_id
        assert dip["beats"] == math.ceil(dip["bound_ms"] / 300.0), template_id
    assert any(math.ceil(b / 300.0) != math.ceil(b / 500.0) for b in bounds)
    alone = orbit.entry_dips["target_orbit"]["bound_ms"]
    assert beside_cascade.entry_dips["target_orbit"]["bound_ms"] > alone  # wider poses
    assert everything.entry_dips["target_orbit"]["bound_ms"] > alone


def _meter_grid(beats_per_bar: int, beat_ms: float, bars: int) -> BeatGrid:
    beats = [15.0]
    for _ in range(beats_per_bar * bars):
        beats.append(beats[-1] + beat_ms)
    return BeatGrid(
        bar_boundaries=beats[::beats_per_bar],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=60_000 / beat_ms,
        beats_per_bar=beats_per_bar,
        duration_ms=beats[-1] + 15.0,
    )


@pytest.mark.parametrize(
    ("beats_per_bar", "slow_only"),
    [pytest.param(3, False, id="3-4"), pytest.param(6, True, id="6-8")],
)
def test_outside_four_four_the_orbit_and_wings_are_left_out(
    beats_per_bar: int, slow_only: bool
) -> None:
    """The families are authored for 4/4. Their 2-bar cycles of continuous motion span
    whole periods only there: in 3/4 the base's 4-beat period, in 6/8 the slow variant's
    8-beat period, ends mid-path at the cycle end, so orbit and wings jump there and are
    left out; the others play."""
    job = family_job(HEADS)
    with physical_catalog():
        admission = _gate(FAMILY_IDS, _meter_grid(beats_per_bar, 500.0, 6), family_rig(HEADS), job)

    assert set(admission.admitted) == set(FAMILY_IDS) - {"target_orbit", "mirror_wings"}
    for exclusion in admission.exclusions:
        reason = exclusion["reason"]
        assert "jumps across the cue" in reason and "preset 'slow'" in reason, exclusion
        base = f"template {exclusion['template_id']!r}: dark repositioning"
        assert (base in reason) is not slow_only, exclusion


_FAST_BEAT_MS = 340.0
"""About 176 BPM, the fastest bars the succession tests use."""


@pytest.fixture(scope="module")
def fast_admission() -> TemplateAdmission:
    """The gate over every family on the family rig, its shortest beats fast."""
    job = family_job(HEADS, **_STRICT)
    with physical_catalog():
        return check_physical_templates(
            list(FAMILY_IDS),
            beat_grid=physical_bars_grid(500.0, _FAST_BEAT_MS, _FAST_BEAT_MS, 500.0),
            fixture_group=family_rig(HEADS),
            initial_states=job.moving_heads.initial_states,
            failure_mode=job.moving_heads.reposition_fallback,
            on_unplayable=job.moving_heads.on_unplayable,
        )


def _every_ordered_pair(items: Sequence[str]) -> list[str]:
    """A sequence whose consecutive pairs are every ordered pair of `items`, each once:
    an Eulerian circuit of the complete digraph with loops (Hierholzer)."""
    edges = {item: list(items) for item in items}
    stack, circuit = [items[0]], []
    while stack:
        if edges[stack[-1]]:
            stack.append(edges[stack[-1]].pop())
        else:
            circuit.append(stack.pop())
    return circuit[::-1]


def test_every_ordered_pair_of_families_renders_back_to_back_at_the_fastest_bars(
    fast_admission: TemplateAdmission,
) -> None:
    """The gate admits every family at about 176 BPM without any fallback or degrade
    (both `error`), and then each section's entry window fits the repositioning from
    whatever the previous family left, at that tempo throughout."""
    assert fast_admission.admitted == FAMILY_IDS and fast_admission.exclusions == ()
    sequence = _every_ordered_pair(FAMILY_IDS)
    assert len(set(pairwise(sequence))) == len(FAMILY_IDS) ** 2
    sections = [(template_id, 2 * i + 1, 2 * i + 2) for i, template_id in enumerate(sequence)]
    grid = physical_bars_grid(*([_FAST_BEAT_MS] * (2 * len(sections) + 1)))
    rig, job = family_rig(HEADS), family_job(HEADS, **_STRICT)
    with physical_catalog():
        pipeline, segments = _render(sections, grid, rig, job)
        _verify(pipeline, segments, rig, job)
    assert pipeline.render_record is not None
    assert pipeline.render_record["unplayable_totals"] == {}


# --- The families' frames --------------------------------------------------------------


def _render(
    sections: list[tuple[str, int, int]], grid: BeatGrid, rig: FixtureGroup, job: JobConfig
) -> tuple[RenderingPipeline, list[FixtureSegment]]:
    pipeline = RenderingPipeline(
        choreography_plan=physical_sections(*sections),
        beat_grid=grid,
        fixture_group=rig,
        job_config=job,
    )
    return pipeline, pipeline.render()


def _verify(
    pipeline: RenderingPipeline, segments: list[FixtureSegment], rig: FixtureGroup, job: JobConfig
) -> None:
    """Replanning the render's cues gives its segments, and every fixture is honest from
    its encoded bytes."""
    cues = [s for s in segments if TRANSACTION_METADATA_KEY not in s.metadata]
    profiles = _profiles(rig)
    replanned = plan_prepositions(
        cues,
        profiles,
        initial_states=job.moving_heads.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(pipeline.beat_grid.duration_ms))) * EFFECT_GRID_MS,
        failure_mode=job.moving_heads.reposition_fallback,
    )
    assert list(replanned.segments) == segments
    for fixture_id, profile in profiles.items():
        initial = job.moving_heads.initial_states[fixture_id]
        assert_honest_transactions(replanned, cues, profile, initial, fixture_id=fixture_id)


def _profiles(rig: FixtureGroup) -> dict[str, FixtureCapabilities]:
    profiles = {}
    for fixture in rig.expand_fixtures():
        assert fixture.config.physical_profile is not None
        profiles[fixture.fixture_id] = fixture.config.physical_profile
    return profiles


def _frames(pipeline: RenderingPipeline, fixture_id: str) -> list[dict[int, int]]:
    return [dict(f.channels) for f in pipeline.frames if f.fixture_id == fixture_id]


def _degrees(frame: dict[int, int], axis: AxisCapability) -> Fraction:
    word = frame[axis.coarse_offset]
    if axis.fine_offset is not None:
        word = word << 8 | frame[axis.fine_offset]
    if axis.inverted:
        word = axis.full_word - word
    span = Fraction(axis.physical_max) - Fraction(axis.physical_min)
    return Fraction(axis.physical_min) + word * span / axis.full_word


def _dark(frame: dict[int, int], profile: FixtureCapabilities) -> bool:
    """Commanded dark: a zero dimmer word or an extinguishing shutter state."""
    dimmer = profile.axes["dimmer"]
    if frame[dimmer.coarse_offset] == dimmer.dmx_word(0):
        return True
    shutter = profile.discrete["shutter"]
    state = next(n for n, s in shutter.states.items() if s.value == frame[shutter.offset])
    return state in profile.visibility.extinguishing_shutter_states


@cache
def _solo(template_id: str, bars: int) -> RenderingPipeline:
    """`bars` bars of `template_id` alone from bar 1 at 120 BPM on the family rig, checked
    honest from its bytes; rendered once per test session."""
    grid = physical_bars_grid(*([500.0] * (bars + 1)))
    rig, job = family_rig(HEADS), family_job(HEADS, **_STRICT)
    with physical_catalog():
        pipeline, segments = _render([(template_id, 1, bars)], grid, rig, job)
        _verify(pipeline, segments, rig, job)
    return pipeline


def _lit_steps(template_id: str, measure: str) -> dict[str, set[int]]:
    """Per head, the signs of every pan change that lands on a lit frame, over two bars
    of `template_id` alone: of the distance from the 0° aim (`outward`) or of pan."""
    pipeline = _solo(template_id, 2)
    profile = _profiles(family_rig(HEADS))["MH1"]
    pan = profile.axes["pan"]
    steps: dict[str, set[int]] = {}
    for fixture_id in HEADS:
        signs = set()
        for before, after in pairwise(_frames(pipeline, fixture_id)):
            if measure == "outward":
                change = abs(_degrees(after, pan)) - abs(_degrees(before, pan))
            else:
                change = _degrees(after, pan) - _degrees(before, pan)
            if change and not _dark(after, profile):
                signs.add(1 if change > 0 else -1)
        steps[fixture_id] = signs
    return steps


def test_fly_out_lights_only_outward_travel_and_fly_in_only_inward_travel() -> None:
    """Every pan change that lands on a lit frame moves away from the aim under
    fly-out and toward it under fly-in, on every head: each return stroke is dark."""
    assert _lit_steps("fly_out_cascade", "outward") == {fixture_id: {1} for fixture_id in HEADS}
    assert _lit_steps("fly_in_cascade", "outward") == {fixture_id: {-1} for fixture_id in HEADS}


def test_lit_pan_direction_is_mirrored_by_wing_and_reversed_from_fly_out_to_fly_in() -> None:
    """The left wing (MH1, MH2) lights pan moving down under fly-out and the right wing
    up; under fly-in each head's lit direction is the opposite."""
    out = _lit_steps("fly_out_cascade", "pan")
    into = _lit_steps("fly_in_cascade", "pan")
    assert out == {"MH1": {-1}, "MH2": {-1}, "MH3": {1}, "MH4": {1}}
    assert into == {fixture_id: {-sign for sign in signs} for fixture_id, signs in out.items()}


def _lit_starts(pipeline: RenderingPipeline, fixture_id: str) -> list[int]:
    """The time of every lit frame that follows a dark one."""
    profile = _profiles(family_rig(HEADS))[fixture_id]
    frames = [f for f in pipeline.frames if f.fixture_id == fixture_id]
    return [
        after.time_ms
        for before, after in pairwise(frames)
        if _dark(dict(before.channels), profile) and not _dark(dict(after.channels), profile)
    ]


@pytest.mark.parametrize("template_id", ["fly_out_cascade", "fly_in_cascade"])
def test_cascade_lights_the_inner_heads_a_beat_after_the_outer_ones(template_id: str) -> None:
    """A quarter-period stagger over the two folded slots of four heads: each inner head
    (MH2, MH3) lights one 500 ms beat after its outer neighbour, mirrored heads together.
    The first stroke may be cut by the entry window, so later ones are compared."""
    pipeline = _solo(template_id, 4)
    starts = {fixture_id: _lit_starts(pipeline, fixture_id)[1:] for fixture_id in HEADS}
    assert len(starts["MH1"]) >= 3
    assert starts["MH4"] == starts["MH1"] and starts["MH3"] == starts["MH2"]
    for outer, inner in zip(starts["MH1"], starts["MH2"], strict=False):
        assert abs(inner - outer - 500) <= EFFECT_GRID_MS, (outer, inner)


def test_mirror_wings_reflect_each_other_about_the_aim() -> None:
    """Heads in mirrored places (MH1/MH4, MH2/MH3) share a phase and reflect pan about
    the 0° aim, tilt equal, wherever both are lit; the inner pair lead the outer."""
    pipeline = _solo("mirror_wings", 2)
    profile = _profiles(family_rig(HEADS))["MH1"]
    pan, tilt = profile.axes["pan"], profile.axes["tilt"]
    word = (Fraction(pan.physical_max) - Fraction(pan.physical_min)) / pan.full_word
    frames = {(f.fixture_id, f.time_ms): dict(f.channels) for f in pipeline.frames}
    times = sorted({time_ms for _, time_ms in frames})
    compared = 0
    for left, right in (("MH1", "MH4"), ("MH2", "MH3")):
        for time_ms in times:
            a, b = frames[left, time_ms], frames[right, time_ms]
            if _dark(a, profile) or _dark(b, profile):
                continue
            compared += 1
            assert abs(_degrees(a, pan) + _degrees(b, pan)) <= word, (left, time_ms)
            assert _degrees(a, tilt) == _degrees(b, tilt), (left, time_ms)
    assert compared > 100
    moving = [t for t in times if t > 1000 and not _dark(frames["MH1", t], profile)]
    assert any(_degrees(frames["MH1", t], pan) != _degrees(frames["MH2", t], pan) for t in moving)


def test_flick_shows_the_preset_state_lit_mid_cycle_and_the_base_color_resumes() -> None:
    """Over two 8-beat cycles each head is lit in its `flick` color (MH1/MH3 red, MH2/MH4
    blue) only within beats 3 to 5 of a cycle, between the two one-beat masks, and lit
    in the base white again in beats 6 to 8."""
    pipeline = _solo("masked_wheel_flick", 4)
    profile = _profiles(family_rig(HEADS))["MH1"]
    color = profile.discrete["color"]
    state_of = {s.value: name for name, s in color.states.items()}
    beats = physical_bars_grid(*([500.0] * 5)).beat_boundaries
    for index, fixture_id in enumerate(HEADS):
        flick = "red" if index % 2 == 0 else "blue"
        lit = [
            (f.time_ms, state_of[dict(f.channels)[color.offset]])
            for f in pipeline.frames
            if f.fixture_id == fixture_id and not _dark(dict(f.channels), profile)
        ]
        for cycle in (0, 8):
            window = (beats[cycle + 3] - EFFECT_GRID_MS, beats[cycle + 5])
            shown = [
                t for t, state in lit if state == flick and beats[cycle] <= t < beats[cycle + 8]
            ]
            assert shown, (fixture_id, cycle)
            assert all(window[0] <= t < window[1] for t in shown), (fixture_id, cycle)
            assert any(
                state == "white" and beats[cycle + 6] <= t < beats[cycle + 8] for t, state in lit
            ), (fixture_id, cycle)
        assert {state for _, state in lit} == {"white", flick}


@pytest.mark.parametrize("template_id", ["target_orbit", "mirror_wings"])
def test_continuous_families_never_go_dark_between_cycles(template_id: str) -> None:
    """Three cycles in one section: once a head is lit after entering, it stays lit to
    the section end."""
    grid = physical_bars_grid(*([500.0] * 7))
    rig, job = family_rig(HEADS), family_job(HEADS, **_STRICT)
    with physical_catalog():
        pipeline, segments = _render([(template_id, 1, 6)], grid, rig, job)
        _verify(pipeline, segments, rig, job)
    profile = _profiles(rig)["MH1"]
    section_end = grid.bar_boundaries[6]
    for fixture_id in HEADS:
        frames = [
            f for f in pipeline.frames if f.fixture_id == fixture_id and f.time_ms < section_end
        ]
        lit = [not _dark(dict(f.channels), profile) for f in frames]
        first = lit.index(True)
        assert frames[first].time_ms < grid.bar_boundaries[1]  # entered in the first bar
        assert all(lit[first:]), (fixture_id, frames[first + lit[first:].index(False)].time_ms)


def test_snap_holds_its_terminal_pose_lit_to_the_section_end() -> None:
    """One cue per head: after its one-beat move the head holds still, lit, until the
    section ends."""
    grid = physical_bars_grid(*([500.0] * 4))
    rig, job = family_rig(HEADS), family_job(HEADS, **_STRICT)
    with physical_catalog():
        pipeline, segments = _render([("finite_snap_hold", 1, 3)], grid, rig, job)
        _verify(pipeline, segments, rig, job)
    profile = _profiles(rig)["MH1"]
    section_end = grid.bar_boundaries[3]
    for fixture_id in HEADS:
        [cue] = [
            s
            for s in segments
            if s.fixture_id == fixture_id and TRANSACTION_METADATA_KEY not in s.metadata
        ]
        assert abs(cue.t1_ms - section_end) < EFFECT_GRID_MS
        held = [
            dict(f.channels)
            for f in pipeline.frames
            if f.fixture_id == fixture_id and cue.t0_ms + 600 <= f.time_ms < cue.t1_ms
        ]
        assert held and all(frame == held[0] for frame in held)
        assert not _dark(held[0], profile)
        assert float(_degrees(held[0], profile.axes["tilt"])) == pytest.approx(55.0, abs=0.01)


@pytest.mark.parametrize("template_id", FAMILY_IDS)
def test_family_renders_honestly_repeatably_and_without_a_head(template_id: str) -> None:
    """Two sections of the family, then another family: honest from the bytes, nothing
    kept dark, identical on a repeat, and removing a head leaves the others' frames."""
    grid = physical_bars_grid(500.0, 500.0, 430.0, 430.0, 500.0, 500.0, 500.0)
    other = "target_orbit" if template_id != "target_orbit" else "finite_snap_hold"
    sections = [(template_id, 1, 2), (template_id, 3, 4), (other, 5, 6)]
    rig, job = family_rig(HEADS), family_job(HEADS)
    present = tuple(h for h in HEADS if h != "MH2")
    with physical_catalog():
        pipeline, segments = _render(sections, grid, rig, job)
        _verify(pipeline, segments, rig, job)
        again, _ = _render(sections, grid, rig, job)
        subset, _ = _render(sections, grid, _without(rig, "MH2"), family_job(present))
    assert pipeline.render_record is not None
    assert pipeline.render_record["unplayable_totals"] == {}
    assert "admission_exclusions" not in pipeline.render_record  # none given: left out
    assert again.frames == pipeline.frames
    for fixture_id in present:
        assert _frames(subset, fixture_id) == _frames(pipeline, fixture_id), fixture_id


def _without(rig: FixtureGroup, gone: str) -> FixtureGroup:
    payload = rig.model_dump(mode="json")
    payload["fixtures"] = [f for f in payload["fixtures"] if f["fixture_id"] != gone]
    for preset in payload["presets"]["attributes"].values():
        preset["fixtures"].pop(gone, None)
    return FixtureGroup.model_validate(payload)
