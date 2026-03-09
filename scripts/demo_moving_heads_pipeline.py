#!/usr/bin/env python3
"""Demo script for Moving Head Pipeline using Pipeline Framework.

Demonstrates the Moving Head choreography flow:
1. Audio Analysis (feature extraction)
2. Audio Profile + Lyrics (parallel)
3. MacroPlanner (overall show strategy)
4. MovingHeadPlanner (template selection coordinated with macro)
5. Rendering to XSQ

Uses the native pipeline definition factory for declarative execution.
Aligned with demo_sequencer_pipeline.py patterns (FE loading, metadata persistence).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from typing import TYPE_CHECKING

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from twinklr.core.pipeline import (
    ExecutionPattern,
    PipelineContext,
    PipelineExecutor,
)
from twinklr.core.pipeline.definitions import build_moving_heads_pipeline
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.library import list_templates
from twinklr.core.session import TwinklrSession
from twinklr.core.utils.formatting import clean_audio_filename
from twinklr.core.utils.logging import configure_logging

if TYPE_CHECKING:
    from twinklr.core.feature_engineering.loader import FEArtifactBundle

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


def save_artifact(data: dict | list, song_name: str, filename: str, output_dir: Path) -> Path:
    """Save artifact (dict or list) to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    with output_path.open("w") as f:
        json.dump(data, f, indent=2, default=str)

    return output_path


def generate_stable_session_id(audio_path: Path) -> str:
    """Generate a deterministic session ID from the audio file name.

    This allows cache reuse across runs for the same audio file.
    """
    name = audio_path.stem.lower().replace(" ", "_")
    hash_suffix = hashlib.md5(str(audio_path.resolve()).encode()).hexdigest()[:8]
    return f"{name}_{hash_suffix}"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Moving Head Pipeline Demo")
    parser.add_argument(
        "audio_file",
        nargs="?",
        default="data/music/11 - Need A Favor.mp3",
        help="Path to audio file",
    )
    parser.add_argument(
        "--new-session",
        action="store_true",
        help="Force new session ID (invalidates cache). Default uses stable ID based on audio file.",
    )
    parser.add_argument(
        "--xsq-template",
        type=Path,
        default=None,
        help="Optional template .xsq to merge into",
    )
    parser.add_argument(
        "--fixture-config",
        type=Path,
        default=None,
        help="Path to fixture config JSON",
    )
    parser.add_argument(
        "--fixtures",
        type=int,
        default=4,
        help="Number of moving head fixtures (default: 4)",
    )
    parser.add_argument(
        "--fe-data",
        type=str,
        default=None,
        help="Path to FE output directory (loads style fingerprint, transition model, etc.).",
    )
    return parser.parse_args()


