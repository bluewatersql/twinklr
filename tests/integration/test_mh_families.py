"""The family catalog (P2.4c): admission, section succession and the families' frames.

The documents in `catalog/templates/moving_heads` load for every run, before
`--template-dir`. Every ordered pair of
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

from tests.support.moving_heads import (
    ALL_CATALOG_IDS,
    CATALOG_IDS,
    FAMILY_IDS,
    TEMPLATE_DIR,
    TEMPLATE_ID,
    allowed_rig,
    assert_honest_transactions,
    bars_grid,
    family_catalog,
    family_job,
    family_rig,
    hold_step,
    loop_template_doc,
    minimal_family_rig,
    overlay,
    p1_job,
    p1_rig,
    plan_section,
    registered_templates,
    sections_plan,
    sweep_step,
    with_preset,
    zoom_job,
    zoom_rig,
)
from twinklr.cli.main import _run_pipeline_async
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import AxisCapability, FixtureCapabilities, FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import SemanticGroupType
from twinklr.core.sequencer.models.template import TemplateDoc, TemplatePreset
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.compile.preset import apply_preset
from twinklr.core.sequencer.moving_heads.export.frame_encoder import frame_times
from twinklr.core.sequencer.moving_heads.pipeline import (
    VARIATION_PRESETS,
    RenderingPipeline,
    TemplateAdmission,
    admit_templates,
)
from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    TEMPLATE_CATALOG_DIR,
    load_template_document,
)
from twinklr.core.sequencer.moving_heads.templates.library import (
    validate_template_document,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

HEADS = ("MH1", "MH2", "MH3", "MH4")
_STRICT = {"reposition_fallback": "error", "on_unplayable": "error"}


# --- The documents ---------------------------------------------------------------------


def test_catalog_holds_the_families_each_explicit_and_degradable() -> None:
    """Each family (the six of P2.4c and the P2.5 zoom pilot) lints, sets on every step
    both start angles (no rig position preset is required), authors its
    dimmer, declares `drop_accent` and declares the reach and rate variants as presets:
    the ladder's `narrow` and `slow` first, then the variation variants (`wide`, `fast`
    and the four reach+rate combinations)."""
    paths = sorted(TEMPLATE_CATALOG_DIR.glob("*.json"))
    assert tuple(path.stem for path in paths) == ALL_CATALOG_IDS
    paths = [path for path in paths if path.stem in CATALOG_IDS]
    for path in paths:
        document = load_template_document(path)
        validate_template_document(document)
        template = document.template
        assert template.template_id == path.stem
        for step in template.steps:
            movement = step.movement
            assert movement.start_pan_deg is not None and movement.start_tilt_deg is not None
            assert step.component_refs is None, path.name
            assert step.dimmer is not None or step.visibility is not None
            assert step.reposition_fallback == "drop_accent", path.name
        assert [preset.preset_id for preset in document.presets] == [
            "narrow",
            "slow",
            "wide",
            "fast",
            "narrow+slow",
            "narrow+fast",
            "wide+slow",
            "wide+fast",
        ]
        assert {p.preset_id for p in document.presets} - {"narrow", "slow"} == VARIATION_PRESETS


def test_each_variation_variant_is_its_reach_and_rate_patches() -> None:
    """`wide` widens every extent `narrow` narrows by half again, `fast` halves every period
    `slow` doubles, and each combination is exactly its reach patch then its rate patch."""
    for path in sorted(TEMPLATE_CATALOG_DIR.glob("*.json")):
        document = load_template_document(path)
        steps = {step.step_id: step for step in document.template.steps}
        if all(step.movement.shape == "hold" for step in steps.values()):
            assert not document.presets  # Static references have no reach/rate variants.
            continue
        patches = {
            preset.preset_id: {
                step_id: patch.model_dump(exclude_none=True)
                for step_id, patch in preset.step_patches.items()
            }
            for preset in document.presets
        }
        for step_id, reach_patch in patches["narrow"].items():
            base = steps[step_id].movement.model_dump()
            assert patches["wide"][step_id]["movement"] == {
                key: round(base[key] * 1.5, 1) for key in reach_patch["movement"]
            }, path.name
        for step_id, rate_patch in patches["slow"].items():
            base = steps[step_id].movement.model_dump()
            assert patches["fast"][step_id]["movement"] == {
                key: base[key] / 2 for key in rate_patch["movement"]
            }, path.name
        for reach in ("narrow", "wide"):
            for rate in ("slow", "fast"):
                merged: dict[str, dict[str, dict[str, float]]] = {}
                for source in (patches[reach], patches[rate]):
                    for step_id, step_patch in source.items():
                        for group, fields in step_patch.items():
                            merged.setdefault(step_id, {}).setdefault(group, {}).update(fields)
                assert patches[f"{reach}+{rate}"] == merged, (path.name, reach, rate)


def test_a_family_preset_keeps_the_flick_overlay() -> None:
    """Applying a preset rebuilds the template; without its overlay a preset would play
    the flick family with no flick."""
    document = load_template_document(TEMPLATE_CATALOG_DIR / "masked_wheel_flick.json")
    overlays = document.template.overlays
    assert overlays
    for preset in document.presets:
        assert apply_preset(document.template, preset).overlays == overlays


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
async def test_run_offers_the_families_and_template_dir_documents(
    tmp_path: Path,
) -> None:
    with family_catalog(admit=False):
        offered = await _cli_offer(tmp_path, family_job(HEADS), family_rig(HEADS), TEMPLATE_DIR)

    assert sorted(offered) == sorted([*ALL_CATALOG_IDS, TEMPLATE_ID])


@pytest.mark.parametrize(
    "spelling",
    [
        pytest.param(TEMPLATE_CATALOG_DIR, id="resolved"),
        pytest.param(TEMPLATE_CATALOG_DIR / ".." / TEMPLATE_CATALOG_DIR.name, id="unresolved"),
    ],
)
@pytest.mark.asyncio
async def test_template_dir_naming_the_catalog_loads_nothing_twice(
    tmp_path: Path, spelling: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with (
        family_catalog(admit=False),
        patch(
            "twinklr.cli.main.load_templates_from_directory",
            side_effect=AssertionError("--template-dir loaded"),
        ),
    ):
        offered = await _cli_offer(tmp_path, family_job(HEADS), family_rig(HEADS), spelling)

    assert tuple(sorted(offered)) == ALL_CATALOG_IDS
    # Rich wraps long paths; the words survive with their spacing normalized.
    assert "already admitted" in " ".join(capsys.readouterr().out.split())


@pytest.mark.asyncio
async def test_runs_in_one_process_admit_the_catalog_once(tmp_path: Path) -> None:
    """A second run reuses the catalog the first admitted instead of failing on it."""
    with family_catalog(admit=False):
        for _ in range(2):
            offered = await _cli_offer(tmp_path, family_job(HEADS), family_rig(HEADS))
            assert tuple(sorted(offered)) == ALL_CATALOG_IDS


# --- Section succession ----------------------------------------------------------------


def test_template_with_an_unknown_bound_term_is_excluded_naming_fixture_and_term() -> None:
    """A template that plays at every gate placement on a head whose tilt latency is
    unknown still has no worst-case entry bound there, so it is left out of the offer;
    one with no cue on that head is admitted."""
    payload = p1_rig().model_dump(mode="json")
    payload["fixtures"][0]["config"]["physical_profile"]["axes"]["tilt"]["latency_ms"] = None
    rig = FixtureGroup.model_validate(payload)
    still = loop_template_doc("p24c_still", [hold_step("still", 0.0)])
    right = loop_template_doc(
        "p24c_still_right", [hold_step("still", 0.0, target=SemanticGroupType.RIGHT)]
    )
    job = p1_job()
    with registered_templates(still, right):
        admission = admit_templates(
            ["p24c_still", "p24c_still_right"],
            beat_grid=bars_grid(500.0, 500.0, 500.0),
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
    return admit_templates(
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
    grid = bars_grid(500.0, 300.0, 500.0, 500.0)
    rig, job = _late_mh3_rig(), family_job(HEADS)
    with family_catalog():
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


_BOTH = ("narrow", "slow")
"""Every family's ladder presets, in the order each declares them."""
_ALL = (*_BOTH, "wide", "fast", "narrow+slow", "narrow+fast", "wide+slow", "wide+fast")
"""Every family's presets: the ladder's, then the variation variants."""


