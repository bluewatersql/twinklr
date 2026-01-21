from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ----------------------------
# Common enums (single source of truth)
# ----------------------------
# User-provided location: models/base.py
from blinkb0t.core.domains.sequencer.moving_heads.models.base import (
    BlendMode,
    BoundaryTransition,
    Category,
    Distribution,
    OrderMode,
    PhaseOffsetMode,
    PhaseUnit,
    QuantizePoint,
    RemainderPolicy,
    RepeatMode,
    TimingMode,
    TransitionMode,
)

# ----------------------------
# single source of truth
# ----------------------------
from blinkb0t.core.domains.sequencer.moving_heads.models.dimmer import Dimmer
from blinkb0t.core.domains.sequencer.moving_heads.models.geometry import (
    Geometry,
    RolePoseGeometry,
)
from blinkb0t.core.domains.sequencer.moving_heads.models.movement import Movement

# ----------------------------
# Timing / phase offsets
# ----------------------------


class BaseTiming(BaseModel):
    """Musical timing for a step (within the template cycle)."""

    model_config = ConfigDict(extra="forbid")

    mode: TimingMode = TimingMode.MUSICAL
    start_offset_bars: float = Field(0.0, ge=0.0)
    duration_bars: float = Field(..., gt=0.0)
    quantize_start: QuantizePoint = QuantizePoint.DOWNBEAT
    quantize_end: QuantizePoint = QuantizePoint.DOWNBEAT


class PhaseOffset(BaseModel):
    """Group+order phase spreading (replaces per_fixture_offsets arrays)."""

    model_config = ConfigDict(extra="forbid")

    unit: PhaseUnit = PhaseUnit.BARS
    mode: PhaseOffsetMode = PhaseOffsetMode.GROUP_ORDER

    group: str = Field(..., min_length=1, description="Group name, e.g. 'ALL'")
    order: OrderMode = OrderMode.LEFT_TO_RIGHT
    spread_bars: float = Field(
        ..., gt=0.0, description="Total phase spread across fixtures in bars."
    )
    distribution: Distribution = Distribution.LINEAR
    wrap: bool = True

    @model_validator(mode="after")
    def _validate(self) -> PhaseOffset:
        if self.mode == PhaseOffsetMode.NONE:
            return self
        if not self.group:
            raise ValueError("phase_offset.group is required when mode != NONE")
        return self


class StepTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_timing: BaseTiming

    # Replaces per_fixture_offsets arrays
    phase_offset: PhaseOffset | None = None

    # Optional internal step looping (secondary; prefer template.repeat)
    internal_loop_enabled: bool = False
    internal_loop_mode: Literal["REPEAT_TO_FILL"] | None = None


# ----------------------------
# Transitions
# ----------------------------


class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TransitionMode = TransitionMode.CROSSFADE
    duration_bars: float = Field(0.0, ge=0.0)
    curve: str = Field("sine", min_length=1)


# ----------------------------
# Repeat contract
# ----------------------------


class Repeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repeatable: bool = True
    mode: RepeatMode = RepeatMode.PING_PONG

    # The canonical cycle definition for repeat-to-fill.
    cycle_bars: float = Field(..., gt=0.0)

    # Which steps are considered the "loop body".
    loop_step_ids: list[str] = Field(default_factory=list)

    # How to treat the boundary between iterations.
    boundary_transition: BoundaryTransition = BoundaryTransition.CONTINUOUS

    # If the window ends mid-cycle, what to do.
    remainder_policy: RemainderPolicy = RemainderPolicy.HOLD_LAST_POSE

    # Optional joiner step (for JOINER mode)
    joiner_step_id: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> Repeat:
        if self.repeatable and not self.loop_step_ids:
            raise ValueError("repeat.loop_step_ids must be non-empty when repeatable == true")
        if self.mode == RepeatMode.JOINER and not self.joiner_step_id:
            raise ValueError("repeat.joiner_step_id is required when mode == JOINER")
        return self


# ----------------------------
# Steps + Template
# ----------------------------


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1, description="Group name (e.g. ALL).")

    timing: StepTiming

    movement: Movement
    geometry: Geometry
    dimmer: Dimmer

    entry_transition: Transition | None = None
    exit_transition: Transition | None = None

    dimmer_floor_dmx: int | None = Field(default=None, ge=0, le=255)
    dimmer_ceiling_dmx: int | None = Field(default=None, ge=0, le=255)

    priority: int = 0
    blend_mode: BlendMode = BlendMode.OVERRIDE


class TemplateDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Template-level safety defaults. Compiler/exporter should apply these.
    dimmer_floor_dmx: int = Field(default=46, ge=0, le=255)
    dimmer_ceiling_dmx: int = Field(default=255, ge=0, le=255)


class TemplateMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    recommended_sections: list[str] = Field(default_factory=list)
    energy_range: list[int] = Field(default_factory=lambda: [0, 100])
    tags: list[str] = Field(default_factory=list)
    best_with: dict[str, Any] = Field(default_factory=dict)


class Template(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., min_length=1)
    version: int = Field(default=1, ge=1)

    name: str = Field(..., min_length=1)
    category: Category

    # Roles & groups enable role_pose validation and phase ordering.
    # These are *role names*, not fixture ids.
    roles: list[str] = Field(default_factory=list)
    groups: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Group name -> list of role names (not fixture ids).",
    )

    # Template timing meta (kept flexible for now)
    timing: dict[str, Any] = Field(
        default_factory=lambda: {"mode": "musical", "default_cycle_bars": 4.0}
    )

    repeat: Repeat
    defaults: TemplateDefaults = Field(default_factory=TemplateDefaults)

    steps: list[Step] = Field(..., min_length=1)
    metadata: TemplateMetadata = Field(default_factory=TemplateMetadata)

    @model_validator(mode="after")
    def _validate_template(self) -> Template:
        # Unique step_ids
        step_ids = [s.step_id for s in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("All step_id values must be unique")

        known = set(step_ids)
        for sid in self.repeat.loop_step_ids:
            if sid not in known:
                raise ValueError(f"repeat.loop_step_ids references unknown step_id: {sid}")
        if self.repeat.joiner_step_id and self.repeat.joiner_step_id not in known:
            raise ValueError(
                f"repeat.joiner_step_id references unknown step_id: {self.repeat.joiner_step_id}"
            )

        # Phase offset groups must exist
        for st in self.steps:
            po = st.timing.phase_offset
            if po and po.mode != PhaseOffsetMode.NONE:
                if po.group not in self.groups:
                    raise ValueError(
                        f"step '{st.step_id}' uses phase_offset.group '{po.group}' "
                        "but it is not defined in template.groups"
                    )

        role_set = set(self.roles)
        for st in self.steps:
            if isinstance(st.geometry, RolePoseGeometry):
                if not self.roles:
                    raise ValueError("Template.roles must be defined when using ROLE_POSE geometry")

                for role_name in st.geometry.pan_pose_by_role.keys():
                    if role_name not in role_set:
                        raise ValueError(
                            f"geometry.pan_pose_by_role contains unknown role '{role_name}'"
                        )

        return self
