"""Typed physical channel values for the physical moving-head renderer.

Trajectories carry absolute integer-millisecond times and explicit units: degrees for
pan/tilt, normalized values for the dimmer, named states for shutter and wheels. A
degree zero and a DMX zero are different things; nothing here is a DMX byte.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.config.fixtures.capabilities import AxisName, DiscreteName, FixtureCapabilities
from twinklr.core.sequencer.models.enum import ChannelName


class PhysicalPoint(BaseModel):
    """A finite value at an absolute time."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    t_ms: int = Field(ge=0)
    value: float = Field(allow_inf_nan=False)


class ContinuousTrajectory(BaseModel):
    """A continuous attribute over time, in an explicit unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit: Literal["degree", "normalized"]
    points: tuple[PhysicalPoint, ...] = Field(min_length=1)
    interpolation: Literal["linear", "hold"]

    @model_validator(mode="after")
    def _validate_points(self) -> ContinuousTrajectory:
        _require_increasing(tuple(point.t_ms for point in self.points))
        if self.unit == "normalized" and any(not 0 <= p.value <= 1 for p in self.points):
            raise ValueError("normalized trajectory values must lie in [0, 1]")
        return self


class DiscretePoint(BaseModel):
    """A semantic state selected at an absolute time."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    t_ms: int = Field(ge=0)
    state: str = Field(min_length=1)


class DiscreteTrajectory(BaseModel):
    """Semantic state changes over time; nothing is interpolated between states."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    events: tuple[DiscretePoint, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_events(self) -> DiscreteTrajectory:
        _require_increasing(tuple(event.t_ms for event in self.events))
        return self


PhysicalValue = ContinuousTrajectory | DiscreteTrajectory

CONTINUOUS_UNITS: dict[ChannelName, str] = {
    ChannelName.PAN: "degree",
    ChannelName.TILT: "degree",
    ChannelName.DIMMER: "normalized",
}
"""Continuous channels and their unit; every other channel takes discrete states."""

_AXIS_KEYS: dict[ChannelName, AxisName] = {
    ChannelName.PAN: "pan",
    ChannelName.TILT: "tilt",
    ChannelName.DIMMER: "dimmer",
}
_DISCRETE_KEYS: dict[ChannelName, DiscreteName] = {
    ChannelName.SHUTTER: "shutter",
    ChannelName.COLOR: "color",
    ChannelName.GOBO: "gobo",
}


class RenderLock(BaseModel):
    """Frames `[start_ms, end_ms)` of these fixtures' channels that must not change."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_ms: int = Field(ge=0)
    end_ms: int
    fixture_ids: tuple[str, ...] = Field(min_length=1)
    channels: tuple[ChannelName, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_span(self) -> RenderLock:
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class PhysicalChannelError(Exception):
    """A physical channel value the fixture's profile cannot honor."""

    def __init__(
        self, *, fixture_id: str, channel: ChannelName, time_ms: int | None, reason: str
    ) -> None:
        self.fixture_id = fixture_id
        self.channel = channel
        self.time_ms = time_ms
        self.reason = reason
        at = "" if time_ms is None else f" at {time_ms} ms"
        super().__init__(f"{fixture_id} {channel.value}{at}: {reason}")


def check_physical_value(
    fixture_id: str,
    channel: ChannelName,
    value: PhysicalValue,
    capabilities: FixtureCapabilities,
) -> None:
    """Raise `PhysicalChannelError` unless the profile supports every point of `value`.

    Continuous values must lie in the axis' operable range; discrete states must be
    declared by the profile.
    """

    def fail(reason: str, time_ms: int | None = None) -> PhysicalChannelError:
        return PhysicalChannelError(
            fixture_id=fixture_id, channel=channel, time_ms=time_ms, reason=reason
        )

    if isinstance(value, ContinuousTrajectory):
        axis_key = _AXIS_KEYS.get(channel)
        axis = capabilities.axes.get(axis_key) if axis_key is not None else None
        if axis is None:
            raise fail(f"profile {capabilities.profile_id!r} declares no {channel.value} axis")
        if value.unit != axis.unit:
            raise fail(f"unit {value.unit!r} does not match the axis unit {axis.unit!r}")
        for point in value.points:
            if not axis.admits(point.value):
                raise fail(
                    f"{point.value} is outside the operable range {axis.operable_range}",
                    point.t_ms,
                )
        return

    wheel_key = _DISCRETE_KEYS.get(channel)
    wheel = capabilities.discrete.get(wheel_key) if wheel_key is not None else None
    if wheel is None:
        raise fail(f"profile {capabilities.profile_id!r} declares no {channel.value} channel")
    for event in value.events:
        if event.state not in wheel.states:
            raise fail(f"state {event.state!r} is not declared by the profile", event.t_ms)


def _require_increasing(times: tuple[int, ...]) -> None:
    if any(later <= earlier for earlier, later in pairwise(times)):
        raise ValueError("times must be strictly increasing")
