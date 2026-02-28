"""Canonical phrase encoder (V1.2)."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.constants import EFFECT_PHRASES_SCHEMA_VERSION
from twinklr.core.feature_engineering.models import (
    AlignedEffectEvent,
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)

_EFFECT_ALIASES: dict[str, str] = {
    "colourwash": "colorwash",
    "colwash": "colorwash",
    "vumeter": "vumeter",
    "vumeters": "vumeter",
    "vu": "vumeter",
    "tendril": "tendrils",
    "singlestrands": "singlestrand",
    "movingheads": "movinghead",
}


_DEFAULT_MAP: dict[str, dict[str, str]] = {
    "off": {
        "effect_family": "off",
        "motion_class": "static",
        "color_class": "unknown",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
    },
    "on": {
        "effect_family": "on",
        "motion_class": "static",
        "color_class": "mono",
        "energy_class": "mid",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
    },
    "adjust": {
        "effect_family": "adjust",
        "motion_class": "static",
        "color_class": "unknown",
        "energy_class": "mid",
        "continuity_class": "transitional",
        "spatial_class": "single_target",
    },
    "bars": {
        "effect_family": "bars",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "butterfly": {
        "effect_family": "butterfly",
        "motion_class": "sweep",
        "color_class": "multi",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "candle": {
        "effect_family": "candle",
        "motion_class": "sparkle",
        "color_class": "mono",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
    },
    "circles": {
        "effect_family": "circles",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "colorwash": {
        "effect_family": "color_wash",
        "motion_class": "static",
        "color_class": "palette",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "multi_target",
    },
    "curtain": {
        "effect_family": "curtain",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "transitional",
        "spatial_class": "multi_target",
    },
    "dmx": {
        "effect_family": "dmx",
        "motion_class": "dmx_program",
        "color_class": "unknown",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "single_target",
    },
    "duplicate": {
        "effect_family": "duplicate",
        "motion_class": "static",
        "color_class": "unknown",
        "energy_class": "mid",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
    },
    "faces": {
        "effect_family": "faces",
        "motion_class": "static",
        "color_class": "multi",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "single_target",
    },
    "fan": {
        "effect_family": "fan",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "fill": {
        "effect_family": "fill",
        "motion_class": "static",
        "color_class": "palette",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "multi_target",
    },
    "fire": {
        "effect_family": "fire",
        "motion_class": "sparkle",
        "color_class": "palette",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "fireworks": {
        "effect_family": "fireworks",
        "motion_class": "sparkle",
        "color_class": "multi",
        "energy_class": "burst",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "galaxy": {
        "effect_family": "galaxy",
        "motion_class": "sweep",
        "color_class": "multi",
        "energy_class": "mid",
        "continuity_class": "sustained",
        "spatial_class": "multi_target",
    },
    "garlands": {
        "effect_family": "garlands",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "glediator": {
        "effect_family": "glediator",
        "motion_class": "dmx_program",
        "color_class": "palette",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "guitar": {
        "effect_family": "guitar",
        "motion_class": "pulse",
        "color_class": "palette",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "single_target",
    },
    "kaleidoscope": {
        "effect_family": "kaleidoscope",
        "motion_class": "sweep",
        "color_class": "multi",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "life": {
        "effect_family": "life",
        "motion_class": "pulse",
        "color_class": "multi",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "single_target",
    },
    "lightning": {
        "effect_family": "lightning",
        "motion_class": "pulse",
        "color_class": "mono",
        "energy_class": "burst",
        "continuity_class": "transitional",
        "spatial_class": "multi_target",
    },
    "lines": {
        "effect_family": "lines",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "liquid": {
        "effect_family": "liquid",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "sustained",
        "spatial_class": "multi_target",
    },
    "marquee": {
        "effect_family": "marquee",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "meteors": {
        "effect_family": "meteors",
        "motion_class": "sweep",
        "color_class": "mono",
        "energy_class": "high",
        "continuity_class": "transitional",
        "spatial_class": "multi_target",
    },
    "morph": {
        "effect_family": "morph",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "transitional",
        "spatial_class": "multi_target",
    },
    "movinghead": {
        "effect_family": "moving_head",
        "motion_class": "dmx_program",
        "color_class": "unknown",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "single_target",
    },
    "music": {
        "effect_family": "music",
        "motion_class": "pulse",
        "color_class": "palette",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "piano": {
        "effect_family": "piano",
        "motion_class": "pulse",
        "color_class": "mono",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "single_target",
    },
    "pictures": {
        "effect_family": "pictures",
        "motion_class": "static",
        "color_class": "multi",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
    },
    "pinwheel": {
        "effect_family": "pinwheel",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "plasma": {
        "effect_family": "plasma",
        "motion_class": "sweep",
        "color_class": "multi",
        "energy_class": "mid",
        "continuity_class": "sustained",
        "spatial_class": "multi_target",
    },
    "ripple": {
        "effect_family": "ripple",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "transitional",
        "spatial_class": "multi_target",
    },
    "servo": {
        "effect_family": "servo",
        "motion_class": "dmx_program",
        "color_class": "unknown",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "single_target",
    },
    "shader": {
        "effect_family": "shader",
        "motion_class": "static",
        "color_class": "palette",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "multi_target",
    },
    "shape": {
        "effect_family": "shape",
        "motion_class": "static",
        "color_class": "palette",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
    },
    "shimmer": {
        "effect_family": "shimmer",
        "motion_class": "sparkle",
        "color_class": "multi",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "shockwave": {
        "effect_family": "shockwave",
        "motion_class": "sweep",
        "color_class": "mono",
        "energy_class": "high",
        "continuity_class": "transitional",
        "spatial_class": "multi_target",
    },
    "singlestrand": {
        "effect_family": "single_strand",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "single_target",
    },
    "snowflakes": {
        "effect_family": "snowflakes",
        "motion_class": "sparkle",
        "color_class": "multi",
        "energy_class": "low",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "snowstorm": {
        "effect_family": "snow_storm",
        "motion_class": "sweep",
        "color_class": "mono",
        "energy_class": "mid",
        "continuity_class": "sustained",
        "spatial_class": "multi_target",
    },
    "spirals": {
        "effect_family": "spirals",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "spirograph": {
        "effect_family": "spirograph",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "state": {
        "effect_family": "state",
        "motion_class": "static",
        "color_class": "unknown",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
    },
    "strobe": {
        "effect_family": "strobe",
        "motion_class": "pulse",
        "color_class": "mono",
        "energy_class": "burst",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "tendrils": {
        "effect_family": "tendrils",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "sketch": {
        "effect_family": "sketch",
        "motion_class": "sweep",
        "color_class": "multi",
        "energy_class": "mid",
        "continuity_class": "transitional",
        "spatial_class": "multi_target",
    },
    "text": {
        "effect_family": "text",
        "motion_class": "static",
        "color_class": "mono",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
    },
    "tree": {
        "effect_family": "tree",
        "motion_class": "static",
        "color_class": "palette",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
    },
    "twinkle": {
        "effect_family": "twinkle",
        "motion_class": "sparkle",
        "color_class": "multi",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "video": {
        "effect_family": "video",
        "motion_class": "static",
        "color_class": "multi",
        "energy_class": "mid",
        "continuity_class": "sustained",
        "spatial_class": "multi_target",
    },
    "vumeter": {
        "effect_family": "vu_meter",
        "motion_class": "pulse",
        "color_class": "palette",
        "energy_class": "high",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
    "warp": {
        "effect_family": "warp",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "high",
        "continuity_class": "transitional",
        "spatial_class": "multi_target",
    },
    "wave": {
        "effect_family": "wave",
        "motion_class": "sweep",
        "color_class": "palette",
        "energy_class": "mid",
        "continuity_class": "rhythmic",
        "spatial_class": "multi_target",
    },
}


@dataclass(frozen=True)
class PhraseEncoderOptions:
    """Runtime options for phrase encoding."""

    effect_type_map_path: Path | None = None


class PhraseEncoder:
    """Encode aligned events into canonical `EffectPhrase` records."""

    def __init__(self, options: PhraseEncoderOptions | None = None) -> None:
        self._options = options or PhraseEncoderOptions()
        self._map = self._load_effect_type_map(self._options.effect_type_map_path)

    @staticmethod
    def _load_effect_type_map(path: Path | None) -> dict[str, dict[str, str]]:
        base = dict(_DEFAULT_MAP)
        if path is None or not path.exists():
            return base
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid effect type map at {path}")
        merged = dict(base)
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, dict):
                merged[PhraseEncoder._normalize_effect_key(key)] = {
                    k: str(v) for k, v in value.items()
                }
        return merged

    @staticmethod
    def _normalize_effect_key(effect_name: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "", effect_name.strip().lower())
        return _EFFECT_ALIASES.get(normalized, normalized)

    def encode(
        self,
        *,
        package_id: str,
        sequence_file_id: str,
        aligned_events: tuple[AlignedEffectEvent, ...],
        enriched_events: list[dict[str, Any]],
    ) -> tuple[EffectPhrase, ...]:
        enriched_by_id = {
            str(event.get("effect_event_id")): event
            for event in enriched_events
            if isinstance(event, dict)
        }
        phrases: list[EffectPhrase] = []
        for row in aligned_events:
            enriched = enriched_by_id.get(row.effect_event_id, {})
            mapping, source, confidence = self._map_effect(row.effect_type)
            energy_class = self._derive_energy_class(row, mapping)
            preserved, blend_mode_raw, mix_raw = self._extract_preserved_params(enriched)
            phrases.append(
                EffectPhrase(
                    schema_version=EFFECT_PHRASES_SCHEMA_VERSION,
                    phrase_id=str(
                        uuid.uuid5(uuid.NAMESPACE_DNS, f"{package_id}:{row.effect_event_id}:v1.2")
                    ),
                    package_id=package_id,
                    sequence_file_id=sequence_file_id,
                    effect_event_id=row.effect_event_id,
                    effect_type=row.effect_type,
                    effect_family=mapping["effect_family"],
                    motion_class=MotionClass(mapping["motion_class"]),
                    color_class=ColorClass(mapping["color_class"]),
                    energy_class=energy_class,
                    continuity_class=ContinuityClass(mapping["continuity_class"]),
                    spatial_class=self._spatial_from_row(mapping["spatial_class"], row),
                    source=source,
                    map_confidence=confidence,
                    target_name=row.target_name,
                    layer_index=row.layer_index,
                    start_ms=row.start_ms,
                    end_ms=row.end_ms,
                    duration_ms=row.duration_ms,
                    start_beat_index=row.start_beat_index,
                    end_beat_index=row.end_beat_index,
                    section_label=row.section_label,
                    onset_sync_score=row.onset_sync_score,
                    param_signature=self._param_signature(row, enriched),
                    preserved_params=preserved,
                    blend_mode=blend_mode_raw,
                    mix=mix_raw,
                )
            )
        return tuple(phrases)

    def _map_effect(self, effect_type: str) -> tuple[dict[str, str], PhraseSource, float]:
        normalized = self._normalize_effect_key(effect_type)
        if normalized in self._map:
            return self._map[normalized], PhraseSource.EFFECT_TYPE_MAP, 1.0
        for key, value in self._map.items():
            if key in normalized:
                return value, PhraseSource.EFFECT_TYPE_MAP, 0.85
        return (
            {
                "effect_family": "unknown",
                "motion_class": "unknown",
                "color_class": "unknown",
                "energy_class": "unknown",
                "continuity_class": "unknown",
                "spatial_class": "unknown",
            },
            PhraseSource.FALLBACK,
            0.25,
        )

    @staticmethod
    def _derive_energy_class(row: AlignedEffectEvent, mapping: dict[str, str]) -> EnergyClass:
        if row.energy_at_onset is not None:
            energy = float(row.energy_at_onset)
            if energy >= 0.82 and (row.onset_sync_score or 0.0) >= 0.75:
                return EnergyClass.BURST
            if energy >= 0.65:
                return EnergyClass.HIGH
            if energy <= 0.22:
                return EnergyClass.LOW
            return EnergyClass.MID

        if row.duration_ms <= 220 and (row.onset_sync_score or 0.0) >= 0.9:
            return EnergyClass.BURST
        if row.duration_ms <= 500:
            return EnergyClass.HIGH
        if row.duration_ms >= 3000:
            return EnergyClass.LOW

        default_energy = mapping.get("energy_class", "unknown")
        if default_energy in {"low", "mid", "high", "burst"}:
            return EnergyClass(default_energy)
        return EnergyClass.UNKNOWN

    @staticmethod
    def _spatial_from_row(mapped: str, row: AlignedEffectEvent) -> SpatialClass:
        if mapped != "unknown":
            return SpatialClass(mapped)
        if "group" in row.target_name.lower():
            return SpatialClass.GROUP
        return SpatialClass.SINGLE_TARGET

    @staticmethod
    def _extract_preserved_params(
        enriched: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None, float | None]:
        """Extract structured params, blend_mode, and mix from enriched event.

        Args:
            enriched: Enriched event dict from profiling.

        Returns:
            Tuple of (preserved_params dict, blend_mode string, mix float).
        """
        preserved: dict[str, Any] = {}
        blend_mode: str | None = None
        mix: float | None = None

        params = enriched.get("effectdb_params", [])
        if isinstance(params, list):
            for param in params:
                if not isinstance(param, dict):
                    continue
                name = str(param.get("param_name_normalized", ""))
                if not name:
                    continue
                value = (
                    param.get("value_string")
                    or param.get("value_float")
                    or param.get("value_int")
                    or param.get("value_bool")
                )
                if value is not None:
                    preserved[name] = value

        raw_blend = enriched.get("blend_mode")
        if isinstance(raw_blend, str) and raw_blend:
            blend_mode = raw_blend

        raw_mix = enriched.get("mix")
        if raw_mix is not None:
            try:
                mix = float(raw_mix)
                mix = max(0.0, min(1.0, mix))
            except (ValueError, TypeError):
                pass

        return preserved, blend_mode, mix

    @staticmethod
    def _param_signature(row: AlignedEffectEvent, enriched: dict[str, Any]) -> str:
        params = enriched.get("effectdb_params", [])
        serialized: str
        if isinstance(params, list) and params:
            tuples: list[tuple[str, str, str, str]] = []
            for param in params:
                if not isinstance(param, dict):
                    continue
                tuples.append(
                    (
                        str(param.get("namespace", "")),
                        str(param.get("param_name_normalized", "")),
                        str(param.get("value_type", "")),
                        str(
                            param.get("value_string")
                            or param.get("value_float")
                            or param.get("value_int")
                            or param.get("value_bool")
                            or ""
                        ),
                    )
                )
            tuples.sort()
            serialized = json.dumps(tuples, separators=(",", ":"), ensure_ascii=False)
        else:
            serialized = str(enriched.get("config_fingerprint") or row.effect_event_id)
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()
