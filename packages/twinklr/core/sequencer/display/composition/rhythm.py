"""Render declared rhythmic brightness against detected musical boundaries."""

from __future__ import annotations

from bisect import bisect_right

from twinklr.core.sequencer.display.composition.models import TemplateCompileError
from twinklr.core.sequencer.display.composition.template_compiler import TemplateCompileContext
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe, RecipeLayer
from twinklr.core.sequencer.vocabulary import GPTimingDriver, LaneKind, MotionVerb


def rhythm_points(
    recipe: EffectRecipe, layer: RecipeLayer, context: TemplateCompileContext
) -> list[tuple[float, float]]:
    """A pulse peaks on its clock and decays over its first half.

    Only explicit cadence is consumed: PULSE motion, or a SPARKLE layer with a
    beat/offbeat tag. Other spatial motion remains continuous. Half-time and
    offbeat are existing categorical recipe tags, never inferred from an ID.
    """
    tags = set(recipe.tags)
    timed_sparkle = MotionVerb.SPARKLE in layer.motion and bool(tags & {"beat", "offbeat"})
    if context.lane != LaneKind.RHYTHM or not (MotionVerb.PULSE in layer.motion or timed_sparkle):
        return []
    grid = context.beat_grid
    if grid is None:
        raise TemplateCompileError(
            template_id=recipe.recipe_id, reason="rhythmic brightness requires the BeatGrid"
        )
    if context.timing_driver == GPTimingDriver.BARS:
        boundaries = grid.bar_boundaries
    elif context.timing_driver == GPTimingDriver.BEATS:
        boundaries = grid.beat_boundaries
    else:
        # A phrase/lyric placement names one timed gesture, not a repeating beat.
        boundaries = [float(context.start_ms), float(context.end_ms)]
    anchor = context.section_start_ms
    if context.timing_driver == GPTimingDriver.BEATS and boundaries:
        # Bar detection can be a few ms after its beat; placement resolution uses
        # that nearest beat too. Dropping it would also shift half-time parity.
        anchor = min(boundaries, key=lambda t: abs(t - anchor))
    boundaries = [t for t in boundaries if t >= anchor]
    stride = 2 if "half-time" in tags else 1
    phase = 0.5 if "offbeat" in tags else 0.0
    onsets = [
        t + phase * (boundaries[i + 1] - t) if phase else t
        for i, t in enumerate(boundaries)
        if i % stride == 0 and (phase == 0 or i + 1 < len(boundaries))
    ]
    points: dict[float, float] = {0.0: 0.0}
    for i, onset in enumerate(onsets):
        if i + 1 < len(onsets):
            end = onsets[i + 1]
            if end < context.start_ms:
                continue
            points[onset + (end - onset) / 2] = 0.0
            points[max(onset, end - 20.0)] = 0.0
        if onset > context.end_ms:
            break
        if onset > 0:
            points[max(0.0, onset - 20.0)] = 0.0
        points[onset] = 1.0
    return sorted(points.items())


def brightness_curve(
    points: list[tuple[float, float]], start_ms: int, end_ms: int, peak_percent: float
) -> str:
    """Clip an absolute envelope to an emitted slice without restarting its phase."""
    times = [t for t, _ in points]

    def value_at(t: float) -> float:
        right = bisect_right(times, t)
        if right == 0:
            return points[0][1]
        if right == len(points):
            return points[-1][1]
        left_t, left_v = points[right - 1]
        right_t, right_v = points[right]
        return left_v + (right_v - left_v) * (t - left_t) / (right_t - left_t)

    clipped = [(float(start_ms), value_at(start_ms))]
    clipped.extend((t, v) for t, v in points if start_ms < t < end_ms)
    clipped.append((float(end_ms), value_at(end_ms)))
    duration = end_ms - start_ms
    # xLights brightness curves span 0-400 percent. Six decimal places retain
    # frame precision even for long placements; the old generic helper rounds to .01.
    values = ";".join(
        f"{(t - start_ms) / duration:.6f}:{v * peak_percent / 400:.6f}" for t, v in clipped
    )
    return (
        "Active=TRUE|Id=ID_VALUECURVE_Brightness|Type=Custom|Min=0.00|Max=400.00|"
        f"RV=FALSE|Values={values}|"
    )
