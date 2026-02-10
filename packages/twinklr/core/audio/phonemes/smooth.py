"""Viseme smoothing for decor usage (Phase 6).

Implements the spec smoothing pipeline:
1. Coalesce adjacent identical visemes.
2. Min-hold: merge short events into neighbor (prefer previous, else next).
3. Burst merge: merge events shorter than min_burst_ms into longer neighbor
   (tie -> previous). Returns burst_merge_count for confidence scoring.
4. Boundary softening: expand boundaries by boundary_soften_ms,
   clamp to neighbors and [0, duration_ms].

Functions:
    coalesce_adjacent: Merge consecutive identical visemes.
    smooth_visemes: Full smoothing pipeline.

Example:
    >>> from twinklr.core.audio.models.phonemes import VisemeEvent
    >>> events = [
    ...     VisemeEvent(viseme="A", start_ms=0, end_ms=100),
    ...     VisemeEvent(viseme="A", start_ms=100, end_ms=200),
    ... ]
    >>> coalesced = coalesce_adjacent(events)
    >>> len(coalesced)
    1
"""

from twinklr.core.audio.models.phonemes import VisemeEvent


def coalesce_adjacent(events: list[VisemeEvent]) -> list[VisemeEvent]:
    """Merge consecutive identical visemes into single events.

    Args:
        events: List of viseme events (assumed sorted by start_ms).

    Returns:
        New list with consecutive identical visemes merged.

    Example:
        >>> events = [
        ...     VisemeEvent(viseme="A", start_ms=0, end_ms=100),
        ...     VisemeEvent(viseme="A", start_ms=100, end_ms=200),
        ... ]
        >>> result = coalesce_adjacent(events)
        >>> len(result)
        1
    """
    if not events:
        return []

    result: list[VisemeEvent] = [events[0]]

    for event in events[1:]:
        prev = result[-1]
        if event.viseme == prev.viseme:
            # Merge: extend previous to cover this event
            result[-1] = VisemeEvent(
                viseme=prev.viseme,
                start_ms=prev.start_ms,
                end_ms=event.end_ms,
                confidence=min(prev.confidence, event.confidence),
            )
        else:
            result.append(event)

    return result


def _apply_min_hold(events: list[VisemeEvent], min_hold_ms: int) -> list[VisemeEvent]:
    """Merge events shorter than min_hold_ms into neighbor.

    Prefer merging into previous event; if no previous, merge into next.

    Args:
        events: List of viseme events.
        min_hold_ms: Minimum hold duration in milliseconds.

    Returns:
        New list with short events merged.
    """
    if not events or min_hold_ms <= 0:
        return list(events)

    result: list[VisemeEvent] = []

    for event in events:
        duration = event.end_ms - event.start_ms
        if duration >= min_hold_ms:
            result.append(event)
        elif result:
            # Merge into previous (extend its end)
            prev = result[-1]
            result[-1] = VisemeEvent(
                viseme=prev.viseme,
                start_ms=prev.start_ms,
                end_ms=event.end_ms,
                confidence=min(prev.confidence, event.confidence),
            )
        else:
            # No previous — hold for now, will merge forward at end
            result.append(event)

    # If first event is still short and there's a next, merge forward
    if len(result) >= 2:
        first = result[0]
        if (first.end_ms - first.start_ms) < min_hold_ms:
            second = result[1]
            result[1] = VisemeEvent(
                viseme=second.viseme,
                start_ms=first.start_ms,
                end_ms=second.end_ms,
                confidence=min(first.confidence, second.confidence),
            )
            result.pop(0)

    return result


