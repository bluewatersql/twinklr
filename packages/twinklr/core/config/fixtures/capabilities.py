"""Explicit fixture capabilities and run initial state for the physical renderer.

A `FixtureCapabilities` profile says which model-relative DMX channels a fixture has,
how calibrated physical values map to DMX words, which bytes select its discrete
states, and what extinguishes its output. Nothing is inferred from the legacy fixture
fields, and nothing unknown (speed, latency, settle time) becomes a number.

`InitialFixtureState` is a run input: where a fixture is at time zero. A reusable
profile never claims a current pose. Nothing renders from either model until the
`physical_v2` renderer ships.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_DMX_EFFECT_CHANNELS = 48
"""Model-relative channels the xLights DMX effect addresses (`DMXEffect.h`)."""

AxisName = Literal["pan", "tilt", "dimmer"]
DiscreteName = Literal["shutter", "color", "gobo"]

_AXIS_UNITS: dict[str, str] = {"pan": "degree", "tilt": "degree", "dimmer": "normalized"}


class AxisCapability(BaseModel):
    """A continuous attribute and its calibrated physical-value-to-DMX-word mapping.

    `physical_min`/`physical_max` are the calibrated endpoints, in fixture-local
    unwrapped units, mapped to DMX word 0 and the full word. `allowed_min`/`allowed_max`
    restrict operation inside that mapping without rescaling it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit: Literal["degree", "normalized"]
    physical_min: float = Field(allow_inf_nan=False)
    physical_max: float = Field(allow_inf_nan=False)
    allowed_min: float | None = Field(
        default=None,
        allow_inf_nan=False,
        description="Lowest operable value; default the calibrated minimum",
    )
    allowed_max: float | None = Field(
        default=None,
        allow_inf_nan=False,
        description="Highest operable value; default the calibrated maximum",
    )
    coarse_offset: int = Field(ge=1, le=MAX_DMX_EFFECT_CHANNELS)
    fine_offset: int | None = Field(default=None, ge=1, le=MAX_DMX_EFFECT_CHANNELS)
    inverted: bool = False
    travel_speed_per_s: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        description=(
            "Configured conservative travel estimate in axis units per second, used for "
            "feasibility. Not a manufacturer maximum-rate claim. Unknown stays null."
        ),
    )
    latency_ms: int | None = Field(default=None, ge=0, description="Command-to-motion latency")
    settle_ms: int | None = Field(default=None, ge=0, description="Settle time after arrival")

    @model_validator(mode="after")
    def _validate_range(self) -> AxisCapability:
        if self.physical_min >= self.physical_max:
            raise ValueError("physical_min must be less than physical_max")
        if self.unit == "normalized" and not 0 <= self.physical_min < self.physical_max <= 1:
            raise ValueError("a normalized axis' physical range must lie within 0 and 1")
        low, high = self.operable_range
        if not self.physical_min <= low < high <= self.physical_max:
            raise ValueError(
                "allowed_min/allowed_max must be ordered and lie within "
                f"[{self.physical_min}, {self.physical_max}]"
            )
        return self

    @property
    def operable_range(self) -> tuple[float, float]:
        low = self.physical_min if self.allowed_min is None else self.allowed_min
        high = self.physical_max if self.allowed_max is None else self.allowed_max
        return low, high

    @property
    def full_word(self) -> int:
        """The largest DMX word: 65535 with a fine channel, else 255."""
        return 65535 if self.fine_offset is not None else 255

    def admits(self, value: float | Fraction) -> bool:
        low, high = self.operable_range
        return low <= value <= high

    def dmx_word(self, value: float | Fraction) -> int:
        """Encode an admitted physical value as an integer DMX word.

        Maps over the full calibrated range, never the allowed window, to 0..255 or,
        with a fine channel, 0..65535; rounds half up in exact arithmetic, then applies
        inversion once. A `Fraction` is mapped exactly, with no float rounding first.

        Raises:
            ValueError: If the value is outside the operable range.
        """
        if not self.admits(value):
            raise ValueError(f"{value} is outside the operable range {self.operable_range}")
        word = self._uninverted_word(Fraction(value))
        return self.full_word - word if self.inverted else word

    def _uninverted_word(self, value: Fraction) -> int:
        low = Fraction(self.physical_min)
        scaled = (value - low) * self.full_word / (Fraction(self.physical_max) - low)
        return (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)

    def check_default_word(self, name: str, defaults: dict[int, int]) -> None:
        """Reject default bytes whose word no admitted value encodes to.

        Inversion is undone first; with a fine channel the word is coarse << 8 | fine.

        Raises:
            ValueError: Naming the axis, its offsets, the word and its decoded value.
        """
        offsets = [self.coarse_offset]
        if self.fine_offset is not None:
            offsets.append(self.fine_offset)
        word = 0
        for offset in offsets:
            word = word << 8 | defaults[offset]
        uninverted = self.full_word - word if self.inverted else word
        low, high = self.operable_range
        if (
            not self._uninverted_word(Fraction(low))
            <= uninverted
            <= self._uninverted_word(Fraction(high))
        ):
            span = Fraction(self.physical_max) - Fraction(self.physical_min)
            decoded = float(self.physical_min + span * uninverted / self.full_word)
            raise ValueError(
                f"{name} default word {word} at offsets {'/'.join(map(str, offsets))} "
                f"decodes to {decoded:g}, outside the allowed window [{low:g}, {high:g}]"
            )


