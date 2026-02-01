"""Example: Using the pipeline framework to build the sequencer pipeline.

This demonstrates how to refactor the demo_sequencer_pipeline.py script
to use the declarative pipeline framework.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from twinklr.core.agents.logging import create_llm_logger
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.config.loader import load_app_config, load_job_config
from twinklr.core.pipeline import (
    ExecutionPattern,
    PipelineContext,
    PipelineDefinition,
    PipelineExecutor,
    StageDefinition,
)
from twinklr.core.pipeline.definition import RetryConfig
from twinklr.core.pipeline.stages import (
    AudioAnalysisStage,
    AudioProfileStage,
    LyricsStage,
    MacroPlannerStage,
)

logger = logging.getLogger(__name__)


def create_sequencer_pipeline(display_groups: list[dict]) -> PipelineDefinition:
    """Create complete sequencer pipeline definition.

    This demonstrates the declarative pipeline approach. The pipeline
    automatically handles:
    - Dependency resolution (audio → profile/lyrics → macro → groups)
    - Parallel execution (profile + lyrics run together)
    - Fan-out pattern (group planner runs N times in parallel)
    - Error handling and retry logic

    Args:
        display_groups: List of display group configurations

    Returns:
        PipelineDefinition ready for execution

    Example:
        >>> pipeline = create_sequencer_pipeline(display_groups)
        >>> executor = PipelineExecutor()
        >>> result = await executor.execute(pipeline, audio_path, context)
    """
    return PipelineDefinition(
        name="twinklr_sequencer",
        description="Complete Twinklr sequencer pipeline: audio → planning → rendering",
        fail_fast=True,
        stages=[
            # ================================================================
            # STAGE 1: Audio Analysis
            # ================================================================
            StageDefinition(
                id="audio",
                stage=AudioAnalysisStage(),
                description="Analyze audio file (tempo, structure, features)",
                critical=True,
            ),
            # ================================================================
            # STAGE 2: Audio Profile + Lyrics (Parallel)
            # ================================================================
            StageDefinition(
                id="profile",
                stage=AudioProfileStage(),
                inputs=["audio"],
                description="Generate audio profile (energy, guidance)",
                critical=True,
            ),
            StageDefinition(
                id="lyrics",
                stage=LyricsStage(),
                pattern=ExecutionPattern.CONDITIONAL,
                inputs=["audio"],
                condition=lambda ctx: ctx.get_state("has_lyrics", False),
                description="Generate lyrics context (themes, narrative)",
                critical=False,  # Non-critical: can proceed without lyrics
            ),
            # ================================================================
            # STAGE 3: Macro Planning
            # ================================================================
            StageDefinition(
                id="macro",
                stage=MacroPlannerStage(display_groups=display_groups),
                inputs=["profile", "lyrics"],
                description="Generate macro plan (overall strategy)",
                retry_config=RetryConfig(
                    max_attempts=2,
                    initial_delay_ms=2000,
                ),
                critical=True,
            ),
            # ================================================================
            # Future stages (to be implemented):
            # ================================================================
            # StageDefinition("group_contexts", GroupPlanningContextBuilder(...), ...),
            # StageDefinition("groups", GroupPlannerStage(), ...),
            # StageDefinition("assets", AssetGeneratorStage(), ...),
            # StageDefinition("assembly", SequenceAssemblerStage(), ...),
            # StageDefinition("render", RenderingStage(), ...),
            # StageDefinition("export", XLightsExportStage(), ...),
        ],
    )


async def main() -> None:
    """Example: Execute sequencer pipeline."""
    # ========================================================================
    # Setup
    # ========================================================================
    repo_root = Path(__file__).parent.parent
    audio_path = repo_root / "data/music/Need A Favor.mp3"
    output_dir = repo_root / "artifacts/pipeline_demo"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load config
    app_config = load_app_config(repo_root / "config.json")
    job_config = load_job_config(repo_root / "job_config.json")

    # Create provider
    provider = OpenAIProvider(api_key="your-key-here")

    # Create LLM logger
    llm_logger = create_llm_logger(
        enabled=job_config.agent.llm_logging.enabled,
        output_dir=output_dir / "llm_calls",
        log_level=job_config.agent.llm_logging.log_level,
        format=job_config.agent.llm_logging.format,
    )

    # Mock display groups
    display_groups = [
        {"role_key": "OUTLINE", "model_count": 10, "group_type": "string"},
        {"role_key": "MEGA_TREE", "model_count": 1, "group_type": "tree"},
        {"role_key": "HERO", "model_count": 5, "group_type": "prop"},
        {"role_key": "ARCHES", "model_count": 5, "group_type": "arch"},
        {"role_key": "WINDOWS", "model_count": 8, "group_type": "window"},
    ]

    # ========================================================================
    # Create Pipeline
    # ========================================================================
    pipeline = create_sequencer_pipeline(display_groups)

    # Validate pipeline
    errors = pipeline.validate_pipeline()
    if errors:
        print("❌ Pipeline validation failed:")
        for error in errors:
            print(f"  - {error}")
        return

    print("✅ Pipeline validated")
    print(f"   Name: {pipeline.name}")
    print(f"   Stages: {len(pipeline.stages)}")
    print(f"   Entry points: {[s.id for s in pipeline.get_entry_points()]}")

    # ========================================================================
    # Create Context
    # ========================================================================
    context = PipelineContext(
        provider=provider,
        app_config=app_config,
        job_config=job_config,
        llm_logger=llm_logger,
        output_dir=output_dir,
    )

    # ========================================================================
    # Execute Pipeline
    # ========================================================================
    print(f"\n🚀 Executing pipeline: {pipeline.name}")
    print(f"   Input: {audio_path}")

    executor = PipelineExecutor()
    result = await executor.execute(
        pipeline=pipeline,
        initial_input=str(audio_path),
        context=context,
    )

    # ========================================================================
    # Results
    # ========================================================================
    print(f"\n{'=' * 60}")
    if result.success:
        print("✅ Pipeline completed successfully!")
    else:
        print("⚠️  Pipeline completed with errors")
        print(f"   Failed stages: {result.failed_stages}")

    print("\n📊 Pipeline Metrics:")
    print(f"   Duration: {result.total_duration_ms / 1000:.1f}s")
    print(f"   Stages completed: {len(result.outputs)}/{len(pipeline.stages)}")

    if result.success:
        print("\n📦 Outputs:")
        for stage_id in result.outputs:
            output = result.outputs[stage_id]
            print(f"   - {stage_id}: {type(output).__name__}")

        # Access specific outputs
        if "macro" in result.outputs:
            macro_plan = result.outputs["macro"]
            print("\n📋 Macro Plan:")
            print(f"   Sections: {len(macro_plan.section_plans)}")

        if "groups" in result.outputs:
            group_plans = result.outputs["groups"]
            print("\n👥 Group Plans:")
            print(f"   Groups: {len(group_plans)}")

    # Show metrics from context
    if context.metrics:
        print("\n📈 Context Metrics:")
        for key, value in context.metrics.items():
            print(f"   - {key}: {value}")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
