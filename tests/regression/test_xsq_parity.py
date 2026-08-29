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

import json
from pathlib import Path

from tests.golden.harness import RIGS, build_fixture_group
from tests.regression.xsq_metrics import extract_xsq_metrics
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.models import JobConfig
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
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
