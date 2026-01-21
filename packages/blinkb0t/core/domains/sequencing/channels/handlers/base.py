"""Base protocol for channel handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup
    from blinkb0t.core.domains.sequencing.models.channels import ChannelEffect


class ChannelHandler(Protocol):
    """Protocol for channel handlers.

    All channel handlers must implement this interface.
    """

    def render(
        self,
        channel_value: str,
        fixtures: FixtureGroup,
        start_time_ms: int,
        end_time_ms: int,
        beat_times_ms: list[int] | None = None,
    ) -> list[ChannelEffect]:
        """Render channel effects for fixtures.

        Args:
            channel_value: Channel specification (e.g., "strobe_fast", "blue", "stars")
            fixtures: Fixture group to render for
            start_time_ms: Effect start time
            end_time_ms: Effect end time
            beat_times_ms: Optional beat times for dynamic patterns (e.g., pulse)

        Returns:
            List of ChannelEffect objects (one per fixture)
        """
        ...
