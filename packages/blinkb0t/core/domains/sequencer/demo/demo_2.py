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
from blinkb0t.core.domains.sequencer.moving_heads.templates.types import lean_right_scan


def main() -> None:
    rig = build_demo_rig()
    template = lean_right_scan.TEMPLATE

    plan = SimpleNamespace(bpm=120, beats_per_bar=4)

    pan_pose_table = {"CENTER": 128}
    tilt_pose_table = {"HORIZON": 128}

    curve_ops = CurveOps()
    geometry = GeometryDispatchResolver(
        role_pose_resolver=RolePoseGeometryResolver(
            pan_pose_table=pan_pose_table, tilt_pose_table=tilt_pose_table
        ),
        geometry_id_resolver=GeometryIdResolver(default_tilt_dmx=128),
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

    print("\n=== DEMO 02: Asymmetric Geometry (GEOMETRY_ID) ===\n")
    print("Template:", template.template_id)
    print("GeometryID: AUDIENCE_SCAN_ASYM (pan_positions=[96,112,144,176])\n")

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

    print("\nTip: look at PAN/TILT static values per fixture.\n")


if __name__ == "__main__":
    main()
