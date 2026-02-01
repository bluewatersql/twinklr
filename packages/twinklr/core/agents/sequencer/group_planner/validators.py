"""Deterministic validators for GroupPlanner outputs.

These validators run before LLM judge evaluation to catch
structural and timing issues quickly.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents.sequencer.group_planner.models import (
    CoordinationMode,
    DisplayGraph,
    GroupPlacement,
    PlacementWindow,
    SectionCoordinationPlan,
    TemplateCatalog,
)
from twinklr.core.agents.sequencer.group_planner.timing import TimingContext


class ValidationSeverity(str, Enum):
    """Severity of validation issue."""

    ERROR = "ERROR"  # Blocks progression
    WARNING = "WARNING"  # Advisory, does not block


class ValidationIssue(BaseModel):
    """Single validation issue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: ValidationSeverity
    code: str
    message: str
    field_path: str | None = None
    fix_hint: str | None = None


class ValidationResult(BaseModel):
    """Result of validation."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)


class SectionPlanValidator:
    """Deterministic validator for SectionCoordinationPlan.

    Validates:
    - Template existence in catalog
    - Group existence in DisplayGraph
    - Timing bounds (placements within section)
    - No within-lane overlaps on same group
    """

    def __init__(
        self,
        display_graph: DisplayGraph,
        template_catalog: TemplateCatalog,
        timing_context: TimingContext,
    ) -> None:
        """Initialize validator with context.

        Args:
            display_graph: Display configuration
            template_catalog: Available templates
            timing_context: Timing information for TimeRef resolution
        """
        self.display_graph = display_graph
        self.template_catalog = template_catalog
        self.timing_context = timing_context

        # Build lookup sets for fast validation
        self._valid_group_ids = {g.group_id for g in display_graph.groups}

    def validate(self, plan: SectionCoordinationPlan) -> ValidationResult:
        """Validate a SectionCoordinationPlan.

        Args:
            plan: Plan to validate

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        # Get section bounds
        section_bounds = self.timing_context.get_section_bounds(plan.section_id)
        section_start_ms: int | None = None
        section_end_ms: int | None = None

        if section_bounds:
            section_start_ms = self.timing_context.resolve_to_ms(section_bounds.start)
            section_end_ms = self.timing_context.resolve_to_ms(section_bounds.end)

        # Validate each lane plan
        for lane_plan in plan.lane_plans:
            for coord_plan in lane_plan.coordination_plans:
                # Validate group_ids exist
                for group_id in coord_plan.group_ids:
                    if group_id not in self._valid_group_ids:
                        errors.append(
                            ValidationIssue(
                                severity=ValidationSeverity.ERROR,
                                code="UNKNOWN_GROUP",
                                message=f"Group '{group_id}' not found in DisplayGraph",
                                field_path=f"lane_plans[{lane_plan.lane.value}].group_ids",
                                fix_hint="Use a valid group_id from DisplayGraph.groups",
                            )
                        )

                # Validate placements
                placements = coord_plan.placements
                errors.extend(
                    self._validate_placements(
                        placements,
                        lane_plan.lane.value,
                        section_start_ms,
                        section_end_ms,
                    )
                )

                # Validate window (for sequenced modes)
                if coord_plan.window:
                    errors.extend(
                        self._validate_window(
                            coord_plan.window,
                            coord_plan.coordination_mode,
                            lane_plan.lane.value,
                            section_start_ms,
                            section_end_ms,
                        )
                    )

        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def _validate_placements(
        self,
        placements: list[GroupPlacement],
        lane_name: str,
        section_start_ms: int | None,
        section_end_ms: int | None,
    ) -> list[ValidationIssue]:
        """Validate a list of placements.

        Checks:
        - Template exists
        - Group exists
        - Timing within section bounds
        - No within-lane overlaps on same group
        """
        errors: list[ValidationIssue] = []

        # Track placements by group for overlap detection
        placements_by_group: dict[str, list[tuple[int, int, str]]] = defaultdict(list)

        for placement in placements:
            # Check template exists
            if not self.template_catalog.has_template(placement.template_id):
                errors.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="UNKNOWN_TEMPLATE",
                        message=f"Template '{placement.template_id}' not found in catalog",
                        field_path=f"placement[{placement.placement_id}].template_id",
                        fix_hint="Use a valid template_id from TemplateCatalog",
                    )
                )

            # Check group exists
            if placement.group_id not in self._valid_group_ids:
                errors.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="UNKNOWN_GROUP",
                        message=f"Group '{placement.group_id}' not found in DisplayGraph",
                        field_path=f"placement[{placement.placement_id}].group_id",
                        fix_hint="Use a valid group_id from DisplayGraph.groups",
                    )
                )

            # Resolve timing
            try:
                start_ms = self.timing_context.resolve_to_ms(placement.start)
                end_ms = self.timing_context.resolve_to_ms(placement.end)
            except ValueError as e:
                errors.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="INVALID_TIMEREF",
                        message=f"Cannot resolve TimeRef: {e}",
                        field_path=f"placement[{placement.placement_id}].start/end",
                    )
                )
                continue

            # Check timing within section bounds
            if section_start_ms is not None and section_end_ms is not None:
                if start_ms < section_start_ms or end_ms > section_end_ms:
                    errors.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="PLACEMENT_OUTSIDE_SECTION",
                            message=(
                                f"Placement '{placement.placement_id}' "
                                f"({start_ms}ms-{end_ms}ms) outside section bounds "
                                f"({section_start_ms}ms-{section_end_ms}ms)"
                            ),
                            field_path=f"placement[{placement.placement_id}].start/end",
                            fix_hint="Adjust placement timing to fit within section bounds",
                        )
                    )

            # Track for overlap detection
            placements_by_group[placement.group_id].append(
                (start_ms, end_ms, placement.placement_id)
            )

        # Check for within-lane overlaps on same group
        for group_id, group_placements in placements_by_group.items():
            # Sort by start time
            sorted_placements = sorted(group_placements, key=lambda x: x[0])

            for i in range(len(sorted_placements) - 1):
                _, end_ms, pid1 = sorted_placements[i]
                next_start_ms, _, pid2 = sorted_placements[i + 1]

                if end_ms > next_start_ms:
                    errors.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="WITHIN_LANE_OVERLAP",
                            message=(
                                f"Overlap detected in lane '{lane_name}' on group "
                                f"'{group_id}': placements '{pid1}' and '{pid2}'"
                            ),
                            field_path=f"lane_plans[{lane_name}].placements",
                            fix_hint="Adjust placement timing to avoid overlaps",
                        )
                    )

        return errors

    def _validate_window(
        self,
        window: PlacementWindow,
        coordination_mode: CoordinationMode,
        lane_name: str,
        section_start_ms: int | None,
        section_end_ms: int | None,
    ) -> list[ValidationIssue]:
        """Validate a placement window."""
        errors: list[ValidationIssue] = []

        # Check template exists
        if not self.template_catalog.has_template(window.template_id):
            errors.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="UNKNOWN_TEMPLATE",
                    message=f"Template '{window.template_id}' not found in catalog",
                    field_path=f"lane_plans[{lane_name}].window.template_id",
                    fix_hint="Use a valid template_id from TemplateCatalog",
                )
            )

        # Resolve timing
        try:
            start_ms = self.timing_context.resolve_to_ms(window.start)
            end_ms = self.timing_context.resolve_to_ms(window.end)
        except ValueError as e:
            errors.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="INVALID_TIMEREF",
                    message=f"Cannot resolve window TimeRef: {e}",
                    field_path=f"lane_plans[{lane_name}].window.start/end",
                )
            )
            return errors

        # Check timing within section bounds
        if section_start_ms is not None and section_end_ms is not None:
            if start_ms < section_start_ms or end_ms > section_end_ms:
                errors.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="WINDOW_OUTSIDE_SECTION",
                        message=(
                            f"Window ({start_ms}ms-{end_ms}ms) outside section bounds "
                            f"({section_start_ms}ms-{section_end_ms}ms)"
                        ),
                        field_path=f"lane_plans[{lane_name}].window.start/end",
                        fix_hint="Adjust window timing to fit within section bounds",
                    )
                )

        return errors
