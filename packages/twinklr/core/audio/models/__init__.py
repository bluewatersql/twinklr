"""Audio enhancement models (v3.0).

This module contains Pydantic models for the audio analyzer v3.0 enhancements:
- Metadata enrichment (embedded tags, fingerprinting, providers)
- Lyrics resolution (embedded, lookup, WhisperX)
- Phoneme/viseme generation (grapheme-to-phoneme, timing, smoothing)

All models use semantic versioning:
- Bundle schema_version: "3.0" (Major.Minor)
- Sub-bundle schema_version: "3.0.0" (Major.Minor.Patch)
"""

from twinklr.core.audio.models.enums import G2PSource, LyricsSourcePath, StageStatus
from twinklr.core.audio.models.lyrics import (
    LyricPhrase,
    LyricsBundle,
    LyricsQuality,
    LyricsSource,
    LyricsSourceKind,
    LyricWord,
)
from twinklr.core.audio.models.metadata import (
    EmbeddedMetadata,
    FingerprintInfo,
    MetadataBundle,
    MetadataCandidate,
    ResolvedMBIDs,
    ResolvedMetadata,
)
from twinklr.core.audio.models.phonemes import (
    Phoneme,
    PhonemeBundle,
    PhonemeSource,
    VisemeEvent,
)
from twinklr.core.audio.models.song_bundle import SongBundle, SongTiming

__all__ = [
    # Metadata (Phase 2)
    "EmbeddedMetadata",
    # Metadata (Phase 3)
    "FingerprintInfo",
    "G2PSource",
    "LyricPhrase",
    "LyricWord",
    # Lyrics (Phase 4)
    "LyricsBundle",
    "LyricsQuality",
    "LyricsSource",
    "LyricsSourceKind",
    "LyricsSourcePath",
    "MetadataBundle",
    "MetadataCandidate",
    # Phonemes (Phase 6)
    "Phoneme",
    "PhonemeBundle",
    "PhonemeSource",
    "ResolvedMBIDs",
    "ResolvedMetadata",
    # Song bundle
    "SongBundle",
    "SongTiming",
    # Enums
    "StageStatus",
    "VisemeEvent",
]
