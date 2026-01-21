from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from blinkb0t.core.domains.sequencer.moving_heads.models.base import ChannelName
from blinkb0t.core.domains.sequencer.moving_heads.models.ir import ChannelSegment


@dataclass(frozen=True)
class _StepWindow:
    t0_ms: int
    t1_ms: int

    @property
    def duration_ms(self) -> int:
        return self.t1_ms - self.t0_ms


class TemplateCompiler:
    """
    MVP compiler that turns a validated TemplateSpec into IR ChannelSegments.

    Demo 01 additions:
    - Resolve step timing from plan + BaseTiming when available (fallback to stub)
    - Apply PhaseOffsetSpec (GROUP_ORDER) to per-fixture segment time windows
    """

    def __init__(
        self,
        geometry_resolver,
        movement_generator,
        dimmer_generator,
        curve_ops,
        iteration_policy=None,
    ):
        self.geometry = geometry_resolver
        self.movement = movement_generator
        self.dimmer = dimmer_generator
        self.curves = curve_ops
        self.iteration_policy = iteration_policy

    # -------------------------
    # Public
    # -------------------------

    def compile(self, rig, plan, template_doc):
        segments: list[ChannelSegment] = []

        # 1) resolve template + preset (still stub; presets applied ahead of compiler in v2)
        template = template_doc

        window = getattr(plan, "window", None)
        start_bar = float(getattr(window, "start_bar", 0.0)) if window else 0.0
        duration_bars = float(getattr(window, "duration_bars", 0.0)) if window else 0.0

        cycle_bars = float(template.repeat.cycle_bars) if template.repeat else 0.0
        repeatable = bool(getattr(template.repeat, "repeatable", False))

        loop_step_ids = set(getattr(template.repeat, "loop_step_ids", []) or [])
        non_loop_steps = [s for s in template.steps if s.step_id not in loop_step_ids]

        if window and repeatable and cycle_bars > 0.0:
            total_cycles = max(1, int(duration_bars // cycle_bars))
            if duration_bars - (total_cycles * cycle_bars) > 1e-6:
                total_cycles += 1

            loop_cutoff_bars: float | None = None
            if non_loop_steps:
                starts = [
                    float(s.timing.base_timing.start_offset_bars)
                    for s in non_loop_steps
                    if getattr(s.timing, "base_timing", None) is not None
                ]
                future_starts = [s for s in starts if s > 0.0]
                if future_starts:
                    loop_cutoff_bars = start_bar + min(future_starts)

            for i in range(total_cycles):
                cycle_offset_bars = start_bar + (i * cycle_bars)
                for step in template.steps:
                    if step.step_id not in loop_step_ids:
                        continue
                    base = step.timing.base_timing
                    if loop_cutoff_bars is not None:
                        step_start = cycle_offset_bars + float(base.start_offset_bars)
                        if step_start >= loop_cutoff_bars:
                            continue
                    step_doc = self._apply_iteration_policy(step, i, total_cycles)
                    segments.extend(
                        self._compile_step(
                            rig=rig,
                            plan=plan,
                            template=template,
                            step=step_doc,
                            cycle_offset_bars=cycle_offset_bars,
                            iteration_index=i,
                        )
                    )

            for step in non_loop_steps:
                segments.extend(
                    self._compile_step(
                        rig=rig,
                        plan=plan,
                        template=template,
                        step=step,
                        cycle_offset_bars=start_bar,
                        iteration_index=0,
                    )
                )
        else:
            for step in template.steps:
                segments.extend(
                    self._compile_step(
                        rig=rig,
                        plan=plan,
                        template=template,
                        step=step,
                        cycle_offset_bars=start_bar,
                        iteration_index=0,
                    )
                )

        if window:
            start_ms = self._bars_to_ms(plan, start_bar)
            end_ms = start_ms + self._bars_to_ms(plan, duration_bars)
            segments = self._clip_segments_to_window(segments, start_ms, end_ms)

        return segments

    # -------------------------
    # Timing helpers
    # -------------------------

    def _bars_to_ms(self, plan: Any, bars: float) -> int:
        """
        Convert musical bars -> milliseconds using plan tempo.
        Falls back to 1000ms per bar if bpm unavailable (demo-friendly).
        """
        bpm = getattr(plan, "bpm", None) or getattr(plan, "tempo_bpm", None)
        beats_per_bar = getattr(plan, "beats_per_bar", 4)

        if bpm is None:
            return round(bars * 1000.0)

        ms_per_beat = 60_000.0 / float(bpm)
        ms_per_bar = ms_per_beat * float(beats_per_bar)
        return round(float(bars) * ms_per_bar)

    def _resolve_step_window(
        self, plan: Any, step: Any, cycle_offset_bars: float = 0.0
    ) -> _StepWindow:
        """
        Use StepTiming.base_timing when present; otherwise return stub window.
        """
        try:
            base = step.timing.base_timing
            t0 = self._bars_to_ms(
                plan, float(base.start_offset_bars) + float(cycle_offset_bars)
            )
            t1 = t0 + self._bars_to_ms(plan, float(base.duration_bars))
            return _StepWindow(t0_ms=t0, t1_ms=t1)
        except Exception:
            # Keep MVP stub behavior
            return _StepWindow(t0_ms=0, t1_ms=1000)

    # -------------------------
    # Phase offsets (Demo 01)
    # -------------------------

    def _fixture_phase_offsets_ms(
        self, rig: Any, plan: Any, step: Any, fixtures: list[str]
    ) -> dict[str, int]:
        """
        Compute per-fixture time offset (ms) based on StepTiming.phase_offset.

        Supports:
        - PhaseOffsetMode.NONE
        - PhaseOffsetMode.GROUP_ORDER (spread across a rig order)
        """
        phase = getattr(step.timing, "phase_offset", None)
        if phase is None:
            return dict.fromkeys(fixtures, 0)

        mode = getattr(phase, "mode", "NONE")
        if str(mode).upper() == "NONE":
            return dict.fromkeys(fixtures, 0)

        # Only GROUP_ORDER in MVP
        if str(mode).upper() != "GROUP_ORDER":
            return dict.fromkeys(fixtures, 0)

        group_name = phase.group
        spread_bars = float(phase.spread_bars)
        spread_ms = self._bars_to_ms(plan, spread_bars)

        # Determine ordered fixtures: start from group fixtures, then apply rig.orders[order]
        group_fixtures = list(rig.groups[group_name])

        order_key = getattr(phase, "order", None)
        order_name = str(order_key).upper() if order_key is not None else "LEFT_TO_RIGHT"
        rig_order = list(getattr(rig, "orders", {}).get(order_name, group_fixtures))

        # Filter to only fixtures in this step's fixture list and in group
        ordered = [fx for fx in rig_order if fx in group_fixtures and fx in fixtures]
        if not ordered:
            ordered = list(fixtures)

        n = len(ordered)
        if n <= 1 or spread_ms <= 0:
            return dict.fromkeys(fixtures, 0)

        # Linear distribution (MVP): offset_i = i/(n-1) * spread
        offsets: dict[str, int] = {}
        for i, fx in enumerate(ordered):
            offsets[fx] = round((i / (n - 1)) * spread_ms)

        # Any fixtures not in ordered keep 0 offset
        for fx in fixtures:
            offsets.setdefault(fx, 0)

        return offsets

    def _apply_wrap(self, t0: int, t1: int, step_window: _StepWindow) -> tuple[int, int]:
        """
        If a phase offset shifts beyond the step window, wrap modulo the step duration.
        This keeps all segments within [t0_ms, t1_ms] for the step.
        """
        dur = max(1, step_window.duration_ms)
        rel0 = (t0 - step_window.t0_ms) % dur
        rel1 = rel0 + (t1 - t0)
        rel1 = min(rel1, dur)
        return step_window.t0_ms + rel0, step_window.t0_ms + rel1

    # -------------------------
    # Compile step
    # -------------------------

    def _compile_step(
        self,
        rig,
        plan,
        template,
        step,
        cycle_offset_bars: float = 0.0,
        iteration_index: int = 0,
    ):
        fixtures = list(rig.groups[step.target])

        step_window = self._resolve_step_window(plan, step, cycle_offset_bars)
        duration_ms = step_window.duration_ms

        # 1) Geometry: absolute base pose per fixture
        base_pose = self.geometry.resolve_base_pose(
            rig=rig,
            fixtures=fixtures,
            geometry=step.geometry,
        )

        # 2) Movement: offset-centered normalized curves
        move = self.movement.generate(step.movement, duration_ms=duration_ms)
        move = self._apply_repeat_mode(move, template, iteration_index)

        # 3) Dimmer: normalized curve or None (HOLD)
        dim_curve = self.dimmer.generate(step.dimmer, duration_ms=duration_ms)

        # 4) Phase offsets
        offsets_ms = self._fixture_phase_offsets_ms(
            rig=rig, plan=plan, step=step, fixtures=fixtures
        )
        wrap = getattr(getattr(step.timing, "phase_offset", None), "wrap", True)

        segments: list[ChannelSegment] = []

        pan_amp_dmx = getattr(rig.calibration, "pan_amplitude_dmx", 90)
        tilt_amp_dmx = getattr(rig.calibration, "tilt_amplitude_dmx", 60)

        for fx in fixtures:
            pan_base, tilt_base = base_pose[fx]

            fx_t0 = step_window.t0_ms + int(offsets_ms.get(fx, 0))
            fx_t1 = step_window.t1_ms + int(offsets_ms.get(fx, 0))
            if wrap:
                fx_t0, fx_t1 = self._apply_wrap(fx_t0, fx_t1, step_window)

            # PAN
            if move.pan is not None:
                segments.append(
                    ChannelSegment(
                        fixture_id=fx,
                        channel=ChannelName.PAN,
                        t0_ms=fx_t0,
                        t1_ms=fx_t1,
                        curve=move.pan,
                        offset_centered=True,
                        base_dmx=pan_base,
                        amplitude_dmx=round(pan_amp_dmx * float(move.amplitude_norm)),
                        clamp_min=0,
                        clamp_max=255,
                    )
                )
            else:
                segments.append(
                    ChannelSegment(
                        fixture_id=fx,
                        channel=ChannelName.PAN,
                        t0_ms=fx_t0,
                        t1_ms=fx_t1,
                        static_dmx=pan_base,
                        clamp_min=0,
                        clamp_max=255,
                    )
                )

            # TILT
            if move.tilt is not None:
                segments.append(
                    ChannelSegment(
                        fixture_id=fx,
                        channel=ChannelName.TILT,
                        t0_ms=fx_t0,
                        t1_ms=fx_t1,
                        curve=move.tilt,
                        offset_centered=True,
                        base_dmx=tilt_base,
                        amplitude_dmx=round(tilt_amp_dmx * float(move.amplitude_norm)),
                        clamp_min=0,
                        clamp_max=255,
                    )
                )
            else:
                segments.append(
                    ChannelSegment(
                        fixture_id=fx,
                        channel=ChannelName.TILT,
                        t0_ms=fx_t0,
                        t1_ms=fx_t1,
                        static_dmx=tilt_base,
                        clamp_min=0,
                        clamp_max=255,
                    )
                )

            # DIMMER
            dimmer_floor, dimmer_ceiling = self._resolve_dimmer_clamp(rig, template, step)
            if dim_curve is not None:
                dimmer_segment = ChannelSegment(
                    fixture_id=fx,
                    channel=ChannelName.DIMMER,
                    t0_ms=fx_t0,
                    t1_ms=fx_t1,
                    curve=dim_curve,
                    clamp_min=dimmer_floor,
                    clamp_max=dimmer_ceiling,
                    blend_mode=step.blend_mode,
                )
                segments.append(dimmer_segment)
                segments.extend(
                    self._compile_dimmer_transitions(
                        step=step,
                        fixture_id=fx,
                        base_segment=dimmer_segment,
                        plan=plan,
                        clamp_min=dimmer_floor,
                        clamp_max=dimmer_ceiling,
                    )
                )
            else:
                dimmer_segment = ChannelSegment(
                    fixture_id=fx,
                    channel=ChannelName.DIMMER,
                    t0_ms=fx_t0,
                    t1_ms=fx_t1,
                    static_dmx=255,  # HOLD convention: full on (floor enforced via clamp)
                    clamp_min=dimmer_floor,
                    clamp_max=dimmer_ceiling,
                    blend_mode=step.blend_mode,
                )
                segments.append(dimmer_segment)
                segments.extend(
                    self._compile_dimmer_transitions(
                        step=step,
                        fixture_id=fx,
                        base_segment=dimmer_segment,
                        plan=plan,
                        clamp_min=dimmer_floor,
                        clamp_max=dimmer_ceiling,
                    )
                )

        return segments

    def _apply_repeat_mode(self, move, template, iteration_index: int):
        repeat = getattr(template, "repeat", None)
        if repeat is None:
            return move
        mode_value = getattr(repeat.mode, "value", str(repeat.mode))
        if str(mode_value).upper() != "PING_PONG":
            return move
        if iteration_index % 2 == 0:
            return move
        pan = self._reverse_curve(move.pan) if move.pan is not None else None
        tilt = self._reverse_curve(move.tilt) if move.tilt is not None else None
        return move.model_copy(update={"pan": pan, "tilt": tilt})

    def _reverse_curve(self, curve):
        if curve is None:
            return None
        pts = list(curve.points)
        reversed_pts = [
            p.model_copy(update={"t": 1.0 - p.t}) for p in reversed(pts)
        ]
        return curve.model_copy(update={"points": reversed_pts})

    def _compile_dimmer_transitions(
        self,
        step,
        fixture_id: str,
        base_segment: ChannelSegment,
        plan: Any,
        clamp_min: int,
        clamp_max: int,
    ) -> list[ChannelSegment]:
        transitions: list[ChannelSegment] = []

        entry = getattr(step, "entry_transition", None)
        exit_transition = getattr(step, "exit_transition", None)

        if entry:
            dur_ms = self._bars_to_ms(plan, float(entry.duration_bars))
            if dur_ms > 0:
                curve = self._transition_curve(entry.mode, entering=True)
                transitions.append(
                    ChannelSegment(
                        fixture_id=fixture_id,
                        channel=ChannelName.DIMMER,
                        t0_ms=base_segment.t0_ms - dur_ms,
                        t1_ms=base_segment.t0_ms,
                        curve=curve,
                        clamp_min=clamp_min,
                        clamp_max=clamp_max,
                        blend_mode=base_segment.blend_mode,
                    )
                )

        if exit_transition:
            dur_ms = self._bars_to_ms(plan, float(exit_transition.duration_bars))
            if dur_ms > 0:
                curve = self._transition_curve(exit_transition.mode, entering=False)
                transitions.append(
                    ChannelSegment(
                        fixture_id=fixture_id,
                        channel=ChannelName.DIMMER,
                        t0_ms=base_segment.t1_ms,
                        t1_ms=base_segment.t1_ms + dur_ms,
                        curve=curve,
                        clamp_min=clamp_min,
                        clamp_max=clamp_max,
                        blend_mode=base_segment.blend_mode,
                    )
                )

        return transitions

    def _transition_curve(self, mode, entering: bool):
        mode_value = getattr(mode, "value", str(mode))
        mode_value = str(mode_value).lower()
        if mode_value == "snap":
            return self.curves.sample(lambda t: 1.0 if entering else 0.0, 2)

        if entering:
            return self.curves.sample(lambda t: t, 16)
        return self.curves.sample(lambda t: 1.0 - t, 16)

    def _resolve_dimmer_clamp(self, rig, template, step) -> tuple[int, int]:
        rig_floor = int(getattr(rig.calibration, "dimmer_floor_dmx", 0))
        template_floor = int(getattr(template.defaults, "dimmer_floor_dmx", 0))
        template_ceiling = int(getattr(template.defaults, "dimmer_ceiling_dmx", 255))
        step_floor = step.dimmer_floor_dmx
        step_ceiling = step.dimmer_ceiling_dmx

        floor = max(rig_floor, template_floor, int(step_floor) if step_floor is not None else 0)
        ceiling_candidates = [255, template_ceiling]
        if step_ceiling is not None:
            ceiling_candidates.append(int(step_ceiling))
        ceiling = min(ceiling_candidates)

        if ceiling < floor:
            ceiling = floor

        return floor, ceiling

    def _apply_iteration_policy(self, step, iteration_index: int, total_iterations: int):
        if self.iteration_policy is None:
            return step
        return self.iteration_policy.apply(step, iteration_index, total_iterations)

    def _clip_segments_to_window(
        self, segments: list[ChannelSegment], start_ms: int, end_ms: int
    ) -> list[ChannelSegment]:
        clipped: list[ChannelSegment] = []
        for seg in segments:
            t0 = max(seg.t0_ms, start_ms)
            t1 = min(seg.t1_ms, end_ms)
            if t1 <= t0:
                continue
            if t0 == seg.t0_ms and t1 == seg.t1_ms:
                clipped.append(seg)
            else:
                clipped.append(seg.model_copy(update={"t0_ms": t0, "t1_ms": t1}))
        return clipped
