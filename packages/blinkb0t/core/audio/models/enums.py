"""Enums for audio enhancement models (v3.0)."""

from enum import Enum


class StageStatus(str, Enum):
    """Status of a processing stage."""

    OK = "OK"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class LyricsSourcePath(str, Enum):
    """Path taken to resolve lyrics."""

    EMBEDDED = "EMBEDDED"
    LOOKUP_SYNCED = "LOOKUP_SYNCED"
    LOOKUP_PLAIN = "LOOKUP_PLAIN"
    WHISPERX_ALIGN = "WHISPERX_ALIGN"
    WHISPERX_TRANSCRIBE = "WHISPERX_TRANSCRIBE"


class G2PSource(str, Enum):
    """Source of grapheme-to-phoneme conversion."""

    CMUDICT = "CMUDICT"
    G2P_EN = "G2P_EN"
    HEURISTIC = "HEURISTIC"
