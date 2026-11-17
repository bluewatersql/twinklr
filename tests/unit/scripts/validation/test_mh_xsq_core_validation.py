from __future__ import annotations

import json
from pathlib import Path

from scripts.validation._core.mh_xsq_validation import (
    MHXSQEffect,
    MHXSQValidationPaths,
    ValidationIssue,
    check_missing_refs,
    load_xsq_effects,
    parse_dmx_settings,
    run_mh_xsq_validation,
    validate_dmx_data_presence,
)
from tests.support import moving_heads as m
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline


def test_parse_dmx_settings_extracts_values_and_curves() -> None:
    values, curves = parse_dmx_settings(
        "E_SLIDER_DMX1=128,E_VALUECURVE_DMX2=Active=TRUE|Foo,E_TEXTCTRL_DMX3=64"
    )

    assert values == {1: 128, 3: 64}
    assert curves == {2: "Active=TRUE|Foo"}


def test_check_missing_refs_reports_none_and_invalid_refs() -> None:
    effects_by_model = {
        "FixtureA": [
            MHXSQEffect(
                element_name="FixtureA",
                effect_type="DMX",
                start_ms=0,
                end_ms=1000,
                ref=None,
                label="a",
            ),
            MHXSQEffect(
                element_name="FixtureA",
                effect_type="DMX",
                start_ms=1000,
                end_ms=2000,
                ref=99,
                label="b",
            ),
        ]
    }

    issues = check_missing_refs(effects_by_model, effectdb={1: "ok"})

    assert any(isinstance(issue, ValidationIssue) for issue in issues)
    assert any(issue.category == "MISSING_REF" and issue.severity == "ERROR" for issue in issues)
    assert any("EffectDB entry not found" in issue.message for issue in issues)


def test_validate_dmx_data_presence_flags_all_zero_effects() -> None:
    effects_by_model = {
        "FixtureA": [
            MHXSQEffect(
                element_name="FixtureA",
                effect_type="DMX",
                start_ms=0,
                end_ms=1000,
                ref=1,
                label="a",
                dmx_channels={1: 0, 2: 0, 3: 0},
            )
        ]
    }

    issues = validate_dmx_data_presence(effects_by_model)

    assert any("ALL ZERO values" in issue for issue in issues)


def test_an_effect_reads_the_effectdb_entry_its_ref_names(tmp_path: Path) -> None:
    xsq_path = tmp_path / "song_twinklr_mh.xsq"
    xsq_path.write_text(
        "<xsequence><EffectDB><Effect></Effect><Effect>E_SLIDER_DMX1=7</Effect>"
        "<Effect>E_SLIDER_DMX1=9</Effect></EffectDB><ElementEffects>"
        '<Element type="model" name="Dmx MH1"><EffectLayer>'
        '<Effect ref="1" name="DMX" startTime="0" endTime="20"/>'
        '<Effect ref="2" name="DMX" startTime="20" endTime="40"/>'
        "</EffectLayer></Element></ElementEffects></xsequence>",
        encoding="utf-8",
    )

    effects = load_xsq_effects(xsq_path)["Dmx MH1"]

    assert [effect.dmx_channels for effect in effects] == [{1: 7}, {1: 9}]


def test_a_rendered_moving_head_xsq_passes(tmp_path: Path) -> None:
    heads = ("MH1", "MH2")
    xsq_path = tmp_path / "song_twinklr_mh.xsq"
    fixture_path = tmp_path / "fixture_config.json"
    rig = m.family_rig(heads)
    with m.family_catalog():
        RenderingPipeline(
            choreography_plan=m.sections_plan(("target_orbit", 1, 2), ("finite_snap_hold", 3, 4)),
            beat_grid=m.bars_grid(*([500.0] * 4)),
            fixture_group=rig,
            job_config=m.family_job(heads),
            output_path=xsq_path,
            media_file="silence.wav",
        ).render()
    fixture_path.write_text(json.dumps(rig.model_dump(mode="json")), encoding="utf-8")

    result = run_mh_xsq_validation(
        MHXSQValidationPaths(xsq_path=xsq_path, fixture_config_path=fixture_path)
    )

    assert result.issues == []
    assert result.stats["models_with_effects"] == len(heads)
    assert result.stats["total_effects"] > 0
