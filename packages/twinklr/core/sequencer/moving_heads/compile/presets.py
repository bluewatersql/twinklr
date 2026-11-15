"""Resolve a physical step's named rig components per fixture (P2.1).

A step's `component_refs` names a position preset and attribute presets the fixture
group declares (`RigPresetLibrary`). Resolution is per fixture, per axis and per
channel. The step is the one the template preset already patched, so a value set on it
(by the template or by a preset patch) wins for that axis or channel alone; the
references supply the rest. Nothing is ever centered or defaulted: an axis set by
neither, an unknown preset id, or a fixture a preset does not declare and whose
declared fallback chain never declares, fails. Two attribute presets setting one
channel of one fixture fail rather than one silently winning. Provenance names the
referenced preset, the preset its fallback chain resolved to and the SHA-256 of the
entry used, never a copy of the values.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from twinklr.core.config.fixtures.presets import (
    AttributePreset,
    FixtureAttributes,
    PoseDegrees,
    PositionPreset,
    RigPresetLibrary,
)
from twinklr.core.sequencer.models.context import ResolvedStepComponents
from twinklr.core.sequencer.models.template import TemplateStep

if TYPE_CHECKING:
    from pydantic import BaseModel


class ComponentRefError(ValueError):
    """A step's component reference that does not resolve on this rig."""

    def __init__(self, message: str, fixture_id: str) -> None:
        self.fixture_id = fixture_id
        super().__init__(message)


def resolve_component_refs(
    step: TemplateStep, fixture_ids: tuple[str, ...], presets: RigPresetLibrary
) -> dict[str, ResolvedStepComponents]:
    """Resolve the step's references for each fixture, with per-channel provenance.

    Args:
        step: A physical step with `component_refs`, after any template preset patch.
        fixture_ids: The fixtures the step targets.
        presets: The fixture group's presets.

    Returns:
        Each fixture's start pose and held channels, with their provenance.

    Raises:
        ComponentRefError: Naming the step, the preset and the fixture, for an unknown
            preset id, a fixture no preset in the fallback chain declares, an axis set by
            neither the step nor a position reference, or two attribute presets setting
            one channel.
    """
    refs = step.component_refs
    if refs is None:
        raise ValueError(f"step {step.step_id!r} names no component references")
    movement = step.movement.physical
    step_pose = {
        "pan": None if movement is None else movement.start_pan_deg,
        "tilt": None if movement is None else movement.start_tilt_deg,
    }
    step_channels: dict[str, Any] = {
        "shutter": step.physical_shutter_state or step.physical_shutter,
        "color": step.physical_color,
        "gobo": step.physical_gobo,
        "dimmer": step.dimmer.physical,
    }

    resolved: dict[str, ResolvedStepComponents] = {}
    for fixture_id in fixture_ids:
        provenance: dict[str, dict[str, str]] = {}
        position = (
            None
            if refs.position_id is None
            else _lookup("position", presets.positions, refs.position_id, fixture_id, step)
        )
        pose: dict[str, float] = {}
        for axis, value in step_pose.items():
            if value is not None:
                pose[axis], provenance[axis] = value, {"source": "step"}
            elif position is not None:
                pose[axis] = getattr(position[0], f"{axis}_deg")
                provenance[axis] = position[1]
            else:
                raise ComponentRefError(
                    f"step {step.step_id!r} sets no {axis} for fixture {fixture_id!r}: "
                    "neither movement.physical nor a position reference sets it",
                    fixture_id,
                )

        held: dict[str, Any] = {}
        for preset_id in refs.attribute_preset_ids:
            entry, entry_provenance = _lookup(
                "attribute", presets.attributes, preset_id, fixture_id, step
            )
            assert isinstance(entry, FixtureAttributes)
            for channel in step_channels:
                value = getattr(entry, channel)
                if value is None:
                    continue
                if channel in held:
                    raise ComponentRefError(
                        f"step {step.step_id!r}: attribute presets "
                        f"{provenance[channel]['preset_id']!r} and {preset_id!r} both set "
                        f"{channel} for fixture {fixture_id!r}; name one",
                        fixture_id,
                    )
                held[channel], provenance[channel] = value, entry_provenance
        for channel, value in step_channels.items():
            if value is not None:
                held.pop(channel, None)
                provenance[channel] = {"source": "step"}
                if isinstance(value, str):  # a static state; a pulse drives the channel
                    held[channel] = value

        resolved[fixture_id] = ResolvedStepComponents(
            pose=PoseDegrees(pan_deg=pose["pan"], tilt_deg=pose["tilt"]),
            provenance=provenance,
            **held,
        )
    return resolved


def _lookup(
    kind: str,
    presets: dict[str, PositionPreset] | dict[str, AttributePreset],
    preset_id: str,
    fixture_id: str,
    step: TemplateStep,
) -> tuple[Any, dict[str, str]]:
    """The fixture's entry in `preset_id` or, failing that, along its fallback chain."""
    if preset_id not in presets:
        raise ComponentRefError(
            f"step {step.step_id!r} references {kind} preset {preset_id!r} for fixture "
            f"{fixture_id!r}, which the fixture group does not declare (declared: "
            f"{sorted(presets)})",
            fixture_id,
        )
    current: str | None = preset_id
    chain: list[str] = []
    while current is not None:
        chain.append(current)
        preset = presets[current]
        entry: BaseModel | None = preset.fixtures.get(fixture_id)
        if entry is not None:
            return entry, {
                "source": kind,
                "preset_id": preset_id,
                "resolved_preset_id": current,
                "sha256": hashlib.sha256(entry.model_dump_json().encode()).hexdigest(),
            }
        current = preset.fallback
    raise ComponentRefError(
        f"step {step.step_id!r} references {kind} preset {preset_id!r}, which declares "
        f"nothing for fixture {fixture_id!r} along its fallback chain {' -> '.join(chain)} "
        "and is never centered",
        fixture_id,
    )
