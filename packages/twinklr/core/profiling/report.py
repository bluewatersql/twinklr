"""Markdown report generators for profiling outputs."""

from __future__ import annotations

from collections import Counter

from twinklr.core.profiling.models.layout import LayoutProfile
from twinklr.core.profiling.models.profile import SequencePackProfile


def _top_items(mapping: dict[str, int], limit: int = 20) -> list[tuple[str, int]]:
    return sorted(mapping.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _safe_pct(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (value / total) * 100.0


def _write_key_value_table(
    lines: list[str],
    rows: list[tuple[str, str]],
    headers: tuple[str, str] = ("Key", "Value"),
) -> None:
    lines.append(f"| {headers[0]} | {headers[1]} |")
    lines.append("| --- | --- |")
    for left, right in rows:
        lines.append(f"| {left} | {right} |")


def _write_ranked_counts_table(
    lines: list[str],
    rows: list[tuple[str, int]],
    total: int,
    label_header: str = "Name",
) -> None:
    lines.append(f"| # | {label_header} | Count | Share |")
    lines.append("| --- | --- | ---: | ---: |")
    for idx, (name, count) in enumerate(rows, start=1):
        lines.append(f"| {idx} | {name} | {count} | {_safe_pct(count, total):.1f}% |")


def generate_layout_report_md(layout_profile: LayoutProfile) -> str:
    """Generate human-readable markdown for a layout profile."""
    lines: list[str] = []
    write = lines.append

    write("# RGB Effects Layout Profile")
    write("")
    write("## Metadata")
    write(f"- Source file: `{layout_profile.metadata.source_file}`")
    write(f"- Source path: `{layout_profile.metadata.source_path}`")
    write(f"- SHA256: `{layout_profile.metadata.file_sha256}`")
    write(f"- File size (bytes): {layout_profile.metadata.file_size_bytes}")
    write(f"- Models: {layout_profile.statistics.total_models}")
    write(f"- Groups: {len(layout_profile.groups)}")
    write("")

    write("## Model Summary")
    write(f"- Display models: {layout_profile.statistics.display_models}")
    write(f"- DMX fixtures: {layout_profile.statistics.dmx_fixtures}")
    write(f"- Auxiliary models: {layout_profile.statistics.auxiliary_models}")
    write(f"- Inactive models: {layout_profile.statistics.inactive_models}")
    write(f"- Total submodels: {layout_profile.statistics.total_submodels}")
    write(f"- Model chained count: {layout_profile.statistics.model_chained_count}")
    write(f"- Address chained count: {layout_profile.statistics.address_chained_count}")
    write("")

    if layout_profile.statistics.pixel_stats is not None:
        pixel_stats = layout_profile.statistics.pixel_stats
        write("## Pixel Statistics")
        write(f"- Total pixels: {pixel_stats.total}")
        write(f"- Min pixels/model: {pixel_stats.min}")
        write(f"- Max pixels/model: {pixel_stats.max}")
        write(f"- Mean pixels/model: {pixel_stats.mean:.2f}")
        write(f"- Median pixels/model: {pixel_stats.median:.2f}")
        write("")

    if layout_profile.statistics.channel_stats:
        write("## Channel Statistics")
        channel_rows = [
            (key, str(value))
            for key, value in sorted(
                layout_profile.statistics.channel_stats.items(), key=lambda item: item[0]
            )
        ]
        _write_key_value_table(lines, channel_rows)
        write("")

    if layout_profile.statistics.model_type_distribution:
        write("## Top Model Types")
        _write_ranked_counts_table(
            lines,
            _top_items(layout_profile.statistics.model_type_distribution, limit=20),
            layout_profile.statistics.total_models,
            label_header="DisplayAs",
        )
        write("")

    if layout_profile.statistics.string_type_distribution:
        write("## String Type Distribution")
        _write_ranked_counts_table(
            lines,
            _top_items(layout_profile.statistics.string_type_distribution, limit=20),
            layout_profile.statistics.total_models,
            label_header="String Type",
        )
        write("")

    if layout_profile.statistics.semantic_tag_distribution:
        write("## Semantic Tag Distribution")
        _write_ranked_counts_table(
            lines,
            _top_items(layout_profile.statistics.semantic_tag_distribution, limit=20),
            layout_profile.statistics.total_models,
            label_header="Tag",
        )
        write("")

    if layout_profile.statistics.model_families:
        write("## Model Families")
        _write_ranked_counts_table(
            lines,
            _top_items(layout_profile.statistics.model_families, limit=20),
            layout_profile.statistics.total_models,
            label_header="Family",
        )
        write("")

    if layout_profile.statistics.protocol_distribution:
        write("## Controller Protocols")
        _write_ranked_counts_table(
            lines,
            _top_items(layout_profile.statistics.protocol_distribution, limit=20),
            layout_profile.statistics.total_models,
            label_header="Protocol",
        )
        write("")

    if layout_profile.statistics.layout_group_distribution:
        write("## Layout Groups")
        _write_ranked_counts_table(
            lines,
            _top_items(layout_profile.statistics.layout_group_distribution, limit=20),
            layout_profile.statistics.total_models,
            label_header="Layout Group",
        )
        write("")

    if layout_profile.statistics.chain_sequences:
        write("## Chain Sequences (Top 20)")
        write("| # | Sequence | Length |")
        write("| --- | --- | ---: |")
        for idx, sequence in enumerate(layout_profile.statistics.chain_sequences[:20], start=1):
            write(f"| {idx} | {' -> '.join(sequence)} | {len(sequence)} |")
        write("")

    if layout_profile.dmx_fixture_summary:
        write("## DMX Fixture Summary")
        _write_ranked_counts_table(
            lines,
            _top_items(layout_profile.dmx_fixture_summary, limit=20),
            layout_profile.statistics.dmx_fixtures,
            label_header="Fixture Type",
        )
        write("")

    if layout_profile.spatial is not None:
        write("## Spatial Distribution")
        write(f"- 3D layout: {layout_profile.spatial.is_3d_layout}")
        write(f"- Bounding box: `{layout_profile.spatial.bounding_box}`")
        write(f"- Center of mass: `{layout_profile.spatial.center_of_mass}`")
        write(f"- Spread: `{layout_profile.spatial.spread}`")
        write("")

    if layout_profile.settings:
        write("## Settings (Top 20)")
        setting_rows = [
            (key, str(value).replace("\n", " "))
            for key, value in sorted(layout_profile.settings.items(), key=lambda item: item[0])[
                :20
            ]
        ]
        _write_key_value_table(lines, setting_rows, headers=("Setting", "Value"))
        write("")

    if layout_profile.models:
        write("## Display Models (Top 25)")
        write("| # | Name | DisplayAs | Category | Pixels | Channels | Layout Group | Tags |")
        write("| --- | --- | --- | --- | ---: | ---: | --- | --- |")
        for idx, model in enumerate(layout_profile.models[:25], start=1):
            tags = ", ".join(model.semantic_tags) if model.semantic_tags else "-"
            write(
                f"| {idx} | {model.name} | {model.display_as} | {model.category.value} "
                f"| {model.pixel_count} | {model.channel_count} | {model.layout_group or '-'} | {tags} |"
            )
        write("")

    dmx_models = [model for model in layout_profile.models if model.dmx_profile is not None]
    if dmx_models:
        write("## DMX Fixtures (Top 25)")
        write("| # | Name | Fixture Type | Channel Count | Color Type |")
        write("| --- | --- | --- | ---: | --- |")
        for idx, model in enumerate(dmx_models[:25], start=1):
            dmx_profile = model.dmx_profile
            if dmx_profile is None:
                continue
            write(
                f"| {idx} | {model.name} | {dmx_profile.fixture_type} | "
                f"{dmx_profile.channel_count} | {dmx_profile.color_type or '-'} |"
            )
        write("")

    if layout_profile.groups:
        homogeneous_count = sum(1 for group in layout_profile.groups if group.is_homogeneous)
        write("## Group Summary")
        write(f"- Total groups: {len(layout_profile.groups)}")
        write(f"- Homogeneous groups: {homogeneous_count}")
        write("")
        write("## Groups (Top 25)")
        write("| # | Name | Members | Pixels | Homogeneous | Layout Group |")
        write("| --- | --- | ---: | ---: | --- | --- |")
        for idx, group in enumerate(layout_profile.groups[:25], start=1):
            write(
                f"| {idx} | {group.name} | {group.model_count} | {group.total_pixels} | "
                f"{'yes' if group.is_homogeneous else 'no'} | {group.layout_group or '-'} |"
            )
        write("")
    else:
        write("## Groups")
        write("- None")
        write("")

    if layout_profile.viewpoints:
        write("## Viewpoints")
        write(f"- Viewpoint count: {len(layout_profile.viewpoints)}")
        write("")

    return "\n".join(lines).strip() + "\n"


def generate_profile_summary_md(profile: SequencePackProfile) -> str:
    """Generate human-readable markdown for full sequence pack profile."""
    lines: list[str] = []
    write = lines.append

    write("# Sequence Pack Profile Summary")
    write("")
    write("## Package")
    write(f"- Package ID: `{profile.manifest.package_id}`")
    write(f"- ZIP SHA256: `{profile.manifest.zip_sha256}`")
    write(f"- Source extension(s): `{', '.join(sorted(profile.manifest.source_extensions))}`")
    write(f"- Files: {len(profile.manifest.files)}")
    write("")

    write("## Sequence Metadata")
    write(f"- Song: {profile.sequence_metadata.song or '-'}")
    write(f"- Artist: {profile.sequence_metadata.artist or '-'}")
    write(f"- Album: {profile.sequence_metadata.album or '-'}")
    write(f"- Author: {profile.sequence_metadata.author or '-'}")
    write(f"- xLights version: {profile.sequence_metadata.xlights_version}")
    write(f"- Duration (ms): {profile.sequence_metadata.sequence_duration_ms}")
    write(f"- Media file: `{profile.sequence_metadata.media_file}`")
    write("")

    write("## Effect Statistics")
    write(f"- Total events: {profile.effect_statistics.total_events}")
    write(f"- Distinct effect types: {profile.effect_statistics.distinct_effect_types}")
    write(f"- Total effect duration (ms): {profile.effect_statistics.total_effect_duration_ms}")
    write(f"- Avg effect duration (ms): {profile.effect_statistics.avg_effect_duration_ms:.2f}")
    write(f"- Targets with effects: {profile.effect_statistics.total_targets_with_effects}")
    write("")

    if profile.effect_statistics.effect_type_counts:
        write("## Top Effect Types (Top 20)")
        top_effect_types = _top_items(profile.effect_statistics.effect_type_counts, limit=20)
        write("| # | Effect Type | Count | Duration (ms) | Share |")
        write("| --- | --- | ---: | ---: | ---: |")
        for idx, (effect_type, count) in enumerate(top_effect_types, start=1):
            duration_ms = profile.effect_statistics.effect_type_durations_ms.get(effect_type, 0)
            write(
                f"| {idx} | {effect_type} | {count} | {duration_ms} | "
                f"{_safe_pct(count, profile.effect_statistics.total_events):.1f}% |"
            )
        write("")

    if profile.effect_statistics.effects_per_target:
        write("## Top Targets By Effects (Top 20)")
        _write_ranked_counts_table(
            lines,
            _top_items(profile.effect_statistics.effects_per_target, limit=20),
            profile.effect_statistics.total_events,
            label_header="Target",
        )
        write("")

    if profile.effect_statistics.layers_per_target:
        write("## Top Targets By Layer Breadth (Top 20)")
        _write_ranked_counts_table(
            lines,
            _top_items(profile.effect_statistics.layers_per_target, limit=20),
            max(profile.effect_statistics.layers_per_target.values()),
            label_header="Target",
        )
        write("")

    if profile.enriched_events:
        layer_counts = Counter(
            event.layer_name or str(event.layer_index) for event in profile.enriched_events
        )
        if layer_counts:
            write("## Top Layers By Event Count (Top 20)")
            write("| # | Layer | Events | Share |")
            write("| --- | --- | ---: | ---: |")
            for idx, (layer_name, count) in enumerate(layer_counts.most_common(20), start=1):
                write(
                    f"| {idx} | {layer_name} | {count} | "
                    f"{_safe_pct(count, profile.effect_statistics.total_events):.1f}% |"
                )
            write("")

        layout_coverage = Counter(
            (event.target_kind.value if event.target_kind is not None else "unknown")
            for event in profile.enriched_events
        )
        if layout_coverage:
            write("## Enrichment Coverage")
            _write_ranked_counts_table(
                lines,
                list(layout_coverage.items()),
                profile.effect_statistics.total_events,
                label_header="Target Kind",
            )
            write("")

    write("## Color Palettes")
    write(f"- Unique colors: {len(profile.palette_profile.unique_colors)}")
    write(f"- Single-color entries: {len(profile.palette_profile.single_colors)}")
    write(f"- Multi-color entries: {len(profile.palette_profile.color_palettes)}")
    if profile.palette_profile.classifications.by_color_family:
        family_counts: dict[str, int] = {
            family: len(entries)
            for family, entries in profile.palette_profile.classifications.by_color_family.items()
            if entries
        }
        if family_counts:
            write("")
            write("### Color Family Distribution")
            _write_ranked_counts_table(
                lines,
                _top_items(family_counts, limit=20),
                sum(family_counts.values()),
                label_header="Color Family",
            )
    write("")

    write("## Assets")
    write(f"- Assets: {len(profile.asset_inventory.assets)}")
    write(f"- Shaders: {len(profile.asset_inventory.shaders)}")
    if profile.asset_inventory.assets:
        write("")
        write("### Asset Inventory (Top 20)")
        write("| # | Type | Value |")
        write("| --- | --- | --- |")
        for idx, asset in enumerate(profile.asset_inventory.assets[:20], start=1):
            for key, value in sorted(asset.items(), key=lambda item: item[0]):
                write(f"| {idx} | {key} | {value} |")
    if profile.asset_inventory.shaders:
        write("")
        write("### Shader Inventory (Top 20)")
        write("| # | Type | Value |")
        write("| --- | --- | --- |")
        for idx, shader in enumerate(profile.asset_inventory.shaders[:20], start=1):
            for key, value in sorted(shader.items(), key=lambda item: item[0]):
                write(f"| {idx} | {key} | {value} |")

    if profile.layout_profile is not None:
        write("")
        write("## Layout")
        write(f"- Models: {profile.layout_profile.statistics.total_models}")
        write(f"- Groups: {len(profile.layout_profile.groups)}")
        write(f"- DMX fixtures: {profile.layout_profile.statistics.dmx_fixtures}")
        write(f"- Display models: {profile.layout_profile.statistics.display_models}")
        write(f"- Auxiliary models: {profile.layout_profile.statistics.auxiliary_models}")
        write(f"- Inactive models: {profile.layout_profile.statistics.inactive_models}")
    else:
        write("")
        write("## Layout")
        write("- No layout profile available in this package.")

    return "\n".join(lines).strip() + "\n"
