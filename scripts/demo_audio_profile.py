#!/usr/bin/env python3
"""Demo script for AudioProfile and Lyrics agents.

Runs both AudioProfile and Lyrics agents in parallel on real audio files with live audio analysis.
"""

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys

from twinklr.core.utils.formatting import clean_audio_filename

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from twinklr.core.agents.audio.lyrics import (
    get_lyrics_spec,
    validate_lyrics,
)
from twinklr.core.agents.audio.lyrics.orchestrator import LyricsOrchestrator
from twinklr.core.agents.audio.profile import (
    get_audio_profile_spec,
    shape_context,
    validate_audio_profile,
)
from twinklr.core.agents.audio.profile.orchestrator import AudioProfileOrchestrator
from twinklr.core.agents.logging import NullLLMCallLogger, create_llm_logger
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.config.loader import load_app_config, load_job_config
from twinklr.core.utils.logging import configure_logging

configure_logging(level="DEBUG")
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


async def main() -> None:
    """Run AudioProfile and Lyrics agents demo."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="AudioProfile & Lyrics Agents Demo")
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
    parser.add_argument(
        "--skip-lyrics",
        action="store_true",
        help="Skip lyrics agent (run audio profile only)",
    )
    args = parser.parse_args()

    print_section("AudioProfile & Lyrics Agents Demo", "=")

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
        temperature = 0.3  # Lower temp for factual analysis

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
        model = "gpt-5.2"
        temperature = 0.3
        config_loaded = False

    clean_file_name = clean_audio_filename(Path(args.audio_file).stem)
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
    print_subsection("3. Setting Up Agents")
    try:
        audio_spec = get_audio_profile_spec(
            model=model,
            temperature=temperature,
        )
        print("✅ AudioProfile spec created")
        print(f"   Agent: {audio_spec.name}")
        print(f"   Model: {audio_spec.model}")
        print(f"   Temperature: {audio_spec.temperature}")
        print(f"   Mode: {audio_spec.mode.value}")

        # Check if lyrics are available
        has_lyrics = bundle.lyrics is not None and bundle.lyrics.text is not None

        if has_lyrics and not args.skip_lyrics:
            lyrics_spec = get_lyrics_spec(
                model=model,
                temperature=0.5,  # Higher temp for creative interpretation
            )
            print("\n✅ Lyrics spec created")
            print(f"   Agent: {lyrics_spec.name}")
            print(f"   Model: {lyrics_spec.model}")
            print(f"   Temperature: {lyrics_spec.temperature}")
            print(f"   Mode: {lyrics_spec.mode.value}")
        else:
            lyrics_spec = None
            if args.skip_lyrics:
                print("\n⏭️  Lyrics agent skipped (--skip-lyrics flag)")
            else:
                print("\n⏭️  Lyrics agent skipped (no lyrics in audio)")

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
                print("\n✅ Provider and logger ready (logging enabled)")
            else:
                llm_logger = NullLLMCallLogger()
                print("\n✅ Provider and logger ready (logging disabled)")
        else:
            llm_logger = NullLLMCallLogger()
            print("\n✅ Provider and logger ready (logging disabled)")
    except Exception as e:
        print(f"❌ Agent setup failed: {e}")
        sys.exit(1)

    # Run agents
    print_subsection("4. Running Agents")

    if lyrics_spec is not None:
        # Run both agents in parallel
        print("⏳ Running AudioProfile and Lyrics agents in parallel...")
        print("   (this may take 15-45 seconds for both agents)\n")
        print(f"   AudioProfile Model: {model} (temp={temperature})")
        print(f"   Lyrics Model: {model} (temp=0.5)")

        try:
            # Run both agents concurrently
            audio_orchestrator = AudioProfileOrchestrator(
                provider=provider,
                llm_logger=llm_logger,
                model=model,
                temperature=temperature,
            )
            audio_task = audio_orchestrator.run(bundle)

            lyrics_orchestrator = LyricsOrchestrator(
                provider=provider,
                llm_logger=llm_logger,
                model=model,
                temperature=0.5,
            )
            lyrics_task = lyrics_orchestrator.run(bundle)

            profile, lyric_context = await asyncio.gather(audio_task, lyrics_task)

            print("\n✅ Both agents completed successfully!")
        except Exception as e:
            print(f"\n❌ Agent execution failed: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
    else:
        # Run audio profile only
        print("⏳ Running AudioProfile agent only...")
        print("   (this may take 10-30 seconds)\n")
        print(f"   Model: {model} (temp={temperature})")

        try:
            orchestrator = AudioProfileOrchestrator(
                provider=provider,
                llm_logger=llm_logger,
                model=model,
                temperature=temperature,
            )
            profile = await orchestrator.run(bundle)
            lyric_context = None
            print("\n✅ AudioProfile agent completed successfully!")
        except Exception as e:
            print(f"\n❌ Agent execution failed: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)

    # Validate output
    print_subsection("5. Validating Outputs")

    # Validate AudioProfile
    try:
        errors = validate_audio_profile(profile)
        if errors:
            print(f"⚠️  AudioProfile validation found {len(errors)} issue(s):")
            for i, error in enumerate(errors, 1):
                print(f"   {i}. {error}")
        else:
            print("✅ AudioProfile: All heuristic validation checks passed")
    except Exception as e:
        print(f"❌ AudioProfile validation failed: {e}")

    # Validate Lyrics
    if lyric_context is not None:
        try:
            issues = validate_lyrics(lyric_context, bundle)
            if issues:
                print(f"\n⚠️  Lyrics validation found {len(issues)} issue(s):")
                for i, issue in enumerate(issues, 1):
                    print(f"   {i}. [{issue.severity.value}] {issue.message}")
            else:
                print("\n✅ Lyrics: All heuristic validation checks passed")
        except Exception as e:
            print(f"\n❌ Lyrics validation failed: {e}")

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

    # Display Lyrics Results (if available)
    if lyric_context is not None:
        print_section("Lyrics Context Results", "=")

        print_subsection("Thematic Analysis")
        print(f"  Has Lyrics: {'Yes' if lyric_context.has_lyrics else 'No'}")
        if lyric_context.themes:
            print(f"  Themes: {', '.join(lyric_context.themes)}")
        print(f"  Mood Arc: {lyric_context.mood_arc}")
        if lyric_context.genre_markers:
            print(f"  Genre Markers: {', '.join(lyric_context.genre_markers)}")

        print_subsection("Narrative Analysis")
        print(f"  Has Narrative: {'Yes' if lyric_context.has_narrative else 'No'}")
        if lyric_context.characters:
            print(f"  Characters: {', '.join(lyric_context.characters)}")
        if lyric_context.story_beats:
            print(f"  Story Beats: {len(lyric_context.story_beats)}")
            print("\n  Story Beat Breakdown:")
            for i, beat in enumerate(lyric_context.story_beats, 1):
                start_s = beat.timestamp_range[0] / 1000
                end_s = beat.timestamp_range[1] / 1000
                print(
                    f"    {i}. [{beat.beat_type}] {beat.section_id} ({start_s:.1f}s - {end_s:.1f}s)"
                )
                print(f"       {beat.description}")
                print(f"       💡 {beat.visual_opportunity}")

        print_subsection("Visual Hooks")
        print(f"  Key Phrases: {len(lyric_context.key_phrases)}")
        if lyric_context.key_phrases:
            print("\n  Key Phrases Breakdown:")
            for i, phrase in enumerate(lyric_context.key_phrases[:10], 1):  # Show first 10
                time_s = phrase.timestamp_ms / 1000
                print(f'    {i}. "{phrase.text}" @ {time_s:.1f}s [{phrase.emphasis}]')
                print(f"       {phrase.section_id}")
                print(f"       💡 {phrase.visual_hint}")

        if lyric_context.recommended_visual_themes:
            print("\n  Recommended Visual Themes:")
            for i, theme in enumerate(lyric_context.recommended_visual_themes, 1):
                print(f"    {i}. {theme}")

        print_subsection("Density & Coverage")
        print(f"  Lyric Density: {lyric_context.lyric_density}")
        print(f"  Vocal Coverage: {lyric_context.vocal_coverage_pct * 100:.1f}%")
        if lyric_context.silent_sections:
            print(f"  Silent Sections: {len(lyric_context.silent_sections)}")
            print("\n  Silent Section Breakdown:")
            for i, section in enumerate(lyric_context.silent_sections, 1):
                start_s = section.start_ms / 1000
                end_s = section.end_ms / 1000
                duration_s = section.duration_ms / 1000
                section_label = f" ({section.section_id})" if section.section_id else ""
                print(f"    {i}. {start_s:.1f}s - {end_s:.1f}s ({duration_s:.1f}s){section_label}")

    # Save to file
    print_section("Saving Outputs", "=")

    # Save AudioProfile
    audio_output_path = Path(f"artifacts/audio_profile/{clean_file_name}.json")
    audio_output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        audio_output_path.write_text(profile.model_dump_json(indent=2))
        print(f"✅ AudioProfile saved to: {audio_output_path}")
        print(f"   Size: {audio_output_path.stat().st_size:,} bytes")
    except Exception as e:
        print(f"⚠️  Failed to save AudioProfile: {e}")

    # Save Lyrics
    if lyric_context is not None:
        lyrics_output_path = Path(f"artifacts/lyrics/{clean_file_name}.json")
        lyrics_output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            lyrics_output_path.write_text(lyric_context.model_dump_json(indent=2))
            print(f"\n✅ Lyrics context saved to: {lyrics_output_path}")
            print(f"   Size: {lyrics_output_path.stat().st_size:,} bytes")
        except Exception as e:
            print(f"\n⚠️  Failed to save Lyrics context: {e}")

    print_section("Demo Complete", "=")
    print("✅ Agent demo completed successfully!\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(130)
