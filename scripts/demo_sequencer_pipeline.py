#!/usr/bin/env python3
"""Demo script for MacroPlanner pipeline.

Demonstrates the complete flow:
1. Audio Analysis (with caching)
2. Audio Profile Agent + Lyrics Agent (parallel)
3. MacroPlanner Agent (with both contexts)

Saves intermediates to artifacts/ for review.
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

from twinklr.core.agents.audio.lyrics import run_lyrics_async
from twinklr.core.agents.audio.profile import run_audio_profile
from twinklr.core.agents.logging import create_llm_logger
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.agents.sequencer.macro_planner import (
    MacroPlannerOrchestrator,
    PlanningContext,
)
from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.config.loader import load_app_config, load_job_config
from twinklr.core.utils.formatting import clean_audio_filename
from twinklr.core.utils.logging import configure_logging

configure_logging(level="INFO")
logger = logging.getLogger(__name__)


def print_section(title: str, char: str = "=") -> None:
    """Print a section header."""
    print(f"\n{char * len(title)}")
    print(f"{title}")
    print(f"{char * len(title)}\n")


def print_subsection(title: str) -> None:
    """Print a subsection header."""
    print(f"\n{title}")
    print("-" * len(title))


def save_artifact(data: dict, song_name: str, filename: str, output_dir: Path) -> Path:
    """Save artifact to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    with output_path.open("w") as f:
        json.dump(data, f, indent=2, default=str)

    return output_path


