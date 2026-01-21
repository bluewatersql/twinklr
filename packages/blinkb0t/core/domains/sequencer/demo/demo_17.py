from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencer.moving_heads.models.ir import ChannelSegment

from blinkb0t.core.domains.sequencer.demo.helper import (
    apply_template_preset,
    build_demo_rig,
    print_segment,
)
from blinkb0t.core.domains.sequencer.moving_heads.curves.curve_ops import CurveOps
from blinkb0t.core.domains.sequencer.moving_heads.dimmer.generator import DimmerGenerator
from blinkb0t.core.domains.sequencer.moving_heads.geometry.role_pose import (
    RolePoseGeometryResolver,
)
from blinkb0t.core.domains.sequencer.moving_heads.models.presets import (
    DefaultsPatch,
    TemplatePreset,
)
from blinkb0t.core.domains.sequencer.moving_heads.movement.generator import MovementGenerator
from blinkb0t.core.domains.sequencer.moving_heads.templates.compiler import TemplateCompiler
from blinkb0t.core.domains.sequencer.moving_heads.templates.types import (
    clamp_extremes_strobe,
)


def main() -> None:
    rig = build_demo_rig()
    template = clamp_extremes_strobe.TEMPLATE

    plan = SimpleNamespace(bpm=120, beats_per_bar=4)

    pan_pose_table = {
        "WIDE_LEFT": 64,
        "MID_LEFT": 96,
        "CENTER": 128,
        "MID_RIGHT": 160,
        "WIDE_RIGHT": 192,
    }
    tilt_pose_table = {"HORIZON": 128}

    curve_ops = CurveOps()
    geometry = RolePoseGeometryResolver(
        pan_pose_table=pan_pose_table, tilt_pose_table=tilt_pose_table
    )
    movement = MovementGenerator(curve_ops=curve_ops, default_samples=16)
    dimmer = DimmerGenerator(curve_ops=curve_ops, default_samples=16)

    compiler = TemplateCompiler(
        geometry_resolver=geometry,
        movement_generator=movement,
        dimmer_generator=dimmer,
        curve_ops=curve_ops,
    )

    preset = TemplatePreset(
        preset_id="lower_floor_attempt",
        name="Lower Floor Attempt",
        defaults=DefaultsPatch(dimmer_floor_dmx=20),
    )

    patched = apply_template_preset(template, preset, clamp_floor_to_template=True)
    segments = compiler.compile(rig=rig, plan=plan, template_doc=patched)

    print("\n=== DEMO 17: Clamp Extremes & Safety ===\n")
    print("Template:", template.template_id)
    print("Rig floor=60, Template floor=80, Preset attempts floor=20 (ignored)\n")

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

    print("\nTip: dimmer clamp_min should stay at 80 despite strobe lows.\n")


if __name__ == "__main__":
    main()
