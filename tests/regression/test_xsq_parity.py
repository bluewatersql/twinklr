"""Post-refactor MH `.xsq` parity against a pre-refactoring baseline.

Two levels:

1. Pin the pre-refactor baseline's sophistication metrics so the extractor cannot drift
   and the reference numbers are locked as the go-forward baseline.
2. Replay the baseline's (pre-refactor) choreography plan through the **current**
   deterministic renderer and assert the emitted MH `.xsq` is on par — same emission
   modality, 20 ms grid, base+transition layering, comparable effect volume, and retained
   value-curve richness. The plan is fixed (no LLM), so this isolates the refactor's effect
   on the deterministic plan->`.xsq` path.

Rig-specific values (element_count, exact channel width) depend on the physical rig and are
not asserted here: the baseline used the owner's private 4x16-channel rig, so we replay on
the in-repo `mh4_minimal` rig (same fixture count) and assert plan-driven richness only.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from tests.golden.harness import RIGS, build_fixture_group
from tests.regression.xsq_metrics import extract_xsq_metrics
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.display_stages import DisplayRenderStage
from twinklr.core.sequencer.display.xlights_mapping import XLightsGroupMapping, XLightsMapping
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.planning.group_plan import GroupPlanSet
from twinklr.core.sequencer.templates.group.models.choreography import ChoreoGroup, ChoreographyGraph
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

_BASELINES = Path(__file__).parent / "baselines"
_MH_XSQ = _BASELINES / "11_need_a_favor_twinklr_mh.xsq"
_MH_PLAN = _BASELINES / "11_need_a_favor.choreography_plan.json"
_MH_META = _BASELINES / "11_need_a_favor.pipeline_metadata.json"
_MH_METRICS = _BASELINES / "11_need_a_favor.metrics.json"

# Display baseline (multi-effect-type). Its head predates the current mediaFile
# requirement, so the tracked fixture carries a minimal mediaFile stub added for
# parseability; effect/EffectDB content is the original pre-refactor output.
_DISPLAY_XSQ = _BASELINES / "02_rudolph_display.xsq"
_DISPLAY_METRICS = _BASELINES / "02_rudolph_display.metrics.json"

# Display replay-render fixtures. The pre-refactor plan references 38 group templates; 10 of
# them were retired from the recipe catalog after the baseline was generated (Feb 2026), so a
# faithful replay of the *whole* plan is no longer possible from any current catalog. We
# instead replay the resolvable subset against a self-contained snapshot of exactly the
# recipes it needs (committed alongside), which reproduces the baseline's effect vocabulary,
# layer depth, and timing deterministically and hermetically (no dependence on the owner's
# gitignored local catalog).
_DISPLAY_PLAN = _BASELINES / "02_rudolph.group_plan_set.json"
_DISPLAY_RECIPES = _BASELINES / "02_rudolph.display_recipes.json"
_DISPLAY_REPLAY_METRICS = _BASELINES / "02_rudolph_display.replay.metrics.json"


def _load_display_recipe_catalog() -> RecipeCatalog:
    recipes = [EffectRecipe.model_validate(item) for item in json.loads(_DISPLAY_RECIPES.read_text())]
    return RecipeCatalog(recipes)


def _filter_plan_to_recipes(plan_set: GroupPlanSet, recipe_ids: set[str]) -> GroupPlanSet:
    """Drop placements whose template is absent from ``recipe_ids`` (retired recipes)."""
    sections = []
    for section in plan_set.section_plans:
        lanes = []
        for lane in section.lane_plans:
            coords = []
            for coord in lane.coordination_plans:
                placements = [p for p in coord.placements if p.template_id in recipe_ids]
                if placements:
                    coords.append(coord.model_copy(update={"placements": placements}))
            if coords:
                lanes.append(lane.model_copy(update={"coordination_plans": coords}))
        if lanes:
            sections.append(section.model_copy(update={"lane_plans": lanes}))
    return plan_set.model_copy(update={"section_plans": sections})


def _display_group_ids(plan_set: GroupPlanSet) -> list[str]:
    ids: set[str] = set()
    for section in plan_set.section_plans:
        for lane in section.lane_plans:
            for coord in lane.coordination_plans:
                ids.update(t.id for t in coord.targets)
                ids.update(p.target.id for p in coord.placements)
    return sorted(ids)


def _replay_display(plan_set: GroupPlanSet, catalog: RecipeCatalog, out: Path):
    group_ids = _display_group_ids(plan_set)
    graph = ChoreographyGraph(
        graph_id="rudolph_replay",
        groups=[ChoreoGroup(id=g, role=g) for g in group_ids],
    )
    mapping = XLightsMapping(
        entries=[
            XLightsGroupMapping(choreo_id=g, group_name=g.replace("_", " ").title())
            for g in group_ids
        ],
    )
    grid = BeatGrid.from_tempo(tempo_bpm=120.0, total_bars=120)
    stage = DisplayRenderStage(recipe_catalog=catalog)
    result = asyncio.run(
        stage.execute(
            {
                "plan_set": plan_set,
                "beat_grid": grid,
                "choreo_graph": graph,
                "xlights_mapping": mapping,
            },
            PipelineContext(session=None),
        )
    )
    assert result.success, result.error
    XSQExporter().export(result.output["sequence"], out)
    return extract_xsq_metrics(out)


def test_baseline_xsq_metrics_are_pinned() -> None:
    """Lock the pre-refactor MH `.xsq` sophistication; guard the extractor from drift."""
    pinned = json.loads(_MH_METRICS.read_text())
    actual = extract_xsq_metrics(_MH_XSQ).to_dict()
    actual["distinct_effect_types"] = list(actual["distinct_effect_types"])
    assert actual == pinned


def test_display_baseline_xsq_metrics_are_pinned() -> None:
    """Lock the pre-refactor display `.xsq` sophistication (multi-effect-type output).

    Exercises the extractor on a rich RGB/pixel sequence (11 effect types, 5 layers),
    complementing the single-modality MH baseline.
    """
    pinned = json.loads(_DISPLAY_METRICS.read_text())
    actual = extract_xsq_metrics(_DISPLAY_XSQ).to_dict()
    actual["distinct_effect_types"] = list(actual["distinct_effect_types"])
    assert actual == pinned


def test_current_renderer_matches_baseline_sophistication(tmp_path: Path) -> None:
    """Replaying the pre-refactor plan through today's renderer stays on par."""
    pinned = json.loads(_MH_METRICS.read_text())
    plan = ChoreographyPlan.model_validate(json.loads(_MH_PLAN.read_text()))
    meta = json.loads(_MH_META.read_text())

    grid = BeatGrid.from_tempo(tempo_bpm=meta["metrics"]["tempo_bpm"], total_bars=180)
    fixture_group = build_fixture_group(RIGS["mh4_minimal"])
    out = tmp_path / "replay.xsq"
    RenderingPipeline(
        choreography_plan=plan,
        beat_grid=grid,
        fixture_group=fixture_group,
        job_config=JobConfig(),
        output_path=out,
        media_file="song.mp3",
    ).render()
    fresh = extract_xsq_metrics(out)

    # Same emission modality and delivery invariants as the baseline.
    assert fresh.distinct_effect_types == tuple(pinned["distinct_effect_types"])
    assert fresh.sequence_timing == pinned["sequence_timing"] == "20 ms"
    assert fresh.max_layers >= 2, "base + transition layering must be retained"

    # Comparable effect volume (plan-driven) within a broad band of the baseline.
    baseline_effects = pinned["placed_effect_count"]
    assert 0.7 * baseline_effects <= fresh.placed_effect_count <= 1.3 * baseline_effects, (
        f"effect volume {fresh.placed_effect_count} diverged from baseline {baseline_effects}"
    )

    # Value-curve richness retained: at least one curved DMX channel per placed effect.
    assert fresh.value_curve_channel_count >= fresh.placed_effect_count


