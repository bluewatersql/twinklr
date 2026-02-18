#!/usr/bin/env python3
"""Demo script for complete Sequencer Pipeline using Pipeline Framework.

Demonstrates the full orchestrated flow:
1. Audio Analysis
2. Audio Profile + Lyrics (parallel)
3. MacroPlanner
4. Section Context Builder
5. GroupPlanner (FAN_OUT per section)
6. GroupPlan Aggregator
7. Holistic Evaluation

Uses the Pipeline Framework for declarative, parallel execution.

Features a realistic residential display graph with 11 prop types,
spatial positions across all axes, zone tags (HOUSE, YARD, ROOF,
PERIMETER), detail capability, and split membership (halves, thirds,
odd/even).
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from twinklr.core.pipeline import (
    ExecutionPattern,
    PipelineContext,
    PipelineExecutor,
)
from twinklr.core.pipeline.definitions import build_display_pipeline
from twinklr.core.sequencer.display.xlights_mapping import (
    XLightsGroupMapping,
    XLightsMapping,
)
from twinklr.core.sequencer.templates.group import load_builtin_group_templates
from twinklr.core.sequencer.templates.group.catalog import (
    build_template_catalog as build_catalog_from_registry,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.display import (
    GroupPosition,
)
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag, SplitDimension
from twinklr.core.sequencer.vocabulary.composition import LaneKind
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
from twinklr.core.session import TwinklrSession
from twinklr.core.utils.formatting import clean_audio_filename
from twinklr.core.utils.logging import configure_logging

configure_logging(level="INFO")
logger = logging.getLogger(__name__)


def print_section(title: str, char: str = "=") -> None:
    """Print a section header."""
    print(f"\n{char * len(title) * 2}")
    print(f"{title.upper()}")
    print(f"{char * len(title) * 2}\n")


def print_subsection(title: str) -> None:
    """Print a subsection header."""
    print(f"\n{title.upper()}")
    print("-" * len(title) * 2)


def save_artifact(data: dict, song_name: str, filename: str, output_dir: Path) -> Path:
    """Save artifact to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    with output_path.open("w") as f:
        json.dump(data, f, indent=2, default=str)

    return output_path


# ---------------------------------------------------------------------------
# Display graph: realistic residential Christmas display
# ---------------------------------------------------------------------------
#
# Physical layout:
#
#   ┌─────────────────────────────────────────────────────┐
#   │  ROOF: stars (peak), icicles (eaves)                │  FAR / HIGH
#   │                                                     │
#   │  HOUSE: outline (roofline+eaves), windows, wreaths  │  FAR / MID-HIGH
#   │                                                     │
#   │  YARD:                                              │
#   │    FAR:  floodlights (wash, behind props)           │  NEAR / LOW
#   │    MID:  mega_tree (center), trees (flanking)       │  NEAR / MID-FULL
#   │    NEAR: arches (foreground row), candy_canes       │  NEAR / LOW
#   │          matrix (left), snowflakes (scattered)      │
#   └─────────────────────────────────────────────────────┘
#
# Total pixel budget: 100% across 11 groups


