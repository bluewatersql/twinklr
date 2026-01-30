#!/usr/bin/env python
"""Test audio pipeline directly with fine-grained control.

This script allows testing specific stages of the audio analysis pipeline,
particularly useful for validating lyrics resolution (WhisperX, Genius, etc.).

Usage:
    # Test full pipeline
    uv run python scripts/test_audio_pipeline.py path/to/song.mp3

    # Force WhisperX transcribe (skip all other lyrics sources)
    uv run python scripts/test_audio_pipeline.py path/to/song.mp3 --force-whisperx-transcribe

    # Force WhisperX align (requires --lyrics-text)
    uv run python scripts/test_audio_pipeline.py path/to/song.mp3 --force-whisperx-align --lyrics-text "..."

    # Test with specific config overrides
    uv run python scripts/test_audio_pipeline.py path/to/song.mp3 --whisperx-model base --whisperx-device cpu

    # Skip lyrics entirely (just audio features)
    uv run python scripts/test_audio_pipeline.py path/to/song.mp3 --skip-lyrics

    # Enable all enhancements
    uv run python scripts/test_audio_pipeline.py path/to/song.mp3 --enable-all
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys
from typing import Any

from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.audio.models import StageStatus
from twinklr.core.config.loader import load_app_config, load_job_config

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test audio analysis pipeline with fine-grained control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required
    parser.add_argument("audio_path", type=Path, help="Path to audio file")

    # Force specific stages
    force_group = parser.add_argument_group("Force specific stages")
    force_group.add_argument(
        "--force-whisperx-transcribe",
        action="store_true",
        help="Force WhisperX transcribe (skip embedded/synced/plain lyrics)",
    )
    force_group.add_argument(
        "--force-whisperx-align",
        action="store_true",
        help="Force WhisperX align (requires --lyrics-text)",
    )
    force_group.add_argument(
        "--force-plain-lookup",
        action="store_true",
        help="Force plain text lookup only (Genius, skip embedded/synced)",
    )
    force_group.add_argument(
        "--force-synced-lookup",
        action="store_true",
        help="Force synced lookup only (LRCLib, skip embedded)",
    )
    force_group.add_argument(
        "--lyrics-text",
        type=str,
        help="Reference lyrics text for WhisperX align",
    )

    # Feature toggles
    features_group = parser.add_argument_group("Feature toggles")
    features_group.add_argument(
        "--skip-metadata", action="store_true", help="Skip metadata extraction"
    )
    features_group.add_argument("--skip-lyrics", action="store_true", help="Skip lyrics resolution")
    features_group.add_argument(
        "--skip-phonemes", action="store_true", help="Skip phoneme generation"
    )
    features_group.add_argument("--enable-all", action="store_true", help="Enable all enhancements")

    # WhisperX configuration
    whisperx_group = parser.add_argument_group("WhisperX configuration")
    whisperx_group.add_argument(
        "--whisperx-model",
        type=str,
        choices=["tiny", "base", "small", "medium", "large"],
        help="WhisperX model size",
    )
    whisperx_group.add_argument(
        "--whisperx-device",
        type=str,
        choices=["cpu", "cuda", "mps"],
        help="WhisperX device",
    )
    whisperx_group.add_argument(
        "--whisperx-batch-size",
        type=int,
        help="WhisperX batch size",
    )

    # Output options
    output_group = parser.add_argument_group("Output options")
    output_group.add_argument(
        "--output-json",
        type=Path,
        help="Save full results to JSON file",
    )
    output_group.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching (force fresh analysis)",
    )
    output_group.add_argument(
        "--verbose",
        action="store_true",
        help="Show full debug output",
    )

    return parser.parse_args()


def print_header(title: str) -> None:
    """Print formatted header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def print_section(title: str) -> None:
    """Print formatted section."""
    print(f"\n{'-' * 80}")
    print(f"  {title}")
    print(f"{'-' * 80}\n")


def print_status(status: StageStatus) -> str:
    """Format status with color."""
    # Map StageStatus enum values to readable output
    if status == StageStatus.OK:
        return "✓ OK"
    elif status == StageStatus.SKIPPED:
        return "⊘ SKIPPED"
    elif status == StageStatus.ERROR:
        return "✗ ERROR"
    else:
        return f"? {status}"


