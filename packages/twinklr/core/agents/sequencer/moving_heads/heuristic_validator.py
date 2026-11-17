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
from itertools import pairwise
import logging
from typing import TYPE_CHECKING, Any, NamedTuple

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
    part_ids,
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


MIN_REASONING_CHARACTERS = 20
"""Below this, or under four words, a reasoning or strategy is a placeholder."""


def _is_placeholder(text: str) -> bool:
    stripped = text.strip()
    return len(stripped) < MIN_REASONING_CHARACTERS or len(stripped.split()) < 4


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

        # Every song section with bars of its own is planned (one plan entry per Song
        # Structure row). A section shorter than a bar shares its start bar with the
        # next one; planning both would overlap, so it is not required.
        if self._song_sections:
            entries = list(self._song_sections.items())
            collapsed = {
                section_id
                for (section_id, entry), (_, following) in pairwise(entries)
                if entry.get("start_bar") == following.get("start_bar")
            }
            missing = [
                f"'{section_id}' (bars {entry.get('start_bar')}-{entry.get('end_bar')})"
                for section_id, entry in entries
                if section_id not in covered_section_ids and section_id not in collapsed
            ]
            if missing:
                errors.append(
                    f"The plan has no section for song section(s) {', '.join(missing)}; plan "
                    "every section of the Song Structure table, each over its own bars"
                )

        # A section the beat grid ends before has no bar to render
        beyond_grid = self.song_structure.get("beyond_grid") or {}
        for section_id in beyond_grid.get("section_ids", []):
            if section_id in covered_section_ids:
                errors.append(
                    f"Section '{section_id}' lies beyond the detected beat grid (its last "
                    f"bar is {self._total_bars}); leave it out of the plan"
                )

        # A strategy and a reason, not a placeholder
        if _is_placeholder(plan.overall_strategy):
            errors.append(
                f"overall_strategy {plan.overall_strategy!r} is a placeholder; say in a "
                "sentence or more how the light follows this song"
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

        # 2) its bars are the song structure's
        if self._song_sections and name in self._song_sections:
            expected_start = self._song_sections[name].get("start_bar")
            expected_end = self._song_sections[name].get("end_bar")
            if expected_start is not None and section.start_bar != expected_start:
                errors.append(
                    f"Section '{name}' start_bar ({section.start_bar}) doesn't match song structure ({expected_start})"
                )
            if expected_end is not None and section.end_bar != expected_end:
                errors.append(
                    f"Section '{name}' end_bar ({section.end_bar}) doesn't match song structure ({expected_end})"
                )

        # 3) a reason, not a placeholder
        if _is_placeholder(section.reasoning):
            errors.append(
                f"Section '{name}': reasoning {section.reasoning!r} is a placeholder; name the "
                "energy, palette colour, lyric cues and moments the section answers"
            )

        # 4) each part: an offered template over its own bars
        units: list[_PlanUnit] = []
        parts = section.part_bars()
        ids = part_ids(section)
        for index, (part, start_bar, end_bar) in enumerate(parts):
            location = name if len(parts) == 1 else f"{name}|{ids[index]}"
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
                    # Plans name sections by their unique section_id.
                    name = (
                        str(section_data.get("section_id") or "")
                        or section_data.get("name")
                        or section_data.get("label")
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
