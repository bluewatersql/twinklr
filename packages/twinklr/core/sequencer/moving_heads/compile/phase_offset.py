"""Phase Offset Calculator for template compilation.

This module provides functions to calculate per-fixture phase offsets
based on the PhaseOffset configuration in templates.
"""

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.models.template import (
    PhaseOffset,
    PhaseOffsetMode,
)


class PhaseOffsetResult(BaseModel):
    """Result of phase offset calculation.

    Stores the calculated offset for each fixture in bars, along with
    the configuration settings.

    Attributes:
        offsets: Mapping of fixture_id to offset in bars.
        spread_bars: The spread value from the configuration.
        wrap: Whether offsets should wrap at cycle boundaries.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    offsets: dict[str, float] = Field(default_factory=dict)
    spread_bars: float = Field(default=0.0)
    wrap: bool = Field(default=True)


def calculate_fixture_offsets(
    config: PhaseOffset,
    fixture_ids: list[str],
) -> PhaseOffsetResult:
    """Calculate phase offsets for each fixture.

    Based on the PhaseOffset configuration, determines the phase
    offset in bars for each fixture in the list.

    Args:
        config: The PhaseOffset configuration.
        fixture_ids: List of fixture IDs in order.

    Returns:
        PhaseOffsetResult with offset for each fixture.
    """
    if not fixture_ids:
        return PhaseOffsetResult(
            offsets={},
            spread_bars=config.spread_bars,
            wrap=config.wrap,
        )

    if config.mode == PhaseOffsetMode.NONE:
        # All fixtures get zero offset
        offsets = dict.fromkeys(fixture_ids, 0.0)
        return PhaseOffsetResult(
            offsets=offsets,
            spread_bars=0.0,
            wrap=config.wrap,
        )

    # GROUP_ORDER mode with LINEAR distribution
    return _calculate_linear_offsets(config, fixture_ids)


def _calculate_linear_offsets(
    config: PhaseOffset,
    fixture_ids: list[str],
) -> PhaseOffsetResult:
    """Calculate linear phase offsets.

    Distributes offsets evenly across fixtures from 0 to spread_bars.

    Args:
        config: The PhaseOffset configuration.
        fixture_ids: List of fixture IDs in order.

    Returns:
        PhaseOffsetResult with linearly distributed offsets.
    """
    n = len(fixture_ids)
    offsets: dict[str, float] = {}

    if n == 1:
        # Single fixture gets zero offset
        offsets[fixture_ids[0]] = 0.0
    else:
        # Distribute linearly from 0 to spread_bars
        for i, fixture_id in enumerate(fixture_ids):
            # i ranges from 0 to n-1
            # offset = (i / (n-1)) * spread_bars
            offsets[fixture_id] = (i / (n - 1)) * config.spread_bars

    return PhaseOffsetResult(
        offsets=offsets,
        spread_bars=config.spread_bars,
        wrap=config.wrap,
    )