class DiscreteState(BaseModel):
    """A semantic state: the DMX range it occupies and the one byte that selects it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    range_min: int = Field(ge=0, le=255)
    range_max: int = Field(ge=0, le=255)
    value: int = Field(ge=0, le=255, description="Byte emitted to select this state")
    settle_ms: int | None = Field(default=None, ge=0, description="Settle time after selection")

    @model_validator(mode="after")
    def _validate_value(self) -> DiscreteState:
        if not self.range_min <= self.value <= self.range_max:
            raise ValueError(
                f"value {self.value} is outside its range [{self.range_min}, {self.range_max}]"
            )
        return self


class DiscreteCapability(BaseModel):
    """A wheel or shutter channel with named states; a range never chooses a byte."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    offset: int = Field(ge=1, le=MAX_DMX_EFFECT_CHANNELS)
    states: dict[str, DiscreteState] = Field(min_length=1)
    default_state: str
    closed_state: str | None = None
    open_state: str | None = None

    @model_validator(mode="after")
    def _validate_keys(self) -> DiscreteCapability:
        for key in (self.default_state, self.closed_state, self.open_state):
            if key is not None and key not in self.states:
                raise ValueError(f"state {key!r} is not one of {sorted(self.states)}")
        # One byte belongs to one state, so no two ranges (or selected bytes) coincide.
        ordered = sorted(self.states.items(), key=lambda item: item[1].range_min)
        for (lower, low), (upper, high) in pairwise(ordered):
            if high.range_min <= low.range_max:
                raise ValueError(
                    f"states {lower!r} [{low.range_min}, {low.range_max}] and {upper!r} "
                    f"[{high.range_min}, {high.range_max}] overlap"
                )
        return self

    def resolve(self, state: str) -> int:
        """Return the byte declared to select a named state.

        Only the state's declared `value`: never a range bound, a byte between two
        states, or the open, closed or default state in place of an unknown one.

        Raises:
            ValueError: If `state` is not declared.
        """
        declared = self.states.get(state)
        if declared is None:
            raise ValueError(f"state {state!r} is not one of {sorted(self.states)}")
        return declared.value


