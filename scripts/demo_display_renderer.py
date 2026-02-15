#!/usr/bin/env python3
"""Demo script for the display renderer pipeline.

Loads the group plan set and audio profile, creates a BeatGrid using
the real tempo/duration from audio analysis, builds section boundaries,
runs the display renderer, and exports an .xsq file for validation
in xLights.

Usage:
    uv run python scripts/demo_display_renderer.py [--plan PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import TYPE_CHECKING

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.models.xsq import (
    SequenceHead,
    XSequence,
)
from twinklr.core.sequencer.display.models.config import RenderConfig
from twinklr.core.sequencer.display.renderer import DisplayRenderer
from twinklr.core.sequencer.planning.group_plan import GroupPlanSet
from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
    ElementType,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

if TYPE_CHECKING:
    from twinklr.core.sequencer.display.renderer import RenderResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("demo_display_renderer")


# ---------------------------------------------------------------------------
# Synthetic BeatGrid
# ---------------------------------------------------------------------------


def build_beat_grid(
    duration_ms: float,
    tempo_bpm: float = 120.0,
    beats_per_bar: int = 4,
) -> BeatGrid:
    """Create a BeatGrid for a given duration and tempo.

    Args:
        duration_ms: Song duration in milliseconds.
        tempo_bpm: Tempo in beats per minute.
        beats_per_bar: Beats per bar (time signature).

    Returns:
        BeatGrid with calculated boundaries.
    """
    ms_per_beat = 60_000.0 / tempo_bpm
    ms_per_bar = ms_per_beat * beats_per_bar
    num_bars = int(duration_ms / ms_per_bar) + 1
    total_beats = num_bars * beats_per_bar

    beat_boundaries = [i * ms_per_beat for i in range(total_beats + 1)]
    bar_boundaries = [i * ms_per_bar for i in range(num_bars + 1)]
    eighth_boundaries = [i * ms_per_beat / 2 for i in range(total_beats * 2 + 1)]
    sixteenth_boundaries = [i * ms_per_beat / 4 for i in range(total_beats * 4 + 1)]

    logger.info(
        "BeatGrid: %.0f BPM, %d bars, %.1fs duration",
        tempo_bpm,
        num_bars,
        duration_ms / 1000,
    )

    return BeatGrid(
        bar_boundaries=bar_boundaries,
        beat_boundaries=beat_boundaries,
        eighth_boundaries=eighth_boundaries,
        sixteenth_boundaries=sixteenth_boundaries,
        tempo_bpm=tempo_bpm,
        beats_per_bar=beats_per_bar,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# Display Graph (matches typical display groups in plans)
# ---------------------------------------------------------------------------


def build_display_graph() -> DisplayGraph:
    """Build a display graph with groups matching the Rudolph plan.

    Each entry maps a plan-level group_id directly to an xLights
    element name. In V0 (group-based), the plan targets groups
    like ``ARCHES`` and the renderer places effects on the
    corresponding xLights model group (e.g., ``"Arches"``).

    The display_name must match an element that exists in the
    xLights layout — groups cannot be created in the sequence
    file alone.
    """
    # (group_id, role, display_name, element_type)
    # group_id is what the plan references
    # display_name is the exact xLights element name
    group_defs: list[tuple[str, str, str, ElementType]] = [
        ("OUTLINE", "OUTLINE", "Outlines", ElementType.MODEL_GROUP),
        ("MEGA_TREE", "MEGA_TREE", "MegaTree", ElementType.MODEL),
        ("HERO", "HERO", "Heroes", ElementType.MODEL_GROUP),
        ("ARCHES", "ARCHES", "Arches", ElementType.MODEL_GROUP),
        ("WINDOWS", "WINDOWS", "Windows", ElementType.MODEL_GROUP),
    ]

    groups = [
        DisplayGroup(
            group_id=group_id,
            role=role,
            display_name=display_name,
            element_type=etype,
        )
        for group_id, role, display_name, etype in group_defs
    ]

    logger.info("DisplayGraph: %d groups across %d roles", len(groups), len(group_defs))

    return DisplayGraph(
        display_id="rudolph_display",
        display_name="Rudolph Demo Display",
        groups=groups,
    )


# ---------------------------------------------------------------------------
# XSequence scaffold
# ---------------------------------------------------------------------------


def build_empty_sequence(duration_ms: int, media_file: str = "") -> XSequence:
    """Create an empty XSequence for the renderer to populate.

    Args:
        duration_ms: Sequence duration.
        media_file: Optional media file reference.

    Returns:
        Empty XSequence with metadata.
    """
    return XSequence(
        head=SequenceHead(
            version="2024.01",
            author="Twinklr Display Renderer (demo)",
            song="Rudolph the Red-Nosed Reindeer",
            sequence_timing="20 ms",
            media_file=media_file,
            sequence_duration_ms=duration_ms,
        ),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def load_plan(plan_path: Path) -> GroupPlanSet:
    """Load a GroupPlanSet from a JSON file."""
    logger.info("Loading plan from %s", plan_path)
    with plan_path.open() as f:
        data = json.load(f)
    return GroupPlanSet.model_validate(data)


def load_audio_profile(profile_path: Path) -> dict:
    """Load audio profile JSON and extract timing essentials.

    Returns a dict with:
      - tempo_bpm: float
      - duration_ms: int
      - sections: list[dict] with section_id, start_ms, end_ms

    Args:
        profile_path: Path to audio_profile.json.

    Returns:
        Dict with timing data extracted from the profile.
    """
    logger.info("Loading audio profile from %s", profile_path)
    with profile_path.open() as f:
        data = json.load(f)

    song_id = data.get("song_identity", {})
    structure = data.get("structure", {})

    tempo_bpm = float(song_id.get("bpm", 120.0))
    duration_ms = int(song_id.get("duration_ms", 190400))
    sections = structure.get("sections", [])

    logger.info(
        "Audio profile: %.1f BPM, %dms duration, %d sections",
        tempo_bpm,
        duration_ms,
        len(sections),
    )

    return {
        "tempo_bpm": tempo_bpm,
        "duration_ms": duration_ms,
        "sections": sections,
    }


def print_result_summary(result: RenderResult) -> None:
    """Print a human-readable summary of the render result."""
    plan = result.render_plan

    print("\n" + "=" * 60)
    print("DISPLAY RENDERER — RESULT SUMMARY")
    print("=" * 60)
    print(f"Render ID:       {plan.render_id}")
    print(f"Duration:        {plan.duration_ms / 1000:.1f}s")
    print(f"Elements:        {result.elements_created}")
    print(f"Effects placed:  {result.effects_written}")
    print(f"EffectDB entries:{result.effectdb_entries}")
    print(f"Palette entries: {result.palette_entries}")
    print(f"Warnings:        {len(result.warnings)}")
    print(f"Missing assets:  {len(result.missing_assets)}")

    print(f"\n--- Elements ({len(plan.groups)}) ---")
    for group in plan.groups:
        total = sum(len(ly.events) for ly in group.layers)
        layer_str = ", ".join(
            f"L{ly.layer_index}({ly.layer_role.value}: {len(ly.events)})" for ly in group.layers
        )
        print(f"  {group.element_name}: {total} effects [{layer_str}]")

    # Effect type histogram
    type_counts: dict[str, int] = {}
    for group in plan.groups:
        for layer in group.layers:
            for event in layer.events:
                type_counts[event.effect_type] = type_counts.get(event.effect_type, 0) + 1

    print("\n--- Effect Types ---")
    for et, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {et}: {count}")

    if result.warnings:
        print("\n--- Warnings (first 10) ---")
        for w in result.warnings[:10]:
            print(f"  ⚠ {w}")

    print("=" * 60)


def load_catalog(catalog_path: Path) -> object:
    """Load an AssetCatalog from a JSON file.

    Args:
        catalog_path: Path to asset_catalog.json.

    Returns:
        AssetCatalog with all entries.
    """
    from twinklr.core.agents.assets.models import AssetCatalog

    logger.info("Loading asset catalog from %s", catalog_path)
    with catalog_path.open() as f:
        data = json.load(f)
    catalog = AssetCatalog.model_validate(data)
    logger.info(
        "Catalog loaded: %d entries (%d created, %d cached, %d failed)",
        len(catalog.entries),
        catalog.total_created,
        catalog.total_cached,
        catalog.total_failed,
    )
    return catalog


def print_asset_resolution_summary(
    plan_set: GroupPlanSet,
    resolved_plan: GroupPlanSet,
) -> None:
    """Print a summary of asset resolution results.

    Args:
        plan_set: Original plan (before resolution).
        resolved_plan: Plan after resolution.
    """
    resolved_count = 0
    total_placements = 0
    for sp in resolved_plan.section_plans:
        for lp in sp.lane_plans:
            for cp in lp.coordination_plans:
                for p in cp.placements:
                    total_placements += 1
                    if p.resolved_asset_ids:
                        resolved_count += 1

    print("\n--- Asset Resolution ---")
    print(f"  Placements:  {total_placements}")
    print(f"  Resolved:    {resolved_count}")
    print(f"  Unresolved:  {total_placements - resolved_count}")


def main() -> None:
    """Run the display renderer demo."""
    default_artifact = Path("artifacts/02_rudolph_the_red_nosed_reindeer")

    parser = argparse.ArgumentParser(description="Demo display renderer")
    parser.add_argument(
        "--plan",
        type=Path,
        default=default_artifact / "group_plan_set.json",
        help="Path to GroupPlanSet JSON file",
    )
    parser.add_argument(
        "--audio-profile",
        type=Path,
        default=default_artifact / "audio_profile.json",
        help="Path to audio_profile.json (provides tempo, duration, section timing)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Path to asset_catalog.json (enables asset overlay rendering)",
    )
    parser.add_argument(
        "--asset-base-path",
        type=Path,
        default=None,
        help="Base path for image/video assets (for Pictures handler)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=default_artifact / "display_rendered.xsq",
        help="Output .xsq file path",
    )
    args = parser.parse_args()

    # 1. Load the group plan
    plan_set = load_plan(args.plan)
    logger.info(
        "Plan loaded: %d sections, %s",
        len(plan_set.section_plans),
        plan_set.plan_set_id,
    )

    # 2. Load audio profile for real tempo, duration, and section timing
    audio = load_audio_profile(args.audio_profile)
    tempo_bpm = audio["tempo_bpm"]
    duration_ms = float(audio["duration_ms"])

    # 3. Build section boundaries for the renderer (BeatGrid timing authority)
    section_boundaries: list[tuple[str, int, int]] = [
        (sec["section_id"], sec["start_ms"], sec["end_ms"]) for sec in audio["sections"]
    ]

    # 4. Optional: Load asset catalog and resolve plan assets
    catalog_index: dict[str, object] | None = None
    if args.catalog and args.catalog.exists():
        catalog = load_catalog(args.catalog)

        # Resolve plan assets (populate resolved_asset_ids)
        from twinklr.core.agents.assets.resolver import resolve_plan_assets

        resolved_plan = resolve_plan_assets(plan_set, catalog)
        print_asset_resolution_summary(plan_set, resolved_plan)
        plan_set = resolved_plan

        # Build catalog index for overlay rendering
        catalog_index = catalog.build_index()
        logger.info(
            "Catalog index: %d entries available for overlay rendering",
            len(catalog_index),
        )
    elif args.catalog:
        logger.warning("Catalog file not found: %s", args.catalog)

    # 5. Build supporting infrastructure
    beat_grid = build_beat_grid(duration_ms, tempo_bpm=tempo_bpm)
    display_graph = build_display_graph()

    # 6. Create empty XSequence
    sequence = build_empty_sequence(int(duration_ms))

    # 7. Run the display renderer
    from twinklr.core.sequencer.templates.group import (
        REGISTRY,
        load_builtin_group_templates,
    )

    load_builtin_group_templates()

    config = RenderConfig()
    renderer = DisplayRenderer(
        beat_grid=beat_grid,
        display_graph=display_graph,
        config=config,
        template_registry=REGISTRY,
    )

    result = renderer.render(
        plan_set,
        sequence,
        asset_base_path=args.asset_base_path,
        catalog_index=catalog_index,
        section_boundaries=section_boundaries,
    )

    # 8. Print summary
    print_result_summary(result)

    # 9. Export .xsq
    args.out.parent.mkdir(parents=True, exist_ok=True)
    exporter = XSQExporter()
    exporter.export(sequence, args.out)
    logger.info("Exported .xsq to %s", args.out)

    print(f"\nOutput: {args.out}")
    print("Open this file in xLights to validate the rendered sequence.")


if __name__ == "__main__":
    main()
