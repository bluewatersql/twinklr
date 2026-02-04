#!/usr/bin/env python3
"""Demo script for Moving Head Pipeline using Pipeline Framework.

Demonstrates the Moving Head choreography flow per V2 Migration spec:
1. Audio Analysis (feature extraction)
2. Audio Profile + Lyrics (parallel)
3. MacroPlanner (overall show strategy)
4. MovingHeadPlanner (template selection coordinated with macro)
5. Rendering to XSQ (future)

Uses the Pipeline Framework for declarative, parallel execution.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from twinklr.core.agents.audio.lyrics.stage import LyricsStage
from twinklr.core.agents.audio.profile.stage import AudioProfileStage
from twinklr.core.agents.audio.stages.analysis import AudioAnalysisStage
from twinklr.core.agents.logging import create_llm_logger
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.agents.sequencer.macro_planner.stage import MacroPlannerStage
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
    MovingHeadRenderingStage,
)
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.caching import FSCache
from twinklr.core.config.loader import load_app_config, load_job_config
from twinklr.core.io import RealFileSystem, absolute_path
from twinklr.core.pipeline import (
    ExecutionPattern,
    PipelineContext,
    PipelineDefinition,
    PipelineExecutor,
    StageDefinition,
)
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.library import list_templates
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


def save_artifact(data: dict | list, song_name: str, filename: str, output_dir: Path) -> Path:
    """Save artifact (dict or list) to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    with output_path.open("w") as f:
        json.dump(data, f, indent=2, default=str)

    return output_path