class VisibilityCapability(BaseModel):
    """What extinguishes the fixture's output. Defaults claim no darkness guarantee."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimmer_zero_extinguishes: bool = False
    extinguishing_shutter_states: tuple[str, ...] = ()
    close_latency_ms: int | None = Field(
        default=None, ge=0, description="Extinction latency; unknown stays null, never zero"
    )
    open_latency_ms: int | None = Field(
        default=None, ge=0, description="Reveal latency; unknown stays null, never zero"
    )


class FixtureCapabilities(BaseModel):
    """A fixture's explicit physical profile for the physical renderer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    profile_id: str = Field(min_length=1)
    provenance: Literal["synthetic", "manufacturer", "measured"]
    footprint: int = Field(
        ge=1, le=MAX_DMX_EFFECT_CHANNELS, description="Model-relative channel count"
    )
    defaults: dict[int, Annotated[int, Field(ge=0, le=255)]] = Field(
        description="Byte for every offset 1..footprint, used where nothing is authored"
    )
    axes: dict[AxisName, AxisCapability] = Field(default_factory=dict)
    discrete: dict[DiscreteName, DiscreteCapability] = Field(default_factory=dict)
    visibility: VisibilityCapability

    @model_validator(mode="after")
    def _validate_profile(self) -> FixtureCapabilities:
        owners: dict[int, str] = {}
        offsets = [
            (f"{name}.coarse_offset", axis.coarse_offset) for name, axis in self.axes.items()
        ]
        offsets += [
            (f"{name}.fine_offset", axis.fine_offset)
            for name, axis in self.axes.items()
            if axis.fine_offset is not None
        ]
        offsets += [(f"{name}.offset", wheel.offset) for name, wheel in self.discrete.items()]
        for owner, offset in offsets:
            if offset in owners:
                raise ValueError(f"offset {offset} is owned by both {owners[offset]} and {owner}")
            if offset > self.footprint:
                raise ValueError(f"{owner} offset {offset} exceeds footprint {self.footprint}")
            owners[offset] = owner

        expected = set(range(1, self.footprint + 1))
        if missing := sorted(expected - self.defaults.keys()):
            raise ValueError(f"missing defaults for offsets {missing}")
        if extra := sorted(self.defaults.keys() - expected):
            raise ValueError(f"defaults for offsets {extra} lie outside footprint {self.footprint}")

        for name, axis in self.axes.items():
            if axis.unit != _AXIS_UNITS[name]:
                raise ValueError(f"{name} axis unit must be {_AXIS_UNITS[name]!r}")

        self._validate_visibility()

        # The default byte state must be one the profile itself could command.
        for wheel_name, wheel in self.discrete.items():
            selected = wheel.states[wheel.default_state].value
            if self.defaults[wheel.offset] != selected:
                raise ValueError(
                    f"{wheel_name} offset {wheel.offset} default byte {self.defaults[wheel.offset]} "
                    f"is not its default state: {wheel.default_state!r} selects {selected}"
                )
        for name, axis in self.axes.items():
            axis.check_default_word(name, self.defaults)
        return self

    def _validate_visibility(self) -> None:
        """Reject darkness the declared channels cannot produce."""
        visibility = self.visibility
        shutter = self.discrete.get("shutter")
        shutter_states = set(shutter.states) if shutter is not None else set()
        if unknown := sorted(set(visibility.extinguishing_shutter_states) - shutter_states):
            raise ValueError(
                f"extinguishing shutter states {unknown} are not declared shutter states"
            )
        if shutter is not None and shutter.open_state in visibility.extinguishing_shutter_states:
            raise ValueError(
                f"open_state {shutter.open_state!r} cannot be an extinguishing shutter state"
            )
        if not visibility.dimmer_zero_extinguishes:
            return
        # Dimmer zero must be commandable and be the calibrated dark endpoint: it then
        # encodes to word 0, or to the full word when the axis is inverted.
        dimmer = self.axes.get("dimmer")
        if dimmer is None:
            raise ValueError("dimmer_zero_extinguishes needs a dimmer axis")
        if dimmer.physical_min != 0:
            raise ValueError(
                "dimmer_zero_extinguishes needs the dimmer calibrated from physical_min 0"
            )
        if not dimmer.admits(0.0):
            raise ValueError(
                "dimmer_zero_extinguishes needs the dimmer's allowed window to admit 0"
            )

    def check_initial_state(self, state: InitialFixtureState | None) -> tuple[str, ...]:
        """Return every reason `state` cannot serve as this fixture's known time-zero state.

        `None` (no run-supplied state) is unknown, whatever this profile's defaults say.
        """
        if state is None:
            return ("initial state is unknown: the run supplies no initial state for this fixture",)
        problems: list[str] = []
        pose: tuple[tuple[AxisName, float], ...] = (
            ("pan", state.pan_deg),
            ("tilt", state.tilt_deg),
        )
        for axis_name, value in pose:
            axis = self.axes.get(axis_name)
            if axis is not None and not axis.admits(value):
                problems.append(f"initial {axis_name} {value} is outside the operable range")
        if "dimmer" in self.axes and state.dimmer is None:
            problems.append("no initial dimmer level")
        for wheel_name, wheel in self.discrete.items():
            selected = state.discrete_states.get(wheel_name)
            if selected is None:
                problems.append(f"no initial {wheel_name} state")
            elif selected not in wheel.states:
                problems.append(
                    f"initial {wheel_name} state {selected!r} is not declared by the profile"
                )
        for extra in sorted(state.discrete_states.keys() - self.discrete.keys()):
            problems.append(f"initial {extra} state names a channel the profile does not declare")
        # Contradictory evidence is not darkness: dark=True needs a declared extinction.
        visibility = self.visibility
        if state.dark and not (
            (visibility.dimmer_zero_extinguishes and state.dimmer == 0)
            or state.discrete_states.get("shutter") in visibility.extinguishing_shutter_states
        ):
            problems.append(
                "initial state claims dark=True, but neither its dimmer nor its shutter "
                "extinguishes the fixture under the profile's visibility declaration"
            )
        return tuple(problems)


class InitialFixtureState(BaseModel):
    """Run-supplied state of one fixture at time zero, with explicit evidence flags."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pan_deg: float = Field(allow_inf_nan=False, description="Unwrapped fixture-local pan")
    tilt_deg: float = Field(allow_inf_nan=False, description="Unwrapped fixture-local tilt")
    dimmer: float | None = Field(default=None, ge=0, le=1, description="Normalized level")
    discrete_states: dict[DiscreteName, str] = Field(
        default_factory=dict, description="Semantic state of each discrete channel"
    )
    settled: bool = Field(description="Run evidence that pose and wheels have settled")
    dark: bool = Field(description="Run evidence that the fixture emits no light")
