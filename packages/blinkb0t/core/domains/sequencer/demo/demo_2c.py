from __future__ import annotations

from types import SimpleNamespace

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
from blinkb0t.core.domains.sequencer.moving_heads.models.ir import ChannelSegment
from blinkb0t.core.domains.sequencer.moving_heads.movement.generator import MovementGenerator
from blinkb0t.core.domains.sequencer.moving_heads.templates.compiler import TemplateCompiler
from blinkb0t.core.domains.sequencer.moving_heads.templates.types import tilt_bias_groups


def main() -> None:
    rig = build_demo_rig()
    template = tilt_bias_groups.TEMPLATE

    plan = SimpleNamespace(bpm=120, beats_per_bar=4)

    pan_pose_table = {"CENTER": 128}
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

    compiler = TemplateCompiler(
        geometry_resolver=geometry,
        movement_generator=movement,
        dimmer_generator=dimmer,
        curve_ops=curve_ops,
    )

    segments = compiler.compile(rig=rig, plan=plan, template_doc=template)

    print("\n=== DEMO 02C: GEOMETRY_ID tilt bias only ===\n")
    print("Template:", template.template_id)
    print("GeometryID: TILT_BIAS_BY_GROUP (OUTER=-12, INNER=+12)\n")

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

    print("\nTip: PAN should be constant, TILT varies by INNER/OUTER.\n")


if __name__ == "__main__":
    main()
