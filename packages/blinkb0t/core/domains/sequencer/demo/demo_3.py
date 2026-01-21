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
from blinkb0t.core.domains.sequencer.moving_heads.templates.iteration import (
    PumpUpIterationPolicy,
)
from blinkb0t.core.domains.sequencer.moving_heads.templates.specs import pump_up_loop


def main() -> None:
    rig = build_demo_rig()
    template = pump_up_loop.TEMPLATE

    plan = SimpleNamespace(
        bpm=120,
        beats_per_bar=4,
        window=PlaybackWindowBars(start_bar=0.0, duration_bars=16.0),
    )

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
    iteration_policy = PumpUpIterationPolicy(target_dimmer_min_norm=0.25)

    compiler = TemplateCompiler(
        geometry_resolver=geometry,
        movement_generator=movement,
        dimmer_generator=dimmer,
        curve_ops=curve_ops,
        iteration_policy=iteration_policy,
    )

    segments = compiler.compile(rig=rig, plan=plan, template_doc=template)

    print("\n=== DEMO 03: Looping with Adjustments ===\n")
    print("Template:", template.template_id)
    print("Window: 16 bars @ 120bpm (4 iterations)")
    print("Adjustments: movement intensity ramps, dimmer min_norm increases\n")

    print("\n=== TEMPLATE ===\n")
    print(
        f"{template.template_id}  steps={[s.step_id for s in template.steps]}  repeat={template.repeat.mode}"
    )

    print("\n=== SEGMENTS (normalized) ===\n")
    for seg in segments:
        print_segment(seg)

    print("\n=== ITERATION SUMMARY ===\n")
    total_cycles = int(plan.window.duration_bars // template.repeat.cycle_bars)
    if plan.window.duration_bars - (total_cycles * template.repeat.cycle_bars) > 1e-6:
        total_cycles += 1
    for i in range(total_cycles):
        step_doc = iteration_policy.apply(template.steps[0], i, total_cycles)
        print(
            f"cycle {i + 1}: movement={step_doc.movement.intensity.value} "
            f"dimmer_min_norm={step_doc.dimmer.min_norm:.2f}"
        )

    print("\n=== SUMMARY (fixture -> channels) ===\n")
    by_fx: dict[str, list[ChannelSegment]] = {}
    for s in segments:
        by_fx.setdefault(s.fixture_id, []).append(s)

    for fx in sorted(by_fx.keys()):
        chans = ", ".join([seg.channel.value for seg in by_fx[fx]])
        print(f"{fx}: {chans}")

    print("\nTip: compare dimmer min_norm across iteration windows.\n")


if __name__ == "__main__":
    main()
