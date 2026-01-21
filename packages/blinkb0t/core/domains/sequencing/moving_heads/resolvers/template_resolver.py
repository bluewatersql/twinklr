"""Template resolution for moving head sequencing.

Extracted from MovingHeadSequencer to simplify orchestration.
Handles per-fixture timing offset explosion for chase/canon effects.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup

logger = logging.getLogger(__name__)


class TemplateResolver:
    """Resolves template IDs to instruction lists.

    Handles per-fixture timing offset explosion: when a template step defines
    per_fixture_offsets, this resolver creates individual fixture instructions
    with staggered timing for chase/canon effects.
    """

    def __init__(
        self,
        template_dir: str | Path | None = None,
        fixtures: FixtureGroup | None = None,
    ):
        """Initialize template resolver.

        Args:
            template_dir: Optional template directory path
            fixtures: Fixture group for semantic group mapping (required for per_fixture_offsets)
        """
        if template_dir:
            self.template_dir = Path(template_dir)
        else:
            # Resolve template directory relative to project root
            self.template_dir = Path.cwd() / "data" / "v2" / "templates"
            if not self.template_dir.exists():
                # Fallback: try relative to this file's location (for tests)
                self.template_dir = (
                    Path(__file__).parent.parent.parent.parent.parent.parent
                    / "data"
                    / "v2"
                    / "templates"
                )

        self.fixtures = fixtures

        # Build semantic group mapping once (for per-fixture offset explosion)
        if fixtures:
            from blinkb0t.core.utils.fixtures import build_semantic_groups

            fixture_ids = [f.fixture_id for f in fixtures]
            self.semantic_groups = build_semantic_groups(fixture_ids)
            logger.debug(
                f"TemplateResolver initialized with {len(fixture_ids)} fixtures, "
                f"{len(self.semantic_groups)} semantic groups"
            )
        else:
            self.semantic_groups = {}
            logger.debug(
                "TemplateResolver initialized without fixtures (per_fixture_offsets disabled)"
            )

    def resolve(
        self, section: dict[str, Any], song_features: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """Resolve template to instructions using TemplateLoader.

        If template steps define per_fixture_offsets, explodes to per-fixture
        instructions with staggered timing for chase/canon effects.

        Args:
            section: Section dict with template_id, params, etc.
            song_features: Song features for timing

        Returns:
            List of instruction dicts or None if template not found.
            May return multiple instructions per step if per_fixture_offsets present.
        """
        from blinkb0t.core.domains.sequencing.moving_heads.templates import TemplateLoader

        template_id = section.get("template_id")
        if not template_id:
            return None

        params = section.get("params", {})

        try:
            # Initialize template loader
            template_loader = TemplateLoader(template_dir=str(self.template_dir))

            # Load template with parameters
            template = template_loader.load_template(template_id, params=params)

            # Convert Template steps to old instruction format
            instructions = []
            for step in template.steps:
                # Check if per-fixture offsets exist
                if step.timing and step.timing.per_fixture_offsets:
                    # EXPLODE: Create one instruction per fixture
                    step_target = step.target
                    target_fixtures = self.semantic_groups.get(step_target, [])

                    if not target_fixtures:
                        logger.warning(
                            f"Cannot explode per_fixture_offsets: unknown target '{step_target}' "
                            f"in step '{step.step_id}' - skipping step"
                        )
                        continue

                    # Scale offsets to fixture count
                    scaled_offsets = scale_offsets_to_fixture_count(
                        step.timing.per_fixture_offsets, len(target_fixtures)
                    )

                    logger.debug(
                        f"Exploding step '{step.step_id}' with per_fixture_offsets: "
                        f"{step_target} → {len(target_fixtures)} fixtures"
                    )

                    # Create one instruction per fixture
                    for fixture_idx, fixture_id in enumerate(target_fixtures):
                        instruction = self._build_instruction_from_step(
                            step=step,
                            target=fixture_id,  # Individual fixture ID (e.g., "MH1")
                            additional_offset_bars=scaled_offsets[fixture_idx],
                            section=section,
                        )
                        instructions.append(instruction)
                else:
                    # NORMAL: Group-level instruction (existing behavior)
                    instruction = self._build_instruction_from_step(
                        step=step,
                        target=step.target,  # Semantic group (e.g., "ALL")
                        additional_offset_bars=0.0,
                        section=section,
                    )
                    instructions.append(instruction)

            logger.debug(
                f"Resolved template '{template_id}' to {len(instructions)} instructions "
                f"(from {len(template.steps)} steps)"
            )
            return instructions

        except Exception as e:
            logger.error(f"Failed to resolve template '{template_id}': {e}", exc_info=True)
            return None

    def _build_instruction_from_step(
        self,
        step: Any,  # PatternStep from models.templates
        target: str,
        additional_offset_bars: float,
        section: dict[str, Any],
    ) -> dict[str, Any]:
        """Build instruction dict from template step.

        Args:
            step: Template step (PatternStep)
            target: Target (semantic group or individual fixture ID)
            additional_offset_bars: Additional timing offset from per_fixture_offsets
            section: Section dict for fallback target

        Returns:
            Instruction dictionary in legacy format
        """
        # Extract ID values (may be enums or strings)
        movement_pattern = str(step.movement_id) if step.movement_id else "static"
        dimmer_profile = str(step.dimmer_id) if step.dimmer_id else "full"
        geometry_pose = str(step.geometry_id) if step.geometry_id else "AUDIENCE_CENTER"

        # Look up movement curve from library
        movement_dict = {"pattern": movement_pattern}
        if step.movement_id:
            from blinkb0t.core.domains.sequencing.libraries.moving_heads import (
                MOVEMENT_LIBRARY,
                MovementID,
            )

            try:
                movement_id_enum = MovementID(str(step.movement_id))
                movement_lib_entry = MOVEMENT_LIBRARY.get(movement_id_enum)
                if movement_lib_entry and movement_lib_entry.primary_curve:
                    # Extract curve name for factory (e.g., "sine", "bounce_out", "s_curve")
                    curve_preset = str(movement_lib_entry.primary_curve.curve.value)
                    movement_dict["curve_preset"] = curve_preset
                    logger.debug(
                        f"Resolved movement '{movement_pattern}' to curve '{curve_preset}'"
                    )
            except (ValueError, KeyError) as e:
                logger.warning(f"Could not resolve curve for movement '{step.movement_id}': {e}")

        # Include categorical parameters from template step
        # These will be resolved by the handler (categorical → numeric)
        if step.movement_params:
            movement_dict.update(step.movement_params)

        dimmer_dict = {"profile_id": dimmer_profile}
        if step.dimmer_params:
            dimmer_dict.update(step.dimmer_params)

        geometry_dict = {"pose_id": geometry_pose}
        if step.geometry_params:
            geometry_dict.update(step.geometry_params)

        instruction = {
            "target": target,
            "movement": movement_dict,
            "dimmer": dimmer_dict,
            "geometry": geometry_dict,
        }

        # Add timing with additional offset
        if step.timing:
            instruction["timing"] = {
                "start_offset_bars": (
                    step.timing.base_timing.start_offset_bars + additional_offset_bars
                ),
                "duration_bars": step.timing.base_timing.duration_bars,
            }

        return instruction


def scale_offsets_to_fixture_count(offsets_8: list[float], num_fixtures: int) -> list[float]:
    """Scale 8-element offset array to actual fixture count.

    Templates always define 8 elements. This function adapts the array
    to match the actual fixture count in the configuration.

    Args:
        offsets_8: 8-element array from template
        num_fixtures: Actual fixture count (4, 6, 8, etc.)

    Returns:
        Scaled offset array matching fixture count

    Examples:
        offsets_8 = [0, 0, 1, 1, 0, 0, 1, 1]

        4 fixtures → use indices [1, 3, 5, 7]
          → [0, 1, 0, 1]

        6 fixtures → use indices [1, 2, 3, 4, 5, 6]
          → [0, 0, 1, 1, 0, 0]

        8 fixtures → use as-is
          → [0, 0, 1, 1, 0, 0, 1, 1]

        12 fixtures → tile and trim
          → [0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1]

    Raises:
        ValueError: If offsets_8 does not have exactly 8 elements
    """
    if len(offsets_8) != 8:
        raise ValueError(
            f"Template per_fixture_offsets must have exactly 8 elements, got {len(offsets_8)}"
        )

    if num_fixtures == 8:
        # Use as-is
        return offsets_8

    elif num_fixtures == 4:
        # Subsample: use indices 1, 3, 5, 7
        return [offsets_8[i] for i in [1, 3, 5, 7]]

    elif num_fixtures == 6:
        # Subsample: use indices 1-6
        return [offsets_8[i] for i in [1, 2, 3, 4, 5, 6]]

    elif num_fixtures < 8:
        # General case: evenly distribute
        step = 8 / num_fixtures
        indices = [int(i * step) for i in range(num_fixtures)]
        return [offsets_8[i] for i in indices]

    else:  # num_fixtures > 8
        # Tile the pattern and trim to length
        repeats = (num_fixtures // 8) + 1
        extended = offsets_8 * repeats
        return extended[:num_fixtures]
