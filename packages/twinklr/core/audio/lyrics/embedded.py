"""Embedded lyrics extraction (Phase 4).

Extracts lyrics from:
1. Sidecar .lrc files (highest priority)
2. SYLT tags (synced lyrics)
3. USLT tags (unsynced lyrics)

LRC format support:
- Standard timestamps: [mm:ss.xx], [mm:ss.x], [mm:ss]
- Metadata tags: [ar:], [ti:], [al:], etc.
- Offset tag: [offset:+/-ms]
- Multiple timestamps per line (chorus repetition)
"""

import logging
import re
from pathlib import Path

from twinklr.core.audio.models.lyrics import LyricPhrase, LyricWord

logger = logging.getLogger(__name__)

# LRC timestamp regex: [mm:ss.xx] or [mm:ss]
LRC_TIMESTAMP_PATTERN = re.compile(r"\[(\d{2}):(\d{2})(?:\.(\d{1,2}))?\]")


def parse_lrc_timestamp(timestamp_str: str) -> int | None:
    """Parse LRC timestamp to milliseconds.

    Supports formats:
    - [mm:ss.xx] - Standard format with centiseconds
    - [mm:ss.x] - Short centiseconds
    - [mm:ss] - No centiseconds

    Args:
        timestamp_str: Timestamp string (e.g., "[01:23.45]")

    Returns:
        Milliseconds, or None if invalid
    """
    match = LRC_TIMESTAMP_PATTERN.match(timestamp_str)
    if not match:
        return None

    minutes = int(match.group(1))
    seconds = int(match.group(2))
    centiseconds_str = match.group(3) or "0"

    # Normalize centiseconds to 2 digits
    if len(centiseconds_str) == 1:
        centiseconds = int(centiseconds_str) * 10
    else:
        centiseconds = int(centiseconds_str)

    total_ms = (minutes * 60 + seconds) * 1000 + centiseconds * 10
    return total_ms


