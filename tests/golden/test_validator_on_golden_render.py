"""Run the existing 587-LOC `.xsq` validator against a freshly rendered sequence.

`scripts/validation/_core/mh_xsq_validation.py` already parses emitted DMX settings,
flags all-zero effects as CRITICAL and cross-checks shutter/colour/gobo mappings — but
until now it only ran post-hoc, when a human pointed
`scripts/validation/validate_artifacts.py` at an artifact directory. It was in neither
`make validate` nor CI (P4-M8). This module wires the existing validator in; it does not
add checks of its own.

Gating rule (P1P-T1 acceptance criteria): findings on the **golden-suite render** gate.
The render currently trips one ERROR, pinned below as a known defect; any *additional*
finding fails the suite. Findings on arbitrary legacy artifacts are explicitly out of
scope and are not gated here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validation._core.mh_xsq_validation import (
    MHXSQValidationPaths,
    load_xsq_effects,
    run_mh_xsq_validation,
    validate_channel_usage_vs_plan,
)
from scripts.validation._core.models import ValidationResult
from tests.golden.harness import RIGS, render_rig

# The findings the baseline render is known to produce, as (severity, category).
# Anything outside this set fails the gate.
BASELINE_FINDINGS = {
    # KNOWN-WRONG PIN: EffectDB indices are 0-based (`XSequence.append_effectdb` returns
    # `len(entries) - 1`), so the very first effect is written as ref="0" — which the
    # validator, and xLights, read as "no EffectDB entry". Exactly one effect per render
    # loses its DMX payload this way. Recorded here, fixed in Lane R.
    ("ERROR", "MISSING_REF"),
}


@pytest.fixture(scope="module")
def rendered_xsq(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A real `.xsq` produced by the golden harness — not a checked-in legacy artifact."""
    output_path = tmp_path_factory.mktemp("golden_render") / "golden.xsq"
    render_rig(RIGS["mh4_minimal"], output_path=output_path)
    return output_path


@pytest.fixture(scope="module")
def validation(rendered_xsq: Path) -> ValidationResult:
    return run_mh_xsq_validation(MHXSQValidationPaths(xsq_path=rendered_xsq), quality_only=True)


def test_validator_runs_on_golden_render(validation: ValidationResult) -> None:
    """The validator executes against freshly rendered output inside the test suite."""
    assert validation.stats["models_with_effects"] == 4
    # 4 fixtures x 11 layer-0 effects: 5 single-step sections plus 3 steps for each
    # of the two narrative sections P1P-T5 added to the plan.
    assert validation.stats["total_effects"] == 44
    assert validation.artifacts_checked


def test_golden_render_findings_match_the_pinned_baseline(
    validation: ValidationResult,
) -> None:
    """No finding beyond the pinned baseline set — this is the CI gate."""
    found = {(issue.severity, issue.category) for issue in validation.issues}
    unexpected = found - BASELINE_FINDINGS
    assert not unexpected, (
        "The validator reported findings the P1P baseline does not have: "
        f"{sorted(unexpected)}. Details: "
        f"{[(i.severity, i.category, i.message) for i in validation.issues]}"
    )


def test_golden_render_has_no_all_zero_effects(validation: ValidationResult) -> None:
    """The validator's all-zero CRITICAL check passes — movement really is emitted.

    This is the check that would have caught P4-F3 and P4-M1 on any real run. It passes
    at baseline, which is what makes it useful as a gate: if a Lane-R change zeroes a
    channel or flattens a curve, this flips to failing.
    """
    dmx_findings = [issue for issue in validation.issues if issue.category == "DMX_DATA"]
    assert dmx_findings == []


def test_validator_sees_movement_on_every_rendered_model(rendered_xsq: Path) -> None:
    """Each fixture model carries effects with real pan/tilt curves, not empty payloads."""
    effects_by_model = load_xsq_effects(rendered_xsq)
    assert sorted(effects_by_model) == ["Dmx MH1", "Dmx MH2", "Dmx MH3", "Dmx MH4"]

    for model_name, effects in effects_by_model.items():
        with_curves = [effect for effect in effects if effect.dmx_curves]
        assert with_curves, f"{model_name} emitted no value curves at all"
        for effect in with_curves:
            assert {11, 13} <= set(effect.dmx_curves), (
                f"{model_name} lost its pan/tilt curves: {sorted(effect.dmx_curves)}"
            )


def test_validator_channel_crosscheck_clean(tmp_path: Path) -> None:
    """P1P-T6 acceptance: the validator's shutter/colour cross-check finds no mismatch.

    Uses `mh4_shutter_out_of_window` (shutter=17, colour=18) deliberately: before this
    task, those channels fell outside the exporter's floor-16 window, so no
    `E_SLIDER_DMX` token existed for them at all and `validate_channel_usage_vs_plan`
    reported "has no shutter/colour data" for every section the plan named a value.
    `get_max_channel` now widens the window to include any mapped channel, so the
    declared default reaches the token and the cross-check finds nothing.

    Checked against the `chorus` section (8000-16000ms), not `intro`: the very first
    effect in the file carries the unrelated, already-pinned MISSING_REF defect
    (`BASELINE_FINDINGS` above; EffectDB ref=0 reads as "no entry"), which empties its
    `dmx_channels` regardless of this task's change and would be a false positive here.
    """
    output_path = tmp_path / "shutter_high_rig.xsq"
    render_rig(RIGS["mh4_shutter_out_of_window"], output_path=output_path)
    effects_by_model = load_xsq_effects(output_path)

    fixture_config = {
        "fixtures": [
            {
                "xlights_model_name": f"Dmx MH{index}",
                "config": {"dmx_mapping": {"shutter_channel": 17, "color_channel": 18}},
            }
            for index in range(1, 5)
        ]
    }
    raw_plan = {"sections": [{"name": "chorus", "channels": {"shutter": "open", "color": "white"}}]}
    implementation = {"sections": [{"name": "chorus", "start_ms": 8000, "end_ms": 16000}]}

    issues = validate_channel_usage_vs_plan(
        raw_plan, implementation, effects_by_model, fixture_config
    )
    assert issues == [], issues
