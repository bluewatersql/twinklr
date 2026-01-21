"""Gap filling with soft home position."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.config.fixtures import Pose as ConfigPose
from blinkb0t.core.domains.sequencing.channels.state import ChannelState
from blinkb0t.core.domains.sequencing.models.channels import DmxEffect
from blinkb0t.core.domains.sequencing.models.poses import PoseID
from blinkb0t.core.domains.sequencing.poses.standards import STANDARD_POSES

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureInstance
    from blinkb0t.core.domains.sequencing.channels.pipeline.gap_detector import Gap

logger = logging.getLogger(__name__)


class GapFiller:
    """Fill gaps with soft home position.

    Creates DMX effects for gaps that hold fixtures at soft home position
    (center/forward) with shutter closed and dimmer off.

    Uses PoseID.SOFT_HOME which maps to Pose(pan_deg=0.0, tilt_deg=0.0).

    Example:
        >>> gaps = [Gap(start_ms=100, end_ms=200)]
        >>> filler = GapFiller()
        >>> gap_effects = filler.fill(gaps, fixture)
        >>> # gap_effects contain soft home position (0,0) with shutter/dimmer off
    """

    def fill(self, gaps: list[Gap], fixture: FixtureInstance) -> list[DmxEffect]:
        """Fill gaps with soft home position effects.

        Args:
            gaps: List of gaps to fill
            fixture: Fixture instance

        Returns:
            List of DmxEffect with soft home position
        """
        gap_effects = []

        for gap in gaps:
            # Get soft home pose (0°, 0°) from domain-driven pose system
            domain_pose = STANDARD_POSES[PoseID.SOFT_HOME]

            # Convert to config Pose type for DMX conversion
            config_pose = ConfigPose(pan_deg=domain_pose.pan_deg, tilt_deg=domain_pose.tilt_deg)

            # Convert to DMX
            pan_dmx, tilt_dmx = fixture.config.degrees_to_dmx(config_pose)

            # Create channel states
            channels = {}

            # Pan/tilt (always present)
            pan_state = ChannelState(fixture=fixture)
            pan_state.set_channel("pan", pan_dmx)
            channels["pan"] = pan_state

            tilt_state = ChannelState(fixture=fixture)
            tilt_state.set_channel("tilt", tilt_dmx)
            channels["tilt"] = tilt_state

            # Add shutter (closed) if fixture has it
            if fixture.config.dmx_mapping.shutter is not None:
                shutter_state = ChannelState(fixture=fixture)
                shutter_state.set_channel("shutter", 0)  # Closed
                channels["shutter"] = shutter_state

            # Add dimmer (off) if fixture has it
            if fixture.config.dmx_mapping.dimmer is not None:
                dimmer_state = ChannelState(fixture=fixture)
                dimmer_state.set_channel("dimmer", 0)  # Off
                channels["dimmer"] = dimmer_state

            # Add color (white/open) if fixture has it
            if fixture.config.dmx_mapping.color is not None:
                color_state = ChannelState(fixture=fixture)
                color_state.set_channel("color", 0)  # White/open
                channels["color"] = color_state

            # Mark this as a gap fill effect for semantic group aggregation
            metadata = {"type": "gap_fill", "source": "gap_filler", "is_gap_fill": True}

            # Add gobo (open) if fixture has it
            if fixture.config.dmx_mapping.gobo is not None:
                gobo_state = ChannelState(fixture=fixture)
                gobo_state.set_channel("gobo", 0)  # Open
                channels["gobo"] = gobo_state

            gap_effects.append(
                DmxEffect(
                    fixture_id=fixture.fixture_id,
                    start_ms=gap.start_ms,
                    end_ms=gap.end_ms,
                    channels=channels,
                    metadata=metadata,
                )
            )

        logger.debug(f"Filled {len(gaps)} gaps for {fixture.fixture_id}")

        return gap_effects
