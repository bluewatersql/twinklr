"""Resolve renderer-neutral section intent into template steps and timed segments.

The planner owns categorical intent; this module is the only conversion into
fixture-specific DMX. Timing is already expressed in milliseconds by the pipeline
through :class:`BeatGrid`, so no average-tempo grid is derived here.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise
from typing import Any

from twinklr.core.curves.models import CurvePoint, PointsCurve
from twinklr.core.sequencer.models.context import SectionRenderIntent, TemplateCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.template import Color, Template
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment


def apply_template_intent(template: Template, intent: SectionRenderIntent) -> Template:
    """Return a copy of ``template`` with section-wide categorical overrides."""
    if intent.intensity is None and intent.color is None:
        return template

    steps = []
    for step in template.steps:
        updates: dict[str, Any] = {}
        if intent.intensity is not None:
            updates["movement"] = step.movement.model_copy(
                update={"intensity": intent.intensity}, deep=True
            )
            updates["dimmer"] = step.dimmer.model_copy(
                update={"intensity": intent.intensity}, deep=True
            )
        if intent.color is not None:
            updates["color"] = Color(preset=intent.color)
        steps.append(step.model_copy(update=updates, deep=True))

    return template.model_copy(update={"steps": steps}, deep=True)


def apply_timed_intents(
    segments: Sequence[FixtureSegment], context: TemplateCompileContext
) -> list[FixtureSegment]:
    """Split compiled segments at event boundaries and apply persistent wheel values."""
    if not context.intent.shutter_events and not context.intent.gobo_events:
        return list(segments)

    fixtures = {fixture.fixture_id: fixture for fixture in context.fixtures}
    resolved: list[FixtureSegment] = []
    for segment in segments:
        fixture = fixtures[segment.fixture_id]
        pieces = [segment]
        pieces = _apply_axis_events(
            pieces,
            events=context.intent.shutter_events,
            channel=ChannelName.SHUTTER,
            registry=context.shutter_registry,
            calibration=fixture.calibration,
            n_samples=context.n_samples,
        )
        pieces = _apply_axis_events(
            pieces,
            events=context.intent.gobo_events,
            channel=ChannelName.GOBO,
            registry=context.gobo_registry,
            calibration=fixture.calibration,
            n_samples=context.n_samples,
        )
        resolved.extend(pieces)
    return resolved


def _apply_axis_events(
    segments: Sequence[FixtureSegment],
    *,
    events: Sequence[Any],
    channel: ChannelName,
    registry: Any,
    calibration: dict[str, Any],
    n_samples: int,
) -> list[FixtureSegment]:
    if not events:
        return list(segments)

    ordered = sorted(events, key=lambda event: event.at_ms)
    output: list[FixtureSegment] = []
    for segment in segments:
        boundaries = sorted(
            {event.at_ms for event in ordered if segment.t0_ms < event.at_ms < segment.t1_ms}
        )
        starts = [segment.t0_ms, *boundaries]
        ends = [*boundaries, segment.t1_ms]
        for start, end in zip(starts, ends, strict=True):
            piece = segment.model_copy(deep=True, update={"t0_ms": start, "t1_ms": end})
            _slice_existing_curves(piece, segment, start, end)
            active = next((event for event in reversed(ordered) if event.at_ms <= start), None)
            if active is not None:
                handler = registry.get(active.pattern_id)
                result = handler.generate(
                    {"calibration": calibration, "pattern": active.pattern_id}, n_samples
                )
                if result.emit:
                    points = result.curve
                    piece.add_channel(
                        channel=channel,
                        curve=PointsCurve(points=points) if points is not None else None,
                        static_dmx=result.static_dmx,
                        value_points=points,
                        clamp_min=result.clamp_min_dmx,
                        clamp_max=result.clamp_max_dmx,
                    )
                piece.add_metadata(f"{channel.value}_trace", result.trace)
                piece.add_metadata(f"{channel.value}_event_ms", active.at_ms)
            output.append(piece)
    return output


def _slice_existing_curves(
    piece: FixtureSegment, original: FixtureSegment, start_ms: int, end_ms: int
) -> None:
    """Keep non-event channel curves continuous when an event splits a segment."""
    duration_ms = original.t1_ms - original.t0_ms
    if duration_ms <= 0 or (start_ms == original.t0_ms and end_ms == original.t1_ms):
        return
    start_norm = (start_ms - original.t0_ms) / duration_ms
    end_norm = (end_ms - original.t0_ms) / duration_ms

    for channel_value in piece.channels.values():
        points = channel_value.value_points
        if points is None:
            curve_points = getattr(channel_value.curve, "points", None)
            points = list(curve_points) if curve_points else None
        if not points:
            continue
        sliced = _slice_points(points, start_norm, end_norm)
        channel_value.value_points = sliced
        channel_value.curve = PointsCurve(points=sliced)


def _slice_points(
    points: Sequence[CurvePoint], start_norm: float, end_norm: float
) -> list[CurvePoint]:
    span = end_norm - start_norm
    selected = [CurvePoint(t=0.0, v=_interpolate(points, start_norm))]
    selected.extend(
        CurvePoint(t=(point.t - start_norm) / span, v=point.v)
        for point in points
        if start_norm < point.t < end_norm
    )
    selected.append(CurvePoint(t=1.0, v=_interpolate(points, end_norm)))
    return selected


def _interpolate(points: Sequence[CurvePoint], at: float) -> float:
    if at <= points[0].t:
        return points[0].v
    for left, right in pairwise(points):
        if at <= right.t:
            width = right.t - left.t
            if width <= 0:
                return right.v
            ratio = (at - left.t) / width
            return left.v + ratio * (right.v - left.v)
    return points[-1].v
