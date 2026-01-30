#!/usr/bin/env python3
"""Demo script for AudioProfile agent.

Runs the AudioProfile agent on real audio files with live audio analysis.
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from twinklr.core.agents.audio.profile import (
    get_audio_profile_spec,
    run_audio_profile,
    shape_context,
    validate_audio_profile,
)
from twinklr.core.agents.logging import NullLLMCallLogger, create_llm_logger
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.audio.analyzer import AudioAnalyzer
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
    """Run AudioProfile agent demo."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="AudioProfile Agent Demo")
    parser.add_argument(
        "audio_file",
        nargs="?",
        default="data/music/Need A Favor.mp3",
        help="Path to audio file (default: data/music/Need A Favor.mp3)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force reanalysis (skip cache)",
    )
    args = parser.parse_args()

    print_section("AudioProfile Agent Demo", "=")

    # Check for API key
    import os

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        print("\nTo run this demo:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  python scripts/demo_audio_profile.py [audio_file]")
        sys.exit(1)

    print("✅ OpenAI API key found")

    # Load configuration
    print_subsection("0. Loading Configuration")
    repo_root = Path(__file__).parent.parent
    try:
        app_config = load_app_config(repo_root / "config.json")
        job_config = load_job_config(repo_root / "job_config.json")

        # Get model settings from config (fallback to plan_agent settings)
        model = job_config.agent.plan_agent.model
        temperature = 0.2  # Lower temp for factual analysis

        print("✅ Configuration loaded")
        print(f"   Model from config: {model}")
        print(f"   Temperature: {temperature} (AudioProfile uses low temp for factual output)")
        print(
            f"   LLM Logging: {'enabled' if job_config.agent.llm_logging.enabled else 'disabled'}"
        )
        config_loaded = True
    except Exception as e:
        print(f"⚠️  Could not load config, using defaults: {e}")
        app_config = None
        job_config = None
        model = "gpt-4o"
        temperature = 0.2
        config_loaded = False

    # Analyze audio
    print_subsection("1. Analyzing Audio")
    audio_path = str(Path(args.audio_file).resolve())
    print(f"   Audio file: {audio_path}")

    if not Path(audio_path).exists():
        print(f"❌ Audio file not found: {audio_path}")
        sys.exit(1)

    try:
        analyzer = AudioAnalyzer(app_config, job_config)
        print(f"   {'🔄 Force reanalysis' if args.no_cache else '📦 Using cache if available'}")
        print("   This may take 30-60 seconds for first analysis...")

        bundle = await analyzer.analyze(audio_path, force_reprocess=args.no_cache)

        print("✅ Analysis complete")
        print(f"   Duration: {bundle.timing.duration_s:.1f}s")
        print(f"   Tempo: {bundle.features.get('tempo_bpm', 'N/A')} BPM")
        sections = bundle.features.get("structure", {}).get("sections", [])
        print(f"   Sections detected: {len(sections)}")
    except Exception as e:
        print(f"❌ Failed to analyze audio: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Shape context
    print_subsection("2. Shaping Context")
    try:
        shaped = shape_context(bundle)
        shaped_size = len(json.dumps(shaped))
        print("✅ Context shaped successfully")
        print(f"   Output size: {shaped_size:,} bytes (~{shaped_size / 1024:.1f}KB)")
        print(f"   Sections: {len(shaped.get('sections', []))}")
        print(f"   Has energy: {'energy' in shaped}")
    except Exception as e:
        print(f"❌ Context shaping failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Setup agent
    print_subsection("3. Setting Up Agent")
    try:
        spec = get_audio_profile_spec(
            model=model,
            temperature=temperature,
        )
        print("✅ Agent spec created")
        print(f"   Agent: {spec.name}")
        print(f"   Model: {spec.model}")
        print(f"   Temperature: {spec.temperature}")
        print(f"   Mode: {spec.mode.value}")

        provider = OpenAIProvider(api_key=api_key)

        # Use proper LLM logger if enabled in config
        if config_loaded and job_config is not None and app_config is not None:
            if job_config.agent.llm_logging.enabled:
                artifact_dir = repo_root / app_config.output_dir / "audio_profile_demo"
                artifact_dir.mkdir(parents=True, exist_ok=True)
                llm_logger = create_llm_logger(
                    output_dir=artifact_dir / "llm_calls",
                    log_level=job_config.agent.llm_logging.log_level,
                    format=job_config.agent.llm_logging.format,
                )
                print("✅ Provider and logger ready (logging enabled)")
            else:
                llm_logger = NullLLMCallLogger()
                print("✅ Provider and logger ready (logging disabled)")
        else:
            llm_logger = NullLLMCallLogger()
            print("✅ Provider and logger ready (logging disabled)")
    except Exception as e:
        print(f"❌ Agent setup failed: {e}")
        sys.exit(1)

    # Run agent
    print_subsection("4. Running AudioProfile Agent")
    print("⏳ Calling LLM (this may take 10-30 seconds)...\n")

    try:
        profile = await run_audio_profile(
            song_bundle=bundle,
            provider=provider,
            llm_logger=llm_logger,
            model=model,
            temperature=temperature,
        )
        print("✅ Agent completed successfully!")
    except Exception as e:
        print(f"❌ Agent execution failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Validate output
    print_subsection("5. Validating Output")
    try:
        errors = validate_audio_profile(profile)
        if errors:
            print(f"⚠️  Validation found {len(errors)} issue(s):")
            for i, error in enumerate(errors, 1):
                print(f"   {i}. {error}")
        else:
            print("✅ All heuristic validation checks passed")
    except Exception as e:
        print(f"❌ Validation failed: {e}")

    # Display results
    print_section("AudioProfile Results", "=")

    print_subsection("Song Identity")
    print(f"  Title: {profile.song_identity.title or 'N/A'}")
    print(f"  Artist: {profile.song_identity.artist or 'N/A'}")
    print(f"  Duration: {profile.song_identity.duration_ms}ms")
    print(f"  BPM: {profile.song_identity.bpm or 'N/A'}")
    print(f"  Key: {profile.song_identity.key or 'N/A'}")
    print(f"  Time Signature: {profile.song_identity.time_signature or 'N/A'}")

    print_subsection("Structure")
    print(f"  Sections: {len(profile.structure.sections)}")
    print(f"  Confidence: {profile.structure.structure_confidence:.2f}")
    if profile.structure.notes:
        print(f"  Notes: {', '.join(profile.structure.notes)}")
    print("\n  Section Breakdown:")
    for i, section in enumerate(profile.structure.sections, 1):
        duration_s = (section.end_ms - section.start_ms) / 1000
        print(
            f"    {i}. {section.section_id:15} | {section.start_ms:6}ms - {section.end_ms:6}ms ({duration_s:5.1f}s)"
        )

    print_subsection("Energy Profile")
    print(f"  Macro Energy: {profile.energy_profile.macro_energy.value}")
    print(f"  Overall Mean: {profile.energy_profile.overall_mean:.2f}")
    print(f"  Confidence: {profile.energy_profile.energy_confidence:.2f}")
    print(f"  Section Profiles: {len(profile.energy_profile.section_profiles)}")
    print(f"  Peaks: {len(profile.energy_profile.peaks)}")

    if profile.energy_profile.peaks:
        print("\n  Major Peaks:")
        for i, peak in enumerate(profile.energy_profile.peaks[:5], 1):  # Show top 5
            print(f"    {i}. {peak.start_ms}ms - {peak.end_ms}ms (energy: {peak.energy:.2f})")

    print_subsection("Lyric Profile")
    print(f"  Plain Lyrics: {'Yes' if profile.lyric_profile.has_plain_lyrics else 'No'}")
    print(f"  Timed Words: {'Yes' if profile.lyric_profile.has_timed_words else 'No'}")
    print(f"  Phonemes: {'Yes' if profile.lyric_profile.has_phonemes else 'No'}")
    print(f"  Lyric Confidence: {profile.lyric_profile.lyric_confidence:.2f}")
    if profile.lyric_profile.notes:
        print(f"  Notes: {profile.lyric_profile.notes}")

    print_subsection("Creative Guidance")
    print(f"  Recommended Layers: {profile.creative_guidance.recommended_layer_count}")
    print(f"  Contrast: {profile.creative_guidance.recommended_contrast.value}")
    print(f"  Motion Density: {profile.creative_guidance.recommended_motion_density.value}")
    print(f"  Asset Usage: {profile.creative_guidance.recommended_asset_usage.value}")
    if profile.creative_guidance.recommended_color_story:
        print(f"  Color Story: {', '.join(profile.creative_guidance.recommended_color_story)}")
    if profile.creative_guidance.cautions:
        print("\n  Cautions:")
        for i, caution in enumerate(profile.creative_guidance.cautions, 1):
            print(f"    {i}. {caution}")

    print_subsection("Planner Hints")
    if profile.planner_hints.section_objectives:
        print("  Section Objectives:")
        for section_id, objective in list(profile.planner_hints.section_objectives.items())[:5]:
            print(f"    • {section_id}: {objective}")
    if profile.planner_hints.avoid_patterns:
        print("\n  Avoid Patterns:")
        for i, pattern in enumerate(profile.planner_hints.avoid_patterns, 1):
            print(f"    {i}. {pattern}")
    if profile.planner_hints.emphasize_groups:
        print(f"\n  Emphasize Groups: {', '.join(profile.planner_hints.emphasize_groups)}")

    # Save to file
    print_section("Saving Output", "=")
    output_path = Path("artifacts/audio_profile_demo_output.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        output_path.write_text(profile.model_dump_json(indent=2))
        print(f"✅ Output saved to: {output_path}")
        print(f"   Size: {output_path.stat().st_size:,} bytes")
    except Exception as e:
        print(f"⚠️  Failed to save output: {e}")

    print_section("Demo Complete", "=")
    print("✅ AudioProfile agent demo completed successfully!\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(130)
