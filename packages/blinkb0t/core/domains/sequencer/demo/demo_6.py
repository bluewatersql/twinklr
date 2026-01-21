from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencer.moving_heads.models.ir import ChannelSegment

from blinkb0t.core.domains.sequencer.demo.helper import build_demo_rig, print_segment
from blinkb0t.core.domains.sequencer.moving_heads.curves.curve_ops import CurveOps
from blinkb0t.core.domains.sequencer.moving_heads.dimmer.generator import DimmerGenerator
from blinkb0t.core.domains.sequencer.moving_heads.geometry.dispatch import (
    GeometryDispatchResolver,
)
from blinkb0t.core.domains.sequencer.moving_heads.geometry.geometry_id import (
    GeometryIdResolver,
)
from blinkb0t.core.domains.sequencer.moving_heads.geometry.role_pose import (
    RolePoseGeometryResolver,
)
from blinkb0t.core.domains.sequencer.moving_heads.movement.generator import MovementGenerator
from blinkb0t.core.domains.sequencer.moving_heads.templates.compiler import TemplateCompiler
from blinkb0t.core.domains.sequencer.moving_heads.templates.types import (
    sweep_lr_chevron_breathe,
    sweep_lr_fan_hold,
    sweep_lr_fan_pulse,
)


def _build_compiler():
    pan_pose_table = {
        "WIDE_LEFT": 64,
        "MID_LEFT": 96,
        "CENTER": 128,
        "MID_RIGHT": 160,
        "WIDE_RIGHT": 192,
    }
    tilt_pose_table = {"HORIZON": 128}

    curve_ops = CurveOps()
    role_pose = RolePoseGeometryResolver(
        pan_pose_table=pan_pose_table, tilt_pose_table=tilt_pose_table
    )
    geometry = GeometryDispatchResolver(
        role_pose_resolver=role_pose,
        geometry_id_resolver=GeometryIdResolver(default_tilt_dmx=128, role_pose_resolver=role_pose),
    )
    movement = MovementGenerator(curve_ops=curve_ops, default_samples=16)
    dimmer = DimmerGenerator(curve_ops=curve_ops, default_samples=16)

    return TemplateCompiler(
        geometry_resolver=geometry,
        movement_generator=movement,
        dimmer_generator=dimmer,
        curve_ops=curve_ops,
    )


def _print_segments(label: str, segments: list[ChannelSegment]) -> None:
    print(f"\n=== {label} SEGMENTS (normalized) ===\n")
    for seg in segments:
        print_segment(seg)

    print("\n=== SUMMARY (fixture -> channels) ===\n")
    by_fx: dict[str, list[ChannelSegment]] = {}
    for s in segments:
        by_fx.setdefault(s.fixture_id, []).append(s)

    for fx in sorted(by_fx.keys()):
        chans = ", ".join([seg.channel.value for seg in by_fx[fx]])
        print(f"{fx}: {chans}")


def main() -> None:
    rig = build_demo_rig()
    compiler = _build_compiler()
    plan = SimpleNamespace(bpm=120, beats_per_bar=4)

    template = sweep_lr_fan_hold.TEMPLATE
    segments = compiler.compile(rig=rig, plan=plan, template_doc=template)
    print("\n=== DEMO 06A: Fan Sweep + Hold ===\n")
    print("Template:", template.template_id)
    _print_segments("06A", segments)

    template = sweep_lr_fan_pulse.TEMPLATE
    segments = compiler.compile(rig=rig, plan=plan, template_doc=template)
    print("\n=== DEMO 06B: Fan Sweep + Pulse ===\n")
    print("Template:", template.template_id)
    _print_segments("06B", segments)

    template = sweep_lr_chevron_breathe.TEMPLATE
    segments = compiler.compile(rig=rig, plan=plan, template_doc=template)
    print("\n=== DEMO 06C: Chevron Sweep + Breathe ===\n")
    print("Template:", template.template_id)
    _print_segments("06C", segments)


if __name__ == "__main__":
    main()