@pytest.mark.parametrize("beats_per_bar", [2, 3, 6])
@pytest.mark.parametrize("zoom", [False, True], ids=["family-rig", "zoom-rig"])
def test_in_other_meters_every_family_is_offered_with_both_variants(
    zoom: bool, beats_per_bar: int
) -> None:
    """The families are authored in 4/4, where their 2-bar cycles hold whole movement
    periods. In 2/4, 3/4 and 6/8 a cycle that would end mid-period, or before the flick's
    overlay ends, grows to whole bars that hold it (`whole_period_cycle`), so no family
    jumps at its cycle boundary: every family and variant is admitted, each playing its
    base when a section names no preset, and each entry dip is reported; only the snap's
    fast variants, which play as its base, `narrow` and `wide` after its own base (its lift
    is inside the dark entry window, so its rate does not show), are left out, and the gate
    says so."""
    rig, job = (
        (zoom_rig(HEADS), zoom_job(HEADS)) if zoom else (family_rig(HEADS), family_job(HEADS))
    )
    template_ids = CATALOG_IDS if zoom else FAMILY_IDS
    with family_catalog():
        admission = _gate(template_ids, _meter_grid(beats_per_bar, 500.0, 10), rig, job)

    assert admission.admitted == template_ids
    assert admission.exclusions == ()
    snap = {"fast", "narrow+fast", "wide+fast"}  # its rate does not show
    assert {(e["template_id"], e["preset_id"]) for e in admission.preset_exclusions} == {
        ("finite_snap_hold", p) for p in snap
    }
    assert admission.admitted_presets == {
        t: tuple(p for p in _ALL if t != "finite_snap_hold" or p not in snap) for t in template_ids
    }
    assert admission.effective_preset == dict.fromkeys(template_ids)
    assert admission.entry_dips.keys() == set(template_ids)


