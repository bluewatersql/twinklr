"""Section-to-bar mapping for the composition engine.

Bridges audio-detected section boundaries with the BeatGrid to resolve
which song-bar each section starts and ends at.  This allows the
TimingResolver to convert section-relative bar/beat references
(from the LLM planners) to absolute song positions.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass

from twinklr.core.sequencer.timing.beat_grid import BeatGrid


@dataclass(frozen=True)
class SectionBarRange:
    """A section's position resolved against the BeatGrid.

    All values are derived from the BeatGrid — the source of truth
    for all timing in the rendering pipeline.

    Attributes:
        section_id: Section identifier (e.g. ``chorus_2``).
        start_bar: 0-indexed bar in the song where this section starts.
        end_bar: 0-indexed bar in the song where this section ends
            (first bar of the *next* section, or song end).
        start_ms: Exact ms from the BeatGrid for the start bar.
        end_ms: Exact ms from the BeatGrid for the end bar.
    """

    section_id: str
    start_bar: int
    end_bar: int
    start_ms: float
    end_ms: float

    @property
    def bar_count(self) -> int:
        """Number of bars in this section."""
        return max(self.end_bar - self.start_bar, 0)


def build_section_bar_map(
    sections: list[tuple[str, int, int]],
    beat_grid: BeatGrid,
) -> dict[str, SectionBarRange]:
    """Build section-to-bar mapping using the BeatGrid.

    For each section, snaps its ``start_ms`` and ``end_ms`` to the
    nearest bar boundary in the BeatGrid and records the bar indices.
    The renderer then uses these indices to anchor section-relative
    bar/beat references to absolute song positions.

    Args:
        sections: List of ``(section_id, start_ms, end_ms)`` tuples
            from the audio profile / macro plan.
        beat_grid: Musical timing grid with bar boundaries.

    Returns:
        Dict mapping ``section_id`` → ``SectionBarRange``.

    Raises:
        ValueError: If *sections* is empty.

    Example:
        >>> sections = [("intro", 0, 400), ("chorus_1", 400, 23800)]
        >>> section_map = build_section_bar_map(sections, beat_grid)
        >>> section_map["chorus_1"].start_bar
        1
    """
    if not sections:
        raise ValueError("sections must not be empty")

    result: dict[str, SectionBarRange] = {}

    for section_id, raw_start_ms, raw_end_ms in sections:
        start_bar = _find_nearest_bar_index(
            beat_grid.bar_boundaries, float(raw_start_ms)
        )
        end_bar = _find_nearest_bar_index(
            beat_grid.bar_boundaries, float(raw_end_ms)
        )

        # Guarantee end_bar >= start_bar
        if end_bar < start_bar:
            end_bar = start_bar

        start_ms = beat_grid.bar_boundaries[start_bar]
        end_ms = beat_grid.bar_boundaries[end_bar]

        result[section_id] = SectionBarRange(
            section_id=section_id,
            start_bar=start_bar,
            end_bar=end_bar,
            start_ms=start_ms,
            end_ms=end_ms,
        )

    return result


def _find_nearest_bar_index(
    bar_boundaries: list[float], time_ms: float
) -> int:
    """Find the index of the bar boundary nearest to *time_ms*.

    Uses binary search for efficiency.

    Args:
        bar_boundaries: Sorted list of bar start times in ms.
        time_ms: Target time in ms.

    Returns:
        0-indexed bar boundary index.
    """
    if not bar_boundaries:
        return 0

    idx = bisect.bisect_left(bar_boundaries, time_ms)

    if idx == 0:
        return 0
    if idx >= len(bar_boundaries):
        return len(bar_boundaries) - 1

    # Compare distances to neighbours
    before = bar_boundaries[idx - 1]
    after = bar_boundaries[idx]

    if abs(time_ms - before) <= abs(time_ms - after):
        return idx - 1
    return idx


__all__ = [
    "SectionBarRange",
    "build_section_bar_map",
]
