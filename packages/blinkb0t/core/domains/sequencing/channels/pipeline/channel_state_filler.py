"""Channel state filling for complete DMX state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.channels.state import ChannelState
from blinkb0t.core.domains.sequencing.models.channels import DmxEffect

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureInstance
    from blinkb0t.core.domains.sequencing.channels.pipeline.effect_splitter import TimeSegment

logger = logging.getLogger(__name__)


class ChannelStateFiller:
    """Fill all channels with explicit values.

    Ensures every DMX channel has an explicit value at each time boundary.
    Missing channels are filled with DMX 0 for active effects, or soft home
    for gaps.

    Example:
        >>> segments = [TimeSegment(start_ms=100, end_ms=200, effects=[...])]
        >>> filler = ChannelStateFiller()
        >>> dmx_effects = filler.fill(segments, fixture)
        >>> # All channels explicitly set in dmx_effects
    """

    ALL_CHANNELS = ["pan", "tilt", "dimmer", "shutter", "color", "gobo"]

    def fill(self, segments: list[TimeSegment], fixture: FixtureInstance) -> list[DmxEffect]:
        """Fill all channels for fixture across segments.

        Args:
            segments: Time segments with active effects
            fixture: Fixture instance

        Returns:
            List of DmxEffect with complete channel state
        """
        dmx_effects = []

        for segment in segments:
            if not segment.effects:
                # Gap segment - will be handled by GapFiller
                continue

            # Collect all channels from active effects
            channels = {}
            for effect in segment.effects:
                logger.info(
                    f"[FILLER_TRACE] Processing effect with channels: {list(effect.channels.keys())}"
                )
                for channel_name, channel_state in effect.channels.items():
                    # Only include channels if fixture has them
                    if self._fixture_has_channel(fixture, channel_name):
                        logger.info(
                            f"[FILLER_TRACE] Adding channel {channel_name}, has curves: {list(channel_state.value_curves.keys())}"
                        )
                        channels[channel_name] = channel_state

            logger.info(
                f"[FILLER_TRACE] After collecting, channels dict has: {list(channels.keys())}"
            )

            # Fill missing channels with DMX 0
            for channel_name in self.ALL_CHANNELS:
                if channel_name not in channels and self._fixture_has_channel(
                    fixture, channel_name
                ):
                    channels[channel_name] = self._create_zero_channel_state(fixture, channel_name)

            if channels:
                # Check if any source effect in this segment is a gap fill
                is_gap_fill = any(
                    effect.metadata.get("is_gap_fill", False) for effect in segment.effects
                )

                metadata: dict[str, str | bool] = {
                    "type": "filled",
                    "source": "channel_state_filler",
                    "source_label": "gap_fill" if is_gap_fill else "effect",
                }
                if is_gap_fill:
                    metadata["is_gap_fill"] = True

                dmx_effects.append(
                    DmxEffect(
                        fixture_id=fixture.fixture_id,
                        start_ms=segment.start_ms,
                        end_ms=segment.end_ms,
                        channels=channels,
                        metadata=metadata,
                    )
                )

        logger.debug(f"Created {len(dmx_effects)} filled DMX effects for {fixture.fixture_id}")

        return dmx_effects

    def _fixture_has_channel(self, fixture: FixtureInstance, channel_name: str) -> bool:
        """Check if fixture has a specific channel."""
        dmx_mapping = fixture.config.dmx_mapping

        channel_map = {
            "pan": dmx_mapping.pan,
            "tilt": dmx_mapping.tilt,
            "dimmer": dmx_mapping.dimmer,
            "shutter": dmx_mapping.shutter,
            "color": dmx_mapping.color,
            "gobo": dmx_mapping.gobo,
        }

        channel_num = channel_map.get(channel_name)
        return channel_num is not None

    def _create_zero_channel_state(
        self, fixture: FixtureInstance, channel_name: str
    ) -> ChannelState:
        """Create ChannelState with DMX 0."""
        state = ChannelState(fixture=fixture)
        state.set_channel(channel_name, 0)
        return state
