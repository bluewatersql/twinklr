"""Effect statistics and parameter profiling."""

from __future__ import annotations

import contextlib
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence

from twinklr.core.profiling.models.effects import (
    CategoricalValueProfile,
    DurationStats,
    EffectStatistics,
    EffectTypeProfile,
    NumericValueProfile,
    ParameterProfile,
)
from twinklr.core.profiling.models.enums import ParameterValueType
from twinklr.core.profiling.models.events import EffectEventRecord

_EFF_PREFIX_RE = re.compile(r"^[A-Z]_[A-Za-z0-9]+_Eff_")


def parse_effectdb_settings(settings_str: str) -> dict[str, str]:
    """Parse comma-separated `key=value` settings into a dictionary."""
    if not settings_str:
        return {}

    params: dict[str, str] = {}
    for part in settings_str.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        clean_key = _EFF_PREFIX_RE.sub("", key.strip())
        params[clean_key] = value.strip()
    return params


def infer_param_type(value: str) -> ParameterValueType:
    """Infer scalar value type from a string value."""
    if value == "":
        return ParameterValueType.EMPTY

    with contextlib.suppress(ValueError):
        int(value)
        return ParameterValueType.INT

    with contextlib.suppress(ValueError):
        float(value)
        return ParameterValueType.FLOAT

    if value.lower() in {"true", "false", "0", "1"}:
        return ParameterValueType.BOOL

    return ParameterValueType.STRING


def is_high_cardinality(param_name: str, values: list[str], n_instances: int) -> bool:
    """Return True when parameter cardinality makes profiles unhelpful/noisy."""
    param_name_lower = param_name.lower()
    exclude_keywords = {
        "text",
        "font",
        "file",
        "palette",
        "path",
        "definition",
        "timing",
        "track",
        "data",
        "label",
        "description",
    }

    if any(keyword in param_name_lower for keyword in exclude_keywords):
        return True

    unique_count = len(set(values))
    return unique_count > n_instances * 0.5 and unique_count > 20


def _is_filtered_param(param_name: str) -> bool:
    return param_name == "BufferStyle" or param_name.startswith("MH") or "DMX" in param_name


def compute_effect_statistics(events: Sequence[EffectEventRecord]) -> EffectStatistics:
    """Compute aggregate and per-type parameter statistics from effect events."""
    if not events:
        return EffectStatistics(
            total_events=0,
            distinct_effect_types=0,
            total_effect_duration_ms=0,
            avg_effect_duration_ms=0.0,
            total_targets_with_effects=0,
            effect_type_counts={},
            effect_type_durations_ms={},
            effect_type_profiles={},
            effects_per_target={},
            layers_per_target={},
        )

    effect_type_counts: Counter[str] = Counter()
    effect_type_durations: Counter[str] = Counter()
    effects_per_target: Counter[str] = Counter()
    layers_per_target: dict[str, set[int]] = defaultdict(set)

    per_type_durations: dict[str, list[int]] = defaultdict(list)
    per_type_buffer_styles: dict[str, set[str]] = defaultdict(set)
    per_type_params: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    total_duration = 0

    for event in events:
        duration = max(0, event.end_ms - event.start_ms)
        total_duration += duration

        effect_type_counts[event.effect_type] += 1
        effect_type_durations[event.effect_type] += duration
        effects_per_target[event.target_name] += 1
        layers_per_target[event.target_name].add(event.layer_index)

        per_type_durations[event.effect_type].append(duration)

        settings = parse_effectdb_settings(event.effectdb_settings or "")
        buffer_style = settings.get("BufferStyle", "default")
        per_type_buffer_styles[event.effect_type].add(buffer_style)

        for param_name, param_value in settings.items():
            if _is_filtered_param(param_name):
                continue
            per_type_params[event.effect_type][param_name].append(param_value)

    effect_type_profiles: dict[str, EffectTypeProfile] = {}

    for effect_type in sorted(effect_type_counts):
        durations = per_type_durations.get(effect_type, [])
        if durations:
            duration_stats = DurationStats(
                count=len(durations),
                min_ms=min(durations),
                max_ms=max(durations),
                avg_ms=statistics.mean(durations),
                median_ms=statistics.median(durations),
            )
        else:
            duration_stats = DurationStats(count=0, min_ms=0, max_ms=0, avg_ms=0.0, median_ms=0.0)

        parameter_profiles: dict[str, ParameterProfile] = {}
        raw_params = per_type_params.get(effect_type, {})

        for param_name in sorted(raw_params):
            values = raw_params[param_name]
            if is_high_cardinality(param_name, values, len(durations)):
                continue

            inferred_types = Counter(infer_param_type(v) for v in values)
            primary_type = inferred_types.most_common(1)[0][0]

            numeric_profile: NumericValueProfile | None = None
            categorical_profile: CategoricalValueProfile | None = None

            if primary_type in {ParameterValueType.INT, ParameterValueType.FLOAT}:
                numeric_values: list[float] = []
                for value in values:
                    with contextlib.suppress(ValueError, TypeError):
                        numeric_values.append(float(value))
                if numeric_values:
                    numeric_profile = NumericValueProfile(
                        min=min(numeric_values),
                        max=max(numeric_values),
                        avg=statistics.mean(numeric_values),
                        median=statistics.median(numeric_values),
                    )
            elif primary_type in {ParameterValueType.STRING, ParameterValueType.BOOL}:
                distinct = tuple(sorted(set(values)))
                if len(distinct) <= 50:
                    categorical_profile = CategoricalValueProfile(
                        distinct_values=distinct,
                        distinct_count=len(distinct),
                    )

            parameter_profiles[param_name] = ParameterProfile(
                type=primary_type,
                count=len(values),
                numeric_profile=numeric_profile,
                categorical_profile=categorical_profile,
            )

        effect_type_profiles[effect_type] = EffectTypeProfile(
            instance_count=effect_type_counts[effect_type],
            duration_stats=duration_stats,
            buffer_styles=tuple(sorted(per_type_buffer_styles.get(effect_type, {"default"}))),
            parameter_names=tuple(sorted(raw_params.keys())),
            parameters=parameter_profiles,
        )

    return EffectStatistics(
        total_events=len(events),
        distinct_effect_types=len(effect_type_counts),
        total_effect_duration_ms=total_duration,
        avg_effect_duration_ms=(total_duration / len(events)) if events else 0.0,
        total_targets_with_effects=len(effects_per_target),
        effect_type_counts=dict(effect_type_counts.most_common()),
        effect_type_durations_ms=dict(effect_type_durations.most_common()),
        effect_type_profiles=effect_type_profiles,
        effects_per_target=dict(effects_per_target),
        layers_per_target={k: len(v) for k, v in layers_per_target.items()},
    )
