"""Unit tests for structured EffectDB parser."""

from __future__ import annotations

from twinklr.core.profiling.effects.effectdb_parser import parse_effectdb_settings
from twinklr.core.profiling.models.enums import (
    EffectDbControlType,
    EffectDbNamespace,
    EffectDbParseStatus,
    ParameterValueType,
)


def test_parse_effectdb_settings_parsed() -> None:
    parsed = parse_effectdb_settings("E_SLIDER_Speed=42,B_CHOICE_BufferStyle=Per Model Default")
    assert parsed.status is EffectDbParseStatus.PARSED
    assert len(parsed.params) == 2
    assert parsed.params[0].namespace is EffectDbNamespace.E
    assert parsed.params[0].control_type is EffectDbControlType.SLIDER
    assert parsed.params[0].value_type is ParameterValueType.INT


def test_parse_effectdb_settings_partial() -> None:
    parsed = parse_effectdb_settings("E_NOTEBOOK1=Channels,not-a-key-value")
    assert parsed.status is EffectDbParseStatus.PARTIAL
    assert len(parsed.params) == 1
    assert parsed.params[0].control_type is EffectDbControlType.UNKNOWN
    assert len(parsed.errors) == 1


def test_parse_effectdb_settings_failed() -> None:
    parsed = parse_effectdb_settings("broken-token")
    assert parsed.status is EffectDbParseStatus.FAILED
    assert parsed.params == ()
    assert parsed.errors


def test_parse_effectdb_settings_empty() -> None:
    parsed = parse_effectdb_settings("")
    assert parsed.status is EffectDbParseStatus.EMPTY
    assert parsed.params == ()
    assert parsed.errors == ()
