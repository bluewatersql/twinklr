"""Test fixtures for AudioProfile agent."""

import json
from pathlib import Path

from twinklr.core.audio.models import SongBundle


def load_need_a_favor_bundle() -> SongBundle:
    """Load 'Need A Favor' SongBundle fixture.

    Returns:
        SongBundle for "Need A Favor" by Luke Combs (~197s, 156 BPM)
    """
    fixture_path = Path(__file__).parent / "need_a_favor_song_bundle.json"
    bundle_data = json.loads(fixture_path.read_text())
    return SongBundle(**bundle_data)


__all__ = ["load_need_a_favor_bundle"]