def _apply_burst_merge(
    events: list[VisemeEvent], min_burst_ms: int
) -> tuple[list[VisemeEvent], int]:
    """Merge events shorter than min_burst_ms into longer neighbor.

    Tie-breaking: prefer previous (merge backward).

    Args:
        events: List of viseme events.
        min_burst_ms: Minimum burst duration in milliseconds.

    Returns:
        Tuple of (smoothed events, burst_merge_count).
    """
    if not events or min_burst_ms <= 0:
        return list(events), 0

    burst_merge_count = 0
    result: list[VisemeEvent] = []

    for i, event in enumerate(events):
        duration = event.end_ms - event.start_ms
        if duration >= min_burst_ms:
            result.append(event)
            continue

        # Need to merge into longer neighbor
        burst_merge_count += 1

        prev_dur = (result[-1].end_ms - result[-1].start_ms) if result else 0
        next_dur = (events[i + 1].end_ms - events[i + 1].start_ms) if i + 1 < len(events) else 0

        if prev_dur >= next_dur and result:
            # Merge into previous (extend its end)
            prev = result[-1]
            result[-1] = VisemeEvent(
                viseme=prev.viseme,
                start_ms=prev.start_ms,
                end_ms=event.end_ms,
                confidence=min(prev.confidence, event.confidence),
            )
        elif i + 1 < len(events):
            # Merge into next (will be handled when next is processed)
            # For now, extend next event's start backward
            next_event = events[i + 1]
            events[i + 1] = VisemeEvent(
                viseme=next_event.viseme,
                start_ms=event.start_ms,
                end_ms=next_event.end_ms,
                confidence=min(event.confidence, next_event.confidence),
            )
        elif result:
            # Last event with no next — merge into previous
            prev = result[-1]
            result[-1] = VisemeEvent(
                viseme=prev.viseme,
                start_ms=prev.start_ms,
                end_ms=event.end_ms,
                confidence=min(prev.confidence, event.confidence),
            )
        else:
            # Only event — keep it
            result.append(event)

    return result, burst_merge_count


def _apply_boundary_soften(
    events: list[VisemeEvent], boundary_soften_ms: int, duration_ms: int
) -> list[VisemeEvent]:
    """Expand boundaries by boundary_soften_ms, clamp to neighbors and [0, duration_ms].

    Args:
        events: List of viseme events.
        boundary_soften_ms: Boundary softening window in milliseconds.
        duration_ms: Total song duration in milliseconds.

    Returns:
        New list with softened boundaries.
    """
    if not events or boundary_soften_ms <= 0:
        return list(events)

    result: list[VisemeEvent] = []

    for i, event in enumerate(events):
        # Expand start earlier
        new_start = event.start_ms - boundary_soften_ms
        # Expand end later
        new_end = event.end_ms + boundary_soften_ms

        # Clamp to [0, duration_ms]
        new_start = max(0, new_start)
        new_end = min(duration_ms, new_end)

        # Clamp to neighbors (don't overlap)
        if i > 0:
            prev_end = result[-1].end_ms
            new_start = max(new_start, prev_end)
        if i < len(events) - 1:
            next_start = events[i + 1].start_ms
            new_end = min(new_end, next_start)

        result.append(
            VisemeEvent(
                viseme=event.viseme,
                start_ms=new_start,
                end_ms=new_end,
                confidence=event.confidence,
            )
        )

    return result


def smooth_visemes(
    events: list[VisemeEvent],
    *,
    min_hold_ms: int,
    min_burst_ms: int,
    boundary_soften_ms: int,
    duration_ms: int,
) -> tuple[list[VisemeEvent], int]:
    """Apply full smoothing pipeline to viseme events.

    Pipeline stages:
    1. Coalesce adjacent identical visemes.
    2. Min-hold: merge events shorter than min_hold_ms into neighbor.
    3. Burst merge: merge events shorter than min_burst_ms into longer neighbor.
    4. Boundary soften: expand boundaries, clamp to neighbors and [0, duration_ms].

    Args:
        events: List of viseme events.
        min_hold_ms: Minimum hold duration in milliseconds.
        min_burst_ms: Minimum burst duration before merging in milliseconds.
        boundary_soften_ms: Boundary softening window in milliseconds.
        duration_ms: Total duration in milliseconds.

    Returns:
        Tuple of (smoothed events, burst_merge_count).

    Example:
        >>> events = [VisemeEvent(viseme="A", start_ms=0, end_ms=200)]
        >>> result, count = smooth_visemes(
        ...     events, min_hold_ms=50, min_burst_ms=40,
        ...     boundary_soften_ms=15, duration_ms=200,
        ... )
        >>> len(result)
        1
    """
    if not events:
        return [], 0

    # Stage 1: Coalesce adjacent identical
    smoothed = coalesce_adjacent(events)

    # Stage 2: Min-hold
    smoothed = _apply_min_hold(smoothed, min_hold_ms)

    # Re-coalesce after min-hold (merges may create new adjacents)
    smoothed = coalesce_adjacent(smoothed)

    # Stage 3: Burst merge
    smoothed, burst_merge_count = _apply_burst_merge(smoothed, min_burst_ms)

    # Re-coalesce after burst merge
    smoothed = coalesce_adjacent(smoothed)

    # Stage 4: Boundary soften
    smoothed = _apply_boundary_soften(smoothed, boundary_soften_ms, duration_ms)

    return smoothed, burst_merge_count
