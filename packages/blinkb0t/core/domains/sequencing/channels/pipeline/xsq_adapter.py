"""XSQ adapter for converting DMX effects to EffectPlacement."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.channels.pipeline.dmx_settings_builder import (
    DmxSettingsBuilder,
)
from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement
from blinkb0t.core.utils.fixtures import (
    build_semantic_groups,
)  # Direct import to avoid circular dependency

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup
    from blinkb0t.core.domains.sequencing.models.channels import DmxEffect
    from blinkb0t.core.domains.sequencing.models.xsq import XSequence

logger = logging.getLogger(__name__)


class XsqAdapter:
    """Convert DmxEffect to EffectPlacement for xLights.

    Handles:
    - Resolving xLights model names
    - Converting channel states to DMX settings strings
    - Adding settings to XSQ EffectDB
    - Creating EffectPlacement dataclasses with correct refs

    Example:
        >>> adapter = XsqAdapter()
        >>> placements = adapter.convert(dmx_effects, fixtures, xsq)
    """

    def convert(
        self,
        dmx_effects: list[DmxEffect],
        fixtures: FixtureGroup,
        xsq: XSequence | None = None,
    ) -> list[EffectPlacement]:
        """Convert DMX effects to xLights EffectPlacement.

        Writes effects to either:
        - Group models (GROUP - MOVING HEADS, GROUP - MH LEFT, etc.) when semantic groups match
        - Individual fixture models (Dmx MH1, MH2, etc.) when no group match

        IMPORTANT: Never writes both group AND individual for the same fixtures at the same time.
        This follows the rule: if semantic group is mapped, render to group; otherwise explode to individuals.

        Args:
            dmx_effects: List of DMX effects
            fixtures: Fixture group for xLights model name resolution
            xsq: Optional XSequence object to add settings to EffectDB (required for DMX channel data)

        Returns:
            List of EffectPlacement objects (groups when possible, individuals otherwise)

        Example:
            >>> adapter = XsqAdapter()
            >>> placements = adapter.convert(dmx_effects, fixtures, sequence)
        """
        placements = []
        xlights_mapping = fixtures.get_xlights_mapping()

        # 1. Try to create group effects first
        group_placements, covered_effects = self._write_group_effects(
            dmx_effects, xlights_mapping, fixtures, xsq
        )
        placements.extend(group_placements)

        # 2. Write individual fixture effects ONLY for effects NOT covered by groups
        uncovered_effects = [e for e in dmx_effects if e not in covered_effects]
        if uncovered_effects:
            individual_placements = self._write_individual_effects(
                uncovered_effects, xlights_mapping, fixtures, xsq
            )
            placements.extend(individual_placements)

        logger.debug(
            f"Converted {len(dmx_effects)} DMX effects to {len(placements)} placements "
            f"({len(group_placements)} group, {len(placements) - len(group_placements)} individual, "
            f"{len(covered_effects)} effects covered by groups)"
        )

        return placements

    def _write_individual_effects(
        self,
        dmx_effects: list[DmxEffect],
        xlights_mapping: dict[str, str],
        fixtures: FixtureGroup,
        xsq: XSequence | None,
    ) -> list[EffectPlacement]:
        """Write effects to individual fixture models.

        Args:
            dmx_effects: DMX effects to write
            xlights_mapping: Fixture ID -> xLights model name mapping
            fixtures: Fixture group
            xsq: XSequence object for EffectDB

        Returns:
            List of EffectPlacement for individual fixtures
        """
        placements = []

        for dmx_effect in dmx_effects:
            # Skip effects with no channel states
            if not dmx_effect.channels:
                logger.debug(f"Skipping empty effect for {dmx_effect.fixture_id}")
                continue

            # Get xLights model name for this fixture
            xlights_name = xlights_mapping.get(dmx_effect.fixture_id)
            if not xlights_name:
                logger.warning(f"No xLights mapping for {dmx_effect.fixture_id}, skipping")
                continue

            # Convert channel states to DMX settings string and add to EffectDB
            ref = 0
            if xsq is not None:
                settings_str = self._channel_states_to_settings(dmx_effect, fixtures)
                ref = xsq.append_effectdb(settings_str)
            else:
                logger.debug("No XSQ provided, using ref=0 (no DMX channel data)")

            # Create EffectPlacement with source label for debugging
            source_label = dmx_effect.metadata.get("source_label", "")
            placements.append(
                EffectPlacement(
                    element_name=xlights_name,
                    effect_name="DMX",
                    start_ms=dmx_effect.start_ms,
                    end_ms=dmx_effect.end_ms,
                    effect_label=source_label,
                    ref=ref,
                    palette=0,
                )
            )

        return placements

    def _write_group_effects(
        self,
        dmx_effects: list[DmxEffect],
        xlights_mapping: dict[str, str],
        fixtures: FixtureGroup,
        xsq: XSequence | None,
    ) -> tuple[list[EffectPlacement], list[DmxEffect]]:
        """Aggregate effects by timing and write to group models.

        Groups effects by (start_ms, end_ms) and checks which semantic groups
        are fully covered. Writes effects to those group models.

        Args:
            dmx_effects: DMX effects to aggregate
            xlights_mapping: Group name -> xLights model name mapping
            fixtures: Fixture group
            xsq: XSequence object for EffectDB

        Returns:
            Tuple of (list of EffectPlacement for group models, list of effects covered by groups)
        """
        if not dmx_effects:
            return [], []

        placements = []
        covered_effects: list[DmxEffect] = []

        # Group effects by timing
        timing_groups: dict[tuple[int, int], list[DmxEffect]] = defaultdict(list)
        for effect in dmx_effects:
            timing_groups[(effect.start_ms, effect.end_ms)].append(effect)

        # Build semantic groups from fixture IDs
        fixture_ids = [f.fixture_id for f in fixtures.fixtures]
        semantic_groups = build_semantic_groups(fixture_ids)

        # For each unique time range, check for group coverage
        for (start_ms, end_ms), effects in timing_groups.items():
            # Filter out gap fills and transitions for semantic group matching
            # These effects bridge between sections and should remain on individual fixture models
            non_aggregatable_effects = [
                e
                for e in effects
                if not e.metadata.get("is_gap_fill", False)
                and e.metadata.get("type") != "transition"
            ]

            fixture_ids_in_effects = {e.fixture_id for e in non_aggregatable_effects}

            # Track if we created a group for this timing window
            group_created = False

            # Check for full group coverage (ALL)
            # Only aggregate actual section effects, not transitions or gap fills
            # IMPORTANT: Only create group effects when there are 2+ fixtures
            # Single fixture effects should always be rendered individually
            if (
                len(fixture_ids_in_effects) == len(fixtures.fixtures)
                and len(fixtures.fixtures) >= 2
            ):
                group_name = xlights_mapping.get("ALL")
                if group_name and non_aggregatable_effects:
                    # Use first aggregatable effect's channels as representative
                    representative_effect = non_aggregatable_effects[0]
                    # Skip if representative effect has no channel states
                    if representative_effect.channels:
                        placement = self._create_group_placement(
                            group_name, representative_effect, start_ms, end_ms, fixtures, xsq
                        )
                        if placement:
                            placements.append(placement)
                            covered_effects.extend(effects)  # Mark ALL effects as covered
                            group_created = True
                            logger.debug(f"Created group effect for ALL: {group_name}")
                    else:
                        logger.debug(
                            f"Skipping empty group effect for ALL at {start_ms}-{end_ms}ms"
                        )

            # Check for semantic group coverage (LEFT, RIGHT, ODD, EVEN, etc.)
            # Only if we didn't already create an ALL group
            if not group_created:
                for sem_name, sem_fixture_ids in semantic_groups.items():
                    if sem_name == "ALL":
                        continue  # Already handled above

                    # Check if this timing group exactly matches the semantic group
                    # Use non-gap effects only for matching
                    # IMPORTANT: Only create group effects when there are 2+ fixtures
                    sem_set = set(sem_fixture_ids)
                    if sem_set == fixture_ids_in_effects and len(sem_set) >= 2:
                        group_name = xlights_mapping.get(sem_name)
                        if group_name and non_aggregatable_effects:
                            # Use first aggregatable effect's channels as representative
                            representative_effect = non_aggregatable_effects[0]
                            # Skip if representative effect has no channel states
                            if representative_effect.channels:
                                placement = self._create_group_placement(
                                    group_name,
                                    representative_effect,
                                    start_ms,
                                    end_ms,
                                    fixtures,
                                    xsq,
                                )
                                if placement:
                                    placements.append(placement)
                                    covered_effects.extend(effects)  # Mark these effects as covered
                                    group_created = True
                                    logger.info(
                                        f"✓ Created group effect for {sem_name}: {group_name}"
                                    )
                            else:
                                logger.debug(
                                    f"Skipping empty group effect for {sem_name} at {start_ms}-{end_ms}ms"
                                )
                                break  # Only create one group per timing window

        return placements, covered_effects

    def _create_group_placement(
        self,
        group_model_name: str,
        representative_effect: DmxEffect,
        start_ms: int,
        end_ms: int,
        fixtures: FixtureGroup,
        xsq: XSequence | None,
    ) -> EffectPlacement | None:
        """Create EffectPlacement for a group model.

        Args:
            group_model_name: xLights group model name
            representative_effect: Representative effect for channel states
            start_ms: Effect start time
            end_ms: Effect end time
            fixtures: Fixture group
            xsq: XSequence object for EffectDB

        Returns:
            EffectPlacement for group model, or None if creation failed
        """
        # Convert channel states to DMX settings string
        ref = 0
        if xsq is not None:
            settings_str = self._channel_states_to_settings(representative_effect, fixtures)
            ref = xsq.append_effectdb(settings_str)

        # Use source label from representative effect for debugging
        source_label = representative_effect.metadata.get("source_label", "")

        return EffectPlacement(
            element_name=group_model_name,
            effect_name="DMX",
            start_ms=start_ms,
            end_ms=end_ms,
            effect_label=source_label,
            ref=ref,
            palette=0,
        )

    def _channel_states_to_settings(self, dmx_effect: DmxEffect, fixtures: FixtureGroup) -> str:
        """Convert channel states to xLights DMX settings string.

        Args:
            dmx_effect: DMX effect with channel states
            fixtures: Fixture group for DMX mapping

        Returns:
            Settings string like "B_CHOICE_BufferStyle=...,E_CHECKBOX_INVDMX1=0,..."
        """
        # Get fixture config to map logical channels to DMX channels
        fixture = None

        # Expand fixtures to ensure we have full FixtureInstance objects
        expanded_fixtures = fixtures.expand_fixtures()

        # Special case: "ALL" or other semantic groups use first fixture's config
        # (all fixtures in a group have the same DMX mapping anyway)
        if dmx_effect.fixture_id == "ALL" or dmx_effect.fixture_id not in [
            f.fixture_id for f in expanded_fixtures
        ]:
            fixture = expanded_fixtures[0] if expanded_fixtures else None
        else:
            # Normal case: look up specific fixture
            for f in expanded_fixtures:
                if f.fixture_id == dmx_effect.fixture_id:
                    fixture = f
                    break

        if not fixture:
            logger.warning(f"No fixture found for {dmx_effect.fixture_id}")
            return "B_CHOICE_BufferStyle=Per Model Default,E_CHECKBOX_INVDMX1=0,E_NOTEBOOK1=Channels 1-16,E_SLIDER_DMX1=0"

        # Use DmxSettingsBuilder to generate proper settings string
        # This handles: E_SLIDER_DMX vs value curves, inversion flags, buffer style, etc.
        builder = DmxSettingsBuilder(fixture)
        return builder.build_settings_string(dmx_effect)
