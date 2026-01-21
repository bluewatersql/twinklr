"""Base classes for effect handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureInstance
    from blinkb0t.core.domains.sequencing.moving_heads.templates.boundary_enforcer import (
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


# Type alias for movement segments: (start_ms, end_ms, pan_dmx, tilt_dmx)
MoveSegment = tuple[int, int, int, int]


class EffectHandler:
    """Base class for movement pattern handlers.

    Each movement pattern (sweep_lr, circle, ballyhoo, etc.) is implemented
    as a separate handler subclass. This enables:
    - Modularity: Each pattern in its own file/class
    - Testability: Test patterns in isolation
    - Extensibility: Add new patterns without modifying core sequencer

    Handlers generate move_segments (time-sliced pan/tilt positions) which are
    then merged with dimmer patterns by the sequencer.
    """

    # Pattern identifier (must be overridden in subclasses)
    pattern_name: str = ""

    def can_handle(self, pattern: str) -> bool:
        """Check if this handler can handle the given pattern.

        Args:
            pattern: Pattern name from plan instruction

        Returns:
            True if this handler handles the pattern
        """
        return pattern == self.pattern_name

    def supports_value_curves(self) -> bool:
        """Whether this pattern supports value curve rendering.

        Patterns with smooth, continuous motion (sweep, circle, etc.)
        can use xLights native value curves. Patterns with discrete
        or random motion (ballyhoo, stab) cannot.

        Returns:
            True if pattern supports value_curve rendering mode
        """
        return False  # Override in subclasses that support curves

    def render(
        self,
        movement: dict[str, Any],
        context: SequencerContext,
        start_ms: int,
        end_ms: int,
        target: str,
        pan_center: int,
        tilt_center: int,
    ) -> list[MoveSegment]:
        """Generate movement segments for this pattern.

        Args:
            movement: Movement specification from plan instruction
            context: Sequencer context with config and state
            start_ms: Section start time in milliseconds
            end_ms: Section end time in milliseconds
            target: Target fixture name (e.g., "MH1")
            pan_center: Center pan DMX value for this fixture
            tilt_center: Center tilt DMX value for this fixture

        Returns:
            List of (start_ms, end_ms, pan_dmx, tilt_dmx) tuples

        Example:
            >>> handler = SweepLRHandler()
            >>> segments = handler.render(
            ...     movement={"amplitude_deg": 60, "steps": 12},
            ...     context=context,
            ...     start_ms=0,
            ...     end_ms=2000,
            ...     target="MH1",
            ...     pan_center=128,
            ...     tilt_center=96
            ... )
            >>> # Returns: [(0, 200, 100, 96), (200, 400, 120, 96), ...]
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement render()")
