# sequencing_v2/dimmer/dimmer_generator.py


from blinkb0t.core.domains.sequencer.moving_heads.curves.curve_ops import CurveOps
from blinkb0t.core.domains.sequencer.moving_heads.models.dimmer import Dimmer
from blinkb0t.core.domains.sequencer.moving_heads.models.ir import PointsBaseCurve
from blinkb0t.core.domains.sequencing.libraries.moving_heads.dimmers import DimmerID

_INTENSITY_TO_DEPTH = {
    "smooth": 0.5,
    "dramatic": 0.8,
    "intense": 1.0,
}


class DimmerGenerator:
    def __init__(self, curve_ops: CurveOps, default_samples: int = 32):
        self.curve_ops = curve_ops
        self.default_samples = default_samples

    def generate(self, spec: Dimmer, duration_ms: int) -> PointsBaseCurve | None:
        dimmer_id = spec.dimmer_id
        depth = _INTENSITY_TO_DEPTH.get(spec.intensity.lower(), 0.5)

        if dimmer_id == DimmerID.HOLD:
            return None

        if dimmer_id == DimmerID.BREATHE:
            return self.curve_ops.sample(
                lambda t: spec.min_norm
                + (spec.max_norm - spec.min_norm)
                * (0.5 - 0.5 * __import__("math").cos(2 * __import__("math").pi * spec.cycles * t)),
                self.default_samples,
            )

        if dimmer_id == DimmerID.FADE_IN:
            return self.curve_ops.sample(
                lambda t: spec.min_norm + (spec.max_norm - spec.min_norm) * t,
                self.default_samples,
            )

        if dimmer_id == DimmerID.FADE_OUT:
            return self.curve_ops.sample(
                lambda t: spec.max_norm - (spec.max_norm - spec.min_norm) * t,
                self.default_samples,
            )

        if dimmer_id == DimmerID.SWELL:
            return self.curve_ops.sample(
                lambda t: spec.min_norm
                + (spec.max_norm - spec.min_norm)
                * (1.0 - abs(2.0 * ((t * spec.cycles) % 1.0) - 1.0)),
                self.default_samples,
            )

        if dimmer_id == DimmerID.STROBE:
            return self.curve_ops.sample(
                lambda t: spec.max_norm
                if __import__("math").sin(2 * __import__("math").pi * spec.cycles * t) >= 0.0
                else spec.min_norm,
                self.default_samples,
            )

        if dimmer_id == DimmerID.PULSE:
            return self.curve_ops.sample(
                lambda t: spec.min_norm
                + depth
                * (spec.max_norm - spec.min_norm)
                * (0.5 + 0.5 * __import__("math").sin(2 * __import__("math").pi * spec.cycles * t)),
                self.default_samples,
            )

        raise ValueError(f"Unsupported dimmer_id: {spec.dimmer_id}")