def test_display_replay_recipes_snapshot_is_self_contained() -> None:
    """Every template the resolvable plan subset references must be in the committed snapshot.

    Guards the fixture: the display replay must not silently depend on the owner's gitignored
    local catalog. If a placement's template is missing from the snapshot the render would
    hard-fail, so self-containment is the precondition for a hermetic replay.
    """
    plan = GroupPlanSet.model_validate(json.loads(_DISPLAY_PLAN.read_text()))
    recipe_ids = {r.recipe_id for r in _load_display_recipe_catalog().recipes}
    filtered = _filter_plan_to_recipes(plan, recipe_ids)
    referenced = {
        placement.template_id
        for section in filtered.section_plans
        for lane in section.lane_plans
        for coord in lane.coordination_plans
        for placement in coord.placements
    }
    assert referenced, "filtered plan must retain resolvable placements"
    assert referenced <= recipe_ids


def test_display_replay_matches_pinned_metrics_and_baseline_vocabulary(tmp_path: Path) -> None:
    """Replaying the resolvable display plan through today's renderer is deterministic and on par.

    Hermetic: renders from the committed recipe snapshot only. Asserts (1) the exact pinned
    replay metrics (deterministic guard) and (2) parity with the pinned pre-refactor display
    baseline on the invariants the plan can drive — effect-type vocabulary is a subset of the
    baseline's, layer depth matches, and the 20 ms grid holds.
    """
    pinned_replay = json.loads(_DISPLAY_REPLAY_METRICS.read_text())
    baseline = json.loads(_DISPLAY_METRICS.read_text())

    plan = GroupPlanSet.model_validate(json.loads(_DISPLAY_PLAN.read_text()))
    catalog = _load_display_recipe_catalog()
    filtered = _filter_plan_to_recipes(plan, {r.recipe_id for r in catalog.recipes})

    metrics = _replay_display(filtered, catalog, tmp_path / "display_replay.xsq")
    actual = metrics.to_dict()
    actual["distinct_effect_types"] = list(actual["distinct_effect_types"])
    assert actual == pinned_replay

    # Parity with the pre-refactor baseline on plan-drivable invariants.
    assert set(metrics.distinct_effect_types) <= set(baseline["distinct_effect_types"])
    assert metrics.max_layers == baseline["max_layers"]
    assert metrics.sequence_timing == baseline["sequence_timing"] == "20 ms"
    assert metrics.placed_effect_count > 0
