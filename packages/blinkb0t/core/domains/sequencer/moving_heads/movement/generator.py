# sequencing_v2/movement/movement_generator.py
from __future__ import annotations

from blinkb0t.core.domains.sequencer.moving_heads.curves.curve_ops import CurveOps
from blinkb0t.core.domains.sequencer.moving_heads.models.ir import PointsBaseCurve
from blinkb0t.core.domains.sequencer.moving_heads.models.movement import Movement
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements import MovementID
from pydantic import BaseModel, ConfigDict, Field

_INTENSITY_TO_AMPLITUDE = {
    "smooth": 0.35,
    "dramatic": 0.70,
    "intense": 1.00,
}


def _triangle_wave(t: float) -> float:
    """
    Triangle wave in [-1, +1] with period 1:
      t in [0,1] -> -1..+1..-1
    """
    # 0..1
    x = t % 1.0
    # triangle 0..1..0
    tri01 = 1.0 - abs(2.0 * x - 1.0)
    # map to -1..+1
    return (tri01 * 2.0) - 1.0


class MovementCurves(BaseModel):
    """
    Normalized movement curves (offset-centered at 0.5).
    For MVP: pan only for SWEEP_LR.
    """

    model_config = ConfigDict(extra="forbid")

    pan: PointsBaseCurve | None = None
    tilt: PointsBaseCurve | None = None

    # amplitude is returned separately so compiler can map to DMX range consistently
    amplitude_norm: float = Field(0.35, ge=0.0, le=1.0)


class MovementGenerator:
    def __init__(self, curve_ops: CurveOps, default_samples: int = 32):
        self.curve_ops: CurveOps = curve_ops
        self.default_samples: int = default_samples

    def generate(self, spec: Movement, duration_ms: int) -> MovementCurves:
        movement_id = spec.movement_id
        amp = _INTENSITY_TO_AMPLITUDE.get(spec.intensity.value, 0.35)
        cycles = float(spec.cycles)

        if movement_id == MovementID.HOLD:
            return MovementCurves(pan=None, tilt=None, amplitude_norm=amp)

        if movement_id == MovementID.SWEEP_LR:
            n = self.default_samples

            # Offset-centered output:
            # v = 0.5 + 0.5 * triangle(t*cycles)  -> stays in [0,1]
            curve = self.curve_ops.sample(
                lambda t: 0.5 + 0.5 * _triangle_wave(t * cycles),
                n_samples=n,
            )

            pts = list(curve.points)
            pts[-1] = pts[-1].model_copy(update={"v": pts[0].v})
            curve = PointsBaseCurve(points=pts)

            return MovementCurves(pan=curve, tilt=None, amplitude_norm=amp)

        if movement_id == MovementID.SWEEP_UD:
            n = self.default_samples

            curve = self.curve_ops.sample(
                lambda t: 0.5 + 0.5 * _triangle_wave(t * cycles),
                n_samples=n,
            )

            pts = list(curve.points)
            pts[-1] = pts[-1].model_copy(update={"v": pts[0].v})
            curve = PointsBaseCurve(points=pts)

            return MovementCurves(pan=None, tilt=curve, amplitude_norm=amp)

        if movement_id == MovementID.CIRCLE:
            n = self.default_samples

            pan_curve = self.curve_ops.sample(
                lambda t: 0.5
                + 0.5 * __import__("math").sin(2 * __import__("math").pi * cycles * t),
                n_samples=n,
            )
            tilt_curve = self.curve_ops.sample(
                lambda t: 0.5
                + 0.5 * __import__("math").cos(2 * __import__("math").pi * cycles * t),
                n_samples=n,
            )

            pan_pts = list(pan_curve.points)
            pan_pts[-1] = pan_pts[-1].model_copy(update={"v": pan_pts[0].v})
            pan_curve = PointsBaseCurve(points=pan_pts)

            tilt_pts = list(tilt_curve.points)
            tilt_pts[-1] = tilt_pts[-1].model_copy(update={"v": tilt_pts[0].v})
            tilt_curve = PointsBaseCurve(points=tilt_pts)

            return MovementCurves(pan=pan_curve, tilt=tilt_curve, amplitude_norm=amp)

        if movement_id == MovementID.BOUNCE:
            n = self.default_samples

            # Bounce-style vertical motion: abs(sin) in [0,1]
            curve = self.curve_ops.sample(
                lambda t: abs(__import__("math").sin(2 * __import__("math").pi * cycles * t)),
                n_samples=n,
            )

            pts = list(curve.points)
            pts[-1] = pts[-1].model_copy(update={"v": pts[0].v})
            curve = PointsBaseCurve(points=pts)

            return MovementCurves(pan=None, tilt=curve, amplitude_norm=amp)

        if movement_id == MovementID.PENDULUM:
            n = self.default_samples

            curve = self.curve_ops.sample(
                lambda t: 0.5
                + 0.5 * __import__("math").sin(2 * __import__("math").pi * cycles * t),
                n_samples=n,
            )

            pts = list(curve.points)
            pts[-1] = pts[-1].model_copy(update={"v": pts[0].v})
            curve = PointsBaseCurve(points=pts)

            return MovementCurves(pan=curve, tilt=None, amplitude_norm=amp)

        if movement_id == MovementID.WAVE_HORIZONTAL:
            n = self.default_samples

            curve = self.curve_ops.sample(
                lambda t: 0.5
                + 0.5 * __import__("math").sin(2 * __import__("math").pi * cycles * t),
                n_samples=n,
            )

            pts = list(curve.points)
            pts[-1] = pts[-1].model_copy(update={"v": pts[0].v})
            curve = PointsBaseCurve(points=pts)

            return MovementCurves(pan=curve, tilt=None, amplitude_norm=amp)

        raise ValueError(f"Unsupported movement_id for MVP: {spec.movement_id!r}")
