"""Deterministic validators for GroupPlanner outputs.

These validators run before LLM judge evaluation to catch
structural and timing issues quickly.

Updated for categorical planning (IntensityLevel, EffectDuration, PlanningTimeRef).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents.sequencer.group_planner.timing import TimingContext
from twinklr.core.sequencer.planning import SectionCoordinationPlan
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models import (
    DisplayGraph,
    GroupPlacement,
    PlacementWindow,
)
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    IntensityLevel,
    LaneKind,
)


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

        # Build lookup set for fast validation
        self._valid_group_ids = {g.group_id for g in display_graph.groups}

    def _get_section_end_bar(self, section_end_ms: int) -> int:
        """Get the bar number for a given millisecond position.

        Args:
            section_end_ms: End time in milliseconds

        Returns:
            Bar number (1-indexed)
        """
        # Find the bar that contains this millisecond
        for bar, bar_info in sorted(self.timing_context.bar_map.items()):
            if bar_info.start_ms + bar_info.duration_ms >= section_end_ms:
                return bar
        # Fallback to last bar
        if self.timing_context.bar_map:
            return max(self.timing_context.bar_map.keys())
        return 1

    def _get_section_end_beat(self, section_end_ms: int) -> int:
        """Get the beat number for a given millisecond position.

        Args:
            section_end_ms: End time in milliseconds

        Returns:
            Beat number (1-indexed)
        """
        # Find the bar that contains this millisecond
        for _bar, bar_info in sorted(self.timing_context.bar_map.items()):
            if bar_info.start_ms <= section_end_ms < bar_info.start_ms + bar_info.duration_ms:
                # Calculate beat within this bar
                offset_ms = section_end_ms - bar_info.start_ms
                beat_duration_ms = bar_info.duration_ms / self.timing_context.beats_per_bar
                beat = int(offset_ms / beat_duration_ms) + 1
                return min(beat, self.timing_context.beats_per_bar)
        # Fallback to last beat
        return self.timing_context.beats_per_bar

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
            # Track group timings across ALL coordination_plans in this lane
            group_timings: dict[str, list[tuple[int, int, str]]] = defaultdict(list)

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

                # Validate config for sequenced modes
                if coord_plan.config and coord_plan.config.group_order:
                    errors.extend(
                        self._validate_group_order(
                            coord_plan.config.group_order,
                            coord_plan.group_ids,
                            lane_plan.lane.value,
                        )
                    )

                # Validate placements
                placements = coord_plan.placements
                placement_errors, placement_timings = self._validate_placements(
                    placements,
                    lane_plan.lane,
                    section_start_ms,
                    section_end_ms,
                )
                errors.extend(placement_errors)

                # Accumulate timings for cross-coordination overlap check
                for group_id, timings in placement_timings.items():
                    group_timings[group_id].extend(timings)

                # Validate window (for sequenced modes)
                if coord_plan.window:
                    window_errors, window_timings = self._validate_window(
                        coord_plan.window,
                        coord_plan.coordination_mode,
                        coord_plan.group_ids,
                        lane_plan.lane,
                        section_start_ms,
                        section_end_ms,
                    )
                    errors.extend(window_errors)

                    # Accumulate window timings for cross-coordination overlap check
                    for group_id, timings in window_timings.items():
                        group_timings[group_id].extend(timings)

            # Check for cross-coordination-plan overlaps within same lane
            overlap_errors, overlap_warnings = self._check_cross_coordination_overlaps(
                group_timings, lane_plan.lane
            )
            errors.extend(overlap_errors)
            warnings.extend(overlap_warnings)

        # Add warning checks for common soft-fail patterns
        warnings.extend(self._check_identical_accent_on_primaries(plan))
        warnings.extend(self._check_timing_driver_mismatch(plan))

        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def _check_identical_accent_on_primaries(
        self, plan: SectionCoordinationPlan
    ) -> list[ValidationIssue]:
        """Check for identical accents on all primary targets simultaneously.

        This is a common soft-fail pattern that flattens focal hierarchy.

        Args:
            plan: Plan to validate

        Returns:
            List of warning issues
        """
        warnings: list[ValidationIssue] = []

        # Find ACCENT lane
        accent_lane = None
        for lane_plan in plan.lane_plans:
            if lane_plan.lane == LaneKind.ACCENT:
                accent_lane = lane_plan
                break

        if not accent_lane:
            return warnings

        # Check each coordination plan in ACCENT lane
        for coord_plan in accent_lane.coordination_plans:
            # Only check UNIFIED coordination modes
            if coord_plan.coordination_mode not in (CoordinationMode.UNIFIED,):
                continue

            # Group placements by (template_id, intensity, approximate_start)
            # If multiple groups have identical placements, warn
            placements = coord_plan.placements
            if len(placements) < 3:
                continue

            # Check if placements use the same template and intensity level
            template_intensity_counts: dict[tuple[str, str], list[str]] = defaultdict(list)
            for p in placements:
                # Use the enum value string for categorical intensity
                intensity_val = (
                    p.intensity.value
                    if isinstance(p.intensity, IntensityLevel)
                    else str(p.intensity)
                )
                key = (p.template_id, intensity_val)
                template_intensity_counts[key].append(p.group_id)

            for (template_id, intensity), groups in template_intensity_counts.items():
                if len(groups) >= 3:
                    # Check if these are primary targets (HERO, MEGA_TREE)
                    primary_groups = [
                        g for g in groups if g.startswith("HERO") or g.startswith("MEGA_TREE")
                    ]
                    if len(primary_groups) >= 3:
                        warnings.append(
                            ValidationIssue(
                                severity=ValidationSeverity.WARNING,
                                code="IDENTICAL_ACCENT_ON_PRIMARIES",
                                message=(
                                    f"All {len(primary_groups)} primary targets ({', '.join(primary_groups[:3])}) "
                                    f"receive identical accent ({template_id}, intensity={intensity}). "
                                    f"This flattens focal hierarchy."
                                ),
                                field_path="lane_plans[ACCENT]",
                                fix_hint=(
                                    "Make ONE target the focal point with PEAK intensity, "
                                    "OR stagger timing by 1+ beat, OR vary templates"
                                ),
                            )
                        )

        return warnings

    def _check_timing_driver_mismatch(self, plan: SectionCoordinationPlan) -> list[ValidationIssue]:
        """Check for timing_driver/snap_rule mismatches.

        Common pattern: timing_driver=LYRICS but placements use BEAT snap.

        Args:
            plan: Plan to validate

        Returns:
            List of warning issues
        """
        warnings: list[ValidationIssue] = []

        for lane_plan in plan.lane_plans:
            timing_driver = lane_plan.timing_driver
            if not timing_driver:
                continue

            # Check if timing_driver is LYRICS but placements use BEAT/BAR
            if timing_driver.upper() == "LYRICS":
                beat_snap_count = 0
                total_placements = 0

                for coord_plan in lane_plan.coordination_plans:
                    for p in coord_plan.placements:
                        total_placements += 1
                        # Check if start/end use bar/beat (not lyrics)
                        if p.start and p.start.bar is not None:
                            beat_snap_count += 1

                if total_placements > 0 and beat_snap_count > total_placements * 0.5:
                    warnings.append(
                        ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            code="TIMING_DRIVER_MISMATCH",
                            message=(
                                f"{lane_plan.lane.value} lane uses timing_driver='LYRICS' "
                                f"but {beat_snap_count}/{total_placements} placements use bar/beat timing. "
                                f"This can cause alignment issues."
                            ),
                            field_path=f"lane_plans[{lane_plan.lane.value}].timing_driver",
                            fix_hint=(
                                "Set timing_driver to 'BEATS' or 'BARS' to match placement anchors"
                            ),
                        )
                    )

        return warnings

    def _validate_group_order(
        self, group_order: list[str], group_ids: list[str], lane_name: str
    ) -> list[ValidationIssue]:
        """Validate group_order for duplicates and membership in group_ids.

        Args:
            group_order: List of group IDs in sequence
            group_ids: List of valid group IDs for this coordination plan
            lane_name: Name of lane

        Returns:
            List of validation issues
        """
        errors: list[ValidationIssue] = []

        # Check for duplicates
        seen = set()
        duplicates = set()
        for group_id in group_order:
            if group_id in seen:
                duplicates.add(group_id)
            seen.add(group_id)

        if duplicates:
            errors.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="DUPLICATE_GROUP_ORDER",
                    message=f"Duplicate groups in group_order: {duplicates}",
                    field_path=f"lane_plans[{lane_name}].config.group_order",
                    fix_hint="Remove duplicate entries from group_order array",
                )
            )

        # Check that all group_order entries are in group_ids
        group_ids_set = set(group_ids)
        invalid_groups = [gid for gid in group_order if gid not in group_ids_set]

        if invalid_groups:
            errors.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="SEQUENCED_CONFIG_GROUP_MISMATCH",
                    message=(
                        f"group_order contains groups not in group_ids: {invalid_groups}. "
                        f"Valid group_ids: {group_ids}"
                    ),
                    field_path=f"lane_plans[{lane_name}].config.group_order",
                    fix_hint=(
                        f"All entries in group_order must be present in group_ids. "
                        f"Remove {invalid_groups} or add them to group_ids."
                    ),
                )
            )

        return errors

    def _check_cross_coordination_overlaps(
        self, group_timings: dict[str, list[tuple[int, int, str]]], lane: LaneKind
    ) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
        """Check for overlaps across coordination_plans within same lane.

        With categorical planning, minor overlaps are downgraded to warnings
        since the renderer will snap/adjust boundaries.

        Args:
            group_timings: Dict mapping group_id to list of (start_ms, end_ms, source) tuples
            lane: Lane kind

        Returns:
            Tuple of (errors, warnings)
        """
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        for group_id, timings in group_timings.items():
            if len(timings) < 2:
                continue

            # Sort by start time
            sorted_timings = sorted(timings, key=lambda x: x[0])

            # Check each pair for overlap
            for i in range(len(sorted_timings)):
                start_i, end_i, source_i = sorted_timings[i]
                for j in range(i + 1, len(sorted_timings)):
                    start_j, end_j, source_j = sorted_timings[j]

                    # Check if they overlap significantly (not just touch or minor overlap)
                    # With categorical planning, renderer will snap/adjust boundaries,
                    # so we use a tolerance of 1 beat (~500ms at typical tempo)
                    overlap_ms = end_i - start_j
                    overlap_tolerance_ms = 500  # ~1 beat, renderer will adjust

                    if start_j < end_i and overlap_ms > overlap_tolerance_ms:
                        # Significant overlap - this is an error
                        errors.append(
                            ValidationIssue(
                                severity=ValidationSeverity.ERROR,
                                code="CROSS_COORDINATION_OVERLAP",
                                message=(
                                    f"Group '{group_id}' appears in multiple coordination_plans "
                                    f"in {lane.value} lane with overlapping timing: "
                                    f"{source_i} ({start_i}-{end_i}ms) and {source_j} ({start_j}-{end_j}ms)"
                                ),
                                field_path=f"lane_plans[{lane.value}]",
                                fix_hint=(
                                    f"MERGE '{group_id}' into a single coordination_plan in {lane.value} "
                                    f"lane, OR remove the shorter placement ({source_j}), OR adjust "
                                    f"timing so {source_j} starts after {end_i}ms"
                                ),
                            )
                        )
                    elif start_j < end_i:
                        # Minor overlap - downgrade to warning, renderer will adjust
                        warnings.append(
                            ValidationIssue(
                                severity=ValidationSeverity.WARNING,
                                code="CROSS_COORDINATION_OVERLAP_MINOR",
                                message=(
                                    f"Group '{group_id}' has minor timing overlap ({overlap_ms}ms) "
                                    f"in {lane.value} lane - renderer will adjust"
                                ),
                                field_path=f"lane_plans[{lane.value}]",
                                fix_hint="Consider adjusting timing to avoid overlap",
                            )
                        )

        return errors, warnings

    def _validate_placements(
        self,
        placements: list[GroupPlacement],
        lane: LaneKind,
        section_start_ms: int | None,
        section_end_ms: int | None,
    ) -> tuple[list[ValidationIssue], dict[str, list[tuple[int, int, str]]]]:
        """Validate a list of placements.

        Checks:
        - Template exists and matches lane
        - Group exists
        - Timing within section bounds
        - Intensity in valid range
        - No within-coordination overlaps on same group

        Returns:
            Tuple of (errors, group_timings)
        """
        errors: list[ValidationIssue] = []

        # Track placements by group for overlap detection
        placements_by_group: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
        group_timings: dict[str, list[tuple[int, int, str]]] = defaultdict(list)

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
            else:
                # Check template-lane compatibility using catalog metadata
                entry = self.template_catalog.get_entry(placement.template_id)
                if entry and lane not in entry.compatible_lanes:
                    # Suggest valid alternatives from the same lane
                    lane_templates = self.template_catalog.list_by_lane(lane)
                    suggestions = [t.template_id for t in lane_templates[:5]]
                    errors.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="TEMPLATE_LANE_MISMATCH",
                            message=(
                                f"Template '{placement.template_id}' is not compatible "
                                f"with {lane.value} lane (compatible: "
                                f"{[lk.value for lk in entry.compatible_lanes]})"
                            ),
                            field_path=f"placement[{placement.placement_id}].template_id",
                            fix_hint=(
                                f"Replace with a {lane.value}-compatible template. "
                                f"Examples: {', '.join(suggestions)}"
                            ),
                        )
                    )

            # Validate intensity is a valid IntensityLevel enum
            # (Pydantic should handle this, but we check for explicit validation)
            if not isinstance(placement.intensity, IntensityLevel):
                try:
                    # Try to convert string to enum
                    IntensityLevel(placement.intensity)
                except ValueError:
                    errors.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="INVALID_INTENSITY_LEVEL",
                            message=(
                                f"Invalid intensity '{placement.intensity}'. "
                                f"Must be one of: WHISPER, SOFT, MED, STRONG, PEAK"
                            ),
                            field_path=f"placement[{placement.placement_id}].intensity",
                            fix_hint="Use a valid IntensityLevel: WHISPER, SOFT, MED, STRONG, PEAK",
                        )
                    )

            # Validate duration is a valid EffectDuration enum
            if not isinstance(placement.duration, EffectDuration):
                try:
                    EffectDuration(placement.duration)
                except ValueError:
                    errors.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="INVALID_DURATION",
                            message=(
                                f"Invalid duration '{placement.duration}'. "
                                f"Must be one of: HIT, BURST, PHRASE, EXTENDED, SECTION"
                            ),
                            field_path=f"placement[{placement.placement_id}].duration",
                            fix_hint="Use a valid EffectDuration: HIT, BURST, PHRASE, EXTENDED, SECTION",
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

            # Resolve timing (using PlanningTimeRef and EffectDuration)
            try:
                start_ms = self.timing_context.resolve_planning_time_ref(placement.start)
                # For end_ms, we need section bounds in bar/beat format
                # For now, use a reasonable default if section bounds not available
                if section_end_ms is not None:
                    end_ms = self.timing_context.resolve_duration_to_end_ms(
                        placement.start,
                        placement.duration,
                        section_end_bar=self._get_section_end_bar(section_end_ms),
                        section_end_beat=self._get_section_end_beat(section_end_ms),
                    )
                else:
                    # No section bounds - estimate end based on duration
                    from twinklr.core.sequencer.vocabulary import DURATION_BEATS

                    min_beats, _ = DURATION_BEATS.get(placement.duration, (4, 4))
                    if min_beats is None:
                        min_beats = 16  # Default for SECTION
                    beat_duration = self.timing_context.beat_duration_ms(placement.start.bar)
                    end_ms = start_ms + int(min_beats * beat_duration)
            except ValueError as e:
                errors.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="INVALID_PLANNING_TIMEREF",
                        message=f"Cannot resolve PlanningTimeRef: {e}",
                        field_path=f"placement[{placement.placement_id}].start",
                    )
                )
                continue

            # Check timing within section bounds
            # With categorical planning, renderer will clamp durations that extend
            # past section end. Only error if start is outside section.
            if section_start_ms is not None and section_end_ms is not None:
                # Critical: start must be within section bounds
                if start_ms < section_start_ms or start_ms >= section_end_ms:
                    errors.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="PLACEMENT_OUTSIDE_SECTION",
                            message=(
                                f"Placement '{placement.placement_id}' "
                                f"starts at {start_ms}ms which is outside section bounds "
                                f"({section_start_ms}ms-{section_end_ms}ms)"
                            ),
                            field_path=f"placement[{placement.placement_id}].start",
                            fix_hint="Adjust placement start to be within section bounds",
                        )
                    )

            # Track for overlap detection (both within-coordination and cross-coordination)
            placements_by_group[placement.group_id].append(
                (start_ms, end_ms, placement.placement_id)
            )
            group_timings[placement.group_id].append(
                (start_ms, end_ms, f"placement:{placement.placement_id}")
            )

        # Check for within-coordination overlaps on same group (same coordination_plan)
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
                            code="WITHIN_COORDINATION_OVERLAP",
                            message=(
                                f"Overlap in {lane.value} lane on group '{group_id}': "
                                f"placements '{pid1}' and '{pid2}'"
                            ),
                            field_path=f"lane_plans[{lane.value}].placements",
                            fix_hint=(
                                f"Each group can only have ONE active placement at a time "
                                f"per lane. Remove '{pid2}' or change its start to after "
                                f"'{pid1}' ends. For continuous coverage, use a single "
                                f"SECTION-duration placement instead of multiple overlapping ones."
                            ),
                        )
                    )

        return errors, group_timings

    def _validate_window(
        self,
        window: PlacementWindow,
        coordination_mode: CoordinationMode,
        group_ids: list[str],
        lane: LaneKind,
        section_start_ms: int | None,
        section_end_ms: int | None,
    ) -> tuple[list[ValidationIssue], dict[str, list[tuple[int, int, str]]]]:
        """Validate a placement window.

        Returns:
            Tuple of (errors, group_timings)
        """
        errors: list[ValidationIssue] = []
        group_timings: dict[str, list[tuple[int, int, str]]] = defaultdict(list)

        # Check template exists
        if not self.template_catalog.has_template(window.template_id):
            errors.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="UNKNOWN_TEMPLATE",
                    message=f"Template '{window.template_id}' not found in catalog",
                    field_path=f"lane_plans[{lane.value}].window.template_id",
                    fix_hint="Use a valid template_id from TemplateCatalog",
                )
            )
        else:
            # Check template-lane compatibility using catalog metadata
            entry = self.template_catalog.get_entry(window.template_id)
            if entry and lane not in entry.compatible_lanes:
                lane_templates = self.template_catalog.list_by_lane(lane)
                suggestions = [t.template_id for t in lane_templates[:5]]
                errors.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="TEMPLATE_LANE_MISMATCH",
                        message=(
                            f"Template '{window.template_id}' is not compatible "
                            f"with {lane.value} lane (compatible: "
                            f"{[lk.value for lk in entry.compatible_lanes]})"
                        ),
                        field_path=f"lane_plans[{lane.value}].window.template_id",
                        fix_hint=(
                            f"Replace with a {lane.value}-compatible template. "
                            f"Examples: {', '.join(suggestions)}"
                        ),
                    )
                )

        # Resolve timing (using PlanningTimeRef)
        try:
            start_ms = self.timing_context.resolve_planning_time_ref(window.start)
            end_ms = self.timing_context.resolve_planning_time_ref(window.end)
        except ValueError as e:
            errors.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="INVALID_PLANNING_TIMEREF",
                    message=f"Cannot resolve window PlanningTimeRef: {e}",
                    field_path=f"lane_plans[{lane.value}].window.start/end",
                )
            )
            return errors, group_timings

        # Validate intensity is a valid IntensityLevel enum
        if not isinstance(window.intensity, IntensityLevel):
            try:
                IntensityLevel(window.intensity)
            except ValueError:
                errors.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="INVALID_INTENSITY_LEVEL",
                        message=(
                            f"Invalid window intensity '{window.intensity}'. "
                            f"Must be one of: WHISPER, SOFT, MED, STRONG, PEAK"
                        ),
                        field_path=f"lane_plans[{lane.value}].window.intensity",
                        fix_hint="Use a valid IntensityLevel: WHISPER, SOFT, MED, STRONG, PEAK",
                    )
                )

        # Check timing within section bounds
        # With categorical planning, renderer will clamp windows that extend
        # past section end. Only error if start is outside section.
        if section_start_ms is not None and section_end_ms is not None:
            if start_ms < section_start_ms or start_ms >= section_end_ms:
                errors.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="WINDOW_OUTSIDE_SECTION",
                        message=(
                            f"Window starts at {start_ms}ms which is outside section bounds "
                            f"({section_start_ms}ms-{section_end_ms}ms)"
                        ),
                        field_path=f"lane_plans[{lane.value}].window.start",
                        fix_hint="Adjust window start to be within section bounds",
                    )
                )

        # Track window timing for all groups in this coordination_plan
        for group_id in group_ids:
            group_timings[group_id].append((start_ms, end_ms, f"window:{coordination_mode.value}"))

        return errors, group_timings


# =============================================================================
# Diversity Validation (Phase 1)
# =============================================================================


@dataclass(frozen=True)
class DiversityConstraints:
    """Diversity constraints for a lane.

    Defines minimum variety requirements to prevent repetitive choreography.

    Attributes:
        min_unique_template_ids: Minimum unique templates required.
        max_uses_per_template_id: Maximum uses of any single template.
        max_consecutive_same_template_id: Maximum consecutive uses of same template.
        top2_share_limit: Maximum share of top 2 templates (0.0-1.0).
    """

    min_unique_template_ids: int
    max_uses_per_template_id: int
    max_consecutive_same_template_id: int
    top2_share_limit: float


# Per-lane diversity constraints (for ~16 section songs)
DIVERSITY_CONSTRAINTS = {
    LaneKind.BASE: DiversityConstraints(
        min_unique_template_ids=5,
        max_uses_per_template_id=3,
        max_consecutive_same_template_id=1,  # A→A ok, A→A→A forbidden
        top2_share_limit=0.50,
    ),
    LaneKind.RHYTHM: DiversityConstraints(
        min_unique_template_ids=9,
        max_uses_per_template_id=2,
        max_consecutive_same_template_id=0,  # A→A forbidden
        top2_share_limit=0.35,
    ),
    LaneKind.ACCENT: DiversityConstraints(
        min_unique_template_ids=8,
        max_uses_per_template_id=2,
        max_consecutive_same_template_id=0,  # A→A forbidden
        top2_share_limit=0.35,
    ),
}


@dataclass(frozen=True)
class LaneDiversityStats:
    """Diversity statistics for a lane.

    Attributes:
        lane: Lane being analyzed.
        total_placements: Total number of placements in lane.
        unique_template_ids: Number of unique template_ids used.
        max_uses_single_template: Maximum uses of any single template.
        max_consecutive_same_template: Maximum consecutive uses of same template.
        top2_share: Share of placements covered by top 2 templates (0.0-1.0).
        template_use_counts: Dict mapping template_id to use count.
    """

    lane: LaneKind
    total_placements: int
    unique_template_ids: int
    max_uses_single_template: int
    max_consecutive_same_template: int
    top2_share: float
    template_use_counts: dict[str, int]


def compute_lane_stats(
    placements: list[GroupPlacement],
    lane: LaneKind,
) -> LaneDiversityStats:
    """Compute diversity statistics for lane placements.

    Args:
        placements: List of GroupPlacement for this lane.
        lane: Lane being analyzed.

    Returns:
        LaneDiversityStats with computed statistics.
    """
    from collections import Counter

    if not placements:
        return LaneDiversityStats(
            lane=lane,
            total_placements=0,
            unique_template_ids=0,
            max_uses_single_template=0,
            max_consecutive_same_template=0,
            top2_share=0.0,
            template_use_counts={},
        )

    template_ids = [p.template_id for p in placements]
    use_counts = Counter(template_ids)

    unique = len(use_counts)
    max_uses = max(use_counts.values())

    # Max consecutive same template
    max_consecutive = 1
    current_consecutive = 1
    for i in range(1, len(template_ids)):
        if template_ids[i] == template_ids[i - 1]:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 1

    # Top 2 share
    top2_count = sum(sorted(use_counts.values(), reverse=True)[:2])
    top2_share = top2_count / len(placements)

    return LaneDiversityStats(
        lane=lane,
        total_placements=len(placements),
        unique_template_ids=unique,
        max_uses_single_template=max_uses,
        max_consecutive_same_template=max_consecutive,
        top2_share=top2_share,
        template_use_counts=dict(use_counts),
    )


def validate_lane_diversity(
    stats: LaneDiversityStats,
    constraints: DiversityConstraints,
) -> list[ValidationIssue]:
    """Validate lane diversity against constraints.

    Args:
        stats: Computed diversity statistics.
        constraints: Diversity constraints to validate against.

    Returns:
        List of ValidationIssue (may be empty if no issues).
    """
    issues: list[ValidationIssue] = []

    # Check min_unique_template_ids
    if stats.unique_template_ids < constraints.min_unique_template_ids:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="INSUFFICIENT_UNIQUE_TEMPLATES",
                message=(
                    f"Insufficient unique templates: {stats.unique_template_ids} "
                    f"(need {constraints.min_unique_template_ids})"
                ),
                field_path=f"lane={stats.lane.value}",
                fix_hint=(
                    f"Add {constraints.min_unique_template_ids - stats.unique_template_ids} "
                    f"more distinct template_ids to {stats.lane.value} lane"
                ),
            )
        )

    # Check max_uses_per_template_id
    if stats.max_uses_single_template > constraints.max_uses_per_template_id:
        overused = [
            tid
            for tid, count in stats.template_use_counts.items()
            if count > constraints.max_uses_per_template_id
        ]
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="TEMPLATE_OVERUSED",
                message=(
                    f"Template(s) overused: {overused} "
                    f"(max {constraints.max_uses_per_template_id} uses)"
                ),
                field_path=f"lane={stats.lane.value}",
                fix_hint="Replace some uses with unused templates",
            )
        )

    # Check max_consecutive_same_template_id
    if stats.max_consecutive_same_template > constraints.max_consecutive_same_template_id:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="CONSECUTIVE_REUSE_VIOLATION",
                message=(
                    f"Consecutive reuse violation: {stats.max_consecutive_same_template} "
                    f"consecutive uses (max {constraints.max_consecutive_same_template_id})"
                ),
                field_path=f"lane={stats.lane.value}",
                fix_hint=f"Break up consecutive sequences in {stats.lane.value} lane",
            )
        )

    # Check top2_share (WARNING only)
    if stats.top2_share > constraints.top2_share_limit:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="TOP_HEAVY_DISTRIBUTION",
                message=(
                    f"Top-heavy distribution: top 2 templates cover {stats.top2_share:.1%} "
                    f"(limit {constraints.top2_share_limit:.1%})"
                ),
                field_path=f"lane={stats.lane.value}",
                fix_hint="Distribute placements more evenly across available templates",
            )
        )

    return issues


def validate_section_diversity(plan: SectionCoordinationPlan) -> ValidationResult:
    """Validate diversity across all lanes in section plan.

    Args:
        plan: SectionCoordinationPlan to validate.

    Returns:
        ValidationResult with diversity-specific errors and warnings.
    """
    all_errors: list[ValidationIssue] = []
    all_warnings: list[ValidationIssue] = []

    for lane_plan in plan.lane_plans:
        lane = lane_plan.lane

        # Collect all placements for this lane
        placements: list[GroupPlacement] = []
        for coord_plan in lane_plan.coordination_plans:
            placements.extend(coord_plan.placements)

        # Skip lanes with no placements
        if not placements:
            continue

        # Compute stats
        stats = compute_lane_stats(placements, lane)

        # Get constraints (skip if no constraints for this lane)
        constraints = DIVERSITY_CONSTRAINTS.get(lane)
        if not constraints:
            continue

        # Validate
        lane_issues = validate_lane_diversity(stats, constraints)

        # Separate errors and warnings
        for issue in lane_issues:
            if issue.severity == ValidationSeverity.ERROR:
                all_errors.append(issue)
            else:
                all_warnings.append(issue)

    return ValidationResult(
        is_valid=len(all_errors) == 0,
        errors=all_errors,
        warnings=all_warnings,
    )