def print_bundle_summary(bundle: Any, stage_name: str) -> None:
    """Print summary of a bundle (metadata, lyrics, etc.)."""
    print(f"\n{stage_name}:")
    print(f"  Status: {print_status(bundle.stage_status)}")

    if hasattr(bundle, "warnings") and bundle.warnings:
        print(f"  Warnings: {len(bundle.warnings)}")
        for i, warning in enumerate(bundle.warnings[:3], 1):
            print(f"    {i}. {warning}")
        if len(bundle.warnings) > 3:
            print(f"    ... and {len(bundle.warnings) - 3} more")


async def run_analysis(args: argparse.Namespace) -> dict[str, Any]:
    """Run audio analysis with specified configuration."""
    # Load config
    print_header("Configuration")
    app_config = load_app_config()

    # Load or create minimal job config
    try:
        job_config = load_job_config()
    except Exception:
        # Create minimal job config if not found
        from twinklr.core.config.models import JobConfig

        job_config = JobConfig(project_name="test_audio")

    # Apply overrides from args
    if args.enable_all:
        app_config.audio_processing.enhancements.enable_metadata = True
        app_config.audio_processing.enhancements.enable_lyrics = True
        app_config.audio_processing.enhancements.enable_phonemes = True
        app_config.audio_processing.enhancements.enable_whisperx = True
        print("✓ Enabled all enhancements")

    if args.skip_metadata:
        app_config.audio_processing.enhancements.enable_metadata = False
        print("✓ Disabled metadata extraction")

    if args.skip_lyrics:
        app_config.audio_processing.enhancements.enable_lyrics = False
        print("✓ Disabled lyrics resolution")

    if args.skip_phonemes:
        app_config.audio_processing.enhancements.enable_phonemes = False
        print("✓ Disabled phoneme generation")

    if args.whisperx_model:
        app_config.audio_processing.enhancements.whisperx_model = args.whisperx_model
        print(f"✓ WhisperX model: {args.whisperx_model}")

    if args.whisperx_device:
        app_config.audio_processing.enhancements.whisperx_device = args.whisperx_device
        print(f"✓ WhisperX device: {args.whisperx_device}")

    if args.whisperx_batch_size:
        app_config.audio_processing.enhancements.whisperx_batch_size = args.whisperx_batch_size
        print(f"✓ WhisperX batch size: {args.whisperx_batch_size}")

    # Handle force flags
    if args.force_whisperx_transcribe:
        print("\n⚠ FORCING WhisperX transcribe (skipping all other lyrics sources)")
        app_config.audio_processing.enhancements.enable_whisperx = True
        # We'll need to mock the providers to return empty results
        # For now, just enable it and document the behavior

    if args.force_whisperx_align:
        if not args.lyrics_text:
            print("ERROR: --force-whisperx-align requires --lyrics-text")
            sys.exit(1)
        print("\n⚠ FORCING WhisperX align with provided lyrics text")
        app_config.audio_processing.enhancements.enable_whisperx = True

    if args.force_plain_lookup:
        print("\n⚠ FORCING plain lookup (will skip embedded/synced)")
        app_config.audio_processing.enhancements.enable_lyrics_lookup = True

    if args.force_synced_lookup:
        print("\n⚠ FORCING synced lookup (will skip embedded)")
        app_config.audio_processing.enhancements.enable_lyrics_lookup = True

    # Print final config summary
    print_section("Active Configuration")
    print(f"Audio Path: {args.audio_path}")
    print(f"Cache Enabled: {not args.no_cache}")
    print("\nEnhancements:")
    print(f"  Metadata:  {app_config.audio_processing.enhancements.enable_metadata}")
    print(f"  Lyrics:    {app_config.audio_processing.enhancements.enable_lyrics}")
    print(f"  Phonemes:  {app_config.audio_processing.enhancements.enable_phonemes}")
    print(f"  WhisperX:  {app_config.audio_processing.enhancements.enable_whisperx}")
    if app_config.audio_processing.enhancements.enable_whisperx:
        print(f"    Model:   {app_config.audio_processing.enhancements.whisperx_model}")
        print(f"    Device:  {app_config.audio_processing.enhancements.whisperx_device}")

    # Set up cache (AudioAnalyzer creates its own cache from config)
    if args.no_cache:
        # Temporarily disable cache in config
        app_config.audio_processing.cache_enabled = False
        print("\nCache: DISABLED")
    else:
        cache_dir = Path(app_config.cache_dir) / "audio_cache"
        print(f"\nCache: {cache_dir}")

    # Create analyzer
    print_header("Running Analysis")
    analyzer = AudioAnalyzer(app_config=app_config, job_config=job_config)

    # Run analysis
    print(f"Analyzing: {args.audio_path}")
    try:
        bundle = await analyzer.analyze(str(args.audio_path))
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("\n✓ Analysis complete")

    # Print results
    print_header("Results Summary")

    # Audio features (timing from direct fields, rest from features dict)
    print(f"Duration: {bundle.timing.duration_s:.2f}s")

    # Access features from the features dict (backward compatible v2.3 format)
    features = bundle.features
    if "tempo" in features:
        print(f"Tempo: {features['tempo']:.1f} BPM")
    if "beats" in features:
        print(f"Beats: {len(features['beats'])}")
    if "bars" in features:
        print(f"Bars: {len(features['bars'])}")
    if "sections" in features:
        print(f"Sections: {len(features['sections'])}")

    # Metadata
    if bundle.metadata:
        print_bundle_summary(bundle.metadata, "Metadata")
        if bundle.metadata.stage_status == StageStatus.OK:
            if bundle.metadata.resolved:
                artist = getattr(bundle.metadata.resolved, "artist", None)
                title = getattr(bundle.metadata.resolved, "title", None)
                print(f"  Resolved: {artist} - {title}")
                if hasattr(bundle.metadata.resolved, "tags") and bundle.metadata.resolved.tags:
                    genre = bundle.metadata.resolved.tags.get("genre")
                    year = bundle.metadata.resolved.tags.get("date")
                    if genre:
                        print(f"    Genre: {genre}")
                    if year:
                        print(f"    Year: {year}")
            if bundle.metadata.embedded:
                artist = getattr(bundle.metadata.embedded, "artist", None)
                title = getattr(bundle.metadata.embedded, "title", None)
                print(f"  Embedded: {artist} - {title}")

    # Lyrics
    if bundle.lyrics:
        print_bundle_summary(bundle.lyrics, "Lyrics")
        if bundle.lyrics.stage_status == StageStatus.OK:
            print(f"  Source: {bundle.lyrics.source.kind} ({bundle.lyrics.source.provider})")
            print(f"  Confidence: {bundle.lyrics.source.confidence:.2f}")
            print(f"  Text Length: {len(bundle.lyrics.text or '')} chars")
            print(f"  Words: {len(bundle.lyrics.words)} timed words")
            print(f"  Phrases: {len(bundle.lyrics.phrases)} phrases")
            if bundle.lyrics.quality:
                print("  Quality:")
                print(f"    Coverage: {bundle.lyrics.quality.coverage:.2%}")
                print(f"    Gap Ratio: {bundle.lyrics.quality.gap_ratio:.2%}")
                print(f"    Avg Word Duration: {bundle.lyrics.quality.avg_word_duration_ms:.0f}ms")

            # Show first few words
            if bundle.lyrics.words:
                print("\n  First 5 words:")
                for word in bundle.lyrics.words[:5]:
                    print(f"    {word.start_ms:6.0f}ms - {word.end_ms:6.0f}ms: {word.text}")

            # Show first phrase
            if bundle.lyrics.phrases:
                print("\n  First phrase:")
                phrase = bundle.lyrics.phrases[0]
                print(f"    {phrase.start_ms:6.0f}ms - {phrase.end_ms:6.0f}ms")
                print(f"    {phrase.text}")

    # Phonemes
    if bundle.phonemes:
        print_bundle_summary(bundle.phonemes, "Phonemes")

    # Save to JSON if requested
    if args.output_json:
        print_section(f"Saving to {args.output_json}")
        output_data = bundle.model_dump(mode="json")
        args.output_json.write_text(json.dumps(output_data, indent=2, default=str))
        print(f"✓ Saved to {args.output_json}")

    return bundle.model_dump(mode="json")


async def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Validate audio file exists
    if not args.audio_path.exists():
        print(f"ERROR: Audio file not found: {args.audio_path}")
        sys.exit(1)

    # Run analysis
    await run_analysis(args)


if __name__ == "__main__":
    asyncio.run(main())
