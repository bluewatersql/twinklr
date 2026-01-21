"""Context classes and helper functions for effect handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureInstance
    from blinkb0t.core.domains.sequencing.moving_heads.boundary_enforcer import (
        BoundaryEnforcer,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Beat Alignment Helpers
# ═══════════════════════════════════════════════════════════════════════════


def get_beats_in_range(beats_s: list[float], start_ms: int, end_ms: int) -> list[int]:
    """Get beat times (in ms) within a time range.

    Args:
        beats_s: Beat times in seconds
        start_ms: Range start in milliseconds
        end_ms: Range end in milliseconds

    Returns:
        List of beat times in milliseconds within the range
    """
    start_s = start_ms / 1000.0
    end_s = end_ms / 1000.0
    return [int(b * 1000) for b in beats_s if start_s <= b < end_s]


def align_to_nearest_beat(time_ms: int, beats_s: list[float]) -> int:
    """Align a time to the nearest beat.

    Args:
        time_ms: Time in milliseconds to align
        beats_s: Beat times in seconds

    Returns:
        Time of nearest beat in milliseconds
    """
    if not beats_s:
        return time_ms

    time_s = time_ms / 1000.0
    nearest_beat = min(beats_s, key=lambda b: abs(b - time_s))
    return int(nearest_beat * 1000)


def get_beat_duration_ms(tempo_bpm: float) -> float:
    """Calculate duration of one beat in milliseconds.

    Args:
        tempo_bpm: Tempo in beats per minute

    Returns:
        Duration of one beat in milliseconds
    """
    return 60000.0 / max(1.0, tempo_bpm)


@dataclass
class SequencerContext:
    """Context information available to effect handlers.

    All fixture configuration is now accessed through the fixture instance.
    Backward compatibility properties provided for gradual migration.
    """

    # Core dependencies
    fixture: FixtureInstance
    boundaries: BoundaryEnforcer
    dmx_curve_mapper: DMXCurveMapper  # Shared curve mapper instance

    # Musical timing and song features
    beats_s: list[float]
    song_features: dict[str, Any]  # tempo_bpm, etc.

    def deg_to_pan_dmx(self, deg: float) -> int:
        """Convert pan degrees to DMX value.

        Delegates to BoundaryEnforcer for consistent clamping.

        Args:
            deg: Pan angle in degrees (relative to center/front)

        Returns:
            DMX value (0-255) clamped to limits
        """
        return self.boundaries.deg_to_pan_dmx(deg)

    def deg_to_tilt_dmx(self, deg: float) -> int:
        """Convert tilt degrees to DMX value.

        Delegates to BoundaryEnforcer for consistent clamping.

        Args:
            deg: Tilt angle in degrees (0 = horizontal, positive = up)

        Returns:
            DMX value (0-255) clamped to limits
        """
        return self.boundaries.deg_to_tilt_dmx(deg)

    # ═══════════════════════════════════════════════════════════════════════════
    # Backward Compatibility Properties
    # ═══════════════════════════════════════════════════════════════════════════
    # These properties provide backward compatibility for handlers that still
    # access these fields directly. They delegate to fixture.config.
    # TODO: Remove these once all handlers are updated to use fixture directly.

    @property
    def pan_range_deg(self) -> float:
        """Get pan range in degrees (backward compat)."""
        return self.fixture.config.pan_tilt_range.pan_range_deg

    @property
    def tilt_range_deg(self) -> float:
        """Get tilt range in degrees (backward compat)."""
        return self.fixture.config.pan_tilt_range.tilt_range_deg

    @property
    def pan_front_dmx(self) -> int:
        """Get front-facing pan DMX value (backward compat)."""
        return self.fixture.config.orientation.pan_front_dmx

    @property
    def tilt_zero_dmx(self) -> int:
        """Get horizontal tilt DMX value (backward compat)."""
        return self.fixture.config.orientation.tilt_zero_dmx

    @property
    def tilt_up_dmx(self) -> int:
        """Get upward tilt DMX value (backward compat)."""
        return self.fixture.config.orientation.tilt_up_dmx

    @property
    def pan_limits(self) -> tuple[int, int]:
        """Get effective pan limits (min, max) (backward compat)."""
        return self.boundaries.pan_limits

    @property
    def tilt_limits(self) -> tuple[int, int]:
        """Get tilt limits (min, max) (backward compat)."""
        return self.boundaries.tilt_limits


# Backward compatibility alias
BaseHandler = None  # Type stub for migration purposes