def parse_lrc_content(
    content: str,
    duration_ms: int | None = None,
) -> list[LyricPhrase]:
    """Parse LRC file content into phrases.

    Args:
        content: LRC file content
        duration_ms: Optional song duration for last phrase end time

    Returns:
        List of LyricPhrase objects with timing
    """
    if not content.strip():
        return []

    phrases: list[tuple[int, str]] = []  # (start_ms, text)
    offset_ms = 0

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        # Check for offset tag
        if line.startswith("[offset:"):
            try:
                offset_str = line[8:-1]  # Extract "+500" or "-200"
                offset_ms = int(offset_str)
            except (ValueError, IndexError):
                logger.warning(f"Invalid offset tag: {line}")
            continue

        # Check for metadata tags (ar:, ti:, al:, etc.)
        if line.startswith("[") and ":" in line:
            # Check if it's metadata (no timestamp format)
            first_bracket = line[: line.find("]") + 1]
            if not LRC_TIMESTAMP_PATTERN.match(first_bracket):
                continue  # Skip metadata

        # Extract all timestamps and text from line
        timestamps = LRC_TIMESTAMP_PATTERN.findall(line)
        if not timestamps:
            continue

        # Remove all timestamps to get text
        text = LRC_TIMESTAMP_PATTERN.sub("", line).strip()

        # Create phrase for each timestamp (handles multiple timestamps)
        for timestamp_tuple in timestamps:
            # Reconstruct timestamp string for parsing
            if timestamp_tuple[2]:  # Has centiseconds
                timestamp_str = f"[{timestamp_tuple[0]}:{timestamp_tuple[1]}.{timestamp_tuple[2]}]"
            else:
                timestamp_str = f"[{timestamp_tuple[0]}:{timestamp_tuple[1]}]"

            start_ms = parse_lrc_timestamp(timestamp_str)
            if start_ms is not None:
                phrases.append((start_ms + offset_ms, text))

    if not phrases:
        return []

    # Sort by start time
    phrases.sort(key=lambda x: x[0])

    # Compute end times (use next phrase's start, or duration if last)
    result: list[LyricPhrase] = []
    for i, (start_ms, text) in enumerate(phrases):
        if i < len(phrases) - 1:
            end_ms = phrases[i + 1][0]
        else:
            # Last phrase: use duration if provided, else same as start
            end_ms = duration_ms if duration_ms is not None else start_ms

        result.append(
            LyricPhrase(
                text=text,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )

    return result


def extract_embedded_lyrics(
    audio_path: str,
    duration_ms: int | None = None,
) -> tuple[str | None, list[LyricPhrase], list[LyricWord], list[str]]:
    """Extract embedded lyrics from audio file.

    Search order:
    1. Sidecar .lrc file (same basename as audio)
    2. SYLT tag (synced lyrics)
    3. USLT tag (unsynced lyrics)

    Args:
        audio_path: Path to audio file
        duration_ms: Optional song duration for timing computation

    Returns:
        Tuple of (text, phrases, words, warnings):
        - text: Full lyrics text (None if not found)
        - phrases: Phrase-level timing (empty if no timing)
        - words: Word-level timing (empty - not extracted from embedded)
        - warnings: List of warning messages
    """
    warnings: list[str] = []
    path = Path(audio_path)

    # Try 1: Sidecar .lrc file
    lrc_path = path.with_suffix(".lrc")
    if lrc_path.exists():
        try:
            lrc_content = lrc_path.read_text(encoding="utf-8")
            phrases = parse_lrc_content(lrc_content, duration_ms=duration_ms)

            if phrases:
                # Build full text from phrases
                text = "\n".join(p.text for p in phrases)
                return text, phrases, [], warnings
            else:
                warnings.append("LRC file found but contains no valid lyrics")

        except Exception as e:
            warnings.append(f"Failed to parse LRC file: {e}")
            logger.warning(f"Failed to parse LRC file {lrc_path}: {e}")

    # Try 2: SYLT tag (synced lyrics)
    try:
        import mutagen

        audio_file = mutagen.File(audio_path)
        if audio_file and audio_file.tags:
            # Look for SYLT frames (ID3v2)
            sylt_keys = [k for k in audio_file.tags.keys() if k.startswith("SYLT")]
            if sylt_keys:
                sylt_frame = audio_file.tags[sylt_keys[0]]
                if hasattr(sylt_frame, "text") and sylt_frame.text:
                    # SYLT format: list of (timestamp, text) tuples
                    phrases_data = []
                    for timestamp, lyric_text in sylt_frame.text:
                        phrases_data.append((timestamp, lyric_text))

                    # Sort by timestamp
                    phrases_data.sort(key=lambda x: x[0])

                    # Build phrases
                    phrases = []
                    for i, (start_ms, text) in enumerate(phrases_data):
                        if i < len(phrases_data) - 1:
                            end_ms = phrases_data[i + 1][0]
                        else:
                            end_ms = duration_ms if duration_ms is not None else start_ms

                        phrases.append(
                            LyricPhrase(
                                text=text,
                                start_ms=start_ms,
                                end_ms=end_ms,
                            )
                        )

                    text = "\n".join(p.text for p in phrases)
                    return text, phrases, [], warnings

            # Try 3: USLT tag (unsynced lyrics)
            uslt_keys = [k for k in audio_file.tags.keys() if k.startswith("USLT")]
            if uslt_keys:
                uslt_frame = audio_file.tags[uslt_keys[0]]
                if hasattr(uslt_frame, "text") and uslt_frame.text:
                    text = uslt_frame.text
                    return text, [], [], warnings  # No timing

    except FileNotFoundError:
        warnings.append(f"Audio file not found: {audio_path}")
    except Exception as e:
        warnings.append(f"Failed to extract lyrics from tags: {e}")
        logger.warning(f"Failed to extract lyrics from {audio_path}: {e}")

    # No lyrics found
    return None, [], [], warnings
