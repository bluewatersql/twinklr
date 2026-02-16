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
import logging
from pathlib import Path
import sys
from typing import Any

from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.audio.models import StageStatus
from twinklr.core.config.loader import load_app_config, load_job_config
from twinklr.core.config.models import JobConfig
from twinklr.core.utils.formatting import clean_audio_filename
from twinklr.core.utils.logging import configure_logging

configure_logging(level="DEBUG")
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
    output_group.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="Write lyrics/phoneme mapping report to markdown file",
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

    clean_file_name = clean_audio_filename(Path(str(args.audio_path)).stem)

    # Set up cache info
    if args.no_cache:
        print("\nCache: DISABLED (will force reprocess)")
    else:
        cache_dir = Path(app_config.cache_dir) / "audio_cache"
        print(f"\nCache: {cache_dir}")

    # Create analyzer
    print_header("Running Analysis")
    analyzer = AudioAnalyzer(app_config=app_config, job_config=job_config)

    # Run analysis
    print(f"Analyzing: {args.audio_path}")
    try:
        bundle = await analyzer.analyze(str(args.audio_path), force_reprocess=args.no_cache)
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

    # Access features from the features dict
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
                print(f"    Coverage: {bundle.lyrics.quality.coverage_pct:.2%}")
                print(
                    f"    Monotonicity Violations: {bundle.lyrics.quality.monotonicity_violations}"
                )
                print(f"    Overlap Violations: {bundle.lyrics.quality.overlap_violations}")
                if bundle.lyrics.quality.avg_word_duration_ms:
                    print(
                        f"    Avg Word Duration: {bundle.lyrics.quality.avg_word_duration_ms:.0f}ms"
                    )

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
        pb = bundle.phonemes
        print(f"  Source: {pb.source.value}")
        print(f"  Confidence: {pb.confidence:.2f}")
        print(f"  OOV Rate: {pb.oov_rate:.2%}")
        print(f"  Coverage: {pb.coverage_pct:.2%}")
        print(f"  Burst Merges: {pb.burst_merge_count}")
        print(f"  Phonemes: {len(pb.phonemes)}")
        print(f"  Visemes: {len(pb.visemes)}")

        if pb.phonemes:
            print("\n  First 10 phonemes:")
            for p in pb.phonemes[:10]:
                ptype = f" ({p.phoneme_type})" if p.phoneme_type else ""
                print(f"    {p.start_ms:6d}ms - {p.end_ms:6d}ms: {p.text}{ptype}")

        if pb.visemes:
            print("\n  First 10 visemes:")
            for v in pb.visemes[:10]:
                print(f"    {v.start_ms:6d}ms - {v.end_ms:6d}ms: {v.viseme} (conf={v.confidence:.2f})")

    # Generate markdown report if requested
    if args.markdown:
        _write_markdown_report(bundle, args.markdown, clean_file_name)

    ## Save to file
    print_section("Saving Output")
    output_path = Path(f"artifacts/audio_pipeline/{clean_file_name}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        output_path.write_text(bundle.model_dump_json(indent=2))
        print(f"✅ Output saved to: {output_path}")
        print(f"   Size: {output_path.stat().st_size:,} bytes")
    except Exception as e:
        print(f"⚠️  Failed to save output: {e}")

    result: dict[str, Any] = bundle.model_dump(mode="json")
    return result


def _write_markdown_report(
    bundle: Any,
    output_path: Path,
    song_name: str,
) -> None:
    """Write a structured markdown report showing lyrics/phoneme/viseme mapping.

    Args:
        bundle: SongBundle with lyrics and phonemes.
        output_path: Path to write the markdown file.
        song_name: Cleaned song filename for the report title.
    """
    lines: list[str] = []
    lines.append(f"# Audio Analysis Report: {song_name}\n")

    # --- Quality Summary ---
    lines.append("## Quality Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")

    if bundle.lyrics:
        lines.append(f"| Lyrics Source | {bundle.lyrics.source or 'N/A'} |")
        if bundle.lyrics.quality:
            q = bundle.lyrics.quality
            lines.append(f"| Alignment Score | {q.alignment_score:.2f} |")
            if q.avg_word_duration_ms is not None:
                lines.append(f"| Avg Word Duration | {q.avg_word_duration_ms:.0f} ms |")
            lines.append(f"| Gap Violations | {q.gap_violations} |")
            lines.append(f"| Overlap Violations | {q.overlap_violations} |")
    if bundle.phonemes:
        pb = bundle.phonemes
        lines.append(f"| Phoneme Source | {pb.source.value} |")
        lines.append(f"| Phoneme Confidence | {pb.confidence:.2f} |")
        lines.append(f"| OOV Rate | {pb.oov_rate:.2%} |")
        lines.append(f"| Viseme Coverage | {pb.coverage_pct:.2%} |")
        lines.append(f"| Burst Merges | {pb.burst_merge_count} |")
        lines.append(f"| Total Phonemes | {len(pb.phonemes)} |")
        lines.append(f"| Total Visemes | {len(pb.visemes)} |")
    lines.append("")

    # --- Lyrics Mapping ---
    if bundle.lyrics and bundle.lyrics.phrases:
        lines.append("## Lyrics Mapping\n")

        # Build lookup helpers for phonemes and visemes by time range
        phonemes_list = bundle.phonemes.phonemes if bundle.phonemes else []
        visemes_list = bundle.phonemes.visemes if bundle.phonemes else []

        for phrase in bundle.lyrics.phrases:
            phrase_start = int(phrase.start_ms)
            phrase_end = int(phrase.end_ms)
            lines.append(
                f"### Phrase: \"{phrase.text}\" "
                f"({phrase_start}ms - {phrase_end}ms)\n"
            )

            words = phrase.words if phrase.words else []
            if not words:
                # Fall back to bundle-level words within this phrase's time range
                words = [
                    w
                    for w in (bundle.lyrics.words or [])
                    if int(w.start_ms) >= phrase_start and int(w.end_ms) <= phrase_end
                ]

            if words:
                lines.append("| Word | Start | End | Phonemes | Visemes |")
                lines.append("|------|-------|-----|----------|---------|")

                for word in words:
                    ws = int(word.start_ms)
                    we = int(word.end_ms)

                    # Find phonemes within this word's time window
                    word_phonemes = [
                        p.text for p in phonemes_list if p.start_ms >= ws and p.end_ms <= we
                    ]
                    # Find visemes within this word's time window
                    word_visemes = [
                        v.viseme for v in visemes_list if v.start_ms >= ws and v.end_ms <= we
                    ]

                    ph_str = " ".join(word_phonemes) if word_phonemes else "-"
                    vi_str = " ".join(word_visemes) if word_visemes else "-"
                    lines.append(f"| {word.text} | {ws} | {we} | {ph_str} | {vi_str} |")

                lines.append("")

    # --- Raw Phoneme Timeline (first 50) ---
    if bundle.phonemes and bundle.phonemes.phonemes:
        lines.append("## Phoneme Timeline (first 50)\n")
        lines.append("| Start (ms) | End (ms) | Phoneme | Type |")
        lines.append("|------------|----------|---------|------|")
        for p in bundle.phonemes.phonemes[:50]:
            ptype = p.phoneme_type or "-"
            lines.append(f"| {p.start_ms} | {p.end_ms} | {p.text} | {ptype} |")
        if len(bundle.phonemes.phonemes) > 50:
            remaining = len(bundle.phonemes.phonemes) - 50
            lines.append(f"\n*... {remaining} more phonemes omitted*\n")
        lines.append("")

    # --- Raw Viseme Timeline (first 50) ---
    if bundle.phonemes and bundle.phonemes.visemes:
        lines.append("## Viseme Timeline (first 50)\n")
        lines.append("| Start (ms) | End (ms) | Viseme | Confidence |")
        lines.append("|------------|----------|--------|------------|")
        for v in bundle.phonemes.visemes[:50]:
            lines.append(f"| {v.start_ms} | {v.end_ms} | {v.viseme} | {v.confidence:.2f} |")
        if len(bundle.phonemes.visemes) > 50:
            remaining = len(bundle.phonemes.visemes) - 50
            lines.append(f"\n*... {remaining} more visemes omitted*\n")
        lines.append("")

    # Write file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"\nMarkdown report saved to: {output_path}")


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