async def main() -> None:
    """Run Moving Head Pipeline demo using Pipeline Framework."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="Moving Head Pipeline Demo")
    parser.add_argument(
        "audio_file",
        nargs="?",
        default="data/music/Need A Favor.mp3",
        help="Path to audio file (default: data/music/Need A Favor.mp3)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force reanalysis of audio (skip cache)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for artifacts",
    )
    args = parser.parse_args()

    print_section("Moving Head Pipeline Demo (Pipeline Framework)", "=")

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        print("\nTo run this demo:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  python scripts/demo.py [audio_file]")
        sys.exit(1)

    print("✅ OpenAI API key found")

    # Setup paths
    repo_root = Path(__file__).parent.parent
    audio_path = Path(args.audio_file)

    if not audio_path.exists():
        print(f"❌ ERROR: Audio file not found: {audio_path}")
        sys.exit(1)

    song_name = clean_audio_filename(audio_path.stem)
    output_dir = args.output_dir or repo_root / "artifacts" / song_name
    logging_dir = Path("data") / "logging"

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {output_dir}")

    # Load configuration
    print_subsection("0. Loading Configuration")
    try:
        app_config = load_app_config(repo_root / "config.json")
        job_config = load_job_config(repo_root / "job_config.json")

        model = job_config.agent.plan_agent.model
        print("✅ Configuration loaded")
        print(f"   Model: {model}")
        print(f"   Max iterations: {job_config.agent.max_iterations}")
    except Exception as e:
        print(f"❌ Could not load config: {e}")
        sys.exit(1)

    # Load Moving Head templates
    print_subsection("1. Loading Templates")
    load_builtin_templates()
    available_templates = [t.template_id for t in list_templates()]
    print(f"📚 Available templates: {len(available_templates)}")
    for t in available_templates[:5]:
        print(f"   - {t}")
    if len(available_templates) > 5:
        print(f"   ... and {len(available_templates) - 5} more")

    # Build display groups (mock for MacroPlanner coordination)
    display_groups = [
        {"role_key": "MOVING_HEADS", "model_count": 4, "group_type": "moving_head"},
        {"role_key": "OUTLINE", "model_count": 10, "group_type": "string"},
        {"role_key": "MEGA_TREE", "model_count": 1, "group_type": "tree"},
    ]

    # ========================================================================
    # Define Pipeline
    # Per spec section 4.4: Audio → Profile → Lyrics → Macro → MovingHead
    # ========================================================================
    print_section("2. Pipeline Definition", "=")

    pipeline = PipelineDefinition(
        name="moving_head_pipeline",
        description="Moving Head choreography pipeline with macro coordination",
        fail_fast=True,
        stages=[
            # Stage 1: Audio Analysis (entry point)
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
            # Stage 3: Macro Planning (coordinates overall show strategy)
            # Outputs list[MacroSectionPlan] with energy targets, motion density, style
            StageDefinition(
                id="macro",
                stage=MacroPlannerStage(display_groups=display_groups),
                inputs=["profile", "lyrics"],
                description="Generate high-level choreography strategy (outputs section list)",
            ),
            # Stage 4: Moving Head Planning (V2 - coordinates with macro)
            # inputs=["audio", "profile", "lyrics", "macro"]
            # - audio: For building BeatGrid (stored in state for rendering)
            # - profile, lyrics, macro: For coordinated planning
            StageDefinition(
                id="moving_heads",
                stage=MovingHeadStage(
                    fixture_count=4,
                    available_templates=available_templates,
                    max_iterations=job_config.agent.max_iterations,
                    min_pass_score=7.0,
                ),
                inputs=["audio", "profile", "lyrics", "macro"],
                description="Generate moving head choreography plan (coordinated with macro)",
            ),
            # Stage 5: Rendering to XSQ
            # Consumes choreography_plan and beat_grid from pipeline state
            StageDefinition(
                id="render",
                stage=MovingHeadRenderingStage(
                    xsq_output_path=output_dir / f"{song_name}_twinklr_mh.xsq",
                    xsq_template_path=repo_root / "data/sequences/Need A Favor.xsq",
                    fixture_config_path=repo_root / "fixture_config.json",
                ),
                inputs=["moving_heads"],
                description="Render choreography to XSQ effects file",
            ),
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

    # Setup caching infrastructure
    fs = RealFileSystem()

    # LLM cache: Short-lived, transparent deduplication of identical LLM calls
    llm_cache_dir = absolute_path("data/cache/llm")
    llm_cache = FSCache(fs, llm_cache_dir)
    await llm_cache.initialize()
    print(f"🔄 LLM cache initialized: {llm_cache_dir}")

    # Agent cache: Long-lived, deterministic caching of agent results
    agent_cache_dir = absolute_path("data/cache/agents")
    agent_cache = FSCache(fs, agent_cache_dir)
    await agent_cache.initialize()
    print(f"💾 Agent cache initialized: {agent_cache_dir}")

    # Create provider with LLM cache
    provider = OpenAIProvider(api_key=api_key, llm_cache=llm_cache)

    llm_logger = create_llm_logger(
        enabled=job_config.agent.llm_logging.enabled if job_config else False,
        output_dir=logging_dir,
        log_level=job_config.agent.llm_logging.log_level if job_config else "standard",
        format=job_config.agent.llm_logging.format if job_config else "json",
    )

    # Create pipeline context with agent cache
    pipeline_context = PipelineContext(
        provider=provider,
        app_config=app_config,
        job_config=job_config,
        cache=agent_cache,
        llm_logger=llm_logger,
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

    # Macro plan (output is list[MacroSectionPlan])
    if "macro" in result.outputs:
        macro_sections = result.outputs["macro"]
        macro_path = save_artifact(
            [section.model_dump() for section in macro_sections],
            song_name,
            "macro_sections.json",
            output_dir,
        )
        print(f"📄 Macro sections: {macro_path.stem}")

    # Choreography plan
    if "moving_heads" in result.outputs:
        plan = result.outputs["moving_heads"]
        plan_path = save_artifact(
            plan.model_dump(),
            song_name,
            "choreography_plan.json",
            output_dir,
        )
        print(f"📄 Choreography plan: {plan_path.stem}")

    # XSQ output
    if "render" in result.outputs:
        xsq_path = result.outputs["render"]
        print(f"📄 XSQ output: {xsq_path}")

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
        print("  4. MovingHeadPlanner (coordinated with macro)")
        print("  5. Rendering → XSQ file")

        if "moving_heads" in result.outputs:
            plan = result.outputs["moving_heads"]
            print("\n🎯 Choreography Plan:")
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
            print(f"\n🎄 XSQ Output: {xsq_path}")
            segment_count = pipeline_context.metrics.get("mh_render_segments", 0)
            print(f"   Segments rendered: {segment_count}")

    else:
        print("❌ Pipeline failed. Check logs for details.")

    print(f"\n📁 All artifacts saved to: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
