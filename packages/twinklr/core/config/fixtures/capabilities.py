"""Explicit fixture capabilities and run initial state for the physical renderer.

A `FixtureCapabilities` profile says which model-relative DMX channels a fixture has,
how calibrated physical values map to DMX words, which bytes select its discrete
states, and what extinguishes its output. Nothing is inferred from the legacy fixture
fields, and nothing unknown (speed, latency, settle time) becomes a number.

A profile that leaves out a value with a safe rule (an axis' unit, the dimmer's range,
a default byte, a state's range, the shutter's open and closed states, the darkness
declaration) has it filled when it loads, so it is the explicit profile it stands for
and dumps as that; `FixtureCapabilities.defaulted` names what was filled, for the
render trace. An inference that could be ambiguous is refused instead.

`InitialFixtureState` is a run input: where a fixture is at time zero. A reusable
profile never claims a current pose; a fixture the run states none for is unknown.
`FixtureCapabilities.default_initial_state` only proposes an entry for the refusal.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from fractions import Fraction
from itertools import pairwise
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, model_validator

if TYPE_CHECKING:
    from pydantic import ModelWrapValidatorHandler

MAX_DMX_EFFECT_CHANNELS = 48
"""Model-relative channels the xLights DMX effect addresses (`DMXEffect.h`)."""

AxisName = Literal["pan", "tilt", "dimmer", "zoom"]
DiscreteName = Literal["shutter", "color", "gobo"]

_AXIS_UNITS: dict[str, str] = {
    "pan": "degree",
    "tilt": "degree",
    "dimmer": "normalized",
    "zoom": "degree",
}
"""Each axis' unit; `zoom` is the beam angle."""

_ZERO_DEFAULT_AXES = frozenset({"pan", "tilt", "dimmer"})
"""Axes whose unlisted default bytes encode the value 0: home for pan and tilt, dark for
the dimmer. Any other unlisted byte is 0."""

PROFILE_GUIDE = "docs/user-guide.md#minimal-physical-profile"
"""Where a refusal points a rig author for a minimal profile and what it must state."""


