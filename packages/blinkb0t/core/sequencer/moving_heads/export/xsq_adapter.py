"""XSQ adapter for converting FixtureSegments to EffectPlacement.

Handles conversion of compiled FixtureSegments to xLights EffectPlacement objects,
including resolving xLights model names and managing EffectDB entries.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from blinkb0t.core.formats.xlights.sequence.models.effect_placement import EffectPlacement
from blinkb0t.core.sequencer.moving_heads.export.dmx_settings_builder import (
    DmxSettingsBuilder,
)
from blinkb0t.core.utils.fixtures import build_semantic_groups

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures.groups import FixtureGroup
    from blinkb0t.core.config.fixtures.instances import FixtureInstance
    from blinkb0t.core.formats.xlights.sequence.models.xsq import XSequence
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
        # Returns segments that were actually grouped (not just fixture IDs)
        group_placements, grouped_segments = self._write_group_effects(
            segments, xlights_mapping, fixture_group, xsq
        )
        placements.extend(group_placements)

        # 2. Write individual fixture effects for segments NOT grouped
        # Convert grouped segments to a set of (fixture_id, t0_ms, t1_ms) for fast lookup
        grouped_keys = {(s.fixture_id, s.t0_ms, s.t1_ms) for s in grouped_segments}
        ungrouped_segments = [
            s for s in segments if (s.fixture_id, s.t0_ms, s.t1_ms) not in grouped_keys
        ]

        if ungrouped_segments:
            individual_placements = self._write_individual_effects(
                ungrouped_segments, xlights_mapping, fixture_group, xsq
            )
            placements.extend(individual_placements)

        logger.debug(
            f"Converted {len(segments)} segments to {len(placements)} placements "
            f"({len(group_placements)} group, {len(placements) - len(group_placements)} individual, "
            f"{len(grouped_segments)} segments grouped)"
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

        # Sort segments by fixture ID and start time to avoid overlapping effects
        sorted_segments = sorted(segments, key=lambda s: (s.fixture_id, s.t0_ms))

        for segment in sorted_segments:
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
                    effect_label=segment.metatag,
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
    ) -> tuple[list[EffectPlacement], list[FixtureSegment]]:
        """Write effects to group models when possible.

        Args:
            segments: FixtureSegments to write
            xlights_mapping: Fixture ID -> xLights model name mapping
            fixture_group: Fixture group
            xsq: XSequence object for EffectDB

        Returns:
            Tuple of (EffectPlacement list, list of grouped segments)
        """
        placements = []
        grouped_segments: list[FixtureSegment] = []

        # Build semantic groups ONLY for groups that have xLights mappings
        # This prevents unnecessary processing of unmapped semantic groups
        all_fixture_ids = [f.fixture_id for f in fixture_group.fixtures]
        all_possible_groups = build_semantic_groups(all_fixture_ids)

        # Filter to only groups that have xLights mappings
        mapped_semantic_groups = {
            name: fixture_ids
            for name, fixture_ids in all_possible_groups.items()
            if name in fixture_group.xlights_semantic_groups
        }

        # Group segments by time range
        # Key: (t0_ms, t1_ms), Value: list of segments
        time_segments: dict[tuple[int, int], list[FixtureSegment]] = defaultdict(list)
        for segment in segments:
            time_segments[(segment.t0_ms, segment.t1_ms)].append(segment)

        # For each time range, try to form group effects
        for (t0_ms, t1_ms), time_range_segments in time_segments.items():
            # Get fixture IDs in this time range
            fixture_ids_in_range = {s.fixture_id for s in time_range_segments}

            # Find ALL semantic groups that are fully covered
            # Then pick the best one based on priority:
            # 1. Largest group (ALL > LEFT/RIGHT > ODD/EVEN)
            # 2. If same size, prefer position-based (LEFT/RIGHT) over parity-based (ODD/EVEN)
            covered_groups = []
            for group_name, group_fixture_ids in mapped_semantic_groups.items():
                if set(group_fixture_ids).issubset(fixture_ids_in_range):
                    covered_groups.append((group_name, group_fixture_ids, len(group_fixture_ids)))

            # Sort by: size descending, then position groups before parity groups
            # LEFT/RIGHT/CENTER/OUTER are position-based
            # ODD/EVEN are parity-based
            def group_priority(item):
                name, _, size = item
                position_groups = {"ALL", "LEFT", "RIGHT", "CENTER", "OUTER", "INNER"}
                is_position = name in position_groups
                return (
                    -size,
                    0 if is_position else 1,
                    name,
                )  # Larger size first, position before parity, alphabetical

            covered_groups.sort(key=group_priority)

            # Use the best group (highest priority)
            best_group = covered_groups[0] if covered_groups else None

            # Write effect for the best matching group
            if best_group is not None:
                group_name, group_fixture_ids, _ = best_group

                # Look up the actual xLights group name
                group_xlights_name = fixture_group.xlights_semantic_groups[group_name]

                # Get all segments for this group
                group_segments = [
                    s for s in time_range_segments if s.fixture_id in group_fixture_ids
                ]

                # All must be true to allow grouping:
                # 1. There are segments in the group
                # 2. All segments allow grouping
                # 3. All segments have identical curves
                if (
                    not group_segments
                    or not all(seg.allow_grouping for seg in group_segments)
                    or not self._segments_have_identical_curves(group_segments)
                ):
                    continue

                # Use first segment as representative (verified identical above)
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
                        effect_label=representative_segment.metatag,
                        ref=ref,
                        palette=0,
                    )
                )

                # Track which segments were grouped
                grouped_segments.extend(group_segments)

                logger.debug(
                    f"Created group effect for {group_name} "
                    f"({len(group_fixture_ids)} fixtures) at {t0_ms}-{t1_ms}ms"
                )

        return placements, grouped_segments

    def _segments_have_identical_curves(self, segments: list[FixtureSegment]) -> bool:
        """Check if all segments have identical channel curves.

        Args:
            segments: List of segments to compare

        Returns:
            True if all segments have identical channel values/curves, False otherwise
        """
        if len(segments) <= 1:
            return True

        # Use first segment as reference
        reference = segments[0]

        # Compare all other segments to the reference
        for segment in segments[1:]:
            # Check if they have the same channels
            if set(segment.channels.keys()) != set(reference.channels.keys()):
                return False

            # Check if channel values match
            for channel_name, channel_value in segment.channels.items():
                ref_channel_value = reference.channels[channel_name]

                # Compare static DMX values
                if channel_value.static_dmx != ref_channel_value.static_dmx:
                    return False

                # Compare curve (the curve type/reference)
                if channel_value.curve != ref_channel_value.curve:
                    return False

                # Compare value_points (the actual curve data - KEY for phase offsets!)
                if channel_value.value_points != ref_channel_value.value_points:
                    return False

                # Compare offset-centered parameters
                if channel_value.offset_centered != ref_channel_value.offset_centered:
                    return False
                if channel_value.base_dmx != ref_channel_value.base_dmx:
                    return False
                if channel_value.amplitude_dmx != ref_channel_value.amplitude_dmx:
                    return False

                # Compare clamping bounds
                if channel_value.clamp_min != ref_channel_value.clamp_min:
                    return False
                if channel_value.clamp_max != ref_channel_value.clamp_max:
                    return False

        return True

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
