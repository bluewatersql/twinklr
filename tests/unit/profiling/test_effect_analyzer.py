"""Unit tests for effect analyzer."""

from __future__ import annotations

from twinklr.core.profiling.effects.analyzer import (
    compute_effect_statistics,
    infer_param_type,
    is_high_cardinality,
    parse_effectdb_settings,
)
from twinklr.core.profiling.models.enums import ParameterValueType
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
            effectdb_settings="BufferStyle=Default,speed=10,Invert=0",
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
            effectdb_settings="BufferStyle=Default,speed=20,Invert=1",
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


def test_parse_effectdb_settings_prefix_strip() -> None:
    settings = parse_effectdb_settings("E_TEXTCTRL_Eff_speed=10,E_CHECKBOX_Eff_Invert=0")
    assert settings == {"speed": "10", "Invert": "0"}


def test_infer_param_type() -> None:
    assert infer_param_type("42") is ParameterValueType.INT
    assert infer_param_type("3.14") is ParameterValueType.FLOAT


def test_is_high_cardinality() -> None:
    values = [str(i) for i in range(80)]
    assert is_high_cardinality("text", values, 100) is True


def test_parameter_profile_generated() -> None:
    stats = compute_effect_statistics(_events())
    profile = stats.effect_type_profiles["Bars"]
    assert "speed" in profile.parameters
    assert profile.parameters["speed"].type is ParameterValueType.INT