def _with_preset(document: TemplateDoc, preset_id: str, patches: dict[str, Any]) -> TemplateDoc:
    """`document` declaring one preset of `patches` by step id."""
    preset = TemplatePreset.model_validate({"preset_id": preset_id, "step_patches": patches})
    return TemplateDoc(template=document.template, presets=[preset])


def test_a_failing_presets_poses_stay_out_of_every_entry_dip() -> None:
    """A preset that compiles at bar 1 but whose own cues cannot be repositioned between
    (a 120-degree sweep jumping back at every cycle) is left out, and its poses widen no
    entry envelope: every admitted template's dip is as if it were not declared."""
    rig, job = p1_rig(), p1_job()
    grid = bars_grid(500.0, 500.0, 500.0)
    still = loop_template_doc("p3_still", [hold_step("still", 0.0)])
    aim = loop_template_doc("p3_aim", [hold_step("aim", 0.0)])
    sweep = {"shape": "linear", "mode": "finite", "pan_extent_deg": 120.0, "period_beats": 4.0}
    swept = _with_preset(aim, "sweep", {"aim": {"movement": sweep}})
    with registered_templates(still, swept):
        admission = _gate(["p3_aim", "p3_still"], grid, rig, job)
    with registered_templates(still, aim):
        undeclared = _gate(["p3_aim", "p3_still"], grid, rig, job)

    assert admission.admitted == ("p3_aim", "p3_still")
    assert admission.admitted_presets == {"p3_aim": (), "p3_still": ()}
    [exclusion] = admission.preset_exclusions
    assert (exclusion["template_id"], exclusion["preset_id"]) == ("p3_aim", "sweep")
    assert "jumps across the cue" in exclusion["reason"]
    assert admission.entry_dips == undeclared.entry_dips


def test_a_base_without_an_entry_bound_is_passed_over_for_a_preset_with_one() -> None:
    """Red's settle time is unknown. The base flicks to red over the first two beats of
    its one cycle, entered from a red initial state, so it plays at every placement, but
    beside white cues it has no entry bound and is not admitted. Its `late` preset starts
    after the flick, plays only white and has a bound, so the template is admitted
    through it: `late` is its effective variant, the base's failure is recorded as a
    preset exclusion naming no preset, and the dip is `late`'s."""
    payload = p1_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        red = fixture["config"]["physical_profile"]["discrete"]["color"]["states"]["red"]
        red["settle_ms"] = None
    rig = FixtureGroup.model_validate(payload)
    policy = p1_job().model_dump(mode="json")
    for state in policy["moving_heads"]["initial_states"].values():
        state["discrete_states"]["color"] = "red"
    job = JobConfig.model_validate(policy)
    still = loop_template_doc("p3_still", [hold_step("still", 0.0)])
    flick = _with_preset(
        loop_template_doc(
            "p3_flick",
            [sweep_step("look", 0.0, 0.0, color="white")],
            mode="ONCE",
            overlays=[overlay("color", 0.0, 2.0, 0.5, "red")],
        ),
        "late",
        {
            "look": {
                "movement": {"period_beats": 2.0},
                "timing": {"base_timing": {"start_offset_bars": 0.5, "duration_bars": 0.5}},
            }
        },
    )
    with registered_templates(still, flick):
        admission = _gate(["p3_flick", "p3_still"], bars_grid(500.0, 500.0, 500.0), rig, job)

    assert admission.admitted == ("p3_flick", "p3_still")
    assert admission.exclusions == ()
    assert admission.effective_preset == {"p3_flick": "late", "p3_still": None}
    assert admission.admitted_presets == {"p3_flick": ("late",), "p3_still": ()}
    [exclusion] = admission.preset_exclusions
    assert (exclusion["template_id"], exclusion["preset_id"]) == ("p3_flick", None)
    assert exclusion["reason"].startswith("template 'p3_flick': fixture")
    assert "discrete.color.states.red.settle_ms unknown" in exclusion["reason"]
    assert admission.entry_dips.keys() == {"p3_flick", "p3_still"}


def _unknown_settle_rig(**states: str) -> FixtureGroup:
    """`p1_rig` whose `wheel` states named by keyword have no known settle time."""
    payload = p1_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        discrete = fixture["config"]["physical_profile"]["discrete"]
        for state, wheel in states.items():
            discrete[wheel]["states"][state]["settle_ms"] = None
    return FixtureGroup.model_validate(payload)


