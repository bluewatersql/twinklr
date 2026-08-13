"""Lyrics agent for narrative and thematic lyric analysis."""

from twinklr.core.agents.audio.lyrics.context import shape_lyrics_context
from twinklr.core.agents.audio.lyrics.models import (
    KeyPhrase,
    LyricContextModel,
    SilentSection,
    StoryBeat,
)
from twinklr.core.agents.audio.lyrics.orchestrator import LyricsOrchestrator
from twinklr.core.agents.audio.lyrics.spec import get_lyrics_spec
from twinklr.core.agents.audio.lyrics.validation import validate_lyrics

__all__ = [
    "KeyPhrase",
    "LyricContextModel",
    "LyricsOrchestrator",
    "SilentSection",
    "StoryBeat",
    "get_lyrics_spec",
    "shape_lyrics_context",
    "validate_lyrics",
]
