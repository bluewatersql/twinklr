"""Unit tests for effect analyzer."""

from __future__ import annotations

from twinklr.core.profiling.effects.analyzer import compute_effect_statistics, is_high_cardinality
from twinklr.core.profiling.models.effectdb import EffectDbParam
from twinklr.core.profiling.models.enums import (
    EffectDbControlType,
    EffectDbNamespace,
    ParameterValueType,
)
from twinklr.core.profiling.models.events import EffectEventRecord


def _events() -> list[EffectEventRecord]:
    return [
        EffectEventRecord(
            effect_event_id="1",
            target_name="Arch 1",
            layer_index=0,
            layer_name="Main",
            effect_type="Bars",
            start_ms=100,
            end_ms=300,
            config_fingerprint="a",
            effectdb_ref=0,
            effectdb_settings_raw="B_CHOICE_BufferStyle=Default,E_TEXTCTRL_Eff_speed=10",
            effectdb_params=(
                EffectDbParam(
                    namespace=EffectDbNamespace.B,
                    control_type=EffectDbControlType.CHOICE,
                    param_name_raw="BufferStyle",
                    param_name_normalized="bufferstyle",
                    value_raw="Default",
                    value_type=ParameterValueType.STRING,
                    value_string="Default",
                ),
                EffectDbParam(
                    namespace=EffectDbNamespace.E,
                    control_type=EffectDbControlType.TEXTCTRL,
                    param_name_raw="Eff_speed",
                    param_name_normalized="eff_speed",
                    value_raw="10",
                    value_type=ParameterValueType.INT,
                    value_int=10,
                    value_float=10.0,
                ),
            ),
            palette="#FF0000",
            protected=False,
            label=None,
        ),
        EffectEventRecord(
            effect_event_id="2",
            target_name="Arch 1",
            layer_index=1,
            layer_name="Accent",
            effect_type="Bars",
            start_ms=400,
            end_ms=700,
            config_fingerprint="b",
            effectdb_ref=0,
            effectdb_settings_raw="B_CHOICE_BufferStyle=Default,E_TEXTCTRL_Eff_speed=20",
            effectdb_params=(
                EffectDbParam(
                    namespace=EffectDbNamespace.B,
                    control_type=EffectDbControlType.CHOICE,
                    param_name_raw="BufferStyle",
                    param_name_normalized="bufferstyle",
                    value_raw="Default",
                    value_type=ParameterValueType.STRING,
                    value_string="Default",
                ),
                EffectDbParam(
                    namespace=EffectDbNamespace.E,
                    control_type=EffectDbControlType.TEXTCTRL,
                    param_name_raw="Eff_speed",
                    param_name_normalized="eff_speed",
                    value_raw="20",
                    value_type=ParameterValueType.INT,
                    value_int=20,
                    value_float=20.0,
                ),
            ),
            palette="#00FF00",
            protected=False,
            label=None,
        ),
    ]


def test_compute_effect_statistics_empty() -> None:
    stats = compute_effect_statistics([])
    assert stats.total_events == 0
    assert stats.distinct_effect_types == 0
    assert stats.effect_type_counts == {}


def test_compute_effect_statistics_known_events() -> None:
    stats = compute_effect_statistics(_events())
    assert stats.total_events == 2
    assert stats.effect_type_counts == {"Bars": 2}
    assert stats.avg_effect_duration_ms == 250.0


def test_is_high_cardinality() -> None:
    values = [str(i) for i in range(80)]
    assert is_high_cardinality("text", values, 100) is True


def test_parameter_profile_generated() -> None:
    stats = compute_effect_statistics(_events())
    profile = stats.effect_type_profiles["Bars"]
    assert "eff_speed" in profile.parameters
    assert profile.parameters["eff_speed"].type is ParameterValueType.INT