def _job_holding(**discrete_states: str) -> JobConfig:
    """`p1_job` whose initial states hold these wheel states."""
    policy = p1_job().model_dump(mode="json")
    for state in policy["moving_heads"]["initial_states"].values():
        state["discrete_states"] |= discrete_states
    return JobConfig.model_validate(policy)


def test_a_rung_without_an_entry_bound_leaves_the_envelope_of_every_dip() -> None:
    """The base pans out to 170 degrees and, flicking to red (no known settle), has no
    entry bound; its `late` preset holds pan 0. With the base gone, every dip is the
    one measured without its 170-degree pose, as if `late` were the template's only
    variant."""
    rig, job = _unknown_settle_rig(red="color"), _job_holding(color="red")
    still = loop_template_doc("p3_still", [hold_step("still", 0.0, color="white")])
    far = _with_preset(
        loop_template_doc(
            "p3_flick",
            [sweep_step("look", 170.0, 0.0, color="white")],
            mode="ONCE",
            overlays=[overlay("color", 0.0, 2.0, 0.5, "red")],
        ),
        "late",
        {
            "look": {
                "movement": {"period_beats": 2.0, "start_pan_deg": 0.0},
                "timing": {"base_timing": {"start_offset_bars": 0.5, "duration_bars": 0.5}},
            }
        },
    )
    alone = loop_template_doc(
        "p3_flick",
        [sweep_step("look", 0.0, 0.0, period_beats=2.0, color="white", start=0.5, duration=0.5)],
        mode="ONCE",
    )
    grid = bars_grid(500.0, 500.0, 500.0)
    with registered_templates(still, far):
        admission = _gate(["p3_flick", "p3_still"], grid, rig, job)
    with registered_templates(still, alone):
        only_late = _gate(["p3_flick", "p3_still"], grid, rig, job)

    assert admission.effective_preset == {"p3_flick": "late", "p3_still": None}
    assert admission.entry_dips == only_late.entry_dips


def test_a_rung_losing_its_bound_only_through_a_failing_rung_keeps_it() -> None:
    """Neither red nor the gobo's dots has a known settle time, and the heads start on
    red and dots. The flick turns to star (known) and flicks red over white: red among the
    held colors leaves it no entry bound on its own. The still template holds dots, so it
    has a bound only while dots is the only gobo state held; the flick's star breaks
    that. Once the flick leaves the envelope, the still template's bound returns, and it
    is admitted."""
    rig = _unknown_settle_rig(red="color", dots="gobo")
    job = _job_holding(color="red", gobo="dots")
    still = loop_template_doc("p3_still", [hold_step("still", 0.0, color="white", gobo="dots")])
    flick = loop_template_doc(
        "p3_flick",
        [sweep_step("look", 0.0, 0.0, color="white", gobo="star")],
        mode="ONCE",
        overlays=[overlay("color", 0.0, 2.0, 0.5, "red")],
    )
    with registered_templates(still, flick):
        admission = _gate(["p3_flick", "p3_still"], bars_grid(500.0, 500.0, 500.0), rig, job)

    assert admission.admitted == ("p3_still",)
    [exclusion] = admission.exclusions
    assert exclusion["template_id"] == "p3_flick"
    assert "discrete.color.states.red.settle_ms unknown" in exclusion["reason"]
    assert admission.entry_dips.keys() == {"p3_still"}


def _preset_plan(*sections: tuple[str, str | None, int, int]) -> ChoreographyPlan:
    """`sections_plan` of `(template_id, preset_id, start_bar, end_bar)`."""
    plan = sections_plan(*((t, start, end) for t, _, start, end in sections))
    return plan.model_copy(
        update={
            "sections": [
                with_preset(section, preset_id)
                for section, (_, preset_id, _, _) in zip(plan.sections, sections, strict=True)
            ]
        }
    )


def _render_admitted(
    plan: ChoreographyPlan,
    grid: BeatGrid,
    rig: FixtureGroup,
    job: JobConfig,
    admission: TemplateAdmission | None,
) -> RenderingPipeline:
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=grid,
        fixture_group=rig,
        job_config=job,
        admission=admission,
    )
    pipeline.render()
    return pipeline


def _jumping_aim(*presets: tuple[str, float]) -> TemplateDoc:
    """`p3_aim`: a one-bar cycle sweeping pan 120 degrees and jumping back at every
    cycle, which no head can do lit, with a preset per `(preset_id, pan extent)`."""
    return TemplateDoc(
        template=loop_template_doc("p3_aim", [sweep_step("aim", 0.0, 120.0)]).template,
        presets=[
            TemplatePreset.model_validate(
                {
                    "preset_id": preset_id,
                    "step_patches": {"aim": {"movement": {"pan_extent_deg": extent}}},
                }
            )
            for preset_id, extent in presets
        ],
    )


