"""Context shaping for Lyrics agent.

Transforms SongBundle into a focused context for lyric analysis.
"""

from typing import Any

from twinklr.core.audio.models import SongBundle
from twinklr.core.audio.sections import generate_section_ids


def shape_lyrics_context(bundle: SongBundle) -> dict[str, Any]:
    """Shape SongBundle for Lyrics agent.

    Extracts:
    - Full lyric text (essential for narrative analysis)
    - Word/phrase timing (for precise moment identification)
    - Song structure sections (for alignment)
    - Quality metrics (for confidence assessment)

    Uses canonical section IDs (per-type counters) from
    ``generate_section_ids`` to ensure alignment with the audio profile
    and downstream pipeline stages.

    Args:
        bundle: Complete SongBundle from audio analysis

    Returns:
        Dict containing shaped context for Lyrics agent
        Token budget: ~20-50KB depending on lyric length
    """
    if bundle.lyrics is None or bundle.lyrics.text is None:
        return {"has_lyrics": False, "reason": "No lyrics available"}

    # Get sections from raw features (same source as AudioProfile)
    structure = bundle.features.get("structure", {})
    sections = structure.get("sections", [])

    # Generate canonical section IDs using the shared utility
    # This ensures lyrics use the same IDs as audio profile / macro / group planners
    section_ids = generate_section_ids(sections)

    return {
        "has_lyrics": True,
        "text": bundle.lyrics.text,
        "words": [
            {"text": w.text, "start_ms": w.start_ms, "end_ms": w.end_ms}
            for w in bundle.lyrics.words
        ],
        "phrases": [
            {"text": p.text, "start_ms": p.start_ms, "end_ms": p.end_ms}
            for p in bundle.lyrics.phrases
        ],
        "sections": [
            {
                "section_id": section_ids[i],
                "name": s.get("label", "unknown"),
                "start_ms": int(s.get("start_s", 0) * 1000),
                "end_ms": int(s.get("end_s", 0) * 1000),
            }
            for i, s in enumerate(sections)
        ],
        "quality": {
            "coverage_pct": bundle.lyrics.quality.coverage_pct if bundle.lyrics.quality else 0.0,
            "source_confidence": (bundle.lyrics.source.confidence if bundle.lyrics.source else 0.0),
        },
        "duration_ms": bundle.timing.duration_ms,
    }