def build_display_graph() -> tuple[ChoreographyGraph, XLightsMapping]:
    """Build a realistic residential Christmas display graph.

    11 prop types with spatial diversity across x/y/z axes,
    zone tags (HOUSE, YARD, ROOF, PERIMETER), detail capability,
    and split membership (halves, thirds, odd/even).

    Returns:
        Tuple of (ChoreographyGraph, XLightsMapping).
    """
    groups = [
        # === ROOF ZONE ===
        ChoreoGroup(
            id="STARS",
            role="STARS",
            element_kind=DisplayElementKind.STAR,
            arrangement=GroupArrangement.CLUSTER,
            prominence=DisplayProminence.ACCENT,
            position=GroupPosition(
                horizontal=HorizontalZone.CENTER,
                vertical=VerticalZone.HIGH,
                depth=DepthZone.FAR,
                zone=DisplayZone.ROOF,
            ),
            fixture_count=3,
            pixel_fraction=0.04,
            detail_capability=DetailCapability.LOW,
            split_membership=[],
            tags=[ChoreoTag.ROOF],
        ),
        ChoreoGroup(
            id="ICICLES",
            role="ICICLES",
            element_kind=DisplayElementKind.ICICLES,
            arrangement=GroupArrangement.HORIZONTAL_ROW,
            prominence=DisplayProminence.SUPPORTING,
            position=GroupPosition(
                horizontal=HorizontalZone.FULL_WIDTH,
                vertical=VerticalZone.HIGH,
                depth=DepthZone.FAR,
                zone=DisplayZone.ROOF,
            ),
            fixture_count=12,
            pixel_fraction=0.08,
            detail_capability=DetailCapability.MEDIUM,
            split_membership=[
                SplitDimension.HALVES_LEFT,
                SplitDimension.HALVES_RIGHT,
                SplitDimension.ODD,
                SplitDimension.EVEN,
            ],
            tags=[ChoreoTag.ROOF],
        ),
        # === HOUSE ZONE ===
        ChoreoGroup(
            id="OUTLINE",
            role="OUTLINE",
            element_kind=DisplayElementKind.STRING,
            arrangement=GroupArrangement.HORIZONTAL_ROW,
            prominence=DisplayProminence.ANCHOR,
            position=GroupPosition(
                horizontal=HorizontalZone.FULL_WIDTH,
                vertical=VerticalZone.HIGH,
                depth=DepthZone.FAR,
                zone=DisplayZone.HOUSE,
            ),
            fixture_count=8,
            pixel_fraction=0.12,
            detail_capability=DetailCapability.MEDIUM,
            split_membership=[
                SplitDimension.HALVES_LEFT,
                SplitDimension.HALVES_RIGHT,
                SplitDimension.ODD,
                SplitDimension.EVEN,
            ],
            tags=[ChoreoTag.HOUSE],
        ),
        ChoreoGroup(
            id="WINDOWS",
            role="WINDOWS",
            element_kind=DisplayElementKind.WINDOW,
            arrangement=GroupArrangement.GRID,
            prominence=DisplayProminence.SUPPORTING,
            position=GroupPosition(
                horizontal=HorizontalZone.CENTER,
                vertical=VerticalZone.MID,
                depth=DepthZone.FAR,
                zone=DisplayZone.HOUSE,
            ),
            fixture_count=6,
            pixel_fraction=0.08,
            detail_capability=DetailCapability.MEDIUM,
            split_membership=[SplitDimension.ODD, SplitDimension.EVEN],
            tags=[ChoreoTag.HOUSE],
        ),
        ChoreoGroup(
            id="WREATHS",
            role="WREATH",
            element_kind=DisplayElementKind.WREATH,
            arrangement=GroupArrangement.HORIZONTAL_ROW,
            prominence=DisplayProminence.ACCENT,
            position=GroupPosition(
                horizontal=HorizontalZone.CENTER,
                vertical=VerticalZone.MID,
                depth=DepthZone.FAR,
                zone=DisplayZone.HOUSE,
            ),
            fixture_count=3,
            pixel_fraction=0.03,
            detail_capability=DetailCapability.MEDIUM,
            split_membership=[SplitDimension.ODD, SplitDimension.EVEN],
            tags=[ChoreoTag.HOUSE],
        ),
        # === YARD ZONE — far depth (background washes) ===
        ChoreoGroup(
            id="FLOODS",
            role="FLOODS",
            element_kind=DisplayElementKind.FLOOD,
            arrangement=GroupArrangement.HORIZONTAL_ROW,
            prominence=DisplayProminence.SUPPORTING,
            position=GroupPosition(
                horizontal=HorizontalZone.FULL_WIDTH,
                vertical=VerticalZone.LOW,
                depth=DepthZone.FAR,
                zone=DisplayZone.YARD,
            ),
            fixture_count=6,
            pixel_fraction=0.05,
            detail_capability=DetailCapability.LOW,
            split_membership=[
                SplitDimension.HALVES_LEFT,
                SplitDimension.HALVES_RIGHT,
                SplitDimension.ODD,
                SplitDimension.EVEN,
            ],
            tags=[ChoreoTag.YARD],
        ),
        # === YARD ZONE — mid depth (hero elements) ===
        ChoreoGroup(
            id="MEGA_TREE",
            role="MEGA_TREE",
            element_kind=DisplayElementKind.TREE,
            arrangement=GroupArrangement.SINGLE,
            prominence=DisplayProminence.HERO,
            position=GroupPosition(
                horizontal=HorizontalZone.CENTER,
                vertical=VerticalZone.FULL_HEIGHT,
                depth=DepthZone.NEAR,
                zone=DisplayZone.YARD,
            ),
            fixture_count=1,
            pixel_fraction=0.20,
            detail_capability=DetailCapability.HIGH,
            split_membership=[],
            tags=[ChoreoTag.YARD],
        ),
        ChoreoGroup(
            id="TREES",
            role="TREES",
            element_kind=DisplayElementKind.TREE,
            arrangement=GroupArrangement.HORIZONTAL_ROW,
            prominence=DisplayProminence.ANCHOR,
            position=GroupPosition(
                horizontal=HorizontalZone.FULL_WIDTH,
                vertical=VerticalZone.MID,
                depth=DepthZone.NEAR,
                zone=DisplayZone.YARD,
            ),
            fixture_count=6,
            pixel_fraction=0.12,
            detail_capability=DetailCapability.HIGH,
            split_membership=[
                SplitDimension.HALVES_LEFT,
                SplitDimension.HALVES_RIGHT,
                SplitDimension.ODD,
                SplitDimension.EVEN,
            ],
            tags=[ChoreoTag.YARD],
        ),
        # === YARD ZONE — near depth (foreground) ===
        ChoreoGroup(
            id="ARCHES",
            role="ARCHES",
            element_kind=DisplayElementKind.ARCH,
            arrangement=GroupArrangement.HORIZONTAL_ROW,
            prominence=DisplayProminence.ANCHOR,
            position=GroupPosition(
                horizontal=HorizontalZone.FULL_WIDTH,
                vertical=VerticalZone.LOW,
                depth=DepthZone.NEAR,
                zone=DisplayZone.YARD,
            ),
            fixture_count=7,
            pixel_fraction=0.10,
            detail_capability=DetailCapability.MEDIUM,
            split_membership=[
                SplitDimension.HALVES_LEFT,
                SplitDimension.HALVES_RIGHT,
                SplitDimension.ODD,
                SplitDimension.EVEN,
            ],
            tags=[ChoreoTag.YARD, ChoreoTag.PERIMETER],
        ),
        ChoreoGroup(
            id="CANDY_CANES",
            role="CANDY_CANES",
            element_kind=DisplayElementKind.CANDY_CANE,
            arrangement=GroupArrangement.HORIZONTAL_ROW,
            prominence=DisplayProminence.SUPPORTING,
            position=GroupPosition(
                horizontal=HorizontalZone.FULL_WIDTH,
                vertical=VerticalZone.LOW,
                depth=DepthZone.NEAR,
                zone=DisplayZone.YARD,
            ),
            fixture_count=8,
            pixel_fraction=0.06,
            detail_capability=DetailCapability.LOW,
            split_membership=[
                SplitDimension.HALVES_LEFT,
                SplitDimension.HALVES_RIGHT,
                SplitDimension.ODD,
                SplitDimension.EVEN,
            ],
            tags=[ChoreoTag.YARD, ChoreoTag.PERIMETER],
        ),
        ChoreoGroup(
            id="MATRIX",
            role="MATRICES",
            element_kind=DisplayElementKind.MATRIX,
            arrangement=GroupArrangement.SINGLE,
            prominence=DisplayProminence.ANCHOR,
            position=GroupPosition(
                horizontal=HorizontalZone.LEFT,
                vertical=VerticalZone.MID,
                depth=DepthZone.NEAR,
                zone=DisplayZone.YARD,
            ),
            fixture_count=1,
            pixel_fraction=0.06,
            detail_capability=DetailCapability.HIGH,
            split_membership=[SplitDimension.HALVES_LEFT],
            tags=[ChoreoTag.YARD],
        ),
        ChoreoGroup(
            id="SNOWFLAKES",
            role="SNOWFLAKES",
            element_kind=DisplayElementKind.SNOWFLAKE,
            arrangement=GroupArrangement.CLUSTER,
            prominence=DisplayProminence.ACCENT,
            position=GroupPosition(
                horizontal=HorizontalZone.RIGHT,
                vertical=VerticalZone.MID,
                depth=DepthZone.NEAR,
                zone=DisplayZone.YARD,
            ),
            fixture_count=8,
            pixel_fraction=0.06,
            detail_capability=DetailCapability.LOW,
            split_membership=[SplitDimension.HALVES_RIGHT, SplitDimension.ODD, SplitDimension.EVEN],
            tags=[ChoreoTag.YARD],
        ),
    ]

    choreo_graph = ChoreographyGraph(
        graph_id="demo_residential_display",
        groups=groups,
    )

    xlights_mapping = XLightsMapping(
        entries=[
            XLightsGroupMapping(choreo_id="STARS", group_name="Roof Stars"),
            XLightsGroupMapping(choreo_id="ICICLES", group_name="Icicles"),
            XLightsGroupMapping(choreo_id="OUTLINE", group_name="House Outline"),
            XLightsGroupMapping(choreo_id="WINDOWS", group_name="Windows"),
            XLightsGroupMapping(choreo_id="WREATHS", group_name="Wreaths"),
            XLightsGroupMapping(choreo_id="FLOODS", group_name="Floods"),
            XLightsGroupMapping(choreo_id="MEGA_TREE", group_name="Mega Tree"),
            XLightsGroupMapping(choreo_id="TREES", group_name="Yard Trees"),
            XLightsGroupMapping(choreo_id="ARCHES", group_name="Arches"),
            XLightsGroupMapping(choreo_id="CANDY_CANES", group_name="Candy Canes"),
            XLightsGroupMapping(choreo_id="MATRIX", group_name="LED Matrix"),
            XLightsGroupMapping(choreo_id="SNOWFLAKES", group_name="Snowflakes"),
        ],
    )

    return choreo_graph, xlights_mapping


