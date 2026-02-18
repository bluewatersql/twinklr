"""Markdown report generators for profiling outputs."""

from __future__ import annotations

from twinklr.core.profiling.models.layout import LayoutProfile
from twinklr.core.profiling.models.profile import SequencePackProfile


def generate_layout_report_md(layout_profile: LayoutProfile) -> str:
    """Generate human-readable markdown for a layout profile."""
    lines: list[str] = []
    write = lines.append

    write("# RGB Effects Layout Profile")
    write("")
    write("## Metadata")
    write(f"- Source file: `{layout_profile.metadata.source_file}`")
    write(f"- SHA256: `{layout_profile.metadata.file_sha256}`")
    write(f"- Models: {layout_profile.statistics.total_models}")
    write(f"- Groups: {len(layout_profile.groups)}")
    write("")

    write("## Model Summary")
    write(f"- Display models: {layout_profile.statistics.display_models}")
    write(f"- DMX fixtures: {layout_profile.statistics.dmx_fixtures}")
    write(f"- Auxiliary models: {layout_profile.statistics.auxiliary_models}")
    write(f"- Inactive models: {layout_profile.statistics.inactive_models}")
    write("")

    if layout_profile.spatial is not None:
        write("## Spatial Distribution")
        write(f"- 3D layout: {layout_profile.spatial.is_3d_layout}")
        write(f"- Bounding box: `{layout_profile.spatial.bounding_box}`")
        write("")

    write("## Groups")
    for group in layout_profile.groups[:20]:
        write(f"- `{group.name}` ({group.model_count} members)")

    return "\n".join(lines).strip() + "\n"


def generate_profile_summary_md(profile: SequencePackProfile) -> str:
    """Generate human-readable markdown for full sequence pack profile."""
    lines: list[str] = []
    write = lines.append

    write("# Sequence Pack Profile Summary")
    write("")
    write("## Package")
    write(f"- Package ID: `{profile.manifest.package_id}`")
    write(f"- Files: {len(profile.manifest.files)}")
    write("")

    write("## Sequence Metadata")
    write(f"- Song: {profile.sequence_metadata.song}")
    write(f"- Artist: {profile.sequence_metadata.artist}")
    write(f"- Duration (ms): {profile.sequence_metadata.sequence_duration_ms}")
    write("")

    write("## Effect Statistics")
    write(f"- Total events: {profile.effect_statistics.total_events}")
    write(f"- Distinct effect types: {profile.effect_statistics.distinct_effect_types}")
    write("")

    write("## Color Palettes")
    write(f"- Unique colors: {len(profile.palette_profile.unique_colors)}")
    write(f"- Single-color entries: {len(profile.palette_profile.single_colors)}")
    write(f"- Multi-color entries: {len(profile.palette_profile.color_palettes)}")
    write("")

    write("## Assets")
    write(f"- Assets: {len(profile.asset_inventory.assets)}")
    write(f"- Shaders: {len(profile.asset_inventory.shaders)}")

    if profile.layout_profile is not None:
        write("")
        write("## Layout")
        write(f"- Models: {profile.layout_profile.statistics.total_models}")
        write(f"- Groups: {len(profile.layout_profile.groups)}")

    return "\n".join(lines).strip() + "\n"
