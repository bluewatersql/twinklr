"""Layout profiler built on top of LayoutParser."""

from __future__ import annotations

import statistics
from collections import Counter
from pathlib import Path

from twinklr.core.formats.xlights.layout.models.rgb_effects import (
    Layout,
    Model,
    ModelGroup,
    ModelGroups,
    Models,
    Settings,
)
from twinklr.core.formats.xlights.layout.parser import LayoutParser
from twinklr.core.profiling.layout.classifier import (
    DMX_MODEL_TYPES,
    classify_model_category,
    classify_semantic_size,
    classify_semantic_tags,
)
from twinklr.core.profiling.layout.spatial import (
    compute_spatial_statistics,
    detect_model_families,
    reconstruct_chain_sequences,
)
from twinklr.core.profiling.models.enums import ModelCategory, StartChannelFormat
from twinklr.core.profiling.models.layout import (
    DmxColorWheelEntry,
    DmxFixtureProfile,
    DmxMotorProfile,
    GroupProfile,
    LayoutMetadata,
    LayoutProfile,
    LayoutStatistics,
    ModelProfile,
    PixelStats,
    StartChannelInfo,
    SubModelProfile,
)
from twinklr.core.utils.logging import get_logger

logger = get_logger(__name__)


class LayoutProfiler:
    """Wrap LayoutParser and compute typed layout profile outputs."""

    def __init__(self) -> None:
        self._parser = LayoutParser()
        # Viewpoints in vendor files can contain dynamic camera arrays not modeled in
        # strict Viewpoints schema yet. Restrict parsing to sections we profile now.
        self._parser.KNOWN_TYPES = {
            "models": Models,
            "modelGroups": ModelGroups,
            "settings": Settings,
        }

    def profile(self, xml_path: Path) -> LayoutProfile:
        """Profile a standalone `xlights_rgbeffects.xml` file."""
        xml_path = Path(xml_path)
        layout = self._parser.parse(xml_path)

        models = [
            self._profile_model(model) for model in (layout.models.model if layout.models else [])
        ]
        model_lookup = {model.name: model for model in models}
        groups = [
            self._profile_group(group, model_lookup)
            for group in (layout.modelGroups.modelGroup if layout.modelGroups else [])
        ]

        statistics_model = self._compute_statistics(models, groups)
        settings = self._extract_settings(layout)
        viewpoints = self._extract_viewpoints(layout)

        dmx_counts: Counter[str] = Counter()
        for model in models:
            if model.dmx_profile is not None:
                dmx_counts[model.dmx_profile.fixture_type] += 1

        return LayoutProfile(
            metadata=LayoutMetadata(
                source_file=xml_path.name,
                source_path=str(xml_path),
                file_sha256=self._sha256_file(xml_path),
                file_size_bytes=xml_path.stat().st_size,
            ),
            statistics=statistics_model,
            spatial=compute_spatial_statistics(models),
            models=tuple(models),
            groups=tuple(groups),
            settings=settings,
            viewpoints=viewpoints,
            dmx_fixture_summary=dict(dmx_counts) if dmx_counts else None,
        )

    def _safe_attr(self, model: Model, key: str, default: str = "") -> str:
        value = getattr(model, key, None)
        if value not in (None, ""):
            return str(value)
        extra = model.model_extra or {}
        if key in extra and extra[key] not in (None, ""):
            return str(extra[key])
        return default

    @staticmethod
    def _safe_int(value: str, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: str, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _sha256_file(path: Path) -> str:
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _infer_pixel_count(self, attrs: dict[str, str]) -> int:
        for count_key, per_key in [
            ("StringCount", "NodesPerString"),
            ("stringCount", "nodesPerString"),
            ("parm1", "parm2"),
        ]:
            if count_key in attrs and per_key in attrs:
                try:
                    return int(attrs[count_key]) * int(attrs[per_key])
                except (TypeError, ValueError):
                    continue

        for key, value in attrs.items():
            if "pixel" in key.lower() and value.isdigit():
                return int(value)

        return 1

    def _infer_node_count(self, attrs: dict[str, str]) -> int:
        parm1 = self._safe_int(attrs.get("parm1", "0"))
        parm2 = self._safe_int(attrs.get("parm2", "0"))
        if parm1 > 0 and parm2 > 0:
            return parm1 * parm2
        return self._infer_pixel_count(attrs)

    def _infer_channels_per_node(self, attrs: dict[str, str]) -> int:
        string_type = attrs.get("StringType", "").lower()
        if "single color" in string_type:
            return 1
        if "rgbw" in string_type:
            return 4
        if "rgb" in string_type:
            return 3
        return 3

    def _infer_channel_count(self, attrs: dict[str, str]) -> int:
        return self._infer_node_count(attrs) * self._infer_channels_per_node(attrs)

    def _infer_string_count(self, attrs: dict[str, str]) -> int:
        if "Strings" in attrs:
            return self._safe_int(attrs["Strings"], 1)
        if "StringCount" in attrs:
            return self._safe_int(attrs["StringCount"], 1)
        return self._safe_int(attrs.get("parm1", "1"), 1)

    def _infer_light_count(self, attrs: dict[str, str]) -> int:
        nodes = self._infer_node_count(attrs)
        parm3 = self._safe_int(attrs.get("parm3", "1"), 1)
        return nodes * max(parm3, 1)

    def _parse_start_channel(self, raw: str) -> StartChannelInfo | None:
        if not raw:
            return None
        if raw.startswith("#"):
            parts = raw[1:].split(":")
            if len(parts) == 2:
                return StartChannelInfo(
                    raw=raw,
                    format=StartChannelFormat.UNIVERSE_CHANNEL,
                    universe=self._safe_int(parts[0]),
                    channel=self._safe_int(parts[1]),
                )
            return None

        if raw.startswith((">", "&gt;")):
            clean = raw.lstrip(">").lstrip("&gt;")
            parts = clean.rsplit(":", 1)
            if len(parts) == 2:
                return StartChannelInfo(
                    raw=raw,
                    format=StartChannelFormat.CHAINED,
                    chained_to=parts[0].strip(),
                    offset=self._safe_int(parts[1]),
                )
            return None

        return StartChannelInfo(
            raw=raw,
            format=StartChannelFormat.ABSOLUTE,
            channel=self._safe_int(raw),
        )

    def _extract_dmx_profile(self, model: Model) -> DmxFixtureProfile | None:
        attrs = self._model_attrs(model)
        display_as = attrs.get("DisplayAs", "").lower()
        if display_as not in DMX_MODEL_TYPES:
            return None

        color_wheel: list[DmxColorWheelEntry] = []
        for i in range(20):
            dmx_key = f"DmxColorWheelDMX{i}"
            color_key = f"DmxColorWheelColor{i}"
            if dmx_key in attrs and color_key in attrs:
                color_wheel.append(
                    DmxColorWheelEntry(dmx_value=attrs[dmx_key], color=attrs[color_key])
                )

        extra = model.model_extra or {}
        pan_raw = extra.get("PanMotor")
        tilt_raw = extra.get("TiltMotor")

        def _motor(raw_motor: object) -> DmxMotorProfile | None:
            if not isinstance(raw_motor, dict):
                return None
            return DmxMotorProfile(
                channel_coarse=raw_motor.get("ChannelCoarse"),
                channel_fine=raw_motor.get("ChannelFine"),
                slew_limit=raw_motor.get("SlewLimit"),
                range_of_motion=raw_motor.get("RangeOfMotion"),
                orient_zero=raw_motor.get("OrientZero"),
                orient_home=raw_motor.get("OrientHome"),
                reverse=raw_motor.get("Reverse"),
            )

        node_names = tuple(n.strip() for n in attrs.get("NodeNames", "").split(",") if n.strip())

        return DmxFixtureProfile(
            fixture_type=attrs.get("DisplayAs", ""),
            channel_count=self._safe_int(attrs.get("parm1", "0")),
            color_type=attrs.get("DmxColorType") or None,
            color_wheel=tuple(color_wheel),
            pan=_motor(pan_raw),
            tilt=_motor(tilt_raw),
            node_names=node_names,
            fixture_name=attrs.get("DmxFixture") or None,
        )

    def _extract_submodels(self, model: Model) -> tuple[SubModelProfile, ...]:
        submodels_raw = (model.model_extra or {}).get("subModel")
        if submodels_raw is None:
            return ()

        if isinstance(submodels_raw, dict):
            items = [submodels_raw]
        elif isinstance(submodels_raw, list):
            items = [item for item in submodels_raw if isinstance(item, dict)]
        else:
            return ()

        out: list[SubModelProfile] = []
        for item in items:
            pixel_ranges = [
                value
                for key, value in sorted(item.items())
                if key.startswith("line") and key[4:].isdigit() and isinstance(value, str)
            ]
            name = str(item.get("name") or item.get("Name") or "")
            if not name:
                continue
            out.append(
                SubModelProfile(
                    name=name,
                    type=str(item.get("type") or "unknown"),
                    layout=str(item.get("layout") or ""),
                    pixel_ranges=tuple(pixel_ranges),
                )
            )
        return tuple(out)

    def _extract_aliases(self, model: Model) -> tuple[str, ...]:
        if model.aliases is None:
            return ()
        alias_field = model.aliases.alias
        aliases = alias_field if isinstance(alias_field, list) else [alias_field]
        names = []
        for alias in aliases:
            name = alias.name
            if name.startswith("oldname:"):
                name = name[8:]
            if name:
                names.append(name)
        return tuple(names)

    def _model_attrs(self, model: Model) -> dict[str, str]:
        attrs = {
            "name": model.name,
            "DisplayAs": model.DisplayAs or "",
            "LayoutGroup": model.LayoutGroup or "",
            "StringType": model.StringType or "",
            "StartChannel": model.StartChannel or "",
            "WorldPosX": model.WorldPosX or "",
            "WorldPosY": model.WorldPosY or "",
            "WorldPosZ": model.WorldPosZ or "",
        }
        extra = model.model_extra or {}
        for key, value in extra.items():
            if isinstance(value, str):
                attrs[key] = value
        return attrs

    def _profile_model(self, model: Model) -> ModelProfile:
        attrs = self._model_attrs(model)
        name = attrs.get("name", "Unknown")
        display_as = attrs.get("DisplayAs", "")
        is_active = attrs.get("Active", "1") == "1"

        category = classify_model_category(name, display_as, is_active)
        semantic_tags = tuple(sorted(classify_semantic_tags(name, display_as)))

        pixel_count = self._infer_pixel_count(attrs)
        node_count = self._infer_node_count(attrs)
        channel_count = self._infer_channel_count(attrs)
        start_channel = self._parse_start_channel(attrs.get("StartChannel", ""))

        start_channel_no: int | None = None
        if start_channel is not None and start_channel.channel is not None:
            start_channel_no = start_channel.channel
        end_channel_no = (
            start_channel_no + channel_count - 1
            if start_channel_no is not None and channel_count > 0
            else None
        )

        buffer_w = self._safe_int(attrs.get("BufferWi", "0"))
        buffer_h = self._safe_int(attrs.get("BufferHt", "0"))
        if buffer_w == 0 and buffer_h == 0:
            buffer_w = self._safe_int(attrs.get("parm1", "0"))
            buffer_h = self._safe_int(attrs.get("parm2", "0"))
        default_buffer_wxh = f"{buffer_w} x {buffer_h}" if (buffer_w > 0 or buffer_h > 0) else ""

        model_chain = attrs.get("ModelChain", "")
        chain_next = model_chain[1:].strip() if model_chain.startswith(">") else None

        controller_connection = None
        if model.controller_connection is not None:
            controller_connection = model.controller_connection.model_dump(exclude_none=True)

        return ModelProfile(
            name=name,
            display_as=display_as,
            category=category,
            is_active=is_active,
            string_type=attrs.get("StringType", ""),
            semantic_tags=semantic_tags,
            semantic_size=classify_semantic_size(name),
            position={
                "world_x": self._safe_float(attrs.get("WorldPosX", "0")),
                "world_y": self._safe_float(attrs.get("WorldPosY", "0")),
                "world_z": self._safe_float(attrs.get("WorldPosZ", "0")),
            },
            scale={
                "x": self._safe_float(attrs.get("ScaleX", "1"), 1.0),
                "y": self._safe_float(attrs.get("ScaleY", "1"), 1.0),
                "z": self._safe_float(attrs.get("ScaleZ", "1"), 1.0),
            },
            rotation={
                "x": self._safe_float(attrs.get("RotateX", "0")),
                "y": self._safe_float(attrs.get("RotateY", "0")),
                "z": self._safe_float(attrs.get("RotateZ", "0")),
            },
            pixel_count=pixel_count,
            node_count=node_count,
            string_count=self._infer_string_count(attrs),
            channels_per_node=self._infer_channels_per_node(attrs),
            channel_count=channel_count,
            light_count=self._infer_light_count(attrs),
            layout_group=attrs.get("LayoutGroup", "Default") or "Default",
            default_buffer_wxh=default_buffer_wxh,
            est_current_amps=round(pixel_count * 0.06, 2) if pixel_count > 0 else 0.0,
            start_channel=start_channel,
            start_channel_no=start_channel_no,
            end_channel_no=end_channel_no,
            controller_connection=controller_connection,
            submodels=self._extract_submodels(model),
            aliases=self._extract_aliases(model),
            dmx_profile=self._extract_dmx_profile(model),
            chain_next=chain_next,
        )

    def _profile_group(
        self, group: ModelGroup, model_lookup: dict[str, ModelProfile]
    ) -> GroupProfile:
        members = tuple(group.get_model_list())
        member_types: Counter[str] = Counter()
        member_categories: Counter[str] = Counter()
        unresolved: list[str] = []
        total_pixels = 0

        for member in members:
            base = member.split("/")[0]
            model = model_lookup.get(base)
            if model is None:
                unresolved.append(member)
                continue
            member_types[model.display_as] += 1
            member_categories[model.category.value] += 1
            total_pixels += model.pixel_count

        return GroupProfile(
            name=group.name,
            members=members,
            model_count=len(members),
            semantic_tags=tuple(sorted(classify_semantic_tags(group.name))),
            layout=str((group.model_extra or {}).get("layout", "")),
            layout_group=group.LayoutGroup or "Default",
            is_homogeneous=len(member_types) <= 1 and len(members) > 0,
            total_pixels=total_pixels,
            member_type_composition=dict(member_types),
            member_category_composition=dict(member_categories),
            unresolved_members=tuple(sorted(set(unresolved))),
        )

    def _compute_statistics(
        self,
        models: list[ModelProfile],
        _groups: list[GroupProfile],
    ) -> LayoutStatistics:
        display_models = [m for m in models if m.category is ModelCategory.DISPLAY]
        dmx_models = [m for m in models if m.category is ModelCategory.DMX_FIXTURE]
        auxiliary_models = [m for m in models if m.category is ModelCategory.AUXILIARY]
        inactive_models = [m for m in models if m.category is ModelCategory.INACTIVE]

        model_type_distribution = Counter(m.display_as for m in display_models if m.display_as)
        string_type_distribution = Counter(m.string_type for m in models if m.string_type)
        semantic_tag_distribution: Counter[str] = Counter()
        for model in models:
            semantic_tag_distribution.update(model.semantic_tags)

        pixel_counts = [m.pixel_count for m in display_models if m.pixel_count > 0]
        pixel_stats = (
            PixelStats(
                total=sum(pixel_counts),
                min=min(pixel_counts),
                max=max(pixel_counts),
                mean=round(statistics.mean(pixel_counts), 1),
                median=round(statistics.median(pixel_counts), 1),
            )
            if pixel_counts
            else None
        )

        channel_counts = [m.channel_count for m in display_models if m.channel_count > 0]
        channel_stats = (
            {
                "total": sum(channel_counts),
                "min": min(channel_counts),
                "max": max(channel_counts),
                "mean": round(statistics.mean(channel_counts), 1),
            }
            if channel_counts
            else None
        )

        protocol_distribution: Counter[str] = Counter()
        for model in models:
            if model.controller_connection and "protocol" in model.controller_connection:
                protocol_distribution[str(model.controller_connection["protocol"])] += 1

        layout_group_distribution = Counter(m.layout_group for m in models)
        chain_sequences = reconstruct_chain_sequences(models)

        return LayoutStatistics(
            total_models=len(models),
            display_models=len(display_models),
            dmx_fixtures=len(dmx_models),
            auxiliary_models=len(auxiliary_models),
            inactive_models=len(inactive_models),
            total_submodels=sum(len(m.submodels) for m in models),
            model_chained_count=sum(1 for m in models if m.chain_next),
            address_chained_count=sum(
                1
                for m in models
                if m.start_channel is not None
                and m.start_channel.format is StartChannelFormat.CHAINED
            ),
            chain_sequences=chain_sequences,
            model_families=detect_model_families(models),
            model_type_distribution=dict(model_type_distribution.most_common()),
            string_type_distribution=dict(string_type_distribution.most_common()),
            semantic_tag_distribution=dict(semantic_tag_distribution.most_common()),
            pixel_stats=pixel_stats,
            channel_stats=channel_stats,
            protocol_distribution=dict(protocol_distribution.most_common()),
            layout_group_distribution=dict(layout_group_distribution.most_common()),
        )

    def _extract_settings(self, layout: Layout) -> dict[str, str]:
        if layout.settings is None:
            return {}
        dumped = layout.settings.model_dump(exclude_none=True)
        return {k: str(v) for k, v in dumped.items() if v not in (None, "")}

    def _extract_viewpoints(self, layout: Layout) -> tuple[dict[str, str | float | bool], ...]:
        if layout.viewpoints is None:
            return ()

        entries: list[dict[str, str | float | bool]] = []
        for camera_name in ("DefaultCamera2D", "DefaultCamera3D"):
            camera = getattr(layout.viewpoints, camera_name, None)
            if camera is None:
                continue
            data = camera.model_dump(exclude_none=True)
            payload: dict[str, str | float | bool] = {"type": camera_name}
            payload.update({k: str(v) for k, v in data.items() if v not in (None, "")})
            entries.append(payload)
        return tuple(entries)