def test_a_section_renders_the_effective_variant_unless_it_names_an_admitted_preset() -> None:
    """`p3_aim`'s base and its `wild` preset jump at every cycle and are not admitted;
    `calm` does not move, so it is the template's effective variant. A section naming no
    preset, `wild` or a preset the template does not declare renders `calm`, the last
    two with a warning naming why and what plays instead; naming `calm` renders it with
    no warning. Without the gate's result the base plays. The trace records the effective
    variant and each rung's exclusion."""
    rig, job = p1_rig(), p1_job()
    grid = bars_grid(500.0, 500.0, 500.0)
    with registered_templates(_jumping_aim(("wild", 150.0), ("calm", 0.0))):
        admission = _gate(["p3_aim"], grid, rig, job)
        runs = {
            (preset, gated): _render_admitted(
                _preset_plan(("p3_aim", preset, 1, 2)),
                grid,
                rig,
                job,
                admission if gated else None,
            )
            for preset, gated in [
                (None, True),
                ("wild", True),
                ("undeclared", True),
                ("calm", True),
                (None, False),
            ]
        }

    assert admission.effective_preset == {"p3_aim": "calm"}
    assert admission.admitted_presets == {"p3_aim": ("calm",)}
    assert [(e["template_id"], e["preset_id"]) for e in admission.preset_exclusions] == [
        ("p3_aim", None),
        ("p3_aim", "wild"),
    ]
    calm = runs["calm", True].frames
    assert runs[None, True].frames == runs["wild", True].frames == calm
    assert runs["undeclared", True].frames == calm
    assert runs[None, False].frames != calm
    for preset in (None, "calm"):
        record = runs[preset, True].render_record
        assert record is not None
        assert not [d for d in record["diagnostics"] if "preset" in d["message"]]
    record = runs["wild", True].render_record
    assert record is not None
    [warning] = [d for d in record["diagnostics"] if "preset 'wild'" in d["message"]]
    assert "is not admitted for template 'p3_aim'" in warning["message"]
    assert "jumps across the cue" in warning["message"]
    assert warning["message"].endswith("the renderer applies its effective variant 'calm'")
    assert (warning["code"], warning["severity"], warning["action"]) == (
        "unsupported_attribute",
        "warning",
        "unchanged",
    )
    [undeclared] = [
        d
        for d in runs["undeclared", True].render_record["diagnostics"]
        if "undeclared" in d["message"]
    ]
    assert "is not declared by template 'p3_aim'" in undeclared["message"]
    assert undeclared["message"].endswith("the renderer applies its effective variant 'calm'")
    assert record["admission_preset_exclusions"] == [dict(e) for e in admission.preset_exclusions]
    assert record["admission_effective_presets"] == {"p3_aim": "calm"}
    assert "admission_exclusions" not in record
    ungated = runs[None, False].render_record or {}
    assert "admission_preset_exclusions" not in ungated
    assert "admission_effective_presets" not in ungated


def test_a_template_dir_template_is_not_laddered_and_refuses_on_any_failing_variant() -> None:
    """A template outside the shipped catalog (not `excludable`) is not admitted through
    a later variant: one whose base fails refuses the run even though its `calm` preset
    passes, naming every failing variant."""
    rig, job = p1_rig(), p1_job()
    with (
        registered_templates(_jumping_aim(("wild", 150.0), ("calm", 0.0))),
        pytest.raises(UnsupportedRenderModeError, match="cannot render") as refused,
    ):
        admit_templates(
            ["p3_aim"],
            beat_grid=bars_grid(500.0, 500.0, 500.0),
            fixture_group=rig,
            initial_states=job.moving_heads.initial_states,
            failure_mode=job.moving_heads.reposition_fallback,
        )
    message = str(refused.value)
    assert "template 'p3_aim': dark repositioning" in message
    assert "template 'p3_aim', preset 'wild': dark repositioning" in message
    assert "preset 'calm'" not in message


def test_a_preset_the_gate_did_not_admit_renders_the_base_when_the_base_is_admitted() -> None:
    """The base holds still and is admitted; its `wild` preset jumps and is not. A
    section naming `wild` renders the base, exactly as one naming an undeclared preset,
    with the warning that no preset applies; the trace records no effective variant,
    since every admitted template plays its base."""
    rig, job = p1_rig(), p1_job()
    grid = bars_grid(500.0, 500.0, 500.0)
    wild = {"shape": "linear", "mode": "finite", "pan_extent_deg": 120.0, "period_beats": 4.0}
    still = _with_preset(
        loop_template_doc("p3_aim", [hold_step("aim", 0.0)]),
        "wild",
        {"aim": {"movement": wild}},
    )
    with registered_templates(still):
        admission = _gate(["p3_aim"], grid, rig, job)
        runs = {
            preset: _render_admitted(
                _preset_plan(("p3_aim", preset, 1, 2)), grid, rig, job, admission
            )
            for preset in (None, "wild", "undeclared")
        }

    assert admission.effective_preset == {"p3_aim": None}
    assert runs["wild"].frames == runs["undeclared"].frames == runs[None].frames
    record = runs["wild"].render_record
    assert record is not None
    [warning] = [d for d in record["diagnostics"] if "preset 'wild'" in d["message"]]
    assert "is not admitted for template 'p3_aim'" in warning["message"]
    assert warning["message"].endswith("the renderer applies no preset")
    assert "admission_effective_presets" not in record


