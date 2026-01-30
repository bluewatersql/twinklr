"""Ramer-Douglas-Peucker curve simplification.

This module provides functions for simplifying curves by removing
points that don't contribute significantly to the overall shape.
"""

import math

from twinklr.core.curves.models import CurvePoint


def perpendicular_distance(
    point: CurvePoint,
    line_start: CurvePoint,
    line_end: CurvePoint,
    scale_t: float = 1.0,
    scale_v: float = 1.0,
) -> float:
    """Calculate perpendicular distance from point to line in scaled space.

    Uses the line segment defined by line_start and line_end.
    If the perpendicular from the point falls outside the segment,
    returns the distance to the nearest endpoint.

    Args:
        point: The point to measure from.
        line_start: Start of the line segment.
        line_end: End of the line segment.
        scale_t: Scaling factor for t (time) dimension.
        scale_v: Scaling factor for v (value) dimension.

    Returns:
        Perpendicular distance in scaled space.

    Example:
        >>> p = CurvePoint(t=0.5, v=0.5)
        >>> a = CurvePoint(t=0.0, v=0.0)
        >>> b = CurvePoint(t=1.0, v=0.0)
        >>> perpendicular_distance(p, a, b)
        0.5
    """
    # Scale coordinates
    px, py = point.t * scale_t, point.v * scale_v
    ax, ay = line_start.t * scale_t, line_start.v * scale_v
    bx, by = line_end.t * scale_t, line_end.v * scale_v

    # Vector from a to b
    abx, aby = bx - ax, by - ay
    ab_len_sq = abx * abx + aby * aby

    # Degenerate case: line_start == line_end
    if ab_len_sq < 1e-10:
        return math.sqrt((px - ax) ** 2 + (py - ay) ** 2)

    # Project point onto line, find parameter t
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))  # Clamp to segment

    # Find closest point on segment
    cx, cy = ax + t * abx, ay + t * aby

    return math.sqrt((px - cx) ** 2 + (py - cy) ** 2)


def simplify_rdp(
    points: list[CurvePoint],
    epsilon: float = 1.0 / 255.0,
    scale_t: float = 1.0,
    scale_v: float = 1.0,
) -> list[CurvePoint]:
    """Simplify curve using Ramer-Douglas-Peucker algorithm.

    Recursively simplifies a curve by removing points that are within
    epsilon distance of the line connecting their neighbors.

    Args:
        points: List of CurvePoints to simplify.
        epsilon: Maximum perpendicular distance tolerance.
            Default is 1/255 (1 DMX unit when scaled).
        scale_t: Scaling factor for t dimension.
        scale_v: Scaling factor for v dimension.

    Returns:
        Simplified list of CurvePoints with endpoints preserved.

    Example:
        >>> points = [CurvePoint(t=i/4, v=i/4) for i in range(5)]
        >>> result = simplify_rdp(points, epsilon=0.01)
        >>> len(result)  # Only endpoints remain (linear)
        2
    """
    if len(points) <= 2:
        return list(points)

    def rdp_recursive(start_idx: int, end_idx: int) -> list[int]:
        """Recursively find points to keep between start and end indices."""
        if end_idx - start_idx <= 1:
            return []

        max_dist = 0.0
        max_idx = start_idx

        # Find point with maximum distance from line
        for i in range(start_idx + 1, end_idx):
            dist = perpendicular_distance(
                points[i],
                points[start_idx],
                points[end_idx],
                scale_t,
                scale_v,
            )
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        # If max distance exceeds epsilon, keep that point and recurse
        if max_dist > epsilon:
            left = rdp_recursive(start_idx, max_idx)
            right = rdp_recursive(max_idx, end_idx)
            return left + [max_idx] + right
        else:
            return []

    # Get indices to keep
    keep_indices = [0] + rdp_recursive(0, len(points) - 1) + [len(points) - 1]
    keep_indices = sorted(set(keep_indices))

    return [points[i] for i in keep_indices]
