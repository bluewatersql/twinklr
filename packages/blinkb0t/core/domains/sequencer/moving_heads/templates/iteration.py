from __future__ import annotations

from blinkb0t.core.domains.sequencer.moving_heads.models.base import IntensityLevel, OrderMode
from blinkb0t.core.domains.sequencer.moving_heads.models.templates import Step


class IterationPolicy:
    def apply(self, step: Step, iteration_index: int, total_iterations: int) -> Step:
        return step


class PumpUpIterationPolicy(IterationPolicy):
    def __init__(
        self,
        target_dimmer_min_norm: float = 0.25,
        start_intensity: IntensityLevel = IntensityLevel.SMOOTH,
        end_intensity: IntensityLevel = IntensityLevel.DRAMATIC,
    ):
        self.target_dimmer_min_norm = target_dimmer_min_norm
        self.start_intensity = start_intensity
        self.end_intensity = end_intensity

    def apply(self, step: Step, iteration_index: int, total_iterations: int) -> Step:
        if total_iterations <= 1:
            return step

        frac = iteration_index / max(1, total_iterations - 1)
        new_step = step

        if step.movement is not None:
            intensity = self.start_intensity if frac < 0.5 else self.end_intensity
            new_step = new_step.model_copy(
                update={"movement": step.movement.model_copy(update={"intensity": intensity})}
            )

        if step.dimmer is not None:
            base_min = float(step.dimmer.min_norm)
            target = float(self.target_dimmer_min_norm)
            new_min = base_min + (target - base_min) * frac
            new_min = max(0.0, min(1.0, new_min))
            new_step = new_step.model_copy(
                update={"dimmer": step.dimmer.model_copy(update={"min_norm": new_min})}
            )

        return new_step


class ReverseEveryOtherPolicy(IterationPolicy):
    def apply(self, step: Step, iteration_index: int, total_iterations: int) -> Step:
        phase = getattr(step.timing, "phase_offset", None)
        if phase is None:
            return step

        reverse = iteration_index % 2 == 1
        order = OrderMode.RIGHT_TO_LEFT if reverse else OrderMode.LEFT_TO_RIGHT

        new_phase = phase.model_copy(update={"order": order})
        new_timing = step.timing.model_copy(update={"phase_offset": new_phase})
        return step.model_copy(update={"timing": new_timing})
