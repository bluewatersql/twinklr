from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencer.moving_heads.models.ir import ChannelSegment

from blinkb0t.core.domains.sequencer.moving_heads.models.ir import PointsCurveSpec
from blinkb0t.core.domains.sequencer.moving_heads.models.presets import TemplatePreset
from blinkb0t.core.domains.sequencer.moving_heads.models.rig import RigProfile
from blinkb0t.core.domains.sequencer.moving_heads.models.templates import (
    StepSpec,
    TemplateSpec,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.dimmers import DimmerID


def fmt_points(points: list[tuple[float, float]], precision: int = 3) -> str:
    inner = ",".join([f"[{t:.{precision}f},{v:.{precision}f}]" for t, v in points])
    return f"[{inner}]"


def curve_points_normalized(curve: PointsCurveSpec) -> list[tuple[float, float]]:
    return [(float(p.t), float(p.v)) for p in curve.points]


def print_segment(seg: ChannelSegment) -> None:
    kind = "STATIC" if seg.static_dmx is not None else "CURVE "
    print(
        f"- {seg.fixture_id:<4} {seg.channel.value:<7} t=[{seg.t0_ms},{seg.t1_ms}] "
        f"{kind} clamp=[{seg.clamp_min},{seg.clamp_max}] blend={seg.blend_mode.value}"
    )
    if seg.static_dmx is not None:
        # For xLights, you'll typically normalize static values too.
        # (Your exporter will do the final mapping based on channel.)
        v_norm = float(seg.static_dmx) / 255.0
        print(f"  static_norm: {v_norm:.3f} (dmx={seg.static_dmx})")
        return

    assert seg.curve is not None
    if isinstance(seg.curve, PointsCurveSpec):
        pts = curve_points_normalized(seg.curve)
        print(f"  points_norm: {fmt_points(pts)}")
    else:
        print(f"  curve: {type(seg.curve).__name__}")

    # Helpful for movement curves
    if seg.offset_centered:
        print(f"  offset_centered: True  base_dmx={seg.base_dmx}  amp_dmx={seg.amplitude_dmx}")


def build_demo_rig() -> RigProfile:
    """4-head rooftop setup: mh1..mh4 with role_bindings, groups, orders, and calibration."""
    return RigProfile.model_validate(
        {
            "rig_id": "demo_rooftop_4",
            "fixtures": ["mh1", "mh2", "mh3", "mh4"],
            "role_bindings": {
                "mh1": "OUTER_LEFT",
                "mh2": "INNER_LEFT",
                "mh3": "INNER_RIGHT",
                "mh4": "OUTER_RIGHT",
            },
            "groups": {
                "ALL": ["mh1", "mh2", "mh3", "mh4"],
                "LEFT": ["mh1", "mh2"],
                "RIGHT": ["mh3", "mh4"],
                "INNER": ["mh2", "mh3"],
                "OUTER": ["mh1", "mh4"],
                "ODD": ["mh1", "mh3"],
                "EVEN": ["mh2", "mh4"],
            },
            "orders": {
                "LEFT_TO_RIGHT": ["mh1", "mh2", "mh3", "mh4"],
                "RIGHT_TO_LEFT": ["mh4", "mh3", "mh2", "mh1"],
                "OUTSIDE_IN": ["mh1", "mh4", "mh2", "mh3"],
                "INSIDE_OUT": ["mh2", "mh3", "mh1", "mh4"],
                "ODD_EVEN": ["mh1", "mh3", "mh2", "mh4"],
            },
            "calibration": {"dimmer_floor_dmx": 60},
        }
    )


def apply_template_preset(
    template: TemplateSpec,
    preset: TemplatePreset,
    *,
    clamp_floor_to_template: bool = False,
) -> TemplateSpec:
    defaults = template.defaults
    if preset.defaults:
        floor = preset.defaults.dimmer_floor_dmx
        ceiling = preset.defaults.dimmer_ceiling_dmx
        if clamp_floor_to_template and floor is not None:
            floor = max(int(defaults.dimmer_floor_dmx), int(floor))
        defaults = defaults.model_copy(
            update={
                "dimmer_floor_dmx": int(floor)
                if floor is not None
                else defaults.dimmer_floor_dmx,
                "dimmer_ceiling_dmx": int(ceiling)
                if ceiling is not None
                else defaults.dimmer_ceiling_dmx,
            }
        )

    steps_by_id: dict[str, StepSpec] = {s.step_id: s for s in template.steps}
    for step_id, patch in preset.step_patches.items():
        if step_id not in steps_by_id:
            continue
        step = steps_by_id[step_id]
        updated = step

        if patch.movement and step.movement is not None:
            movement = step.movement
            if patch.movement.intensity is not None:
                movement = movement.model_copy(update={"intensity": patch.movement.intensity})
            if patch.movement.cycles is not None:
                movement = movement.model_copy(update={"cycles": patch.movement.cycles})
            updated = updated.model_copy(update={"movement": movement})

        if patch.dimmer and step.dimmer is not None:
            dimmer = step.dimmer
            if patch.dimmer.intensity is not None:
                dimmer = dimmer.model_copy(update={"intensity": patch.dimmer.intensity})
            if patch.dimmer.min_norm is not None:
                dimmer = dimmer.model_copy(update={"min_norm": patch.dimmer.min_norm})
            if patch.dimmer.max_norm is not None:
                dimmer = dimmer.model_copy(update={"max_norm": patch.dimmer.max_norm})
            if patch.dimmer.cycles is not None:
                dimmer = dimmer.model_copy(update={"cycles": patch.dimmer.cycles})
            if patch.dimmer.dimmer_params:
                override_id = patch.dimmer.dimmer_params.get("dimmer_id")
                if override_id is not None:
                    if isinstance(override_id, DimmerID):
                        dimmer_id = override_id
                    else:
                        dimmer_id = DimmerID(str(override_id))
                    dimmer = dimmer.model_copy(update={"dimmer_id": dimmer_id})
            updated = updated.model_copy(update={"dimmer": dimmer})

        steps_by_id[step_id] = updated

    return template.model_copy(update={"defaults": defaults, "steps": list(steps_by_id.values())})
