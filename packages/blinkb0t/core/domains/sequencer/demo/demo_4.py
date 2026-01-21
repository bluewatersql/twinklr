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
from blinkb0t.core.domains.sequencer.moving_heads.movement.generator import MovementGenerator
from blinkb0t.core.domains.sequencer.moving_heads.templates.compiler import TemplateCompiler
from blinkb0t.core.domains.sequencer.moving_heads.templates.types import (
    crossfade_between_steps,
    snap_in_fade_out,
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


def _print_step_transitions(template) -> None:
    print("\n=== STEP TRANSITIONS ===\n")
    for step in template.steps:
        entry = step.entry_transition
        exit_transition = step.exit_transition
        if entry:
            entry_desc = f"{entry.mode.value} {entry.duration_bars} bars"
        else:
            entry_desc = "none"
        if exit_transition:
            exit_desc = f"{exit_transition.mode.value} {exit_transition.duration_bars} bars"
        else:
            exit_desc = "none"
        print(f"{step.step_id}: entry={entry_desc}  exit={exit_desc}")


def main() -> None:
    rig = build_demo_rig()
    compiler = _build_compiler()
    plan = SimpleNamespace(bpm=120, beats_per_bar=4)

    template = snap_in_fade_out.TEMPLATE
    segments = compiler.compile(rig=rig, plan=plan, template_doc=template)
    print("\n=== DEMO 04A: Snap In + Fade Through Black ===\n")
    print("Template:", template.template_id)
    _print_step_transitions(template)
    _print_segments("04A", segments)

    template = crossfade_between_steps.TEMPLATE
    segments = compiler.compile(rig=rig, plan=plan, template_doc=template)
    print("\n=== DEMO 04B: Crossfade Between Steps ===\n")
    print("Template:", template.template_id)
    _print_step_transitions(template)
    _print_segments("04B", segments)


if __name__ == "__main__":
    main()