class AxisCapability(BaseModel):
    """A continuous attribute and its calibrated physical-value-to-DMX-word mapping.

    `physical_min`/`physical_max` are the calibrated endpoints, in fixture-local
    unwrapped units, mapped to DMX words `dmx_min` and `dmx_max` (by default 0 and the
    full word). `allowed_min`/`allowed_max` restrict operation inside that mapping
    without rescaling it.
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
    # Left out of dumps at their defaults, so existing profiles dump as before.
    dmx_min: int = Field(
        default=0,
        ge=0,
        exclude_if=lambda value: value == 0,
        description="Word the calibrated minimum maps to; default 0",
    )
    dmx_max: int | None = Field(
        default=None,
        ge=1,
        exclude_if=lambda value: value is None,
        description="Word the calibrated maximum maps to; default the full word",
    )
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
        if self.dmx_max is not None and self.dmx_max > self.full_word:
            raise ValueError(
                f"dmx_max {self.dmx_max} must not exceed the full word {self.full_word}"
            )
        word_min, word_max = self.word_range
        if word_min >= word_max:
            raise ValueError(f"dmx_min {word_min} must be below dmx_max {word_max}")
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

    @property
    def word_range(self) -> tuple[int, int]:
        """The words the calibrated range maps over: `(dmx_min, dmx_max)`, by default
        `(0, full_word)`."""
        return self.dmx_min, self.full_word if self.dmx_max is None else self.dmx_max

    def admits(self, value: float | Fraction) -> bool:
        low, high = self.operable_range
        return low <= value <= high

    def dmx_word(self, value: float | Fraction) -> int:
        """Encode an admitted physical value as an integer DMX word.

        Maps over the full calibrated range, never the allowed window, to the word range
        (`dmx_min` + the normalized value times `dmx_max - dmx_min`; by default 0..255
        or, with a fine channel, 0..65535); rounds half up in exact arithmetic, then
        applies inversion once, reflecting the word about `dmx_min + dmx_max`. A
        `Fraction` is mapped exactly, with no float rounding first.

        Raises:
            ValueError: If the value is outside the operable range.
        """
        if not self.admits(value):
            raise ValueError(f"{value} is outside the operable range {self.operable_range}")
        word = self._uninverted_word(Fraction(value))
        return self._invert(word)

    def word_center(self, word: int) -> float:
        """A value that encodes to `word` with margin: the word's center, kept in the
        allowed window, so no float rounding lands on a DMX rounding tie.

        Raises:
            ValueError: If no admitted value encodes to `word` exactly.
        """
        low, high = (Fraction(bound) for bound in self.operable_range)
        value = float(min(max(self._word_value(self._invert(word)), low), high))
        if not self.admits(value) or self.dmx_word(value) != word:
            raise ValueError(f"word {word} cannot be commanded exactly")
        return value

    def default_word(self, defaults: Mapping[int, int]) -> int:
        """The word the default bytes encode: coarse, or coarse << 8 | fine."""
        word = defaults[self.coarse_offset]
        if self.fine_offset is not None:
            word = word << 8 | defaults[self.fine_offset]
        return word

    def _invert(self, word: int) -> int:
        """Inversion, its own inverse: the word reflected about `dmx_min + dmx_max`."""
        word_min, word_max = self.word_range
        return word_min + word_max - word if self.inverted else word

    def _uninverted_word(self, value: Fraction) -> int:
        # `(value - low) * (word_max - word_min) / (high - low)` rounded half up, in
        # integers: `(2n + d) // 2d` is `floor(n / d + 1/2)` for any nonzero `d`, so the
        # quotient `n / d` needs no reducing.
        low_n, low_d = self.physical_min.as_integer_ratio()
        high_n, high_d = self.physical_max.as_integer_ratio()
        word_min, word_max = self.word_range
        n = (value.numerator * low_d - low_n * value.denominator) * (word_max - word_min) * high_d
        d = value.denominator * (high_n * low_d - low_n * high_d)
        return word_min + (2 * n + d) // (2 * d)

    def _word_value(self, uninverted: int) -> Fraction:
        """The exact calibrated value an uninverted word encodes, at its center."""
        word_min, word_max = self.word_range
        span = Fraction(self.physical_max) - Fraction(self.physical_min)
        return Fraction(self.physical_min) + span * (uninverted - word_min) / (word_max - word_min)

    def check_default_word(self, name: str, defaults: Mapping[int, int]) -> None:
        """Reject default bytes whose word no admitted value encodes to.

        Inversion is undone first; with a fine channel the word is coarse << 8 | fine.

        Raises:
            ValueError: Naming the axis, its offsets, the word and its decoded value.
        """
        offsets = [self.coarse_offset]
        if self.fine_offset is not None:
            offsets.append(self.fine_offset)
        word = self.default_word(defaults)
        uninverted = self._invert(word)
        low, high = self.operable_range
        if (
            not self._uninverted_word(Fraction(low))
            <= uninverted
            <= self._uninverted_word(Fraction(high))
        ):
            decoded = float(self._word_value(uninverted))
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
    # The states carry it once loaded, so it is left out of dumps: a profile dumps as
    # the one that writes it on every state.
    settle_ms: int | None = Field(
        default=None,
        ge=0,
        exclude=True,
        description="Settle time every state that states none of its own inherits",
    )

    @model_validator(mode="before")
    @classmethod
    def _inherit_settle(cls, data: Any) -> Any:
        """Give each state without its own `settle_ms` the channel's."""
        if not isinstance(data, Mapping) or data.get("settle_ms") is None:
            return data
        states = data.get("states")
        if not isinstance(states, Mapping):
            return data
        settle = data["settle_ms"]
        inherited: dict[Any, Any] = {}
        for name, state in states.items():
            if isinstance(state, Mapping) and "settle_ms" not in state:
                state = {**state, "settle_ms": settle}
            elif isinstance(state, DiscreteState) and "settle_ms" not in state.model_fields_set:
                state = state.model_copy(update={"settle_ms": settle})
            inherited[name] = state
        return {**data, "states": inherited}

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
    """What extinguishes the fixture's output.

    The field defaults claim no darkness guarantee, and an instance built in Python is
    taken as written. A profile that leaves a key out, or the whole declaration, has it
    derived when it loads (`_fill_defaults`): darkness only from a dimmer calibrated
    from 0 and the shutter's closed state, never a latency.
    """

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
    """A fixture's explicit physical profile for the physical renderer.

    Values left out are filled when the profile loads (`_fill_defaults`), so the model
    always holds the explicit profile; `defaulted` names what was filled.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    profile_id: str = Field(min_length=1)
    provenance: Literal["synthetic", "manufacturer", "measured"]
    footprint: int = Field(
        ge=1, le=MAX_DMX_EFFECT_CHANNELS, description="Model-relative channel count"
    )
    defaults: dict[int, Annotated[int, Field(ge=0, le=255)]] = Field(
        description=(
            "Byte for every offset 1..footprint, used where nothing is authored; an "
            "unlisted offset is filled when the profile loads"
        )
    )
    axes: dict[AxisName, AxisCapability] = Field(default_factory=dict)
    discrete: dict[DiscreteName, DiscreteCapability] = Field(default_factory=dict)
    visibility: VisibilityCapability = Field(
        description="What extinguishes output; an absent declaration is derived on load"
    )
    # Not a field: the profile dumps exactly as the explicit one it stands for.
    _defaulted: tuple[str, ...] = PrivateAttr(default=())

    @model_validator(mode="wrap")
    @classmethod
    def _fill_left_out_values(
        cls, data: Any, handler: ModelWrapValidatorHandler[FixtureCapabilities]
    ) -> FixtureCapabilities:
        """Fill what a written profile leaves out, then validate the explicit profile."""
        if not isinstance(data, Mapping):
            return handler(data)
        filled, defaulted = _fill_defaults(data)
        profile = handler(filled)
        profile._defaulted = tuple(defaulted)
        return profile

    @property
    def defaulted(self) -> tuple[str, ...]:
        """Paths of the values this profile left out and its loading filled, in order."""
        return self._defaulted

    def default_initial_state(self) -> InitialFixtureState:
        """The entry a refusal proposes for a fixture the run states no initial state
        for: the fixture at rest at its default bytes, settled.

        Each axis is at the value its default word encodes (0 when that word is the one
        0 encodes, else the word's center, which validation guarantees is admitted),
        each discrete channel in its `default_state`, and it is dark exactly when that
        dimmer level or shutter state extinguishes it under the visibility declaration.
        Nothing establishes that a head rests there; only a run that states it does.
        """
        values: dict[str, float] = {}
        for name, axis in self.axes.items():
            word = axis.default_word(self.defaults)
            values[name] = (
                0.0 if axis.admits(0.0) and axis.dmx_word(0.0) == word else axis.word_center(word)
            )
        states = {name: wheel.default_state for name, wheel in self.discrete.items()}
        dimmer = values.get("dimmer")
        visibility = self.visibility
        dark = (visibility.dimmer_zero_extinguishes and dimmer == 0) or (
            states.get("shutter") in visibility.extinguishing_shutter_states
        )
        return InitialFixtureState(
            pan_deg=values.get("pan", 0.0),
            tilt_deg=values.get("tilt", 0.0),
            zoom_deg=values.get("zoom"),
            dimmer=dimmer,
            discrete_states=states,
            settled=True,
            dark=dark,
        )

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

        # Loading fills every offset of the footprint (`_fill_defaults`).
        expected = set(range(1, self.footprint + 1))
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
        for axis_name, value in state.pose.items():
            axis = self.axes.get(axis_name)
            if axis is None and axis_name == "zoom":
                problems.append("initial zoom names an axis the profile does not declare")
            elif axis is not None and not axis.admits(value):
                problems.append(f"initial {axis_name} {value} is outside the operable range")
        if "zoom" in self.axes and state.zoom_deg is None:
            problems.append("no initial zoom")
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
    # Left out of dumps when absent, so existing initial states dump as before.
    zoom_deg: float | None = Field(
        default=None,
        allow_inf_nan=False,
        exclude_if=lambda value: value is None,
        description="Beam angle; required exactly when the profile declares a zoom axis",
    )
    dimmer: float | None = Field(default=None, ge=0, le=1, description="Normalized level")
    discrete_states: dict[DiscreteName, str] = Field(
        default_factory=dict, description="Semantic state of each discrete channel"
    )
    settled: bool = Field(description="Run evidence that pose and wheels have settled")
    dark: bool = Field(description="Run evidence that the fixture emits no light")

    @property
    def pose(self) -> dict[AxisName, float]:
        """The pose axes' values: pan and tilt, and the zoom when given."""
        pose: dict[AxisName, float] = {"pan": self.pan_deg, "tilt": self.tilt_deg}
        if self.zoom_deg is not None:
            pose["zoom"] = self.zoom_deg
        return pose


def _offset_keys(given: Mapping[Any, Any]) -> dict[int, Any] | None:
    """`given` keyed by integer offset, or None when a key is not a whole offset (an
    int, or a string of digits as JSON writes it): field validation refuses that key,
    and nothing is truncated into an offset it does not name."""
    defaults: dict[int, Any] = {}
    for offset, byte in given.items():
        if isinstance(offset, str) and offset.strip().isdigit():
            offset = int(offset)
        if not isinstance(offset, int) or isinstance(offset, bool):
            return None
        defaults[offset] = byte
    return defaults


def _offsets_text(offsets: list[int]) -> str:
    return ("offsets " if len(offsets) > 1 else "offset ") + "/".join(map(str, offsets))


def _fill_defaults(data: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """A written profile with every value it leaves out filled, and those values' paths.

    Fills only what is absent (an explicit null is kept): an axis' `unit`; the dimmer's
    `physical_min` 0 and `physical_max` 1; a state's `range_min`/`range_max` as its
    `value`; the shutter's `closed_state`/`open_state` as the state named exactly
    `closed`/`open`; a discrete channel's `default_state` and default byte from each
    other, or the state selecting byte 0; pan, tilt and dimmer default bytes as the word
    encoding 0, inversion applied; every other default byte 0; and the visibility's
    `dimmer_zero_extinguishes` (a dimmer calibrated from 0 that admits 0) and
    `extinguishing_shutter_states` (the shutter's closed state). Timings are never
    filled. Input this cannot read is left for field validation to report.

    Raises:
        ValueError: Where filling a value would be a guess, saying what to state.
    """
    data = dict(data)
    defaulted: list[str] = []
    # Every unlisted default byte is filled from the footprint, so it is checked first.
    footprint = data.get("footprint")
    if not isinstance(footprint, int) or isinstance(footprint, bool):
        raise ValueError(
            f"footprint must be a whole number of channels, got {footprint!r}; the "
            "default bytes of the channels it spans are filled from it"
        )

    axes = data.get("axes")
    checked: dict[str, AxisCapability] = {}
    if isinstance(axes, Mapping):
        axes = dict(axes)
        for name, axis in axes.items():
            if isinstance(axis, Mapping) and name in _AXIS_UNITS:
                axis = dict(axis)
                filled: dict[str, str | float] = {"unit": _AXIS_UNITS[name]}
                if name == "dimmer":
                    filled |= {"physical_min": 0.0, "physical_max": 1.0}
                for key, value in filled.items():
                    if key not in axis:
                        axis[key] = value
                        defaulted.append(f"axes.{name}.{key}")
                axes[name] = axis
            # An axis that does not validate is reported by field validation.
            with suppress(ValidationError):
                checked[name] = AxisCapability.model_validate(axis)
        data["axes"] = axes

    discrete = data.get("discrete")
    wheels: dict[str, dict[str, Any]] = {}
    if isinstance(discrete, Mapping):
        discrete = dict(discrete)
        for name, wheel in discrete.items():
            if not isinstance(wheel, Mapping) or not isinstance(wheel.get("states"), Mapping):
                continue
            wheel = dict(wheel)
            states = dict(wheel["states"])
            for state_name, state in states.items():
                if isinstance(state, Mapping) and "value" in state:
                    state = dict(state)
                    for key in ("range_min", "range_max"):
                        if key not in state:
                            state[key] = state["value"]
                            defaulted.append(f"discrete.{name}.states.{state_name}.{key}")
                    states[state_name] = state
            wheel["states"] = states
            if name == "shutter":
                for key in ("closed_state", "open_state"):
                    state_name = key.removesuffix("_state")
                    if key not in wheel and state_name in states:
                        wheel[key] = state_name
                        defaulted.append(f"discrete.shutter.{key}")
            discrete[name] = wheels[name] = wheel
        data["discrete"] = discrete

    footprint = data["footprint"]
    given = data.get("defaults", {})
    if 1 <= footprint <= MAX_DMX_EFFECT_CHANNELS and isinstance(given, Mapping):
        defaults = _offset_keys(given)
        if defaults is not None:
            listed = len(defaults)
            defaulted += _fill_wheel_defaults(wheels, defaults)
            defaulted += _fill_axis_defaults(checked, defaults)
            for offset in range(1, footprint + 1):
                if offset not in defaults:
                    defaults[offset] = 0
                    defaulted.append(f"defaults.{offset}")
            # Filled bytes in offset order, so the profile dumps as the explicit one.
            data["defaults"] = (
                dict(sorted(defaults.items())) if len(defaults) > listed else defaults
            )

    visibility = data.get("visibility", {})
    if isinstance(visibility, Mapping):
        visibility = dict(visibility)
        if "dimmer_zero_extinguishes" not in visibility:
            dimmer = checked.get("dimmer")
            visibility["dimmer_zero_extinguishes"] = (
                dimmer is not None and dimmer.physical_min == 0 and dimmer.admits(0.0)
            )
            defaulted.append("visibility.dimmer_zero_extinguishes")
        if "extinguishing_shutter_states" not in visibility:
            closed = wheels.get("shutter", {}).get("closed_state")
            visibility["extinguishing_shutter_states"] = [] if closed is None else [closed]
            defaulted.append("visibility.extinguishing_shutter_states")
        data["visibility"] = visibility
    return data, defaulted


def _fill_wheel_defaults(
    wheels: Mapping[str, dict[str, Any]], defaults: dict[int, Any]
) -> list[str]:
    """Each discrete channel's default state and byte, filled from each other; with
    neither given, the state selecting byte 0."""
    defaulted: list[str] = []
    for name, wheel in wheels.items():
        offset = wheel.get("offset")
        # A malformed offset or state (a bare byte, say) is reported by field validation.
        if not isinstance(offset, int) or not all(
            isinstance(state, Mapping | DiscreteState) for state in wheel["states"].values()
        ):
            continue
        values = {
            state_name: state.get("value") if isinstance(state, Mapping) else state.value
            for state_name, state in wheel["states"].items()
        }
        if "default_state" in wheel:
            if offset not in defaults and wheel["default_state"] in values:
                defaults[offset] = values[wheel["default_state"]]
                defaulted.append(f"defaults.{offset}")
            continue
        listed = offset in defaults
        byte = defaults.get(offset, 0)
        selecting = [state_name for state_name, value in values.items() if value == byte]
        if not selecting:
            if listed:
                raise ValueError(
                    f"discrete.{name}: default byte {byte} at offset {offset} selects no "
                    "declared state; set default_state or list the byte of a state"
                )
            raise ValueError(
                f"discrete.{name}: default_state is not set and no state selects byte 0 "
                f"(the default for an unlisted offset {offset}); set default_state"
            )
        wheel["default_state"] = selecting[0]
        defaulted.append(f"discrete.{name}.default_state")
        if not listed:
            defaults[offset] = byte
            defaulted.append(f"defaults.{offset}")
    return defaulted


def _fill_axis_defaults(axes: Mapping[str, AxisCapability], defaults: dict[int, Any]) -> list[str]:
    """Default bytes of each axis none of whose offsets is listed: the word encoding 0
    for pan, tilt and dimmer, else 0, refused when the axis cannot command it."""
    defaulted: list[str] = []
    for name, axis in axes.items():
        offsets = [axis.coarse_offset]
        if axis.fine_offset is not None:
            offsets.append(axis.fine_offset)
        if any(offset in defaults for offset in offsets):
            continue
        many = len(offsets) > 1
        where = f"{_offsets_text(offsets)} {'are' if many else 'is'} not listed in `defaults`"
        them = "them" if many else "it"
        if name in _ZERO_DEFAULT_AXES:
            low, high = axis.operable_range
            if not axis.admits(0.0):
                raise ValueError(
                    f"axes.{name}: {where}, and 0 is outside its allowed window "
                    f"[{low:g}, {high:g}], so its default position cannot be derived; "
                    f"list {them} in `defaults`"
                )
            word = axis.dmx_word(0.0)
        else:
            word = 0
        filled = dict(zip(offsets, (word >> 8, word & 0xFF) if many else (word,), strict=True))
        try:
            axis.check_default_word(name, filled)
        except ValueError as error:
            raise ValueError(
                f"axes.{name}: {where}, so {them} defaulted to 0, which the axis cannot "
                f"command ({error}); list {them} in `defaults`"
            ) from None
        defaults.update(filled)
        defaulted += [f"defaults.{offset}" for offset in offsets]
    return defaulted