def parse_args() -> argparse.Namespace:
    # Parse arguments
    parser = argparse.ArgumentParser(description="Sequencer Pipeline Demo")
    parser.add_argument(
        "audio_file",
        nargs="?",
        default="data/music/Need A Favor.mp3",
        help="Path to audio file (default: data/music/Need A Favor.mp3)",
    )
    parser.add_argument(
        "--new-session",
        action="store_true",
        help="Force new session ID (invalidates cache). Default uses stable ID based on audio file.",
    )
    return parser.parse_args()


def generate_stable_session_id(audio_path: Path) -> str:
    """Generate a deterministic session ID from the audio file name.

    This allows cache reuse across runs for the same audio file.
    """
    import hashlib

    # Use audio filename (without extension) as basis for stable ID
    name = audio_path.stem.lower().replace(" ", "_")
    # Add a hash suffix to handle collisions
    hash_suffix = hashlib.md5(str(audio_path.resolve()).encode()).hexdigest()[:8]
    return f"{name}_{hash_suffix}"


async def main() -> None:
    args = parse_args()

    print_section("Sequencer Pipeline Demo (Pipeline Framework)", "=")

    # Setup paths
    repo_root = Path(__file__).parent.parent
    audio_path = Path(args.audio_file)

    if not audio_path.exists():
        print(f"ERROR: Audio file not found: {audio_path}")
        sys.exit(1)

    song_name = clean_audio_filename(audio_path.stem)
    output_dir = repo_root / "artifacts" / song_name

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Generate session ID - stable by default for cache reuse
    if args.new_session:
        session_id = None  # Will generate new UUID
        print("New session: cache will not be reused")
    else:
        session_id = generate_stable_session_id(audio_path)
        print(f"Session ID: {session_id} (use --new-session to invalidate cache)")

    session = TwinklrSession.from_directory(repo_root, session_id=session_id)

    # Build display graph with hierarchy and metadata
    choreo_graph, xlights_mapping = build_display_graph()
    display_groups = choreo_graph.to_planner_summary()

    # Build catalog from registry
    load_builtin_group_templates()
    template_catalog = build_catalog_from_registry()

    print_subsection("1. Display Configuration")
    print(f"Choreography graph: {len(choreo_graph.groups)} groups")

    # Show groups by zone
    for tag in [ChoreoTag.ROOF, ChoreoTag.HOUSE, ChoreoTag.YARD]:
        zone_ids = choreo_graph.groups_by_tag.get(tag, [])
        if zone_ids:
            print(f"\n  {tag.value} zone:")
            for gid in zone_ids:
                g = choreo_graph.get_group(gid)
                if g is None:
                    continue
                kind_str = f" [{g.element_kind.value}]" if g.element_kind else ""
                prom_str = f" {g.prominence.value}" if g.prominence else ""
                pct_str = f" {g.pixel_fraction:.0%}" if g.pixel_fraction > 0 else ""
                tag_str = ", ".join(t.value for t in g.tags if t != tag)
                print(
                    f"    {g.id}{kind_str} ({g.fixture_count} models{pct_str})"
                    f" [{prom_str.strip()}]" + (f"  tags: {tag_str}" if tag_str else "")
                )

    # Show tag summary
    print("\n  Tag summary:")
    for tag, ids in choreo_graph.groups_by_tag.items():
        print(f"    {tag.value}: {', '.join(ids)}")

    print(f"\n  Template catalog: {len(template_catalog.entries)} templates")
    for lane in LaneKind:
        lane_templates = template_catalog.list_by_lane(lane)
        if lane_templates:
            print(f"    {lane.value}: {len(lane_templates)} templates")

    # ========================================================================
    # Define Pipeline
    # ========================================================================
    print_section("2. Pipeline Definition", "=")

    pipeline = build_display_pipeline(
        choreo_graph=choreo_graph,
        template_catalog=template_catalog,
        display_groups=display_groups,
        song_name=song_name,
        max_iterations=session.job_config.agent.max_iterations,
        min_pass_score=session.job_config.agent.success_threshold / 10.0,
        enable_holistic=True,
        enable_assets=False,
        xlights_mapping=xlights_mapping,
    )

    # Validate pipeline
    errors = pipeline.validate_pipeline()
    if errors:
        print(f"Pipeline validation failed: {errors}")
        sys.exit(1)

    print(f"Pipeline '{pipeline.name}' validated")
    print(f"   Stages: {len(pipeline.stages)}")
    for stage in pipeline.stages:
        deps = f" (inputs: {stage.inputs})" if stage.inputs else ""
        pattern = (
            f" [{stage.pattern.value}]" if stage.pattern != ExecutionPattern.SEQUENTIAL else ""
        )
        print(f"   - {stage.id}{pattern}{deps}")

    # ========================================================================
    # Create Pipeline Context with Caching
    # ========================================================================
    print_section("3. Pipeline Execution", "=")

    # Create pipeline context with agent cache
    pipeline_context = PipelineContext(
        session=session,
        output_dir=output_dir,
    )

    # Store choreo graph and mapping in state for rendering stages
    pipeline_context.set_state("choreo_graph", choreo_graph)
    pipeline_context.set_state("xlights_mapping", xlights_mapping)

    print(f"Input: {audio_path.name}")
    print("Starting pipeline execution...")

    # ========================================================================
    # Execute Pipeline
    # ========================================================================
    executor = PipelineExecutor()
    result = await executor.execute(
        pipeline=pipeline,
        initial_input=str(audio_path),
        context=pipeline_context,
    )

    # ========================================================================
    # Process Results
    # ========================================================================
    print_section("4. Pipeline Results", "=")

    print(f"Overall Success: {'YES' if result.success else 'NO'}")
    print(f"Duration: {result.total_duration_ms:.0f}ms ({result.total_duration_ms / 1000:.1f}s)")
    print(f"Stages Completed: {len(result.outputs)}/{len(pipeline.stages)}")

    if result.failed_stages:
        print(f"\nFailed stages: {result.failed_stages}")
        for stage_id in result.failed_stages:
            stage_result = result.stage_results.get(stage_id)
            if stage_result:
                print(f"   - {stage_id}: {stage_result.error}")

    # Save artifacts
    print_subsection("Saving Artifacts")

    # Audio bundle summary
    if "audio" in result.outputs:
        bundle = result.outputs["audio"]
        bundle_path = save_artifact(
            {
                "schema_version": bundle.schema_version,
                "audio_path": bundle.audio_path,
                "recording_id": bundle.recording_id,
                "timing": bundle.timing.model_dump(),
                "features_keys": list(bundle.features.keys()),
                "warnings": bundle.warnings,
            },
            song_name,
            "audio_bundle_summary.json",
            output_dir,
        )
        print(f"Audio bundle: {bundle_path.stem}")

    # Audio profile
    if "profile" in result.outputs:
        profile = result.outputs["profile"]
        profile_path = save_artifact(
            profile.model_dump(),
            song_name,
            "audio_profile.json",
            output_dir,
        )
        print(f"Audio profile: {profile_path.stem}")

    # Lyrics context
    if "lyrics" in result.outputs and result.outputs["lyrics"] is not None:
        lyrics = result.outputs["lyrics"]
        lyrics_path = save_artifact(
            lyrics.model_dump(),
            song_name,
            "lyric_context.json",
            output_dir,
        )
        print(f"Lyric context: {lyrics_path.stem}")

    # Macro plan (output is list[MacroSectionPlan], not MacroPlan)
    if "macro" in result.outputs:
        macro_sections = result.outputs["macro"]
        # Save section list (this is what FAN_OUT consumes)
        macro_path = save_artifact(
            [section.model_dump() for section in macro_sections],
            song_name,
            "macro_sections.json",
            output_dir,
        )
        print(f"Macro sections: {macro_path.stem}")

    # GroupPlanSet
    if "aggregate" in result.outputs:
        group_plan_set = result.outputs["aggregate"]
        group_plan_path = save_artifact(
            group_plan_set.model_dump(),
            song_name,
            "group_plan_set.json",
            output_dir,
        )
        print(f"Group plan set: {group_plan_path.stem}")

    # Holistic evaluation (stored in context state, not output -- stage is pass-through)
    holistic_eval = pipeline_context.get_state("holistic_evaluator_result")
    if holistic_eval is not None:
        holistic_path = save_artifact(
            holistic_eval.model_dump(),
            song_name,
            "holistic_evaluation.json",
            output_dir,
        )
        print(f"Holistic evaluation: {holistic_path.stem}")
        print(f"   Score: {holistic_eval.score:.1f}, Status: {holistic_eval.status.value}")

    # Display render -> XSQ export
    if "display_render" in result.outputs:
        render_output = result.outputs["display_render"]
        render_result = render_output["render_result"]
        xsequence = render_output["sequence"]

        # Export .xsq file
        from twinklr.core.formats.xlights.sequence.exporter import XSQExporter

        xsq_path = output_dir / f"{song_name}_display.xsq"
        exporter = XSQExporter()
        exporter.export(xsequence, xsq_path)
        print(f"XSQ output: {xsq_path.name}")
        print(
            f"   Effects: {render_result.effects_written}, "
            f"Elements: {render_result.elements_created}, "
            f"Warnings: {len(render_result.warnings)}"
        )

    # Metrics summary
    print_subsection("Pipeline Metrics")
    for key, value in pipeline_context.metrics.items():
        print(f"   {key}: {value}")

    # ========================================================================
    # Summary
    # ========================================================================
    print_section("Pipeline Complete!", "=")

    if result.success:
        print("Full pipeline completed successfully!")
        print("\nStages executed:")
        print("  1. Audio Analysis")
        print("  2. Audio Profile + Lyrics (parallel)")
        print("  3. MacroPlanner -> list[MacroSectionPlan]")
        print("  4. GroupPlanner (FAN_OUT per section)")
        print("  5. Aggregator (collect section plans)")
        print("  6. Holistic Evaluation (cross-section quality)")
        print("  7. Asset Resolution")
        print("  8. Display Rendering -> .xsq export")

        if "aggregate" in result.outputs:
            gps = result.outputs["aggregate"]
            print(f"\nGroupPlanSet: {len(gps.section_plans)} sections")
            if gps.narrative_assets:
                print(f"Narrative directives: {len(gps.narrative_assets)}")
                for nd in gps.narrative_assets:
                    sections = ", ".join(nd.section_ids) if nd.section_ids else "?"
                    print(
                        f"   - [{nd.emphasis}] {nd.directive_id}: "
                        f"{nd.subject[:50]}... (sections: {sections})"
                    )

        if "display_render" in result.outputs:
            rr = result.outputs["display_render"]["render_result"]
            print(
                f"\nDisplay Render: {rr.effects_written} effects on {rr.elements_created} elements"
            )

    else:
        print("Pipeline failed. Check logs for details.")

    print(f"\nAll artifacts saved to: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
