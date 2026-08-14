"""Fixture-aware default handlers for discrete moving-head channels."""

from __future__ import annotations

from typing import Any

from twinklr.core.curves.models import CurvePoint
from twinklr.core.sequencer.moving_heads.handlers.protocols import WheelResult
from twinklr.core.sequencer.moving_heads.libraries.color import ColorLibrary, ColorPreset
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboLibrary, GoboPattern
from twinklr.core.sequencer.moving_heads.libraries.shutter import (
    ShutterLibrary,
    ShutterPattern,
)

PLAN_INTENT_CHANNEL_WINDOW_MAX = 16
"""Highest physical channel schema-v2 plan intent may actively override.

P1P-T6 independently widened exporter default emission through ``get_max_channel``.
Thus a fixture-mapped shutter at channel 17 still exports its declared default, while
this renderer layer drops the plan override required by P2P-T2's counterexample.
"""


def _mapping(params: dict[str, Any]) -> Any | None:
    calibration = params.get("calibration") or {}
    fixture_config = calibration.get("fixture_config")
    return fixture_config.dmx_mapping if fixture_config is not None else None


class DefaultColorHandler:
    """Resolve a named library colour through a fixture's wheel map."""

    handler_id = "__default__"

    def generate(self, params: dict[str, Any], n_samples: int) -> WheelResult:
        del n_samples
        preset = ColorPreset(params["preset"])
        definition = ColorLibrary.get_preset(preset)
        mapping = _mapping(params)
        if mapping is None:
            return WheelResult(
                static_dmx=definition.dmx_value,
                trace=f"resolved:color library {preset.value}={definition.dmx_value}",
            )
        if mapping.color is None:
            fallback = int(mapping.color_map.get("open", 0))
            return WheelResult(
                static_dmx=fallback,
                trace=f"fallback:color channel unavailable; default={fallback}",
            )
        if preset.value not in mapping.color_map:
            fallback = int(mapping.color_map.get("open", 0))
            return WheelResult(
                static_dmx=fallback,
                trace=f"fallback:color preset {preset.value!r} absent; default={fallback}",
            )
        value = int(mapping.color_map[preset.value])
        return WheelResult(static_dmx=value, trace=f"resolved:color {preset.value}={value}")


class DefaultShutterHandler:
    """Resolve shutter patterns through fixture-declared shutter values."""

    handler_id = "__default__"

    def generate(self, params: dict[str, Any], n_samples: int) -> WheelResult:
        pattern = ShutterPattern(params["pattern"])
        definition = ShutterLibrary.get_pattern(pattern)
        mapping = _mapping(params)
        if mapping is None:
            fallback = definition.dmx_value
            if fallback is None:
                fallback = ShutterLibrary.DMX_OPEN
            return WheelResult(
                static_dmx=fallback,
                trace=f"resolved:shutter library {pattern.value}={fallback}",
            )
        if mapping.shutter is None:
            fallback = int(mapping.shutter_default)
            return WheelResult(
                static_dmx=fallback,
                trace=f"fallback:shutter channel unavailable; default={fallback}",
            )
        if mapping.shutter > PLAN_INTENT_CHANNEL_WINDOW_MAX:
            return WheelResult(
                emit=False,
                trace=(
                    f"warning:shutter channel {mapping.shutter} outside plan-intent "
                    f"window 1-{PLAN_INTENT_CHANNEL_WINDOW_MAX}; dropped"
                ),
            )

        shutter_map = mapping.shutter_map
        if pattern is ShutterPattern.PULSE:
            closed = int(shutter_map.closed)
            opened = int(shutter_map.open)
            samples = max(2, n_samples)
            low = min(closed, opened)
            high = max(closed, opened)
            span = high - low
            closed_norm = 0.0 if span == 0 else (closed - low) / span
            open_norm = 0.0 if span == 0 else (opened - low) / span
            curve = [
                CurvePoint(
                    t=index / (samples - 1),
                    v=closed_norm if index % 2 == 0 else open_norm,
                )
                for index in range(samples)
            ]
            return WheelResult(
                curve=curve,
                clamp_min_dmx=low,
                clamp_max_dmx=high,
                trace=f"resolved:shutter pulse={closed}/{opened}",
            )

        value = int(getattr(shutter_map, pattern.value))
        return WheelResult(static_dmx=value, trace=f"resolved:shutter {pattern.value}={value}")


class DefaultGoboHandler:
    """Resolve a named gobo through a fixture's wheel map."""

    handler_id = "__default__"

    def generate(self, params: dict[str, Any], n_samples: int) -> WheelResult:
        del n_samples
        pattern = GoboPattern(params["pattern"])
        definition = GoboLibrary.get_pattern(pattern)
        mapping = _mapping(params)
        if mapping is None:
            return WheelResult(
                static_dmx=definition.dmx_value,
                trace=f"resolved:gobo library {pattern.value}={definition.dmx_value}",
            )
        if mapping.gobo is None:
            fallback = int(mapping.gobo_map.get("open", 0))
            return WheelResult(
                static_dmx=fallback,
                trace=f"fallback:gobo channel unavailable; default={fallback}",
            )
        if pattern.value not in mapping.gobo_map:
            fallback = int(mapping.gobo_map.get("open", 0))
            return WheelResult(
                static_dmx=fallback,
                trace=f"fallback:gobo pattern {pattern.value!r} absent; default={fallback}",
            )
        value = int(mapping.gobo_map[pattern.value])
        return WheelResult(static_dmx=value, trace=f"resolved:gobo {pattern.value}={value}")
