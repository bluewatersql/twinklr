"""Phase Offset Calculator for template compilation.

This module provides functions to calculate per-fixture phase offsets
based on the PhaseOffset configuration in templates.
"""

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.sequencer.models.template import (
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

    Example:
        >>> result = PhaseOffsetResult(
        ...     offsets={"f1": 0.0, "f2": 0.25},
        ...     spread_bars=0.5,
        ...     wrap=True,
        ... )
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    offsets: dict[str, float] = Field(default_factory=dict)
    spread_bars: float = Field(default=0.0)
    wrap: bool = Field(default=True)

    def get_normalized(
        self,
        fixture_id: str,
        step_duration_bars: float,
        wrap: bool | None = None,
    ) -> float:
        """Get the normalized offset for a fixture.

        Args:
            fixture_id: The fixture ID.
            step_duration_bars: Duration of the step in bars.
            wrap: Whether to wrap. If None, uses the result's wrap setting.

        Returns:
            Normalized offset in [0, 1] range (or > 1 if no wrap).

        Raises:
            KeyError: If fixture_id not found.
        """
        offset_bars = self.offsets[fixture_id]
        should_wrap = self.wrap if wrap is None else wrap
        return calculate_normalized_offset(offset_bars, step_duration_bars, should_wrap)


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

    Example:
        >>> config = PhaseOffset(
        ...     mode=PhaseOffsetMode.GROUP_ORDER,
        ...     group="fronts",
        ...     spread_bars=1.0,
        ... )
        >>> result = calculate_fixture_offsets(config, ["f1", "f2", "f3", "f4"])
        >>> result.offsets["f2"]  # Second fixture gets 1/3 of spread
        0.333...
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


def calculate_normalized_offset(
    offset_bars: float,
    step_duration_bars: float,
    wrap: bool = True,
) -> float:
    """Convert bar offset to normalized offset [0, 1].

    Args:
        offset_bars: Offset in bars.
        step_duration_bars: Step duration in bars.
        wrap: If True, wrap offsets > 1.0 using modulo.

    Returns:
        Normalized offset.

    Example:
        >>> calculate_normalized_offset(0.5, 4.0)  # 0.5 bars in 4 bar step
        0.125
        >>> calculate_normalized_offset(5.0, 4.0, wrap=True)  # Wraps
        0.25
    """
    if step_duration_bars <= 0:
        return 0.0

    normalized = offset_bars / step_duration_bars

    if wrap:
        normalized = normalized % 1.0

    return normalized