async def main() -> None:
    """Run MacroPlanner pipeline demo."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="MacroPlanner Pipeline Demo")
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
        help="Output directory for artifacts (default: artifacts/macro_planner_demo_TIMESTAMP)",
    )
    args = parser.parse_args()

    print_section("MacroPlanner Pipeline Demo", "=")

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        print("\nTo run this demo:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  python scripts/demo_macro_planner.py [audio_file]")
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
        print(f"⚠️  Could not load config, using defaults: {e}")
        app_config = None
        job_config = None
        model = "gpt-5.2"

    # ========================================================================
    # STAGE 1: Audio Analysis
    # ========================================================================
    print_section("STAGE 1: Audio Analysis", "=")

    try:
        analyzer = AudioAnalyzer(app_config, job_config)

        print(f"🎵 Analyzing: {audio_path.name}")
        print(f"   {'🔄 Force reanalysis' if args.no_cache else '📦 Using cache if available'}")
        print("   This may take 30-60 seconds for first analysis...")

        bundle = await analyzer.analyze(str(audio_path), force_reprocess=args.no_cache)

        # Save audio bundle for reference
        bundle_path = save_artifact(
            {
                "schema_version": bundle.schema_version,
                "audio_path": bundle.audio_path,
                "recording_id": bundle.recording_id,
                "timing": bundle.timing.model_dump(),
                "features_keys": list(bundle.features.keys()),  # Just keys, full features is huge
                "warnings": bundle.warnings,
            },
            song_name,
            "audio_bundle_summary.json",
            output_dir,
        )

        print("✅ Audio analysis complete")
        print(f"   Duration: {bundle.timing.duration_ms / 1000:.1f}s")
        print(f"   Tempo: {bundle.features.get('tempo_bpm', 'N/A')} BPM")
        sections = bundle.features.get("structure", {}).get("sections", [])
        print(f"   Sections: {len(sections)}")
        print(f"   📄 Saved: {bundle_path}")

    except Exception as e:
        print(f"❌ Audio analysis failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # ========================================================================
    # STAGE 2: Phase 1 Agents (Audio Profile + Lyrics)
    # ========================================================================
    print_section("STAGE 2: Phase 1 Agents", "=")

    try:
        provider = OpenAIProvider(api_key=api_key)

        # Setup LLM logging
        llm_logger = create_llm_logger(
            enabled=job_config.agent.llm_logging.enabled if job_config else False,
            output_dir=output_dir / "llm_calls",
            log_level=job_config.agent.llm_logging.log_level if job_config else "standard",
            format=job_config.agent.llm_logging.format if job_config else "yaml",
        )

        # Check if lyrics are available
        has_lyrics = bundle.lyrics is not None and bundle.lyrics.text is not None

        if has_lyrics:
            print("🤖 Running AudioProfile and Lyrics agents in parallel...")
            print("   This provides complete song understanding (musical + narrative)")

            # Run both agents concurrently
            audio_task = run_audio_profile(
                song_bundle=bundle,
                provider=provider,
                llm_logger=llm_logger,
                model=model,
                temperature=0.3,
            )

            lyrics_task = run_lyrics_async(
                song_bundle=bundle,
                provider=provider,
                llm_logger=llm_logger,
                model=model,
                temperature=0.5,
            )

            audio_profile, lyric_context = await asyncio.gather(audio_task, lyrics_task)

            # Save both outputs
            audio_profile_path = save_artifact(
                audio_profile.model_dump(),
                song_name,
                "audio_profile.json",
                output_dir,
            )

            lyric_context_path = save_artifact(
                lyric_context.model_dump(),
                song_name,
                "lyric_context.json",
                output_dir,
            )

            print("\n✅ Both agents complete")
            print("   AudioProfile:")
            print(f"     - Macro energy: {audio_profile.energy_profile.macro_energy}")
            print(
                f"     - Recommended layers: {audio_profile.creative_guidance.recommended_layer_count}"
            )
            print(
                f"     - Recommended contrast: {audio_profile.creative_guidance.recommended_contrast}"
            )
            print(f"     - 📄 Saved: {audio_profile_path}")
            print("   Lyrics Context:")
            print(f"     - Has narrative: {lyric_context.has_narrative}")
            print(f"     - Themes: {', '.join(lyric_context.themes[:3])}")
            print(f"     - Key phrases: {len(lyric_context.key_phrases)}")
            print(f"     - 📄 Saved: {lyric_context_path}")
        else:
            print("🤖 Running AudioProfile agent only (no lyrics available)...")

            audio_profile = await run_audio_profile(
                song_bundle=bundle,
                provider=provider,
                llm_logger=llm_logger,
                model=model,
                temperature=0.3,
            )

            lyric_context = None

            # Save audio profile
            audio_profile_path = save_artifact(
                audio_profile.model_dump(),
                song_name,
                "audio_profile.json",
                output_dir,
            )

            print("\n✅ Audio profile complete")
            print(f"   Macro energy: {audio_profile.energy_profile.macro_energy}")
            print(
                f"   Recommended layers: {audio_profile.creative_guidance.recommended_layer_count}"
            )
            print(
                f"   Recommended contrast: {audio_profile.creative_guidance.recommended_contrast}"
            )
            print(f"   📄 Saved: {audio_profile_path}")

    except Exception as e:
        print(f"❌ Phase 1 agents failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # ========================================================================
    # STAGE 3: MacroPlanner Agent
    # ========================================================================
    print_section("STAGE 3: MacroPlanner Agent", "=")

    try:
        # Mock display groups (minimal for demo)
        display_groups = [
            {"role_key": "OUTLINE", "model_count": 10, "group_type": "string"},
            {"role_key": "MEGA_TREE", "model_count": 1, "group_type": "tree"},
            {"role_key": "HERO", "model_count": 5, "group_type": "prop"},
            {"role_key": "ARCHES", "model_count": 5, "group_type": "arch"},
            {"role_key": "WINDOWS", "model_count": 8, "group_type": "window"},
        ]

        print(f"🎯 Display groups: {len(display_groups)}")
        for group in display_groups:
            print(f"   - {group['role_key']}: {group['model_count']} models")

        # Create planning context
        planning_context = PlanningContext(
            audio_profile=audio_profile,
            lyric_context=lyric_context,
            display_groups=display_groups,
        )

        print("\n📋 Planning context created:")
        print("   - Audio profile: ✅")
        print(
            f"   - Lyric context: {'✅' if planning_context.has_lyrics else '⏭️  (not available)'}"
        )
        print(f"   - Display groups: {len(planning_context.display_groups)}")

        # Create orchestrator
        orchestrator = MacroPlannerOrchestrator(
            provider=provider,
            max_iterations=job_config.agent.max_iterations if job_config else 3,
            min_pass_score=7.0,
            llm_logger=llm_logger,
        )

        print(
            f"\n🤖 Running MacroPlanner (max {orchestrator.controller.config.max_iterations} iterations)..."
        )
        if planning_context.has_lyrics:
            print("   Context: Musical analysis + Narrative/thematic analysis")
        else:
            print("   Context: Musical analysis only")

        result = await orchestrator.run(planning_context=planning_context)

        # Save macro plan (handle None case)
        if result.plan:
            macro_plan_path = save_artifact(
                result.plan.model_dump(),
                song_name,
                "macro_plan.json",
                output_dir,
            )

            # Save iteration metadata
            _ = save_artifact(
                {
                    "success": result.success,
                    "iterations": result.context.current_iteration,
                    "final_score": result.context.final_verdict.score
                    if result.context.final_verdict
                    else None,
                    "termination_reason": result.context.termination_reason,
                    "total_tokens": result.context.total_tokens_used,
                    "verdicts": [
                        {
                            "iteration": v.iteration,
                            "status": v.status.value,
                            "score": v.score,
                            "confidence": v.confidence,
                            "strengths": v.strengths,
                            "issues": [
                                {
                                    "category": i.category.value,
                                    "severity": i.severity.value,
                                    "message": i.message,
                                }
                                for i in v.issues
                            ],
                        }
                        for v in result.context.verdicts
                    ],
                },
                song_name,
                "macro_plan_audit.json",
                output_dir,
            )

            print("\n✅ MacroPlanner complete")
            print(f"   Success: {result.success}")
            print(f"   Iterations: {result.context.current_iteration}")
            if result.context.final_verdict:
                print(f"   Final score: {result.context.final_verdict.score:.1f}/10.0")
                print(f"   Status: {result.context.final_verdict.status.value}")
            print(f"   Total tokens: {result.context.total_tokens_used:,}")
            print(f"   📄 Saved: {macro_plan_path}")

            # Print plan summary
            print_subsection("MacroPlan Summary")
            plan = result.plan
            print(f"Theme: {plan.global_story.theme}")
            print(f"Motifs: {', '.join(plan.global_story.motifs)}")
            print(f"Layers: {len(plan.layering_plan.layers)}")
            for layer in plan.layering_plan.layers:
                print(
                    f"  - Layer {layer.layer_index} ({layer.layer_role.value}): {layer.usage_notes[:50]}..."
                )
            print(f"Sections: {len(plan.section_plans)}")
            for section in plan.section_plans:
                print(
                    f"  - {section.section.name}: {section.energy_target.value} energy, {section.choreography_style.value}"
                )
            if len(plan.section_plans) > 3:
                print(f"  ... and {len(plan.section_plans) - 3} more")
        else:
            print("\n❌ MacroPlanner failed to produce a plan")
            print(f"   Termination: {result.context.termination_reason}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ MacroPlanner failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # ========================================================================
    # Summary
    # ========================================================================
    print_section("Pipeline Complete! 🎉", "=")
    print("✅ Audio Analysis → Audio Profile → MacroPlanner")
    print(f"\n📁 All artifacts saved to: {output_dir}")
    print("\nPending stages:")
    print("  4. GroupPlanner (per display group)")
    print("  5. Asset Generation (imagery/shaders)")
    print("  6. Sequence Assembly (IR composition)")
    print("  7. Rendering & Export (xLights .xsq)")


if __name__ == "__main__":
    asyncio.run(main())
