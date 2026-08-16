"""Adapt an xLights layout into Twinklr's planner and output mapping models."""

from __future__ import annotations

from collections import Counter
import re

from twinklr.core.formats.xlights.layout.models.rgb_effects import Layout, Model
from twinklr.core.profiling.layout.classifier import classify_semantic_tags
from twinklr.core.sequencer.display.xlights_mapping import XLightsGroupMapping, XLightsMapping
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.display import GroupPosition
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag
from twinklr.core.sequencer.vocabulary.display import (
    DetailCapability,
    DisplayElementKind,
    DisplayProminence,
    GroupArrangement,
)
from twinklr.core.sequencer.vocabulary.spatial import (
    DepthZone,
    DisplayZone,
    HorizontalZone,
    VerticalZone,
)

_KIND_BY_TAG: dict[str, DisplayElementKind] = {
    "arch": DisplayElementKind.ARCH,
    "cane": DisplayElementKind.CANDY_CANE,
    "cube": DisplayElementKind.CUBE,
    "flood": DisplayElementKind.FLOOD,
    "icicle": DisplayElementKind.ICICLES,
    "matrix": DisplayElementKind.MATRIX,
    "moving_head": DisplayElementKind.MOVING_HEAD,
    "snowflake": DisplayElementKind.SNOWFLAKE,
    "spinner": DisplayElementKind.SPINNER,
    "star": DisplayElementKind.STAR,
    "tree": DisplayElementKind.TREE,
    "window": DisplayElementKind.WINDOW_FRAME,
    "wreath": DisplayElementKind.WREATH,
}
_DISPLAY_AS_KINDS: dict[str, DisplayElementKind] = {
    "circle": DisplayElementKind.CIRCLE,
    "custom": DisplayElementKind.CUSTOM,
    "poly line": DisplayElementKind.POLYLINE,
    "single line": DisplayElementKind.SINGLE_LINE,
}
_ID_PARTS = re.compile(r"[^A-Z0-9]+")


def _active(model: Model) -> bool:
    return str((model.model_extra or {}).get("Active", "1")) != "0"


def _float(model: Model, name: str) -> float:
    raw = getattr(model, name, None)
    if raw is None or raw == "":
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _pixel_count(model: Model) -> int:
    values = model.model_extra or {}
    for count_key, per_key in (
        ("StringCount", "NodesPerString"),
        ("stringCount", "nodesPerString"),
        ("parm1", "parm2"),
    ):
        try:
            count = int(values.get(count_key, 0)) * int(values.get(per_key, 0))
        except (TypeError, ValueError):
            continue
        if count > 0:
            return count
    return 1


def _sanitize_id(name: str, used: set[str]) -> str:
    base = _ID_PARTS.sub("_", name.upper()).strip("_") or "DISPLAY_GROUP"
    if not base[0].isalpha():
        base = f"GROUP_{base}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _model_kind(model: Model) -> DisplayElementKind:
    tags = classify_semantic_tags(model.name, model.DisplayAs or "")
    for tag in sorted(tags):
        if tag in _KIND_BY_TAG:
            return _KIND_BY_TAG[tag]
    display_as = (model.DisplayAs or "").lower()
    if display_as.startswith("dmx"):
        return DisplayElementKind.DMX
    return _DISPLAY_AS_KINDS.get(display_as, DisplayElementKind.CUSTOM)


def _group_kind(models: list[Model]) -> DisplayElementKind:
    kinds = {_model_kind(model) for model in models}
    return next(iter(kinds)) if len(kinds) == 1 else DisplayElementKind.GROUP


