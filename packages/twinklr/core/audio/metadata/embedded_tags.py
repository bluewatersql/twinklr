"""Embedded tag extraction using mutagen (Phase 2).

Extracts metadata from audio file tags (MP3, FLAC, M4A, etc.)
using mutagen for format-agnostic reading.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from mutagen import File

from twinklr.core.audio.models.metadata import EmbeddedMetadata

logger = logging.getLogger(__name__)


def extract_embedded_metadata(audio_path: str | Path) -> EmbeddedMetadata:
    """Extract embedded metadata from audio file tags.

    Uses mutagen for format-agnostic tag reading. Normalizes tags to
    canonical field names regardless of format (ID3, Vorbis, MP4, etc.).

    Args:
        audio_path: Path to audio file

    Returns:
        EmbeddedMetadata with extracted tags

    Example:
        metadata = extract_embedded_metadata("song.mp3")
        print(f"Title: {metadata.title}")
        print(f"Artist: {metadata.artist}")
    """
    warnings: list[str] = []

    try:
        # Load file with mutagen
        audio_file = File(str(audio_path))

        if audio_file is None or not hasattr(audio_file, "tags") or audio_file.tags is None:
            warnings.append(f"No tags found in {Path(audio_path).name}")
            return EmbeddedMetadata(warnings=warnings)

        tags = audio_file.tags

        # Extract basic metadata
        title = _get_tag_value(tags, ["TIT2", "title", "\xa9nam"])
        artist = _get_tag_value(tags, ["TPE1", "artist", "\xa9ART"])
        album = _get_tag_value(tags, ["TALB", "album", "\xa9alb"])
        album_artist = _get_tag_value(tags, ["TPE2", "albumartist", "aART"])

        # Track and disc numbers
        track_number, track_total = _parse_number_pair(
            _get_tag_value(tags, ["TRCK", "tracknumber"])
        )
        disc_number, disc_total = _parse_number_pair(_get_tag_value(tags, ["TPOS", "discnumber"]))

        # Date/year
        date_raw = _get_tag_value(tags, ["TDRC", "date", "\xa9day", "year"])
        year = _extract_year(date_raw) if date_raw else None
        date_iso = _normalize_date(date_raw) if date_raw else None

        # Genre (can be multiple)
        genre = _get_tag_list(tags, ["TCON", "genre", "\xa9gen"])

        # Other metadata
        comment = _get_tag_value(tags, ["COMM", "comment", "\xa9cmt"])
        grouping = _get_tag_value(tags, ["GRP1", "grouping", "\xa9grp"])

        # Compilation flag
        compilation_raw = _get_tag_value(tags, ["TCMP", "compilation", "cpil"])
        compilation = _parse_bool(compilation_raw)

        # Lyrics detection
        lyrics_embedded_present = any(key in tags for key in ["USLT", "SYLT", "lyrics", "\xa9lyr"])

        # Artwork extraction
        artwork_info = _extract_artwork_info(audio_file)

        return EmbeddedMetadata(
            title=title,
            artist=artist,
            album=album,
            album_artist=album_artist,
            track_number=track_number,
            track_total=track_total,
            disc_number=disc_number,
            disc_total=disc_total,
            date_raw=date_raw,
            date_iso=date_iso,
            year=year,
            genre=genre,
            comment=comment,
            grouping=grouping,
            compilation=compilation,
            lyrics_embedded_present=lyrics_embedded_present,
            artwork_present=artwork_info["present"],
            artwork_mime=artwork_info["mime"],
            artwork_hash_sha256=artwork_info["hash"],
            artwork_size_bytes=artwork_info["size"],
            warnings=warnings,
        )

    except FileNotFoundError:
        warnings.append(f"Audio file not found: {audio_path}")
        return EmbeddedMetadata(warnings=warnings)
    except Exception as e:
        logger.warning(f"Error extracting tags from {audio_path}: {e}")
        warnings.append(f"Tag extraction error: {str(e)}")
        return EmbeddedMetadata(warnings=warnings)


def _get_tag_value(tags: Any, keys: list[str]) -> str | None:
    """Get first non-empty tag value from list of possible keys.

    Args:
        tags: Mutagen tags object
        keys: List of possible tag keys (format-specific)

    Returns:
        Tag value or None
    """
    for key in keys:
        if key in tags:
            value = tags[key]
            # Handle different tag formats
            if hasattr(value, "text"):
                # ID3 tags
                text_list = value.text
                if text_list and len(text_list) > 0:
                    text = str(text_list[0]).strip()
                    return text if text else None
            elif isinstance(value, list) and len(value) > 0:
                # Vorbis comments
                text = str(value[0]).strip()
                return text if text else None
            elif isinstance(value, str):
                text = value.strip()
                return text if text else None
    return None


def _get_tag_list(tags: Any, keys: list[str]) -> list[str]:
    """Get tag value as list (for multi-value fields like genre).

    Args:
        tags: Mutagen tags object
        keys: List of possible tag keys

    Returns:
        List of tag values
    """
    for key in keys:
        if key in tags:
            value = tags[key]
            if hasattr(value, "text"):
                # ID3 tags
                return [str(v).strip() for v in value.text if str(v).strip()]
            elif isinstance(value, list):
                # Vorbis comments
                return [str(v).strip() for v in value if str(v).strip()]
            elif isinstance(value, str):
                return [value.strip()] if value.strip() else []
    return []


def _parse_number_pair(value: str | None) -> tuple[int | None, int | None]:
    """Parse 'number/total' format (e.g., '5/12').

    Args:
        value: String like '5/12' or '5'

    Returns:
        Tuple of (number, total)
    """
    if not value:
        return None, None

    try:
        if "/" in value:
            parts = value.split("/")
            number = int(parts[0].strip()) if parts[0].strip() else None
            total = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else None
            return number, total
        else:
            return int(value.strip()), None
    except (ValueError, IndexError):
        return None, None


def _extract_year(date_str: str) -> int | None:
    """Extract year from date string.

    Args:
        date_str: Date string (YYYY, YYYY-MM, YYYY-MM-DD, etc.)

    Returns:
        Year as int or None
    """
    try:
        # Try to extract first 4 digits
        year_str = date_str.strip()[:4]
        year = int(year_str)
        if 1000 <= year <= 9999:
            return year
    except (ValueError, IndexError):
        pass
    return None


def _normalize_date(date_str: str) -> str | None:
    """Normalize date to ISO format (YYYY or YYYY-MM or YYYY-MM-DD).

    Args:
        date_str: Raw date string

    Returns:
        Normalized ISO date or None
    """
    # Simple normalization - just return the string if it looks date-like
    # More sophisticated parsing can be added later
    if date_str and len(date_str) >= 4:
        return date_str.strip()
    return None


def _parse_bool(value: str | None) -> bool | None:
    """Parse boolean-like values from tags.

    Args:
        value: String representation of boolean

    Returns:
        Boolean or None
    """
    if not value:
        return None

    value_lower = value.strip().lower()
    if value_lower in ("1", "true", "yes"):
        return True
    elif value_lower in ("0", "false", "no"):
        return False
    return None


def _extract_artwork_info(audio_file: Any) -> dict[str, Any]:
    """Extract artwork metadata (not the artwork itself).

    Args:
        audio_file: Mutagen File object

    Returns:
        Dict with artwork info (present: bool, mime: str|None, hash: str|None, size: int|None)
    """
    result: dict[str, Any] = {
        "present": False,
        "mime": None,
        "hash": None,
        "size": None,
    }

    try:
        # Try to get pictures (works for MP3, FLAC, etc.)
        pictures = getattr(audio_file, "pictures", [])
        if pictures and len(pictures) > 0:
            # Use first picture
            picture = pictures[0]
            artwork_data = picture.data
            result["present"] = True
            result["mime"] = picture.mime
            result["hash"] = hashlib.sha256(artwork_data).hexdigest()
            result["size"] = len(artwork_data)
            return result

        # Try tags for embedded images (ID3 APIC)
        if hasattr(audio_file, "tags") and audio_file.tags:
            for key in audio_file.tags.keys():
                if key.startswith("APIC"):
                    apic = audio_file.tags[key]
                    artwork_data = apic.data
                    result["present"] = True
                    result["mime"] = apic.mime
                    result["hash"] = hashlib.sha256(artwork_data).hexdigest()
                    result["size"] = len(artwork_data)
                    return result

    except Exception as e:
        logger.debug(f"Could not extract artwork info: {e}")

    return result
