"""Heuristic validator for choreography plans.

Fast, deterministic validation without LLM calls.
Catches technical errors before expensive judge evaluation.
Primary validation layer - judge only evaluates creative quality.

V2 Migration:
- Supports both legacy dict-based input and new MovingHeadPlanningContext
- Use `from_context()` class method for V2 usage
- Use `create_validator_function()` for StandardIterationController integration
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection

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
    """Flattened evaluation unit (section or segment)."""

    # identity / location
    location: str  # e.g. "verse_1" or "verse_1:A"
    parent_section: str

    # bars
    start_bar: int
    end_bar: int

    # selection
    template_id: str
    preset_id: str | None
    modifiers: dict[str, str]


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
        result = heuristic_validator.validate(plan)
        return result.errors  # Only errors, not warnings

    return validate


class HeuristicValidator:
    """Code-based validator for choreography plans.

    Primary technical validation layer. Performs comprehensive checks:
    - Template existence in library
    - Timing validity (bar ranges, no overlaps)
    - Section coverage (no large gaps)
    - Segmentation validity (1–3 segments, contiguous, full coverage)
    - Basic parameter validation
    - Bar numbering (1-indexed)

    This is the main technical gate. Judge focuses on creative quality.

    V2 Usage:
        Use `from_context()` class method or `create_validator_function()` factory.

    Legacy Usage:
        Direct instantiation with available_templates and song_structure dict.
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

        covered_section_names: set[str] = set()
        units: list[_PlanUnit] = []

        # Validate each section structurally + collect flattened units
        for section in plan.sections:
            covered_section_names.add(section.section_name)
            section_units = self._validate_section(section, errors, warnings)
            units.extend(section_units)

        # Cross-section checks using flattened units
        self._validate_units_timing_and_coverage(units, errors, warnings)

        # Compare against song structure (section coverage/mismatch) if available
        if self._song_sections:
            missing_sections = set(self._song_sections.keys()) - covered_section_names
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
        units: list[_PlanUnit] = []

        # 1) basic bars
        if section.start_bar < 1:
            errors.append(
                f"Section '{section.section_name}' has invalid start_bar ({section.start_bar}); must be >= 1 (1-indexed)"
            )
        if section.end_bar < section.start_bar:
            errors.append(
                f"Section '{section.section_name}' end_bar ({section.end_bar}) must be >= start_bar ({section.start_bar})"
            )

        # 2) schema form: either single-template OR segmented
        # Note: segments can be None (null in JSON) or omitted entirely - both are treated as "no segments"
        segments_value = getattr(section, "segments", None)
        has_segments = bool(segments_value)  # None, [], or missing all evaluate to False
        has_single = bool(getattr(section, "template_id", None))

        if has_segments and has_single:
            errors.append(
                f"Section '{section.section_name}': provide either 'segments' OR 'template_id', not both"
            )
            return units
        if not has_segments and not has_single:
            errors.append(
                f"Section '{section.section_name}': must provide either 'segments' or 'template_id'"
            )
            return units

        # 3) compare to song structure if present (warn only)
        if self._song_sections and section.section_name in self._song_sections:
            expected_start = self._song_sections[section.section_name].get("start_bar")
            expected_end = self._song_sections[section.section_name].get("end_bar")
            if expected_start is not None and section.start_bar != expected_start:
                warnings.append(
                    f"Section '{section.section_name}' start_bar ({section.start_bar}) doesn't match song structure ({expected_start})"
                )
            if expected_end is not None and section.end_bar != expected_end:
                warnings.append(
                    f"Section '{section.section_name}' end_bar ({section.end_bar}) doesn't match song structure ({expected_end})"
                )

        # 4) single-template section
        if has_single:
            template_id = section.template_id  # type: ignore[assignment]
            if template_id not in self.available_templates:
                errors.append(
                    f"Section '{section.section_name}': template '{template_id}' not in library"
                )

            # warn on very short (0-length or 1-bar-ish)
            if section.end_bar - section.start_bar < 1:
                warnings.append(
                    f"Section '{section.section_name}' is very short ({section.end_bar - section.start_bar} bars)"
                )

            units.append(
                _PlanUnit(
                    location=section.section_name,
                    parent_section=section.section_name,
                    start_bar=section.start_bar,
                    end_bar=section.end_bar,
                    template_id=template_id or "",
                    preset_id=section.preset_id,
                    modifiers=dict(section.modifiers or {}),
                )
            )
            return units

        # 5) segmented section
        segs = list(section.segments or [])  # type: ignore[arg-type]
        if not (1 <= len(segs) <= 3):
            errors.append(
                f"Section '{section.section_name}': segments must be 1–3 items (got {len(segs)})"
            )
            return units

        # sort by bars for deterministic validation
        segs_sorted = sorted(segs, key=lambda s: (s.start_bar, s.end_bar))

        # validate each segment and build units
        for seg in segs_sorted:
            loc = f"{section.section_name}:{seg.segment_id}"

            if seg.start_bar < 1:
                errors.append(
                    f"Segment '{loc}' has invalid start_bar ({seg.start_bar}); must be >= 1"
                )
            if seg.end_bar < seg.start_bar:
                errors.append(
                    f"Segment '{loc}' end_bar ({seg.end_bar}) must be >= start_bar ({seg.start_bar})"
                )

            if seg.template_id not in self.available_templates:
                errors.append(f"Segment '{loc}': template '{seg.template_id}' not in library")

            if seg.end_bar - seg.start_bar < 1:
                warnings.append(
                    f"Segment '{loc}' is very short ({seg.end_bar - seg.start_bar} bars)"
                )

            # must be within parent section range
            if seg.start_bar < section.start_bar or seg.end_bar > section.end_bar:
                errors.append(
                    f"Segment '{loc}' bar range ({seg.start_bar}-{seg.end_bar}) must be within section "
                    f"({section.start_bar}-{section.end_bar})"
                )

            units.append(
                _PlanUnit(
                    location=loc,
                    parent_section=section.section_name,
                    start_bar=seg.start_bar,
                    end_bar=seg.end_bar,
                    template_id=seg.template_id,
                    preset_id=seg.preset_id,
                    modifiers=dict(seg.modifiers or {}),
                )
            )

        # validate contiguity + full coverage within the section
        first = segs_sorted[0]
        last = segs_sorted[-1]
        if first.start_bar != section.start_bar:
            errors.append(
                f"Section '{section.section_name}': first segment must start at section start_bar ({section.start_bar}); "
                f"got {first.start_bar}"
            )
        if last.end_bar != section.end_bar:
            errors.append(
                f"Section '{section.section_name}': last segment must end at section end_bar ({section.end_bar}); "
                f"got {last.end_bar}"
            )

        for prev, nxt in zip(segs_sorted, segs_sorted[1:], strict=False):
            if prev.end_bar + 1 != nxt.start_bar:
                errors.append(
                    f"Section '{section.section_name}': segments must be contiguous and non-overlapping; "
                    f"found gap/overlap between '{prev.segment_id}' ({prev.start_bar}-{prev.end_bar}) and "
                    f"'{nxt.segment_id}' ({nxt.start_bar}-{nxt.end_bar})"
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
