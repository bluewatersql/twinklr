"""XSQ adapter for converting FixtureSegments to EffectPlacement.

Handles conversion of compiled FixtureSegments to xLights EffectPlacement objects,
including resolving xLights model names and managing EffectDB entries.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from blinkb0t.core.formats.xlights.xsq.effect_placement import EffectPlacement
from blinkb0t.core.sequencer.moving_heads.export.dmx_settings_builder import (
    DmxSettingsBuilder,
)
from blinkb0t.core.utils.fixtures import build_semantic_groups

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures.groups import FixtureGroup
    from blinkb0t.core.config.fixtures.instances import FixtureInstance
    from blinkb0t.core.formats.xlights.models.xsq import XSequence
    from blinkb0t.core.sequencer.moving_heads.channels.state import FixtureSegment

logger = logging.getLogger(__name__)


class XsqAdapter:
    """Convert FixtureSegments to EffectPlacements for xLights.

    Handles:
    - Resolving xLights model names
    - Converting channel values to DMX settings strings
    - Adding settings to XSQ EffectDB
    - Creating EffectPlacement dataclasses with correct refs
    - Writing to groups when possible, individuals otherwise

    Example:
        >>> adapter = XsqAdapter()
        >>> placements = adapter.convert(segments, fixture_group, xsq)
    """

    def convert(
        self,
        segments: list[FixtureSegment],
        fixture_group: FixtureGroup,
        xsq: XSequence | None = None,
    ) -> list[EffectPlacement]:
        """Convert FixtureSegments to xLights EffectPlacement.

        Writes effects to either:
        - Group models (GROUP - MOVING HEADS, GROUP - MH LEFT, etc.) when semantic groups match
        - Individual fixture models (Dmx MH1, MH2, etc.) when no group match

        IMPORTANT: Never writes both group AND individual for the same fixtures at the same time.
        This follows the rule: if semantic group is mapped, render to group; otherwise explode to individuals.

        Args:
            segments: List of FixtureSegments to convert
            fixture_group: Fixture group for xLights model name resolution
            xsq: Optional XSequence object to add settings to EffectDB (required for DMX channel data)

        Returns:
            List of EffectPlacement objects (groups when possible, individuals otherwise)

        Example:
            >>> adapter = XsqAdapter()
            >>> placements = adapter.convert(segments, fixture_group, sequence)
        """
        placements = []
        xlights_mapping = fixture_group.get_xlights_mapping()

        # 1. Try to create group effects first
        group_placements, covered_fixture_ids = self._write_group_effects(
            segments, xlights_mapping, fixture_group, xsq
        )
        placements.extend(group_placements)

        # 2. Write individual fixture effects ONLY for fixtures NOT covered by groups
        uncovered_segments = [s for s in segments if s.fixture_id not in covered_fixture_ids]
        if uncovered_segments:
            individual_placements = self._write_individual_effects(
                uncovered_segments, xlights_mapping, fixture_group, xsq
            )
            placements.extend(individual_placements)

        logger.debug(
            f"Converted {len(segments)} segments to {len(placements)} placements "
            f"({len(group_placements)} group, {len(placements) - len(group_placements)} individual, "
            f"{len(covered_fixture_ids)} fixtures covered by groups)"
        )

        return placements

    def _write_individual_effects(
        self,
        segments: list[FixtureSegment],
        xlights_mapping: dict[str, str],
        fixture_group: FixtureGroup,
        xsq: XSequence | None,
    ) -> list[EffectPlacement]:
        """Write effects to individual fixture models.

        Args:
            segments: FixtureSegments to write
            xlights_mapping: Fixture ID -> xLights model name mapping
            fixture_group: Fixture group
            xsq: XSequence object for EffectDB

        Returns:
            List of EffectPlacement for individual fixtures
        """
        placements = []

        for segment in segments:
            # Skip segments with no channels
            if not segment.channels:
                logger.debug(f"Skipping empty segment for {segment.fixture_id}")
                continue

            # Get xLights model name for this fixture
            xlights_name = xlights_mapping.get(segment.fixture_id)
            if not xlights_name:
                logger.warning(f"No xLights mapping for {segment.fixture_id}, skipping")
                continue

            # Get fixture instance for DMX mapping
            fixture = fixture_group.get_fixture(segment.fixture_id)
            if not fixture:
                logger.warning(f"Fixture {segment.fixture_id} not found in group, skipping")
                continue

            # Convert segment to DMX settings string and add to EffectDB
            ref = 0
            if xsq is not None:
                settings_str = self._segment_to_settings(segment, fixture)
                ref = xsq.append_effectdb(settings_str)
            else:
                logger.debug("No XSQ provided, using ref=0 (no DMX channel data)")

            # Create EffectPlacement
            placements.append(
                EffectPlacement(
                    element_name=xlights_name,
                    effect_name="DMX",
                    start_ms=segment.t0_ms,
                    end_ms=segment.t1_ms,
                    effect_label="",  # Could add metadata here
                    ref=ref,
                    palette=0,
                )
            )

        return placements

    def _write_group_effects(
        self,
        segments: list[FixtureSegment],
        xlights_mapping: dict[str, str],
        fixture_group: FixtureGroup,
        xsq: XSequence | None,
    ) -> tuple[list[EffectPlacement], set[str]]:
        """Write effects to group models when possible.

        Args:
            segments: FixtureSegments to write
            xlights_mapping: Fixture ID -> xLights model name mapping
            fixture_group: Fixture group
            xsq: XSequence object for EffectDB

        Returns:
            Tuple of (EffectPlacement list, set of covered fixture IDs)
        """
        placements = []
        covered_fixture_ids: set[str] = set()

        # Build semantic groups from fixture IDs
        all_fixture_ids = [f.fixture_id for f in fixture_group.fixtures]
        semantic_groups = build_semantic_groups(all_fixture_ids)

        # Group segments by time range
        # Key: (t0_ms, t1_ms), Value: list of segments
        time_segments: dict[tuple[int, int], list[FixtureSegment]] = defaultdict(list)
        for segment in segments:
            time_segments[(segment.t0_ms, segment.t1_ms)].append(segment)

        # For each time range, try to form group effects
        for (t0_ms, t1_ms), time_range_segments in time_segments.items():
            # Get fixture IDs in this time range
            fixture_ids_in_range = {s.fixture_id for s in time_range_segments}

            # Check if any semantic group is fully covered
            for group_name, group_fixture_ids in semantic_groups.items():
                if set(group_fixture_ids).issubset(fixture_ids_in_range):
                    # This semantic group is fully covered at this time
                    # Create a group effect if the group has an xLights mapping

                    # Determine group xLights name (e.g., "GROUP - MH LEFT")
                    # This is a convention - might need to be configurable
                    group_xlights_name = f"GROUP - {group_name.upper()}"

                    # Check if all fixtures in the group have identical channel settings
                    # (simplification: we'll write the first fixture's settings for the group)
                    group_segments = [
                        s for s in time_range_segments if s.fixture_id in group_fixture_ids
                    ]

                    if not group_segments:
                        continue

                    # Use first segment as representative (assumes identical settings)
                    representative_segment = group_segments[0]
                    representative_fixture = fixture_group.get_fixture(
                        representative_segment.fixture_id
                    )

                    if not representative_fixture:
                        continue

                    # Convert to DMX settings string
                    ref = 0
                    if xsq is not None:
                        settings_str = self._segment_to_settings(
                            representative_segment, representative_fixture
                        )
                        ref = xsq.append_effectdb(settings_str)

                    # Create group effect
                    placements.append(
                        EffectPlacement(
                            element_name=group_xlights_name,
                            effect_name="DMX",
                            start_ms=t0_ms,
                            end_ms=t1_ms,
                            effect_label="",
                            ref=ref,
                            palette=0,
                        )
                    )

                    # Mark these fixtures as covered
                    covered_fixture_ids.update(group_fixture_ids)

                    logger.debug(
                        f"Created group effect for {group_name} "
                        f"({len(group_fixture_ids)} fixtures) at {t0_ms}-{t1_ms}ms"
                    )

        return placements, covered_fixture_ids

    def _segment_to_settings(self, segment: FixtureSegment, fixture: FixtureInstance) -> str:
        """Convert FixtureSegment to DMX settings string.

        Args:
            segment: FixtureSegment with channel values
            fixture: Fixture instance for DMX mapping

        Returns:
            xLights DMX effect settings string
        """
        builder = DmxSettingsBuilder(fixture)
        return builder.build_settings_string(segment)
