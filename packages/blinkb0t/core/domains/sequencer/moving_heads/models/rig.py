"""Sequencing v2 core models (Step 1 – MVP).

This module defines the foundational Pydantic models for a clean,
compiler-based moving-head sequencing architecture.

Guiding principles implemented here:
- Fixtures, groups, and orders are *rig config* (not templates)
- Pydantic for all models
- Validation ensures config correctness early
- Models are data-only (no rendering); helpers are minimal and side-effect free

You can drop this into your repo and wire it up via DI.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from blinkb0t.core.domains.sequencer.moving_heads.models.base import (
    AimZone,
    OrderMode,
    SemanticGroup,
    TemplateRole,
)
from blinkb0t.core.domains.sequencing.models.poses import PoseID


class FixtureCalibration(BaseModel):
    """Per-fixture calibration limits."""

    model_config = ConfigDict(extra="forbid")

    pan_min: int = Field(..., ge=0, le=255)
    pan_max: int = Field(..., ge=0, le=255)
    pan_center: int = Field(..., ge=0, le=255)

    tilt_min: int = Field(..., ge=0, le=255)
    tilt_max: int = Field(..., ge=0, le=255)
    tilt_center: int = Field(..., ge=0, le=255)

    dimmer_floor_dmx: int = Field(default=0, ge=0, le=255)


class GlobalCalibration(BaseModel):
    """Rig-wide calibration defaults."""

    model_config = ConfigDict(extra="forbid")

    pan_amplitude_dmx: int = Field(90, ge=0, le=255)
    tilt_amplitude_dmx: int = Field(60, ge=0, le=255)
    dimmer_floor_dmx: int = Field(0, ge=0, le=255)


class RigCalibration(BaseModel):
    """Complete calibration settings."""

    model_config = ConfigDict(extra="forbid")

    global_: GlobalCalibration = Field(alias="global")
    fixtures: dict[str, FixtureCalibration] = Field(default_factory=dict)
    pose_tokens: dict[PoseID, float]  # token -> normalized [0,1]
    aim_zones: dict[AimZone, float]  # zone -> normalized [0,1]


class RigProfile(BaseModel):
    """Rig configuration (fixtures + semantics).

    - `fixtures` are the physical units.
    - `groups` define semantic targeting (ALL/LEFT/RIGHT/INNER/OUTER/...)
    - `orders` define chase orderings (LEFT_TO_RIGHT/OUTSIDE_IN/...)
    - `role_bindings` define optional roles per fixture (OUTER_LEFT/INNER_LEFT/...)

    This is intentionally separate from templates so templates remain portable.
    """

    model_config = ConfigDict(extra="forbid")

    rig_id: str = Field(..., min_length=1)

    # Fixtures are referenced by ID (e.g., "mh1", "mh2").
    # You can attach your existing FixtureInstance/FixtureConfig elsewhere.
    fixtures: list[str] = Field(..., min_length=1)

    # Optional role semantics (fixture_id -> role). Roles are strings on purpose
    # so you can evolve without a global enum.
    role_bindings: dict[str, TemplateRole] = Field(default_factory=dict)

    # groups: name -> list of fixture_ids
    groups: dict[SemanticGroup, list[str]] = Field(default_factory=dict)

    # orders: name -> list of fixture_ids (must be permutation/subset)
    orders: dict[OrderMode, list[str]] = Field(default_factory=dict)

    calibration: RigCalibration = Field(default_factory=RigCalibration)  # type: ignore

    @field_validator("fixtures")
    @classmethod
    def _fixtures_unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("RigProfile.fixtures must be unique")
        return v

    @model_validator(mode="after")
    def _validate_groups_orders(self) -> RigProfile:
        fixture_set = set(self.fixtures)

        # Validate groups reference known fixtures
        for gname, members in self.groups.items():
            unknown = [m for m in members if m not in fixture_set]
            if unknown:
                raise ValueError(f"Group '{gname}' references unknown fixtures: {unknown}")

        # Validate orders reference known fixtures and contain no duplicates
        for oname, members in self.orders.items():
            unknown = [m for m in members if m not in fixture_set]
            if unknown:
                raise ValueError(f"Order '{oname}' references unknown fixtures: {unknown}")
            if len(set(members)) != len(members):
                raise ValueError(f"Order '{oname}' contains duplicates: {members}")

        # Validate role bindings reference known fixtures
        for fx in self.role_bindings.keys():
            if fx not in fixture_set:
                raise ValueError(f"role_bindings references unknown fixture '{fx}'")

        # Convenience: default ALL group if omitted
        if SemanticGroup.ALL not in self.groups:
            self.groups[SemanticGroup.ALL] = list(self.fixtures)

        return self

    # Lightweight helpers (no side effects)
    def resolve_group(self, group: SemanticGroup) -> list[str]:
        """Return fixture ids for a semantic group."""
        if group not in self.groups:
            raise KeyError(f"Unknown group '{group}'")
        return list(self.groups[group])

    def resolve_order(self, order: OrderMode, fixtures: list[str] | None = None) -> list[str]:
        """Return fixture ids for an order.

        If `fixtures` is provided, returns the order filtered to that subset.
        """
        if order not in self.orders:
            raise KeyError(f"Unknown order '{order}'")
        ordered = list(self.orders[order])
        if fixtures is None:
            return ordered
        fixture_set = set(fixtures)
        return [fx for fx in ordered if fx in fixture_set]
