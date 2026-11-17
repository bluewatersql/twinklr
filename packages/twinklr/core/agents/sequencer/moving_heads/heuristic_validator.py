"""Heuristic validator for choreography plans.

Fast, deterministic validation without LLM calls. It refuses what is structurally
invalid against the song and the template library (a template not offered, a section
beyond the song, overlapping sections), which the refinement loop re-plans. The plan
model itself enforces the context-free rules (bar order, parts, event fields), and
`moment_cues.bind_lyric_moment_cues` repairs single items instead of refusing them.

- Use `from_context()` with a `MovingHeadPlanningContext`
- Use `create_validator_function()` for StandardIterationController integration
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, NamedTuple

from twinklr.core.agents.sequencer.moving_heads.models import (
    PART_IDS,
    ChoreographyPlan,
    PlanSection,
)

if TYPE_CHECKING:
    from twinklr.core.agents.sequencer.moving_heads.context import MovingHeadPlanningContext

logger = logging.getLogger(__name__)


@dataclass
class HeuristicValidationResult:
    """Result of heuristic validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]


class _PlanUnit(NamedTuple):
    """Flattened evaluation unit (a section, or one part of a section of several)."""

    # identity / location
    location: str  # e.g. "verse_1" or "verse_1|A"
    parent_section: str

    # bars
    start_bar: int
    end_bar: int

    # selection
    template_id: str
    preset_id: str | None


def create_validator_function(
    context: MovingHeadPlanningContext,
) -> Callable[[ChoreographyPlan], list[str]]:
    """Create validator function for StandardIterationController.

    Factory function that creates the callable expected by V2 iteration controller.

    Args:
        context: MovingHead planning context

    Returns:
        Validator function that takes a plan and returns list of error messages

    Example:
        >>> validator = create_validator_function(planning_context)
        >>> errors = validator(plan)  # Returns list[str] of errors
    """
    heuristic_validator = HeuristicValidator.from_context(context)

    def validate(plan: ChoreographyPlan) -> list[str]:
        """Validate plan and return list of error messages."""
        return heuristic_validator.validate(plan).errors

    return validate


