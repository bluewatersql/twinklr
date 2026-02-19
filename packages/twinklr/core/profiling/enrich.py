"""Join extracted effect events with layout profile context."""

from __future__ import annotations

from collections.abc import Sequence

from twinklr.core.profiling.models.enums import TargetKind
from twinklr.core.profiling.models.events import EffectEventRecord
from twinklr.core.profiling.models.layout import GroupProfile, LayoutProfile, ModelProfile
from twinklr.core.profiling.models.profile import EnrichedEventRecord


def _model_bbox(model: ModelProfile) -> tuple[float, float, float, float]:
    x = model.position.get("world_x", 0.0)
    y = model.position.get("world_y", 0.0)
    return x, y, x, y


def _group_bbox(
    group: GroupProfile, model_lookup: dict[str, ModelProfile]
) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for member in group.members:
        base = member.split("/")[0]
        model = model_lookup.get(base)
        if model is None:
            continue
        xs.append(model.position.get("world_x", 0.0))
        ys.append(model.position.get("world_y", 0.0))
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def enrich_events(
    events: Sequence[EffectEventRecord],
    layout_profile: LayoutProfile | None,
) -> tuple[EnrichedEventRecord, ...]:
    """Enrich effect events with optional layout model/group context."""
    model_lookup: dict[str, ModelProfile] = {}
    group_lookup: dict[str, GroupProfile] = {}
    if layout_profile is not None:
        model_lookup = {model.name: model for model in layout_profile.models}
        group_lookup = {group.name: group for group in layout_profile.groups}

    enriched: list[EnrichedEventRecord] = []
    for event in events:
        model = model_lookup.get(event.target_name)
        if model is not None:
            x0, y0, x1, y1 = _model_bbox(model)
            enriched.append(
                EnrichedEventRecord(
                    effect_event_id=event.effect_event_id,
                    target_name=event.target_name,
                    layer_index=event.layer_index,
                    layer_name=event.layer_name,
                    effect_type=event.effect_type,
                    start_ms=event.start_ms,
                    end_ms=event.end_ms,
                    config_fingerprint=event.config_fingerprint,
                    effectdb_ref=event.effectdb_ref,
                    effectdb_settings_raw=event.effectdb_settings_raw,
                    effectdb_parser_version=event.effectdb_parser_version,
                    effectdb_parse_status=event.effectdb_parse_status,
                    effectdb_params=event.effectdb_params,
                    effectdb_parse_errors=event.effectdb_parse_errors,
                    palette=event.palette,
                    protected=event.protected,
                    label=event.label,
                    feat_duration_ms=event.end_ms - event.start_ms,
                    target_kind=TargetKind.MODEL,
                    target_semantic_tags=model.semantic_tags,
                    target_category=model.category.value,
                    target_pixel_count=model.pixel_count,
                    target_string_type=model.string_type,
                    target_layout_group=model.layout_group,
                    target_is_homogeneous=None,
                    target_x0=x0,
                    target_y0=y0,
                    target_x1=x1,
                    target_y1=y1,
                )
            )
            continue

        group = group_lookup.get(event.target_name)
        if group is not None:
            bbox = _group_bbox(group, model_lookup)
            gx0: float | None = None
            gy0: float | None = None
            gx1: float | None = None
            gy1: float | None = None
            if bbox is not None:
                gx0, gy0, gx1, gy1 = bbox

            target_category = None
            if len(group.member_category_composition) == 1:
                target_category = next(iter(group.member_category_composition.keys()))

            enriched.append(
                EnrichedEventRecord(
                    effect_event_id=event.effect_event_id,
                    target_name=event.target_name,
                    layer_index=event.layer_index,
                    layer_name=event.layer_name,
                    effect_type=event.effect_type,
                    start_ms=event.start_ms,
                    end_ms=event.end_ms,
                    config_fingerprint=event.config_fingerprint,
                    effectdb_ref=event.effectdb_ref,
                    effectdb_settings_raw=event.effectdb_settings_raw,
                    effectdb_parser_version=event.effectdb_parser_version,
                    effectdb_parse_status=event.effectdb_parse_status,
                    effectdb_params=event.effectdb_params,
                    effectdb_parse_errors=event.effectdb_parse_errors,
                    palette=event.palette,
                    protected=event.protected,
                    label=event.label,
                    feat_duration_ms=event.end_ms - event.start_ms,
                    target_kind=TargetKind.GROUP,
                    target_semantic_tags=group.semantic_tags,
                    target_category=target_category,
                    target_pixel_count=group.total_pixels,
                    target_string_type=None,
                    target_layout_group=group.layout_group,
                    target_is_homogeneous=group.is_homogeneous,
                    target_x0=gx0,
                    target_y0=gy0,
                    target_x1=gx1,
                    target_y1=gy1,
                )
            )
            continue

        enriched.append(
            EnrichedEventRecord(
                effect_event_id=event.effect_event_id,
                target_name=event.target_name,
                layer_index=event.layer_index,
                layer_name=event.layer_name,
                effect_type=event.effect_type,
                start_ms=event.start_ms,
                end_ms=event.end_ms,
                config_fingerprint=event.config_fingerprint,
                effectdb_ref=event.effectdb_ref,
                effectdb_settings_raw=event.effectdb_settings_raw,
                effectdb_parser_version=event.effectdb_parser_version,
                effectdb_parse_status=event.effectdb_parse_status,
                effectdb_params=event.effectdb_params,
                effectdb_parse_errors=event.effectdb_parse_errors,
                palette=event.palette,
                protected=event.protected,
                label=event.label,
                feat_duration_ms=event.end_ms - event.start_ms,
                target_kind=TargetKind.UNKNOWN,
            )
        )

    return tuple(enriched)
