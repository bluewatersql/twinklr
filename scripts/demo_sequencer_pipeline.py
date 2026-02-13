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
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from twinklr.core.agents.audio.lyrics.stage import LyricsStage
from twinklr.core.agents.audio.profile.stage import AudioProfileStage
from twinklr.core.agents.audio.stages.analysis import AudioAnalysisStage
from twinklr.core.agents.sequencer.group_planner import (
    DisplayGraph,
    DisplayGroup,
    LaneKind,
)
from twinklr.core.agents.sequencer.group_planner.stage import (
    GroupPlanAggregatorStage,
    GroupPlannerStage,
)

# from twinklr.core.agents.sequencer.holistic_evaluator.stage import HolisticEvaluatorStage  # Not yet implemented
from twinklr.core.agents.sequencer.macro_planner.stage import MacroPlannerStage
from twinklr.core.pipeline import (
    ExecutionPattern,
    PipelineContext,
    PipelineDefinition,
    PipelineExecutor,
    StageDefinition,
)
from twinklr.core.sequencer.templates.group import load_builtin_group_templates
from twinklr.core.sequencer.templates.group.catalog import (
    build_template_catalog as build_catalog_from_registry,
)
from twinklr.core.sequencer.templates.group.models.display import ElementType
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


def build_display_graph(display_groups: list[dict]) -> DisplayGraph:
    """Build DisplayGraph from display group configs.

    Creates one DisplayGroup entry per role (group-based targeting).
    Each entry represents an xLights model group that the planner
    targets directly (e.g., ``ARCHES`` not ``ARCHES_1``).

    The ``fixture_count`` field carries the model count for planning
    context (e.g., how many arches are in the group).

    Single-model roles (model_count=1) use ``ElementType.MODEL``.
    Multi-model roles use ``ElementType.MODEL_GROUP``.
    """
    groups_list = []
    for g in display_groups:
        role_key = str(g["role_key"])
        model_count: int = g["model_count"]  # type: ignore[assignment]
        element_type = ElementType.MODEL if model_count == 1 else ElementType.MODEL_GROUP

        groups_list.append(
            DisplayGroup(
                group_id=role_key,
                role=role_key,
                display_name=role_key,
                element_type=element_type,
                fixture_count=model_count,
            )
        )

    return DisplayGraph(
        display_id="demo_display",
        display_name="Demo Display",
        groups=groups_list,
    )


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
        print(f"❌ ERROR: Audio file not found: {audio_path}")
        sys.exit(1)

    song_name = clean_audio_filename(audio_path.stem)
    output_dir = repo_root / "artifacts" / song_name

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {output_dir}")

    # Generate session ID - stable by default for cache reuse
    if args.new_session:
        session_id = None  # Will generate new UUID
        print("🔄 New session: cache will not be reused")
    else:
        session_id = generate_stable_session_id(audio_path)
        print(f"📦 Session ID: {session_id} (use --new-session to invalidate cache)")

    session = TwinklrSession.from_directory(repo_root, session_id=session_id)

    # Build display groups (mock for demo)
    display_groups = [
        {"role_key": "OUTLINE", "model_count": 10, "group_type": "string"},
        {"role_key": "MEGA_TREE", "model_count": 1, "group_type": "tree"},
        {"role_key": "HERO", "model_count": 5, "group_type": "prop"},
        {"role_key": "ARCHES", "model_count": 5, "group_type": "arch"},
        {"role_key": "WINDOWS", "model_count": 8, "group_type": "window"},
    ]

    # Build display graph and template catalog
    display_graph = build_display_graph(display_groups)

    # Build catalog from registry
    load_builtin_group_templates()
    template_catalog = build_catalog_from_registry()

    print_subsection("1. Display Configuration")
    print(f"🎯 Display graph: {len(display_graph.groups)} groups")
    for role, group_ids in display_graph.groups_by_role.items():
        print(f"   - {role}: {', '.join(group_ids)}")

    print(f"\n📚 Template catalog: {len(template_catalog.entries)} templates")
    for lane in LaneKind:
        lane_templates = template_catalog.list_by_lane(lane)
        if lane_templates:
            print(f"   - {lane.value}: {len(lane_templates)} templates")

    # ========================================================================
    # Define Pipeline
    # ========================================================================
    print_section("2. Pipeline Definition", "=")

    pipeline = PipelineDefinition(
        name="sequencer_pipeline",
        description="Complete audio to group coordination pipeline",
        fail_fast=True,
        stages=[
            # Stage 1: Audio Analysis
            StageDefinition(
                id="audio",
                stage=AudioAnalysisStage(),
                description="Analyze audio file for tempo, structure, features",
            ),
            # Stage 2a: Audio Profile (parallel with lyrics)
            StageDefinition(
                id="profile",
                stage=AudioProfileStage(),
                inputs=["audio"],
                description="Generate musical analysis and creative guidance",
            ),
            # Stage 2b: Lyrics Analysis (parallel with profile, conditional)
            StageDefinition(
                id="lyrics",
                stage=LyricsStage(),
                inputs=["audio"],
                pattern=ExecutionPattern.CONDITIONAL,
                condition=lambda ctx: ctx.get_state("has_lyrics", False),
                critical=False,  # Pipeline continues if no lyrics
                description="Generate narrative and thematic analysis",
            ),
            # Stage 3: Macro Planning
            # Outputs list[MacroSectionPlan] for direct FAN_OUT
            # Stores full MacroPlan in state
            StageDefinition(
                id="macro",
                stage=MacroPlannerStage(display_groups=display_groups),
                inputs=["profile", "lyrics"],
                description="Generate high-level choreography strategy (outputs section list)",
            ),
            # Stage 4: GroupPlanner (FAN_OUT - parallel per section)
            # Each invocation:
            # - Receives ONE MacroSectionPlan
            # - Builds its own context from state (audio_bundle, macro_plan)
            # - Uses display_graph, template_catalog from constructor
            StageDefinition(
                id="groups",
                stage=GroupPlannerStage(
                    display_graph=display_graph,
                    template_catalog=template_catalog,
                    max_iterations=session.job_config.agent.max_iterations,
                    min_pass_score=session.job_config.agent.success_threshold / 10.0,
                ),
                inputs=["macro"],
                pattern=ExecutionPattern.FAN_OUT,
                description="Generate section coordination plans (parallel per section)",
            ),
            # Stage 5: Aggregator
            StageDefinition(
                id="aggregate",
                stage=GroupPlanAggregatorStage(plan_set_id=f"{song_name}_group_plan"),
                inputs=["groups"],
                description="Aggregate section plans into GroupPlanSet",
            ),
            # # Stage 6: Holistic Evaluation (Not yet implemented)
            # StageDefinition(
            #     id="holistic",
            #     stage=HolisticEvaluatorStage(
            #         display_graph=display_graph,
            #         template_catalog=template_catalog,
            #     ),
            #     inputs=["aggregate"],
            #     description="Evaluate complete GroupPlanSet quality",
            # ),
        ],
    )

    # Validate pipeline
    errors = pipeline.validate_pipeline()
    if errors:
        print(f"❌ Pipeline validation failed: {errors}")
        sys.exit(1)

    print(f"✅ Pipeline '{pipeline.name}' validated")
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

    print(f"🎵 Input: {audio_path.name}")
    print("🚀 Starting pipeline execution...")

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

    print(f"Overall Success: {'✅' if result.success else '❌'}")
    print(f"Duration: {result.total_duration_ms:.0f}ms ({result.total_duration_ms / 1000:.1f}s)")
    print(f"Stages Completed: {len(result.outputs)}/{len(pipeline.stages)}")

    if result.failed_stages:
        print(f"\n❌ Failed stages: {result.failed_stages}")
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
        print(f"📄 Audio bundle: {bundle_path.stem}")

    # Audio profile
    if "profile" in result.outputs:
        profile = result.outputs["profile"]
        profile_path = save_artifact(
            profile.model_dump(),
            song_name,
            "audio_profile.json",
            output_dir,
        )
        print(f"📄 Audio profile: {profile_path.stem}")

    # Lyrics context
    if "lyrics" in result.outputs:
        lyrics = result.outputs["lyrics"]
        lyrics_path = save_artifact(
            lyrics.model_dump(),
            song_name,
            "lyric_context.json",
            output_dir,
        )
        print(f"📄 Lyric context: {lyrics_path.stem}")

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
        print(f"📄 Macro sections: {macro_path.stem}")

    # GroupPlanSet
    if "aggregate" in result.outputs:
        group_plan_set = result.outputs["aggregate"]
        group_plan_path = save_artifact(
            group_plan_set.model_dump(),
            song_name,
            "group_plan_set.json",
            output_dir,
        )
        print(f"📄 Group plan set: {group_plan_path.stem}")

    # Holistic evaluation
    if "holistic" in result.outputs:
        holistic_eval = result.outputs["holistic"]
        holistic_path = save_artifact(
            holistic_eval.model_dump(),
            song_name,
            "holistic_evaluation.json",
            output_dir,
        )
        print(f"📄 Holistic evaluation: {holistic_path.stem}")

    # Metrics summary
    print_subsection("Pipeline Metrics")
    for key, value in pipeline_context.metrics.items():
        print(f"   {key}: {value}")

    # ========================================================================
    # Summary
    # ========================================================================
    print_section("Pipeline Complete! 🎉", "=")

    if result.success:
        print("✅ Full pipeline completed successfully!")
        print("\nStages executed:")
        print("  1. Audio Analysis")
        print("  2. Audio Profile + Lyrics (parallel)")
        print("  3. MacroPlanner → list[MacroSectionPlan]")
        print("  4. GroupPlanner (FAN_OUT per section)")
        print("  5. Aggregator (collect section plans)")
        print("  6. Holistic Evaluation")

        # if "holistic" in result.outputs:
        #     holistic = result.outputs["holistic"]
        #     print(f"\n🎯 Final Score: {holistic.score:.1f}/10")
        #     print(f"   Status: {holistic.status.value}")
        #     print(f"   Approved: {'✅ Yes' if holistic.is_approved else '❌ No'}")
        #     if holistic.cross_section_issues:
        #         print(f"   Issues: {len(holistic.cross_section_issues)}")

        if "aggregate" in result.outputs:
            gps = result.outputs["aggregate"]
            print(f"\n📊 GroupPlanSet: {len(gps.section_plans)} sections")
            if gps.narrative_assets:
                print(f"📖 Narrative directives: {len(gps.narrative_assets)}")
                for nd in gps.narrative_assets:
                    sections = ", ".join(nd.section_ids) if nd.section_ids else "?"
                    print(
                        f"   - [{nd.emphasis}] {nd.directive_id}: "
                        f"{nd.subject[:50]}... (sections: {sections})"
                    )

    else:
        print("❌ Pipeline failed. Check logs for details.")

    print(f"\n📁 All artifacts saved to: {output_dir}")

    print("\nPending stages (not yet implemented):")
    print("  8. Asset Generation (imagery/shaders)")
    print("  9. Sequence Assembly (IR composition)")
    print(" 10. Rendering & Export (xLights .xsq)")


if __name__ == "__main__":
    asyncio.run(main())
