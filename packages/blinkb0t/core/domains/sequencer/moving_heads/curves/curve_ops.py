# sequencing_v2/curves/curve_ops.py

from __future__ import annotations

from collections.abc import Callable
from math import isfinite

from blinkb0t.core.domains.sequencer.moving_heads.models.ir import CurvePoint, PointsBaseCurve


def _round_t(t: float, ndigits: int = 6) -> float:
    # helps keep t stable in JSON and reduces tiny FP noise
    return round(float(t), ndigits)


def _clamp01(x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return float(x)


def _assert_non_empty(points: list[CurvePoint]) -> None:
    if len(points) < 2:
        raise ValueError("Need at least 2 points")


def _is_uniform_grid(points: list[CurvePoint], eps: float = 1e-6) -> bool:
    """
    True if t looks like 0..1 sampled at fixed spacing (including endpoint 1.0).
    """
    _assert_non_empty(points)
    ts = [p.t for p in points]
    if abs(ts[0] - 0.0) > eps or abs(ts[-1] - 1.0) > eps:
        return False
    # compute step
    n = len(ts) - 1
    if n <= 0:
        return False
    dt = 1.0 / n
    for i, t in enumerate(ts):
        if abs(t - (i * dt)) > eps:
            return False
    return True


def _rotate_values(values: list[float], shift: int) -> list[float]:
    if not values:
        return values
    shift = shift % len(values)
    if shift == 0:
        return values[:]
    return values[-shift:] + values[:-shift]


def _interp_piecewise(points: list[CurvePoint], t: float) -> float:
    """
    Linear interpolation of v at time t over monotonic points.
    Assumes points have non-decreasing t in [0,1].
    """
    _assert_non_empty(points)

    if t <= points[0].t:
        return points[0].v
    if t >= points[-1].t:
        return points[-1].v

    # binary search
    lo, hi = 0, len(points) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if points[mid].t <= t:
            lo = mid
        else:
            hi = mid

    p0, p1 = points[lo], points[hi]
    if p1.t == p0.t:
        return p1.v
    u = (t - p0.t) / (p1.t - p0.t)
    return float(p0.v + u * (p1.v - p0.v))


class CurveOps:
    """
    Pure curve operations for PointsBaseCurve.

    Design notes:
    - Points are normalized: t,v in [0,1]
    - Prefer fixed-grid sampling for stability (phase shift via rotation)
    """

    def sample(self, fn: Callable[[float], float], n_samples: int) -> PointsBaseCurve:
        """
        Sample fn(t) at uniform grid t = 0..1 with n_samples intervals.
        Produces n_samples+1 points including endpoints.
        """
        if n_samples < 2:
            raise ValueError("n_samples must be >= 2")
        pts: list[CurvePoint] = []
        for i in range(n_samples + 1):
            t = i / n_samples
            v = fn(t)
            if not isfinite(v):
                raise ValueError(f"fn produced non-finite v at t={t}: {v}")
            pts.append(CurvePoint(t=_round_t(t), v=_clamp01(v)))
        return PointsBaseCurve(points=pts)

    def resample_to_grid(self, curve: PointsBaseCurve, n_samples: int) -> PointsBaseCurve:
        """
        Resample an arbitrary curve to a uniform grid using linear interpolation.
        Useful as a fallback when time-shifting non-uniform curves.
        """
        if n_samples < 2:
            raise ValueError("n_samples must be >= 2")
        src = curve.points
        pts: list[CurvePoint] = []
        for i in range(n_samples + 1):
            t = i / n_samples
            v = _interp_piecewise(src, t)
            pts.append(CurvePoint(t=_round_t(t), v=_clamp01(v)))
        return PointsBaseCurve(points=pts)

    def time_shift(
        self,
        curve: PointsBaseCurve,
        offset_norm: float,
        *,
        wrap: bool = True,
        grid_samples: int | None = None,
    ) -> PointsBaseCurve:
        """
        Shift curve in time by offset_norm in [0,1] (can be any float; mod applied).
        - If curve is uniform grid, uses rotation for exactness.
        - Otherwise, resamples to uniform grid first (recommended).
        """
        if not curve.points:
            return curve

        # normalize offset
        off = float(offset_norm)
        if wrap:
            off = off % 1.0
        else:
            # no-wrap: clamp; outside range becomes endpoint values (handled by resampling)
            off = max(0.0, min(1.0, off))

        pts = curve.points

        # If non-uniform, resample (either to given grid size or inferred size)
        if not _is_uniform_grid(pts):
            if grid_samples is None:
                # infer grid size from point count if it looks like sampled data
                grid_samples = max(2, len(pts) - 1)
            curve = self.resample_to_grid(curve, grid_samples)
            pts = curve.points

        # Now uniform grid rotation
        n = len(pts) - 1  # intervals
        if n <= 0:
            return curve

        shift_steps = int(round(off * n))
        # Rotate only the values; keep t grid the same.
        values = [p.v for p in pts]
        rotated = _rotate_values(values, shift_steps)

        # Important: endpoint at t=1.0 should match t=0.0 for loop-readiness
        # On a uniform grid, points include both. Ensure that property holds.
        rotated[-1] = rotated[0]

        out = [CurvePoint(t=p.t, v=_clamp01(rotated[i])) for i, p in enumerate(pts)]
        return PointsBaseCurve(points=out)

    def invert(self, curve: PointsBaseCurve) -> PointsBaseCurve:
        """Invert values: v -> 1 - v (time unchanged)."""
        out = [CurvePoint(t=p.t, v=_clamp01(1.0 - p.v)) for p in curve.points]
        return PointsBaseCurve(points=out)

    def clamp(
        self, curve: PointsBaseCurve, vmin: float = 0.0, vmax: float = 1.0
    ) -> PointsBaseCurve:
        """Clamp values into [vmin, vmax] then renormalize to [0,1] if desired later (MVP: just clamp)."""
        lo, hi = float(vmin), float(vmax)
        if hi < lo:
            raise ValueError("vmax must be >= vmin")
        out = []
        for p in curve.points:
            v = p.v
            if v < lo:
                v = lo
            elif v > hi:
                v = hi
            out.append(CurvePoint(t=p.t, v=_clamp01(v)))
        return PointsBaseCurve(points=out)

    def multiply(self, a: PointsBaseCurve, b: PointsBaseCurve) -> PointsBaseCurve:
        """
        Multiply two curves (envelope application).
        If grids differ, b is interpolated onto a's t grid.
        """
        out: list[CurvePoint] = []
        b_pts = b.points

        for p in a.points:
            vb = _interp_piecewise(b_pts, p.t) if b_pts else 1.0
            out.append(CurvePoint(t=p.t, v=_clamp01(p.v * vb)))

        return PointsBaseCurve(points=out)

    def simplify_near_collinear(
        self, curve: PointsBaseCurve, epsilon: float = 0.01
    ) -> PointsBaseCurve:
        """
        Drop points that lie nearly on the line between neighbors.
        Keeps first and last points.
        """
        pts = curve.points
        if len(pts) <= 2:
            return curve
        eps = float(epsilon)
        if eps < 0:
            raise ValueError("epsilon must be >= 0")

        kept: list[CurvePoint] = [pts[0]]

        def dist_to_line(p0: CurvePoint, p1: CurvePoint, p2: CurvePoint) -> float:
            # distance in v from p1 to line through p0->p2 at t1
            t0, v0 = p0.t, p0.v
            t1, v1 = p1.t, p1.v
            t2, v2 = p2.t, p2.v
            if t2 == t0:
                return abs(v1 - v2)
            u = (t1 - t0) / (t2 - t0)
            v_line = v0 + u * (v2 - v0)
            return abs(v1 - v_line)

        for i in range(1, len(pts) - 1):
            p0 = kept[-1]
            p1 = pts[i]
            p2 = pts[i + 1]
            if dist_to_line(p0, p1, p2) > eps:
                kept.append(p1)

        kept.append(pts[-1])
        return PointsBaseCurve(points=kept)
