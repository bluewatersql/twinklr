from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencer.moving_heads.models.ir import ChannelSegment

from blinkb0t.core.domains.sequencer.demo.helper import build_demo_rig, print_segment
from blinkb0t.core.domains.sequencer.moving_heads.curves.curve_ops import CurveOps
from blinkb0t.core.domains.sequencer.moving_heads.dimmer.generator import DimmerGenerator
from blinkb0t.core.domains.sequencer.moving_heads.geometry.role_pose import RolePoseGeometryResolver
from blinkb0t.core.domains.sequencer.moving_heads.movement.generator import MovementGenerator
from blinkb0t.core.domains.sequencer.moving_heads.templates.compiler import TemplateCompiler
from blinkb0t.core.domains.sequencer.moving_heads.templates.specs import fan_pulse


def main() -> None:
    rig = build_demo_rig()

    # Plan is not used in the current compiler stub timing (as per your earlier demo).
    # When you hook BPM/section duration, replace this with your real Plan model.
    plan = SimpleNamespace()

    template = fan_pulse.TEMPLATE

    # Pose tables (tune to your rig)
    pan_pose_table = {
        "WIDE_LEFT": 64,
        "MID_LEFT": 96,
        "CENTER": 128,
        "MID_RIGHT": 160,
        "WIDE_RIGHT": 192,
    }
    tilt_pose_table = {"HORIZON": 128, "UP": 180, "DOWN": 80}

    curve_ops = CurveOps()
    geometry = RolePoseGeometryResolver(
        pan_pose_table=pan_pose_table, tilt_pose_table=tilt_pose_table
    )
    movement = MovementGenerator(curve_ops=curve_ops, default_samples=32)
    dimmer = DimmerGenerator(curve_ops=curve_ops, default_samples=32)

    compiler = TemplateCompiler(
        geometry_resolver=geometry,
        movement_generator=movement,
        dimmer_generator=dimmer,
        curve_ops=curve_ops,
    )

    segments = compiler.compile(rig=rig, plan=plan, template_doc=template)

    print("\n=== TEMPLATE ===\n")
    print(
        f"{template.template_id}  steps={[s.step_id for s in template.steps]}  repeat={template.repeat.mode}"
    )

    print("\n=== SEGMENTS (normalized) ===\n")
    for seg in segments:
        print_segment(seg)

    print("\n=== SUMMARY (fixture -> channels) ===\n")
    by_fx: dict[str, list[ChannelSegment]] = {}
    for s in segments:
        by_fx.setdefault(s.fixture_id, []).append(s)

    for fx in sorted(by_fx.keys()):
        chans = ", ".join([seg.channel.value for seg in by_fx[fx]])
        print(f"{fx}: {chans}")


if __name__ == "__main__":
    main()