_FAST_BEAT_MS = 340.0
"""About 176 BPM, the fastest bars the succession tests use."""


@pytest.fixture(scope="module")
def fast_admission() -> TemplateAdmission:
    """The gate over every family on the family rig, its shortest beats fast."""
    job = family_job(HEADS, **_STRICT)
    with family_catalog():
        return admit_templates(
            list(FAMILY_IDS),
            beat_grid=bars_grid(500.0, _FAST_BEAT_MS, _FAST_BEAT_MS, 500.0),
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
    grid = bars_grid(*([_FAST_BEAT_MS] * (2 * len(sections) + 1)))
    rig, job = family_rig(HEADS), family_job(HEADS, **_STRICT)
    with family_catalog():
        pipeline, segments = _render(sections, grid, rig, job)
        _verify(pipeline, segments, rig, job)
    assert pipeline.render_record is not None
    assert pipeline.render_record["unplayable_totals"] == {}


# --- The families' frames --------------------------------------------------------------


def _render(
    sections: list[tuple[str, int, int]], grid: BeatGrid, rig: FixtureGroup, job: JobConfig
) -> tuple[RenderingPipeline, list[FixtureSegment]]:
    pipeline = RenderingPipeline(
        choreography_plan=sections_plan(*sections),
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
    grid = bars_grid(*([500.0] * (bars + 1)))
    rig, job = family_rig(HEADS), family_job(HEADS, **_STRICT)
    with family_catalog():
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
    beats = bars_grid(*([500.0] * 5)).beat_boundaries
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
    grid = bars_grid(*([500.0] * 7))
    rig, job = family_rig(HEADS), family_job(HEADS, **_STRICT)
    with family_catalog():
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
    grid = bars_grid(*([500.0] * 4))
    rig, job = family_rig(HEADS), family_job(HEADS, **_STRICT)
    with family_catalog():
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
    grid = bars_grid(500.0, 500.0, 430.0, 430.0, 500.0, 500.0, 500.0)
    other = "target_orbit" if template_id != "target_orbit" else "finite_snap_hold"
    sections = [(template_id, 1, 2), (template_id, 3, 4), (other, 5, 6)]
    rig, job = family_rig(HEADS), family_job(HEADS)
    present = tuple(h for h in HEADS if h != "MH2")
    with family_catalog():
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


# --- Profile defaults (C1.0) -----------------------------------------------------------


def test_a_minimal_rig_is_admitted_and_delivered_byte_identical_to_the_explicit_rig(
    tmp_path: Path,
) -> None:
    """One minimal profile in `base_config` and `position_index` in place of a topology:
    the gate admits what it admits on the explicit rig (a profile per head, a declared
    topology), and the render delivers the same frames and the same `.xsq`. Only the
    trace differs: it lists, per head, what the profile left to its defaults."""
    grid = bars_grid(*([500.0] * 7))
    sections = [("mirror_wings", 1, 2), ("masked_wheel_flick", 3, 4), ("fly_out_cascade", 5, 6)]
    job = family_job(HEADS, **_STRICT)
    rigs = {"explicit": (family_rig(HEADS), job), "minimal": (minimal_family_rig(HEADS), job)}
    pipelines: dict[str, RenderingPipeline] = {}
    admissions: dict[str, TemplateAdmission] = {}
    with family_catalog():
        for name, (rig, job) in rigs.items():
            admissions[name] = _gate(CATALOG_IDS, grid, rig, job)
            pipelines[name] = RenderingPipeline(
                choreography_plan=sections_plan(*sections),
                beat_grid=grid,
                fixture_group=rig,
                job_config=job,
                output_path=tmp_path / name / "song.xsq",
                admission=admissions[name],
            )
            pipelines[name].render()

    assert admissions["minimal"] == admissions["explicit"]
    assert {template_id for template_id, _, _ in sections} <= set(admissions["explicit"].admitted)
    explicit, minimal = pipelines["explicit"], pipelines["minimal"]
    assert minimal.frames == explicit.frames
    assert (tmp_path / "minimal" / "song.xsq").read_bytes() == (
        tmp_path / "explicit" / "song.xsq"
    ).read_bytes()
    assert explicit.render_record is not None and minimal.render_record is not None
    for record in explicit.render_record["fixtures"]:
        assert "defaulted" not in record
    profile = minimal_family_rig(HEADS).expand_fixtures()[0].config.physical_profile
    assert profile is not None and "axes.pan.unit" in profile.defaulted
    for record in minimal.render_record["fixtures"]:
        assert record["defaulted"] == list(profile.defaulted)


# --- Variation variants (song-intent W10a) ---------------------------------------------


def _slow_heads(speed: float) -> FixtureGroup:
    """`family_rig` whose pan and tilt travel at `speed` degrees a second."""
    payload = family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = speed
    return FixtureGroup.model_validate(payload)


def test_every_combined_variant_is_dry_compiled_never_inferred() -> None:
    """At 240 BPM on 720-degree heads the cascades' `fast` passes (up to about 306 BPM) and
    so does `wide` (about 407), but `wide+fast` does not (about 204): speeds multiply, so the
    gate compiles each combination and judges it alone; it plays only fitted to the rig
    (`fitting`), at a strength the gate compiled, while `fast` and `wide` play as authored."""
    with family_catalog():
        admission = _gate(
            FAMILY_IDS, bars_grid(*([250.0] * 16)), family_rig(HEADS), family_job(HEADS)
        )

    for cascade in ("fly_in_cascade", "fly_out_cascade"):
        offered = admission.offer.templates[cascade]
        assert "fast" in offered.variants and "wide" in offered.variants
        assert "fast" not in offered.fitted and "wide" not in offered.fitted
        assert "wide+fast" in offered.variants and offered.fitted["wide+fast"]


def test_variation_variants_never_decide_admission_or_the_effective_variant() -> None:
    """On 300-degree heads at 170 BPM the cascades' `fast` and `wide` fail while
    `narrow+fast` passes: the families are admitted and play their effective variant by
    the ladder (base, `narrow`, `slow`) exactly as before the variation variants existed;
    the variation variants that pass are offered, `wide` only fitted to the rig
    (`fitting`), and `fast`, which no reduced reach at its halved period fits, is recorded."""
    with family_catalog():
        admission = _gate(
            FAMILY_IDS, bars_grid(*([60_000 / 170] * 16)), _slow_heads(300.0), family_job(HEADS)
        )

    assert set(admission.effective_preset.values()) <= {None, "narrow", "slow"}
    cascade = admission.offer.templates["fly_in_cascade"]
    assert cascade.fitted.keys() == {"wide"}
    assert "narrow+fast" in cascade.variants and "fast" not in cascade.variants
    refused = {
        (e["template_id"], e["preset_id"])
        for e in admission.preset_exclusions
        if e["preset_id"] in VARIATION_PRESETS
    }
    assert ("fly_in_cascade", "fast") in refused and ("fly_in_cascade", "wide") not in refused


def test_a_variation_variant_moves_wider_or_faster_than_the_base() -> None:
    """Each family's `wide` reaches further on the axes `narrow` narrows and `fast` turns
    over more often on the steps `slow` slows, read from the compiled pan and tilt."""
    from twinklr.core.sequencer.models.context import TemplateCompileContext
    from twinklr.core.sequencer.models.enum import ChannelName
    from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
    from twinklr.core.sequencer.models.moving_heads.topology import rig_topology
    from twinklr.core.sequencer.moving_heads.compile.template_compiler import compile_template
    from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
    from twinklr.core.sequencer.moving_heads.templates import get_template
    from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map, cue_limits

    rig = zoom_rig(HEADS)
    grid = bars_grid(*([500.0] * 4))
    phase_map = build_musical_phase_map(grid)
    fixtures = build_fixture_contexts(rig_profile_from_fixture_group(rig), rig)

    def motion(template_id: str, preset_id: str | None) -> tuple[float, int]:
        """The widest pan or tilt swing on MH1 and how often its direction turns."""
        document = get_template(template_id)
        preset = next((p for p in document.presets if p.preset_id == preset_id), None)
        context = TemplateCompileContext(
            section_id="s",
            template_id=template_id,
            preset_id=preset_id,
            fixtures=fixtures,
            beat_grid=grid,
            start_bar=1,
            duration_bars=4,
            presets=rig.presets,
            topology=rig_topology(rig),
            fixture_group_id=rig.group_id,
        )
        start_limit, end_limit = cue_limits(phase_map, int(grid.duration_ms))
        cues = compile_template(
            document.template,
            context,
            preset,
            phase_map=phase_map,
            start_limit_ms=start_limit,
            end_limit_ms=end_limit,
        )
        values: dict[ChannelName, list[float]] = {ChannelName.PAN: [], ChannelName.TILT: []}
        for cue in sorted(cues.segments, key=lambda c: c.t0_ms):
            if cue.fixture_id != "MH1":
                continue
            for channel, series in values.items():
                held = cue.channels.get(channel)
                points = getattr(getattr(held, "physical", None), "points", ())
                series += [point.value for point in points]
        swing = max(max(s) - min(s) for s in values.values() if s)
        turns = 0
        for series in values.values():
            steps = [b - a for a, b in pairwise(series) if b != a]
            turns += sum(1 for a, b in pairwise(steps) if a * b < 0)
        return swing, turns

    with family_catalog():
        for template_id in CATALOG_IDS:
            base_swing, base_turns = motion(template_id, None)
            wide_swing, _ = motion(template_id, "wide")
            _, fast_turns = motion(template_id, "fast")
            assert wide_swing > base_swing, template_id
            if template_id != "finite_snap_hold":  # one move, then a hold: no turns
                assert fast_turns > base_turns, template_id


@pytest.mark.parametrize("zoom", [False, True], ids=["family-rig", "zoom-rig"])
def test_a_rig_whose_allowed_ranges_are_narrower_than_physical_runs_end_to_end(
    zoom: bool,
) -> None:
    """Allowed (operable) ranges narrower than physical on pan, tilt and zoom, as real rigs
    declare: the gate admits, its offer facts are bounded over the allowed range (the
    darkness a transition's move may need was once measured over the physical range and
    raised), and repair and a render with variants, a motif and transitions play inside
    the allowed range."""
    from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
    from twinklr.core.sequencer.moving_heads.song_intent import offer_for_prompt

    rig = allowed_rig(zoom_rig(HEADS) if zoom else family_rig(HEADS))
    job = zoom_job(HEADS) if zoom else family_job(HEADS)
    template_ids = CATALOG_IDS if zoom else FAMILY_IDS
    grid = bars_grid(*([500.0] * 16))
    with family_catalog():
        admission = _gate(template_ids, grid, rig, job)
        assert admission.admitted
        assert admission.offer.dark_change_ms is not None
        assert offer_for_prompt(admission.offer, {}, ["s1", "s2", "s3"])
        first, second = admission.admitted[0], admission.admitted[-1]
        sections = [
            plan_section("s1", 1, 4, first, motif_id="m"),
            plan_section(
                "s2",
                5,
                8,
                second,
                motif_id="m",
                variation="WIDEN",
                transitions=[
                    {
                        "edge": "ENTRY",
                        "mode": "crossfade",
                        "length": "BAR",
                        "curve": "linear",
                        "split": "HALF",
                        "channels": [],
                    }
                ],
            ),
            plan_section(
                "s3",
                9,
                12,
                first,
                variation="FASTER",
                transitions=[
                    {
                        "edge": "ENTRY",
                        "mode": "snap",
                        "length": "BEAT",
                        "curve": "linear",
                        "split": "QUARTER",
                        "channels": [],
                    }
                ],
            ),
        ]
        repaired = repair_rig_intent(
            ChoreographyPlan(sections=sections, overall_strategy=""), admission.offer, {}, grid
        )
        pipeline = RenderingPipeline(
            choreography_plan=repaired,
            beat_grid=grid,
            fixture_group=rig,
            job_config=job,
            media_file="silence.wav",
            admission=admission,
        )
        pipeline.render()

    profile = rig.expand_fixtures()[0].config.physical_profile
    assert profile is not None
    for name, axis in profile.axes.items():
        if name == "dimmer":
            continue
        low, high = sorted(axis.dmx_word(v) for v in axis.operable_range)
        for frame in pipeline.frames:
            channels = dict(frame.channels)
            word = channels[axis.coarse_offset]
            if axis.fine_offset is not None:
                word = word << 8 | channels[axis.fine_offset]
            assert low <= word <= high, (frame.fixture_id, frame.time_ms, name, word)


def test_an_offer_fact_that_cannot_be_computed_is_unknown_not_a_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The darkness bound is an offer fact: where it cannot be computed it is unknown (repair
    then warns on every transition window it would have bounded) and the gate goes on."""
    from twinklr.core.sequencer.moving_heads import song_intent

    def broken(*_: Any, **__: Any) -> int:
        raise ValueError("an unforeseen profile")

    with patch.object(song_intent, "worst_case_entry_ms", broken):
        offer = song_intent.rig_offer(family_rig(HEADS), bars_grid(*([500.0] * 4)))

    assert offer.dark_change_ms is None
    assert "is unknown on" in caplog.text


def test_the_offer_times_a_full_crossing_over_the_allowed_range() -> None:
    """How long the slowest head takes to cross its whole range is measured over the range
    it may be commanded across (allowed), not the physical one: 285 of pan at 720 degree/s
    is 396 ms (not 750), 125 of tilt 174 ms (not 375)."""
    from twinklr.core.sequencer.moving_heads.song_intent import rig_offer

    grid = bars_grid(*([500.0] * 4))

    assert rig_offer(family_rig(HEADS), grid).full_travel_ms == {"pan": 750, "tilt": 375}
    assert rig_offer(allowed_rig(family_rig(HEADS)), grid).full_travel_ms == {
        "pan": 396,
        "tilt": 174,
    }