class HeuristicValidator:
    """Code-based validator for choreography plans.

    Technical checks against the song and the library:
    - Template existence in library, for every part
    - Timing validity (bars within the song, no overlaps)
    - Section coverage (gaps and uncovered song sections are warnings)
    - Bar numbering (1-indexed)

    This is the main technical gate. Judge focuses on creative quality.

    Usage:
        Use `from_context()`, `create_validator_function()`, or construct it with the
        available templates and a song structure dict.
    """

    def __init__(
        self,
        available_templates: list[str],
        song_structure: dict[str, Any],
    ):
        """Initialize validator with template list and song structure.

        Args:
            available_templates: List of valid template IDs
            song_structure: Song structure dict with sections and timing

        Note:
            For V2 usage, prefer `from_context()` class method.
        """
        self.available_templates = set(available_templates)
        self.song_structure = song_structure

        self._song_sections = self._normalize_song_sections(song_structure.get("sections", []))
        self._total_bars = self._infer_total_bars(song_structure)

    @classmethod
    def from_context(cls, context: MovingHeadPlanningContext) -> HeuristicValidator:
        """Create validator from MovingHeadPlanningContext (V2).

        Extracts templates and song structure from the structured context model.

        Args:
            context: MovingHead planning context

        Returns:
            Configured HeuristicValidator instance
        """
        # Build song structure dict from context
        song_structure = context.for_prompt()["song_structure"]

        return cls(
            available_templates=context.available_templates,
            song_structure=song_structure,
        )

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def validate(self, plan: ChoreographyPlan) -> HeuristicValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if not plan.sections:
            errors.append("Plan has no sections")
            return HeuristicValidationResult(valid=False, errors=errors, warnings=warnings)

        covered_section_ids: set[str] = set()
        units: list[_PlanUnit] = []

        # Validate each section structurally + collect flattened units
        for section in plan.sections:
            covered_section_ids.add(section.section_id)
            section_units = self._validate_section(section, errors, warnings)
            units.extend(section_units)

        # Cross-section checks using flattened units
        self._validate_units_timing_and_coverage(units, errors, warnings)

        # Compare against song structure (section coverage/mismatch) if available
        if self._song_sections:
            missing_sections = set(self._song_sections.keys()) - covered_section_ids
            if missing_sections:
                warnings.append(
                    f"Plan doesn't cover all song sections: {', '.join(sorted(missing_sections))}"
                )

        valid = len(errors) == 0

        if valid:
            logger.debug(
                "Heuristic validation passed (%d warnings, %d plan-units, %d sections)",
                len(warnings),
                len(units),
                len(plan.sections),
            )
        else:
            logger.warning(
                "Heuristic validation failed (%d errors, %d warnings)", len(errors), len(warnings)
            )
            for i, error in enumerate(errors, 1):
                logger.warning("  Error %d: %s", i, error)

        return HeuristicValidationResult(valid=valid, errors=errors, warnings=warnings)

    # ---------------------------------------------------------------------
    # Section validation + flattening
    # ---------------------------------------------------------------------

    def _validate_section(
        self,
        section: PlanSection,
        errors: list[str],
        warnings: list[str],
    ) -> list[_PlanUnit]:
        name = section.section_id

        # 1) basic bars (the plan model enforces their order)
        if section.start_bar < 1:
            errors.append(
                f"Section '{name}' has invalid start_bar ({section.start_bar}); must be >= 1 (1-indexed)"
            )

        # 2) compare to song structure if present (warn only)
        if self._song_sections and name in self._song_sections:
            expected_start = self._song_sections[name].get("start_bar")
            expected_end = self._song_sections[name].get("end_bar")
            if expected_start is not None and section.start_bar != expected_start:
                warnings.append(
                    f"Section '{name}' start_bar ({section.start_bar}) doesn't match song structure ({expected_start})"
                )
            if expected_end is not None and section.end_bar != expected_end:
                warnings.append(
                    f"Section '{name}' end_bar ({section.end_bar}) doesn't match song structure ({expected_end})"
                )

        # 3) each part: an offered template over its own bars
        units: list[_PlanUnit] = []
        parts = section.part_bars()
        for index, (part, start_bar, end_bar) in enumerate(parts):
            location = name if len(parts) == 1 else f"{name}|{PART_IDS[index]}"
            if part.template_id not in self.available_templates:
                errors.append(f"Section '{location}': template '{part.template_id}' not in library")
            if end_bar - start_bar < 1:
                warnings.append(f"Section '{location}' is very short ({end_bar - start_bar} bars)")
            units.append(
                _PlanUnit(
                    location=location,
                    parent_section=name,
                    start_bar=start_bar,
                    end_bar=end_bar,
                    template_id=part.template_id,
                    preset_id=part.preset_id,
                )
            )
        return units

    # ---------------------------------------------------------------------
    # Cross-unit timing checks
    # ---------------------------------------------------------------------

    def _validate_units_timing_and_coverage(
        self,
        units: list[_PlanUnit],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        if not units:
            return

        # Sort by time to check overlaps/gaps across the entire plan.
        # Note: This is intentionally global; if your plan can repeat bar ranges per section group
        # you can scope this later. For now, it's a strong technical gate.
        units_sorted = sorted(units, key=lambda u: (u.start_bar, u.end_bar, u.location))

        # Validate each unit within known total bars if available
        if self._total_bars is not None:
            for u in units_sorted:
                if u.end_bar > self._total_bars:
                    errors.append(
                        f"Unit '{u.location}' ends at bar {u.end_bar}, beyond total_bars ({self._total_bars})"
                    )

        # Overlaps + gaps
        prev = units_sorted[0]
        for cur in units_sorted[1:]:
            if cur.start_bar <= prev.end_bar:
                # overlap (including touching inside)
                errors.append(
                    f"Overlap detected: '{prev.location}' ({prev.start_bar}-{prev.end_bar}) "
                    f"overlaps '{cur.location}' ({cur.start_bar}-{cur.end_bar})"
                )
            else:
                gap = cur.start_bar - prev.end_bar - 1
                if gap >= 1:
                    # warn on gaps (you can choose threshold later)
                    warnings.append(
                        f"Gap detected: {gap} bar(s) uncovered between '{prev.location}' "
                        f"ending at {prev.end_bar} and '{cur.location}' starting at {cur.start_bar}"
                    )
            prev = cur

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _normalize_song_sections(song_sections_raw: Any) -> dict[str, Any]:
        """Normalize song sections into dict keyed by name/label."""
        song_sections: dict[str, Any] = {}
        if isinstance(song_sections_raw, list):
            for section_data in song_sections_raw:
                if isinstance(section_data, dict):
                    name = (
                        section_data.get("name")
                        or section_data.get("label")
                        or str(section_data.get("section_id", ""))
                    )
                    if name:
                        song_sections[name] = section_data
        elif isinstance(song_sections_raw, dict):
            song_sections = song_sections_raw
        return song_sections

    @staticmethod
    def _infer_total_bars(song_structure: dict[str, Any]) -> int | None:
        """Best-effort total bars extraction across likely shapes."""
        # common: song_structure["total_bars"]
        total = song_structure.get("total_bars")
        if isinstance(total, int) and total >= 1:
            return total

        # or nested beat grid / metadata
        beat_grid = song_structure.get("beat_grid") or song_structure.get("beatGrid") or {}
        if isinstance(beat_grid, dict):
            total = beat_grid.get("total_bars") or beat_grid.get("totalBars")
            if isinstance(total, int) and total >= 1:
                return total

        # or derive from max end_bar among sections
        sections = song_structure.get("sections")
        if isinstance(sections, list):
            ends = []
            for s in sections:
                if isinstance(s, dict) and isinstance(s.get("end_bar"), int):
                    ends.append(s["end_bar"])
            if ends:
                return int(max(ends))

        return None
