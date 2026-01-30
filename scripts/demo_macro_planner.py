#!/usr/bin/env python3
"""Demo script for MacroPlanner agent.

Runs the MacroPlanner agent on a real AudioProfile with live LLM calls.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.logging import NullLLMCallLogger, create_llm_logger
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.agents.sequencer.macro_planner.orchestrator import (
    MacroPlannerConfig,
    MacroPlannerOrchestrator,
)
from twinklr.core.agents.shared.judge.models import VerdictStatus
from twinklr.core.config.loader import load_app_config, load_job_config


def print_section(title: str, char: str = "=") -> None:
    """Print a section header."""
    print(f"\n{char * 80}")
    print(f"{title:^80}")
    print(f"{char * 80}\n")


def print_subsection(title: str) -> None:
    """Print a subsection header."""
    print(f"\n{title}")
    print("-" * len(title))


async def main() -> None:
    """Run MacroPlanner agent demo."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="MacroPlanner Agent Demo")
    parser.add_argument(
        "audio_profile",
        nargs="?",
        default="artifacts/audio_profile_demo_output.json",
        help="Path to AudioProfile JSON (default: artifacts/audio_profile_demo_output.json)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum iterations for agent loop (default: 5)",
    )
    args = parser.parse_args()

    print_section("MacroPlanner Agent Demo", "=")

    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        print("\nTo run this demo:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  python scripts/demo_macro_planner.py [audio_profile.json]")
        sys.exit(1)

    print("✅ OpenAI API key found")

    # Load configuration
    print_subsection("0. Loading Configuration")
    repo_root = Path(__file__).parent.parent
    try:
        app_config = load_app_config(repo_root / "config.json")
        job_config = load_job_config(repo_root / "job_config.json")

        # Get model settings from config
        planner_model = job_config.agent.plan_agent.model
        # Judge uses same model for now
        judge_model = planner_model

        print("✅ Configuration loaded")
        print(f"   Planner Model: {planner_model}")
        print(f"   Judge Model: {judge_model}")
        print(f"   Max Iterations: {args.max_iterations}")
        print(
            f"   LLM Logging: {'enabled' if job_config.agent.llm_logging.enabled else 'disabled'}"
        )
        config_loaded = True
    except Exception as e:
        print(f"⚠️  Could not load config, using defaults: {e}")
        app_config = None
        job_config = None
        planner_model = "gpt-4o"
        judge_model = "gpt-4o"
        config_loaded = False

    # Load AudioProfile
    print_subsection("1. Loading AudioProfile")
    audio_profile_path = Path(args.audio_profile).resolve()
    print(f"   Profile path: {audio_profile_path}")

    if not audio_profile_path.exists():
        print(f"❌ AudioProfile not found: {audio_profile_path}")
        print("\n💡 TIP: Run the AudioProfile demo first:")
        print("   python scripts/demo_audio_profile.py")
        sys.exit(1)

    try:
        with audio_profile_path.open() as f:
            profile_data = json.load(f)
        audio_profile = AudioProfileModel.model_validate(profile_data)

        print("✅ AudioProfile loaded successfully")
        print(f"   Song: {audio_profile.song_identity.title or 'Unknown'}")
        print(f"   Duration: {audio_profile.song_identity.duration_ms}ms")
        print(f"   Sections: {len(audio_profile.structure.sections)}")
        print(f"   Energy: {audio_profile.energy_profile.macro_energy.value}")
    except Exception as e:
        print(f"❌ Failed to load AudioProfile: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Setup orchestrator
    print_subsection("2. Setting Up MacroPlanner Orchestrator")
    try:
        provider = OpenAIProvider(api_key=api_key)

        # Use proper LLM logger if enabled in config
        if config_loaded and job_config is not None and app_config is not None:
            if job_config.agent.llm_logging.enabled:
                artifact_dir = repo_root / app_config.output_dir / "macro_planner_demo"
                artifact_dir.mkdir(parents=True, exist_ok=True)
                llm_logger = create_llm_logger(
                    output_dir=artifact_dir / "llm_calls",
                    log_level=job_config.agent.llm_logging.log_level,
                    format=job_config.agent.llm_logging.format,
                )
                print("✅ LLM logger ready (logging enabled)")
            else:
                llm_logger = NullLLMCallLogger()
                print("✅ LLM logger ready (logging disabled)")
        else:
            llm_logger = NullLLMCallLogger()
            print("✅ LLM logger ready (logging disabled)")

        config = MacroPlannerConfig(
            max_iterations=args.max_iterations,
            llm_logger=llm_logger,
        )

        orchestrator = MacroPlannerOrchestrator(provider=provider, config=config)

        print("✅ Orchestrator created")
        print(f"   Max Iterations: {config.max_iterations}")
        print(f"   Prompt Base: {config.prompt_base_path}")
    except Exception as e:
        print(f"❌ Orchestrator setup failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Run orchestrator
    print_subsection("3. Running MacroPlanner Orchestration")
    print(f"⏳ Starting orchestration (max {args.max_iterations} iterations)...")
    print("   This may take 30-90 seconds per iteration...\n")

    try:
        result = await orchestrator.orchestrate_async(audio_profile)

        if result.success:
            print("✅ Orchestration completed successfully!")
        else:
            print("⚠️  Orchestration finished but did not fully succeed")
            if result.error_message:
                print(f"   Error: {result.error_message}")

        print(f"\n   Final State: {result.context.state.value}")
        print(f"   Iterations Used: {result.context.current_iteration}")
        print(f"   Total Tokens: {result.context.total_tokens_used:,}")
        if result.context.termination_reason:
            print(f"   Termination: {result.context.termination_reason}")

    except Exception as e:
        print(f"❌ Orchestration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Display iteration history
    if result.context.verdicts:
        print_subsection("4. Iteration History")
        for i, verdict in enumerate(result.context.verdicts, 1):
            status_emoji = {
                VerdictStatus.APPROVE: "✅",
                VerdictStatus.SOFT_FAIL: "⚠️",
                VerdictStatus.HARD_FAIL: "❌",
            }.get(verdict.status, "❓")

            print(f"\n   Iteration {i}:")
            print(f"      Status: {status_emoji} {verdict.status.value}")
            print(f"      Score: {verdict.score:.1f}/10 (confidence: {verdict.confidence:.2f})")
            print(f"      Assessment: {verdict.overall_assessment[:80]}...")

            if verdict.score_breakdown:
                print("      Breakdown:")
                for dimension, score in verdict.score_breakdown.items():
                    print(f"         • {dimension}: {score:.1f}")

            if verdict.issues:
                print(f"      Issues: {len(verdict.issues)}")

    # Display final plan
    if result.plan:
        print_section("MacroPlan Results", "=")

        plan = result.plan

        print_subsection("Global Story")
        print(f"  Theme: {plan.global_story.theme}")
        print(f"  Motifs: {', '.join(plan.global_story.motifs)}")
        print(f"  Pacing: {plan.global_story.pacing_notes}")
        print(f"  Color Story: {plan.global_story.color_story}")

        print_subsection("Section Plans")
        print(f"  Total Sections: {len(plan.section_plans)}")
        print()
        for i, section in enumerate(plan.section_plans, 1):
            duration_s = (section.end_ms - section.start_ms) / 1000
            print(f"  {i}. {section.section_name} ({section.section_id})")
            print(f"     Time: {section.start_ms}ms - {section.end_ms}ms ({duration_s:.1f}s)")
            print(f"     Focus Groups: {', '.join(section.primary_focus_groups)}")
            if section.secondary_groups:
                print(f"     Secondary: {', '.join(section.secondary_groups)}")
            print(f"     Style: {section.choreography_style.value}")
            print(f"     Motion: {section.motion_density.value}")
            print(f"     Energy Target: {section.energy_target.value}")
            print(f"     Layers: {len(section.layering_plan.layers)}")
            for layer in section.layering_plan.layers:
                print(f"        • Layer {layer.layer_index}: {layer.intent}")
                if layer.preferred_templates:
                    print(f"          (Suggests: {', '.join(layer.preferred_templates)})")
            if section.objectives:
                print("     Objectives:")
                for obj in section.objectives:
                    print(f"        • {obj}")
            if section.avoid:
                print(f"     Avoid: {', '.join(section.avoid)}")
            print()

        print_subsection("Global Constraints")
        print(f"  Max Layers: {plan.global_constraints.max_layers}")
        print(f"  Default Blend Mode: {plan.global_constraints.default_blend_mode}")
        print(f"  Intensity Policy: {plan.global_constraints.intensity_policy}")

        asset_requirements = getattr(plan, "asset_requirements", [])
        if asset_requirements:
            print_subsection("Asset Requirements")
            for i, asset in enumerate(asset_requirements, 1):
                # Handle both AssetRequirement objects and strings (LLM sometimes returns strings)
                if isinstance(asset, str):
                    print(f"  {i}. {asset}")
                else:
                    print(f"  {i}. {asset.asset_name} ({asset.asset_type})")
                    print(f"     Purpose: {asset.purpose}")
                    if asset.notes:
                        print(f"     Notes: {asset.notes}")

        print_subsection("Quality Metrics")
        if plan.judge_score is not None:
            print(f"  Final Judge Score: {plan.judge_score:.1f}/10")
        if plan.judge_feedback:
            print(f"  Judge Feedback: {plan.judge_feedback[:100]}...")
        print(f"  Iterations: {plan.iteration}")

        # Save to file
        print_section("Saving Output", "=")
        output_path = Path("artifacts/macro_planner_demo_output.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            output_path.write_text(plan.model_dump_json(indent=2))
            print(f"✅ MacroPlan saved to: {output_path}")
            print(f"   Size: {output_path.stat().st_size:,} bytes")
        except Exception as e:
            print(f"⚠️  Failed to save output: {e}")

    else:
        print_section("MacroPlan Results", "=")
        print("⚠️  No plan was generated")
        print(f"   State: {result.context.state.value}")
        if result.error_message:
            print(f"   Error: {result.error_message}")

    # Summary
    print_section("Demo Complete", "=")
    if result.success and result.plan:
        print("✅ MacroPlanner agent demo completed successfully!")
        print(f"   • {result.context.current_iteration} iterations")
        print(f"   • {len(result.plan.section_plans)} sections planned")
        print(f"   • {result.context.total_tokens_used:,} tokens used")
    else:
        print("⚠️  Demo completed with issues")
        print(f"   State: {result.context.state.value}")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(130)