async def main() -> None:
    """Run Moving Head Pipeline demo using native pipeline definitions."""
    args = parse_args()

    print_section("Moving Head Pipeline Demo (Pipeline Framework)", "=")

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
        session_id = None
        print("New session: cache will not be reused")
    else:
        session_id = generate_stable_session_id(audio_path)
        print(f"Session ID: {session_id} (use --new-session to invalidate cache)")

    session = TwinklrSession.from_directory(repo_root, session_id=session_id)

    # Load Moving Head templates
    print_subsection("1. Loading Templates")
    load_builtin_templates()
    available_templates = [t.template_id for t in list_templates()]
    print(f"Available templates: {len(available_templates)}")
    for t in available_templates[:5]:
        print(f"   - {t}")
    if len(available_templates) > 5:
        print(f"   ... and {len(available_templates) - 5} more")

    # Load FE artifacts (optional, aligns with display pipeline)
    fe_bundle: FEArtifactBundle | None = None
    if args.fe_data:
        from twinklr.core.feature_engineering.loader import load_fe_artifacts

        fe_dir = Path(args.fe_data)
        if fe_dir.exists():
            fe_bundle = load_fe_artifacts(fe_dir)
            print(f"FE data loaded from {fe_dir}")
            if fe_bundle.style_fingerprint:
                print("   Style fingerprint: loaded")
            if fe_bundle.transition_graph:
                print("   Transition graph: loaded")
            if fe_bundle.motif_catalog:
                print("   Motif catalog: loaded")
            if fe_bundle.color_arc:
                print("   Color arc: loaded")
        else:
            print(f"WARNING: FE data directory not found: {fe_dir}")

    # Build display groups (for MacroPlanner coordination)
    # Each group requires a concrete 'id' field for the macro planner to reference it.
    display_groups: list[dict[str, object]] = [
        {
            "id": "MOVING_HEADS",
            "role_key": "MOVING_HEADS",
            "model_count": args.fixtures,
            "group_type": "moving_head",
        },
        {"id": "OUTLINE", "role_key": "OUTLINE", "model_count": 10, "group_type": "string"},
        {"id": "MEGA_TREE", "role_key": "MEGA_TREE", "model_count": 1, "group_type": "tree"},
    ]

    # Resolve paths
    xsq_output_path = output_dir / f"{song_name}_twinklr_mh.xsq"
    xsq_template_path = args.xsq_template or (repo_root / "data/sequences/Need A Favor.xsq")
    fixture_config_path = args.fixture_config or (repo_root / "fixture_config.json")

    # ========================================================================
    # Define Pipeline (using native factory)
    # ========================================================================
    print_section("2. Pipeline Definition", "=")

    pipeline = build_moving_heads_pipeline(
        display_groups=display_groups,
        fixture_count=args.fixtures,
        available_templates=available_templates,
        xsq_output_path=xsq_output_path,
        max_iterations=session.job_config.agent.max_iterations,
        min_pass_score=7.0,
        xsq_template_path=xsq_template_path if xsq_template_path.exists() else None,
        fixture_config_path=fixture_config_path if fixture_config_path.exists() else None,
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

    pipeline_context = PipelineContext(
        session=session,
        output_dir=output_dir,
    )

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

    # Lyrics context (conditional stage - may be None if no lyrics detected)
    if result.outputs.get("lyrics") is not None:
        lyrics = result.outputs["lyrics"]
        lyrics_path = save_artifact(
            lyrics.model_dump(),
            song_name,
            "lyric_context.json",
            output_dir,
        )
        print(f"Lyric context: {lyrics_path.stem}")

    # Macro plan (output is list[MacroSectionPlan])
    if "macro" in result.outputs:
        macro_sections = result.outputs["macro"]
        macro_path = save_artifact(
            [section.model_dump() for section in macro_sections],
            song_name,
            "macro_sections.json",
            output_dir,
        )
        print(f"Macro sections: {macro_path.stem}")

    # Choreography plan
    if "moving_heads" in result.outputs:
        plan = result.outputs["moving_heads"]
        plan_path = save_artifact(
            plan.model_dump(),
            song_name,
            "choreography_plan.json",
            output_dir,
        )
        print(f"Choreography plan: {plan_path.stem}")

    # XSQ output
    if "render" in result.outputs:
        xsq_path = result.outputs["render"]
        print(f"XSQ output: {xsq_path}")

    # Metrics summary
    print_subsection("Pipeline Metrics")
    for key, value in pipeline_context.metrics.items():
        print(f"   {key}: {value}")

    # ========================================================================
    # Summary
    # ========================================================================
    print_section("Pipeline Complete!", "=")

    # Save pipeline metadata (aligns with display pipeline pattern)
    import datetime

    pipeline_metadata = {
        "pipeline": "moving_heads_pipeline",
        "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "audio_file": str(audio_path),
        "song_name": song_name,
        "session_id": session_id,
        "fixture_count": args.fixtures,
        "template_count": len(available_templates),
        "fe_data": args.fe_data,
        "success": result.success,
        "duration_ms": result.total_duration_ms,
        "stages_completed": len(result.outputs),
        "stages_total": len(pipeline.stages),
        "failed_stages": list(result.failed_stages) if result.failed_stages else [],
        "metrics": dict(pipeline_context.metrics),
    }
    metadata_path = save_artifact(
        pipeline_metadata, song_name, "pipeline_metadata.json", output_dir
    )
    print(f"Pipeline metadata: {metadata_path.stem}")

    if result.success:
        print("Full pipeline completed successfully!")
        print("\nStages executed:")
        print("  1. Audio Analysis")
        print("  2. Audio Profile + Lyrics (parallel)")
        print("  3. MacroPlanner -> list[MacroSectionPlan]")
        print("  4. MovingHeadPlanner (coordinated with macro)")
        print("  5. Rendering -> XSQ file")

        if "moving_heads" in result.outputs:
            plan = result.outputs["moving_heads"]
            print("\nChoreography Plan:")
            print(f"   Sections: {len(plan.sections)}")
            print(f"   Strategy: {plan.overall_strategy[:80]}...")

            for section in plan.sections[:3]:
                print(
                    f"   - {section.section_name}: {section.template_id} "
                    f"(bars {section.start_bar}-{section.end_bar})"
                )
            if len(plan.sections) > 3:
                print(f"   ... and {len(plan.sections) - 3} more sections")

        if "render" in result.outputs:
            xsq_path = result.outputs["render"]
            print(f"\nXSQ Output: {xsq_path}")
            segment_count = pipeline_context.metrics.get("mh_render_segments", 0)
            print(f"   Segments rendered: {segment_count}")

    else:
        print("Pipeline failed. Check logs for details.")

    print(f"\nAll artifacts saved to: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
