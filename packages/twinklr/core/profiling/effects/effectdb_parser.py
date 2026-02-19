"""Structured parser for xLights EffectDB settings payloads."""

from __future__ import annotations

import re
from dataclasses import dataclass

from twinklr.core.profiling.models.effectdb import EffectDbParam
from twinklr.core.profiling.models.enums import (
    EffectDbControlType,
    EffectDbNamespace,
    EffectDbParseStatus,
    ParameterValueType,
)

_KEY_PATTERN = re.compile(r"^(?P<ns>[A-Z])_(?P<ctrl>[A-Za-z0-9]+)_(?P<name>.+)$")
_SHORT_KEY_PATTERN = re.compile(r"^(?P<ns>[A-Z])_(?P<name>.+)$")
_NORMALIZE_PARAM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ParsedEffectDbSettings:
    """Parse result for an EffectDB settings payload."""

    status: EffectDbParseStatus
    params: tuple[EffectDbParam, ...]
    errors: tuple[str, ...]


def _infer_value_type(value: str) -> ParameterValueType:
    if value == "":
        return ParameterValueType.EMPTY

    if value.lower() in {"true", "false"}:
        return ParameterValueType.BOOL

    try:
        int(value)
    except ValueError:
        pass
    else:
        return ParameterValueType.INT

    try:
        float(value)
    except ValueError:
        return ParameterValueType.STRING
    else:
        return ParameterValueType.FLOAT


def _normalize_param_name(name: str) -> str:
    normalized = _NORMALIZE_PARAM_RE.sub("_", name.strip().lower()).strip("_")
    return normalized or "unknown"


def _to_namespace(namespace_text: str) -> EffectDbNamespace:
    if namespace_text == "E":
        return EffectDbNamespace.E
    if namespace_text == "B":
        return EffectDbNamespace.B
    if namespace_text == "T":
        return EffectDbNamespace.T
    return EffectDbNamespace.UNKNOWN


def _to_control_type(control_text: str) -> EffectDbControlType:
    normalized = control_text.upper()
    try:
        return EffectDbControlType[normalized]
    except KeyError:
        return EffectDbControlType.UNKNOWN


def parse_effectdb_settings(settings: str | None) -> ParsedEffectDbSettings:
    """Parse EffectDB settings string into structured parameters."""
    if settings is None or not settings.strip():
        return ParsedEffectDbSettings(
            status=EffectDbParseStatus.EMPTY,
            params=(),
            errors=(),
        )

    params: list[EffectDbParam] = []
    errors: list[str] = []

    for idx, token in enumerate(settings.split(",")):
        part = token.strip()
        if not part:
            continue
        if "=" not in part:
            errors.append(f"token[{idx}] missing '=': {part}")
            continue

        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()

        match = _KEY_PATTERN.match(key)
        if match is None:
            short_match = _SHORT_KEY_PATTERN.match(key)
            if short_match is None:
                errors.append(f"token[{idx}] invalid key format: {key}")
                continue
            namespace = _to_namespace(short_match.group("ns"))
            control_type = EffectDbControlType.UNKNOWN
            param_name_raw = short_match.group("name")
        else:
            namespace = _to_namespace(match.group("ns"))
            control_type = _to_control_type(match.group("ctrl"))
            param_name_raw = match.group("name")
        param_name_normalized = _normalize_param_name(param_name_raw)
        value_type = _infer_value_type(value)

        value_int: int | None = None
        value_float: float | None = None
        value_bool: bool | None = None
        value_string: str | None = None

        if value_type == ParameterValueType.INT:
            value_int = int(value)
            value_float = float(value_int)
        elif value_type == ParameterValueType.FLOAT:
            value_float = float(value)
        elif value_type == ParameterValueType.BOOL:
            value_bool = value.lower() == "true"
        else:
            value_string = value

        params.append(
            EffectDbParam(
                namespace=namespace,
                control_type=control_type,
                param_name_raw=param_name_raw,
                param_name_normalized=param_name_normalized,
                value_raw=value,
                value_type=value_type,
                value_int=value_int,
                value_float=value_float,
                value_bool=value_bool,
                value_string=value_string,
            )
        )

    if params and not errors:
        status = EffectDbParseStatus.PARSED
    elif params and errors:
        status = EffectDbParseStatus.PARTIAL
    elif errors:
        status = EffectDbParseStatus.FAILED
    else:
        status = EffectDbParseStatus.EMPTY

    return ParsedEffectDbSettings(status=status, params=tuple(params), errors=tuple(errors))
