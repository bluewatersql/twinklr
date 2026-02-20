"""Build a music library index by extracting metadata from audio files.

Scans one or more directories for audio files and reads embedded tags
(ID3 for MP3, Vorbis for FLAC/OGG, etc.) using ``mutagen``.  The result
is a :class:`MusicLibraryIndex` that can be persisted as JSON and loaded
by :class:`AudioDiscoveryService` for metadata-based matching.
"""

from __future__ import annotations

import logging
from pathlib import Path

import mutagen

from twinklr.core.feature_engineering.models.music_library import (
    MusicLibraryEntry,
    MusicLibraryIndex,
)

logger = logging.getLogger(__name__)

_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}
)


def build_music_library_index(
    source_dirs: tuple[Path, ...],
    *,
    audio_extensions: frozenset[str] = _AUDIO_EXTENSIONS,
) -> MusicLibraryIndex:
    """Scan *source_dirs* and extract metadata from every audio file.

    Args:
        source_dirs: Directories to scan recursively.
        audio_extensions: File extensions to consider as audio.

    Returns:
        A :class:`MusicLibraryIndex` ready for JSON serialization.
    """
    entries: list[MusicLibraryEntry] = []
    for directory in source_dirs:
        resolved = directory.resolve()
        if not resolved.is_dir():
            logger.warning("Skipping non-existent directory: %s", directory)
            continue
        for path in sorted(resolved.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in audio_extensions:
                continue
            entries.append(_extract_entry(path))

    return MusicLibraryIndex(
        source_dirs=tuple(str(d.resolve()) for d in source_dirs),
        entries=tuple(entries),
    )


def _extract_entry(path: Path) -> MusicLibraryEntry:
    """Read tags from a single audio file, returning an entry with whatever is available."""
    title = ""
    artist = ""
    album = ""
    duration_s = 0.0

    try:
        tags = mutagen.File(path, easy=True)
        if tags is not None:
            title = _first_tag(tags, "title")
            artist = _first_tag(tags, "artist")
            album = _first_tag(tags, "album")
            if hasattr(tags, "info") and hasattr(tags.info, "length"):
                duration_s = float(tags.info.length)
    except Exception:  # noqa: BLE001
        logger.debug("Could not read tags from %s", path, exc_info=True)

    return MusicLibraryEntry(
        path=str(path),
        title=title,
        artist=artist,
        album=album,
        duration_s=round(duration_s, 2),
    )


def _first_tag(tags: mutagen.FileType, key: str) -> str:  # type: ignore[type-arg]
    """Safely extract the first value of a tag key."""
    val = tags.get(key)
    if val and isinstance(val, list) and len(val) > 0:
        return str(val[0])
    return ""
