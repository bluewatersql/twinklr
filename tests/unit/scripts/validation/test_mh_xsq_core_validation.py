from __future__ import annotations

from scripts.validation._core.mh_xsq_validation import (
    MHXSQEffect,
    ValidationIssue,
    check_missing_refs,
    parse_dmx_settings,
    validate_dmx_data_presence,
)


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
