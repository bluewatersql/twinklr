"""Effect extraction from parsed XSequence models."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from twinklr.core.formats.xlights.sequence.models.xsq import Effect, XSequence
from twinklr.core.profiling.constants import EFFECTDB_PARSER_VERSION
from twinklr.core.profiling.effects.effectdb_parser import parse_effectdb_settings
from twinklr.core.profiling.models.events import BaseEffectEventsFile, EffectEventRecord


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _config_fingerprint(config: dict[str, Any]) -> str:
    return hashlib.sha1(_canonical_json(config).encode("utf-8")).hexdigest()


def _build_effect_config_dict(
    sequence: XSequence,
    effect: Effect,
) -> tuple[dict[str, Any], int | None, str | None]:
    config: dict[str, Any] = {}
    config.update(effect.parameters)
    config["_palette"] = effect.palette
    config["_protected"] = effect.protected
    if effect.label is not None:
        config["_label"] = effect.label

    effectdb_ref = effect.ref if isinstance(effect.ref, int) else None
    effectdb_settings: str | None = None

    if effectdb_ref is not None:
        settings = sequence.effect_db.get(effectdb_ref)
        if settings is not None:
            effectdb_settings = settings
            config["_effectdb_settings_raw"] = effectdb_settings

    return config, effectdb_ref, effectdb_settings


def extract_effect_events(
    sequence: XSequence,
    package_id: str,
    sequence_file_id: str,
    sequence_sha256: str,
) -> BaseEffectEventsFile:
    """Extract all effect events from a parsed XSequence.

    Events are sorted by `(start_ms, layer_name, target_name, effect_type)`.
    """
    events: list[EffectEventRecord] = []

    for element in sequence.element_effects:
        target_name = element.element_name
        for layer in element.layers:
            layer_name = layer.name or f"layer_{layer.index}"
            for effect in layer.effects:
                config, effectdb_ref, effectdb_settings = _build_effect_config_dict(
                    sequence, effect
                )
                parsed_settings = parse_effectdb_settings(effectdb_settings)
                events.append(
                    EffectEventRecord(
                        effect_event_id=str(uuid.uuid4()),
                        target_name=target_name,
                        layer_index=layer.index,
                        layer_name=layer_name,
                        effect_type=effect.effect_type,
                        start_ms=effect.start_time_ms,
                        end_ms=effect.end_time_ms,
                        config_fingerprint=_config_fingerprint(config),
                        effectdb_ref=effectdb_ref,
                        effectdb_settings_raw=effectdb_settings,
                        effectdb_parser_version=EFFECTDB_PARSER_VERSION,
                        effectdb_parse_status=parsed_settings.status,
                        effectdb_params=parsed_settings.params,
                        effectdb_parse_errors=parsed_settings.errors,
                        palette=effect.palette,
                        protected=effect.protected,
                        label=effect.label,
                    )
                )

    events.sort(key=lambda e: (e.start_ms, e.layer_name, e.target_name, e.effect_type))

    return BaseEffectEventsFile(
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        sequence_sha256=sequence_sha256,
        events=tuple(events),
    )