def _arrangement(models: list[Model]) -> GroupArrangement:
    if len(models) == 1:
        return GroupArrangement.SINGLE
    spans = {
        GroupArrangement.HORIZONTAL_ROW: max(_float(m, "WorldPosX") for m in models)
        - min(_float(m, "WorldPosX") for m in models),
        GroupArrangement.VERTICAL_COLUMN: max(_float(m, "WorldPosY") for m in models)
        - min(_float(m, "WorldPosY") for m in models),
        GroupArrangement.DEPTH_SEQUENCE: max(_float(m, "WorldPosZ") for m in models)
        - min(_float(m, "WorldPosZ") for m in models),
    }
    dominant, span = max(spans.items(), key=lambda item: (item[1], -list(spans).index(item[0])))
    return dominant if span > 0.0 else GroupArrangement.CLUSTER


def _axis_zone(value: float, low: float, high: float, zones: tuple[object, ...]) -> object:
    if high <= low:
        return zones[len(zones) // 2]
    fraction = (value - low) / (high - low)
    index = min(len(zones) - 1, max(0, round(fraction * (len(zones) - 1))))
    return zones[index]


def _position(
    models: list[Model],
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
) -> GroupPosition:
    x = sum(_float(model, "WorldPosX") for model in models) / len(models)
    y = sum(_float(model, "WorldPosY") for model in models) / len(models)
    z = sum(_float(model, "WorldPosZ") for model in models) / len(models)
    horizontal = _axis_zone(
        x,
        *bounds[0],
        (
            HorizontalZone.FAR_LEFT,
            HorizontalZone.LEFT,
            HorizontalZone.CENTER_LEFT,
            HorizontalZone.CENTER,
            HorizontalZone.CENTER_RIGHT,
            HorizontalZone.RIGHT,
            HorizontalZone.FAR_RIGHT,
        ),
    )
    vertical = _axis_zone(
        y,
        *bounds[1],
        (
            VerticalZone.GROUND,
            VerticalZone.LOW,
            VerticalZone.MID,
            VerticalZone.HIGH,
            VerticalZone.TOP,
        ),
    )
    depth = _axis_zone(z, *bounds[2], (DepthZone.NEAR, DepthZone.MID, DepthZone.FAR))
    name_tags = set().union(
        *(classify_semantic_tags(model.name, model.DisplayAs or "") for model in models)
    )
    if name_tags & {"roof", "star", "icicle"} and vertical in {VerticalZone.HIGH, VerticalZone.TOP}:
        zone = DisplayZone.ROOF
    elif name_tags & {"window", "outline", "wreath"}:
        zone = DisplayZone.HOUSE
    else:
        zone = DisplayZone.YARD
    return GroupPosition(
        horizontal=horizontal,  # type: ignore[arg-type]
        vertical=vertical,  # type: ignore[arg-type]
        depth=depth,  # type: ignore[arg-type]
        zone=zone,
    )


def _detail(pixel_count: int) -> DetailCapability:
    if pixel_count >= 400:
        return DetailCapability.HIGH
    if pixel_count >= 80:
        return DetailCapability.MEDIUM
    return DetailCapability.LOW


def layout_to_choreography(
    layout: Layout,
    *,
    graph_id: str = "xlights_layout",
) -> tuple[ChoreographyGraph, XLightsMapping]:
    """Create graph/mapping from explicit groups plus active ungrouped models.

    Group membership is resolved recursively and strictly: cycles and unknown names
    fail before planning. An active model claimed by any group is not duplicated as a
    standalone target.
    """
    raw_models = layout.models.model if layout.models else []
    duplicate_model_names = sorted(
        name for name, count in Counter(model.name for model in raw_models).items() if count > 1
    )
    if duplicate_model_names:
        raise ValueError(
            f"xLights layout contains duplicate raw model names: {duplicate_model_names}"
        )
    active_models = [model for model in raw_models if _active(model)]
    inactive_model_names = {model.name for model in raw_models if not _active(model)}
    model_by_name = {model.name: model for model in active_models}
    raw_groups = layout.modelGroups.modelGroup if layout.modelGroups else []
    group_by_name = {group.name: group for group in raw_groups}
    if len(group_by_name) != len(raw_groups):
        duplicates = sorted(
            name for name, count in Counter(group.name for group in raw_groups).items() if count > 1
        )
        raise ValueError(f"xLights layout contains duplicate model-group names: {duplicates}")
    intersecting_names = sorted({model.name for model in raw_models} & set(group_by_name))
    if intersecting_names:
        raise ValueError(
            f"xLights layout raw name(s) used by both a model and model group: {intersecting_names}"
        )

    def resolve_group(name: str, stack: tuple[str, ...] = ()) -> list[Model]:
        if name in stack:
            raise ValueError(f"xLights model-group membership cycle: {' -> '.join((*stack, name))}")
        group = group_by_name[name]
        resolved: list[Model] = []
        seen: set[str] = set()
        for member in group.get_model_list():
            base = member.split("/", 1)[0]
            if base in model_by_name:
                candidates = [model_by_name[base]]
            elif base in inactive_model_names:
                candidates = []
            elif base in group_by_name:
                candidates = resolve_group(base, (*stack, name))
            else:
                raise ValueError(
                    f"xLights model group {name!r} references unknown model/group {base!r}"
                )
            for candidate in candidates:
                if candidate.name not in seen:
                    seen.add(candidate.name)
                    resolved.append(candidate)
        return resolved

    resolved_groups: list[tuple[str, list[Model], str | None]] = []
    claimed: set[str] = set()
    for group in raw_groups:
        members = resolve_group(group.name)
        if not members:
            continue
        claimed.update(model.name for model in members)
        resolved_groups.append((group.name, members, group.name))
    resolved_groups.extend(
        (model.name, [model], None) for model in active_models if model.name not in claimed
    )
    if not resolved_groups:
        raise ValueError("xLights layout contains no targetable models")

    axis_bounds = tuple(
        (
            min(_float(model, axis) for model in active_models),
            max(_float(model, axis) for model in active_models),
        )
        for axis in ("WorldPosX", "WorldPosY", "WorldPosZ")
    )
    used_ids: set[str] = set()
    total_pixels = sum(_pixel_count(model) for model in active_models)
    graph_groups: list[ChoreoGroup] = []
    mapping_entries: list[XLightsGroupMapping] = []
    for name, members, group_name in resolved_groups:
        group_id = _sanitize_id(name, used_ids)
        pixels = sum(_pixel_count(model) for model in members)
        kind = _group_kind(members)
        position = _position(members, axis_bounds)  # type: ignore[arg-type]
        tag_by_zone = {
            DisplayZone.HOUSE: ChoreoTag.HOUSE,
            DisplayZone.ROOF: ChoreoTag.ROOF,
            DisplayZone.YARD: ChoreoTag.YARD,
            DisplayZone.PERIMETER: ChoreoTag.PERIMETER,
        }
        fraction = pixels / total_pixels if total_pixels else 0.0
        name_lower = name.lower()
        if "mega" in name_lower or kind is DisplayElementKind.MATRIX:
            prominence = DisplayProminence.HERO
        elif fraction >= 0.25:
            prominence = DisplayProminence.ANCHOR
        elif len(members) > 1:
            prominence = DisplayProminence.SUPPORTING
        else:
            prominence = DisplayProminence.ACCENT
        graph_groups.append(
            ChoreoGroup(
                id=group_id,
                role=group_id,
                element_kind=kind,
                arrangement=_arrangement(members),
                prominence=prominence,
                detail_capability=_detail(pixels),
                position=position,
                fixture_count=len(members),
                pixel_fraction=fraction,
                tags=[tag_by_zone[position.zone]] if position.zone in tag_by_zone else [],
            )
        )
        mapping_entries.append(
            XLightsGroupMapping(
                choreo_id=group_id,
                group_name=group_name,
                model_names=[] if group_name is not None else [members[0].name],
            )
        )

    return (
        ChoreographyGraph(graph_id=graph_id, groups=graph_groups),
        XLightsMapping(entries=mapping_entries),
    )


__all__ = ["layout_to_choreography"]
