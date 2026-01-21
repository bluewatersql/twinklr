from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencer.moving_heads.models.ir import ChannelSegment

from blinkb0t.core.domains.sequencer.demo.helper import build_demo_rig, print_segment
from blinkb0t.core.domains.sequencer.moving_heads.curves.curve_ops import CurveOps
from blinkb0t.core.domains.sequencer.moving_heads.dimmer.generator import DimmerGenerator
from blinkb0t.core.domains.sequencer.moving_heads.geometry.role_pose import (
    RolePoseGeometryResolver,
)
from blinkb0t.core.domains.sequencer.moving_heads.models.plan import PlaybackWindowBars
from blinkb0t.core.domains.sequencer.moving_heads.movement.generator import MovementGenerator
from blinkb0t.core.domains.sequencer.moving_heads.templates.compiler import TemplateCompiler
from blinkb0t.core.domains.sequencer.moving_heads.templates.specs import (
    sweep_lr_continuous_phase,
    sweep_lr_pingpong_phase,
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
    geometry = RolePoseGeometryResolver(
        pan_pose_table=pan_pose_table, tilt_pose_table=tilt_pose_table
    )
    movement = MovementGenerator(curve_ops=curve_ops, default_samples=16)
    dimmer = DimmerGenerator(curve_ops=curve_ops, default_samples=16)

    return TemplateCompiler(
        geometry_resolver=geometry,
        movement_generator=movement,
        dimmer_generator=dimmer,
        curve_ops=curve_ops,
    )


def _print_loop_summary(segments: list[ChannelSegment]) -> None:
    print("\n=== LOOP CHECK (PAN endpoints) ===\n")
    for seg in segments:
        if seg.channel.value != "PAN" or seg.curve is None:
            continue
        if seg.curve.kind != "POINTS":
            continue
        points = seg.curve.points
        first = points[0].v
        last = points[-1].v
        print(f"{seg.fixture_id}: first={first:.3f} last={last:.3f}")


def _run(label: str, template) -> None:
    rig = build_demo_rig()
    compiler = _build_compiler()
    plan = SimpleNamespace(
        bpm=120,
        beats_per_bar=4,
        window=PlaybackWindowBars(start_bar=0.0, duration_bars=8.0),
    )

    segments = compiler.compile(rig=rig, plan=plan, template_doc=template)
    print(f"\n=== DEMO 13{label}: {template.template_id} ===\n")
    print("Window: 8 bars (2 cycles)")

    print("\n=== SEGMENTS (normalized) ===\n")
    for seg in segments:
        print_segment(seg)

    _print_loop_summary(segments)


def main() -> None:
    _run("A", sweep_lr_continuous_phase.TEMPLATE)
    _run("B", sweep_lr_pingpong_phase.TEMPLATE)


if __name__ == "__main__":
    main()
