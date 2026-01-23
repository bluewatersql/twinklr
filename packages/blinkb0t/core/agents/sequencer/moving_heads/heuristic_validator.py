"""Heuristic validator for choreography plans.

Fast, deterministic validation without LLM calls.
Catches basic errors before expensive LLM validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from blinkb0t.core.agents.sequencer.moving_heads.models import ChoreographyPlan

logger = logging.getLogger(__name__)


@dataclass
class HeuristicValidationResult:
    """Result of heuristic validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]


class HeuristicValidator:
    """Non-LLM validator for choreography plans.

    Performs fast checks:
    - Template existence
    - Basic timing validity
    - Section coverage
    - Empty sequences
    """

    def __init__(
        self,
        available_templates: list[str],
        song_structure: dict[str, Any],
    ):
        """Initialize heuristic validator.

        Args:
            available_templates: List of available template names
            song_structure: Song structure with sections and total_bars
        """
        self.available_templates = set(available_templates)
        self.song_structure = song_structure

    def validate(self, plan: ChoreographyPlan) -> HeuristicValidationResult:
        """Validate choreography plan.

        Args:
            plan: Choreography plan to validate

        Returns:
            Validation result with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check 1: Plan has sections
        if not plan.sections or len(plan.sections) == 0:
            errors.append("Plan has no sections")
            return HeuristicValidationResult(valid=False, errors=errors, warnings=warnings)

        # Check 2: Validate each section
        song_sections_raw = self.song_structure.get("sections", [])
        covered_sections = set()

        # Normalize song_sections to dict format for consistent handling
        song_sections: dict[str, Any] = {}
        if isinstance(song_sections_raw, list):
            # Convert list of sections to dict keyed by name/label
            for section_data in song_sections_raw:
                if isinstance(section_data, dict):
                    # Try common keys for section name
                    name = (
                        section_data.get("name")
                        or section_data.get("label")
                        or str(section_data.get("section_id", ""))
                    )
                    if name:
                        song_sections[name] = section_data
        elif isinstance(song_sections_raw, dict):
            song_sections = song_sections_raw

        for section in plan.sections:
            covered_sections.add(section.section_name)

            # Check section timing
            if section.start_bar < 0:
                errors.append(f"Section '{section.section_name}' has negative start_bar")

            if section.end_bar <= section.start_bar:
                errors.append(
                    f"Section '{section.section_name}' end_bar ({section.end_bar}) "
                    f"<= start_bar ({section.start_bar})"
                )

            # Check section matches song structure (if available)
            if section.section_name in song_sections:
                expected_start = song_sections[section.section_name].get("start_bar")
                expected_end = song_sections[section.section_name].get("end_bar")

                if expected_start is not None and section.start_bar != expected_start:
                    warnings.append(
                        f"Section '{section.section_name}' start_bar ({section.start_bar}) "
                        f"doesn't match song structure ({expected_start})"
                    )

                if expected_end is not None and section.end_bar != expected_end:
                    warnings.append(
                        f"Section '{section.section_name}' end_bar ({section.end_bar}) "
                        f"doesn't match song structure ({expected_end})"
                    )

            # Check template exists
            if section.template_id not in self.available_templates:
                errors.append(
                    f"Section '{section.section_name}': "
                    f"template '{section.template_id}' not in library"
                )

        # Check 3: Coverage (only warn if we have song sections to compare against)
        if song_sections:
            missing_sections = set(song_sections.keys()) - covered_sections
            if missing_sections:
                warnings.append(
                    f"Plan doesn't cover all song sections: {', '.join(sorted(missing_sections))}"
                )

        # Determine overall validity
        valid = len(errors) == 0

        if valid:
            logger.info(
                f"Heuristic validation passed "
                f"({len(warnings)} warnings, {len(covered_sections)} sections)"
            )
        else:
            logger.warning(
                f"Heuristic validation failed ({len(errors)} errors, {len(warnings)} warnings)"
            )
            # Log each error for debugging
            for i, error in enumerate(errors, 1):
                logger.warning(f"  Error {i}: {error}")

        return HeuristicValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
        )
