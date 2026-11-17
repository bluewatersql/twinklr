"""Named rig components for the moving-head renderer: position and attribute presets.

A fixture group may declare named presets: per-fixture aims (`PositionPreset`) and
per-fixture shutter/color/gobo states and dimmer level (`AttributePreset`). A
template step refers to them by id, so the template carries no rig-specific angle or
profile state name. A preset that does not declare a fixture may name a fallback preset
of the same kind; nothing is ever filled in with a center or default value.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.config.fixtures.capabilities import DiscreteName, FixtureCapabilities

PresetId = Annotated[str, Field(pattern=r"\S")]
"""A preset id: not empty and not only whitespace."""

StateName = Annotated[str, Field(pattern=r"\S")]
"""A profile state name: not empty and not only whitespace."""


class PoseDegrees(BaseModel):
    """A fixture-local aim in unwrapped degrees; never taken modulo 360."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pan_deg: float = Field(allow_inf_nan=False)
    tilt_deg: float = Field(allow_inf_nan=False)


class FixtureAttributes(BaseModel):
    """One fixture's held states, named as its own physical profile names them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    shutter: StateName | None = None
    color: StateName | None = None
    gobo: StateName | None = None
    dimmer: float | None = Field(default=None, ge=0, le=1, description="Normalized level")

    @model_validator(mode="after")
    def _validate_any(self) -> FixtureAttributes:
        if (
            self.shutter is None
            and self.color is None
            and self.gobo is None
            and self.dimmer is None
        ):
            raise ValueError("an attribute entry sets no shutter, color, gobo or dimmer")
        return self


class PositionPreset(BaseModel):
    """Per-fixture aims; `fallback` names the position preset for fixtures not listed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixtures: dict[str, PoseDegrees] = Field(default_factory=dict)
    fallback: PresetId | None = None


class AttributePreset(BaseModel):
    """Per-fixture held states; `fallback` names the attribute preset for fixtures not listed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixtures: dict[str, FixtureAttributes] = Field(default_factory=dict)
    fallback: PresetId | None = None


class RigPresetLibrary(BaseModel):
    """A fixture group's named position and attribute presets. Rig data, not a global
    target database: ids are local to the group, and fixture ids are the group's."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    positions: dict[PresetId, PositionPreset] = Field(default_factory=dict)
    attributes: dict[PresetId, AttributePreset] = Field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.positions and not self.attributes

    @model_validator(mode="after")
    def _validate_fallbacks(self) -> RigPresetLibrary:
        """Every fallback names a declared preset of the same kind, and no chain cycles."""
        presets: Mapping[str, PositionPreset | AttributePreset]
        for kind, presets in (("position", self.positions), ("attribute", self.attributes)):
            for preset_id in presets:
                chain = [preset_id]
                fallback = presets[preset_id].fallback
                while fallback is not None:
                    if fallback not in presets:
                        raise ValueError(
                            f"{kind} preset {chain[-1]!r} falls back to {fallback!r}, "
                            "which is not declared"
                        )
                    if fallback in chain:
                        raise ValueError(
                            f"{kind} preset fallbacks form a cycle: {' -> '.join([*chain, fallback])}"
                        )
                    chain.append(fallback)
                    fallback = presets[fallback].fallback
        return self

    def check_rig(self, profiles: Mapping[str, FixtureCapabilities | None]) -> None:
        """Reject a preset naming a fixture outside the group, or an attribute its
        fixture's physical profile cannot select.

        Args:
            profiles: Each fixture of the group and its physical profile, if any.

        Raises:
            ValueError: Naming the preset, the fixture and the channel.
        """
        for kind, presets in (("position", self.positions), ("attribute", self.attributes)):
            for preset_id, preset in presets.items():
                for fixture_id in preset.fixtures:
                    if fixture_id not in profiles:
                        raise ValueError(
                            f"{kind} preset {preset_id!r} names fixture {fixture_id!r}, "
                            "which is not in the group"
                        )
        for preset_id, attribute_preset in self.attributes.items():
            for fixture_id, entry in attribute_preset.fixtures.items():
                where = f"attribute preset {preset_id!r}, fixture {fixture_id!r}"
                profile = profiles[fixture_id]
                if profile is None:
                    raise ValueError(f"{where}: the fixture has no physical_profile")
                states: tuple[tuple[DiscreteName, str | None], ...] = (
                    ("shutter", entry.shutter),
                    ("color", entry.color),
                    ("gobo", entry.gobo),
                )
                for channel, state in states:
                    if state is None:
                        continue
                    capability = profile.discrete.get(channel)
                    if capability is None:
                        raise ValueError(f"{where}: the profile declares no {channel} channel")
                    if state not in capability.states:
                        raise ValueError(
                            f"{where}: {channel} state {state!r} is not one of "
                            f"{sorted(capability.states)}"
                        )
                if entry.dimmer is not None:
                    dimmer = profile.axes.get("dimmer")
                    if dimmer is None:
                        raise ValueError(f"{where}: the profile declares no dimmer axis")
                    if not dimmer.admits(entry.dimmer):
                        raise ValueError(
                            f"{where}: dimmer {entry.dimmer} is outside the operable range "
                            f"{dimmer.operable_range}"
                        )
