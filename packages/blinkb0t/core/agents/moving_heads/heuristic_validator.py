"""Heuristic validation for generated plans.

Fast, deterministic checks without LLM calls.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentPlan
from blinkb0t.core.config.poses import PoseLibrary

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """Validation issue severity."""

    ERROR = "error"  # Blocks progress
    WARNING = "warning"  # Noted but not blocking
    INFO = "info"  # Informational only


class ValidationIssue(BaseModel):
    """Single validation issue.

    Converted from dataclass to Pydantic for validation and serialization.
    """

    severity: Severity = Field(description="Issue severity level")
    rule: str = Field(description="Validation rule that triggered")
    section_name: str | None = Field(default=None, description="Section where issue occurred")
    message: str = Field(description="Human-readable issue description")

    model_config = ConfigDict(frozen=True, extra="forbid")


class ValidationResult(BaseModel):
    """Result of heuristic validation.

    Converted from dataclass to Pydantic for validation and serialization.
    Note: Pydantic models can have methods, so add_error/warning/info work as before.
    """

    passed: bool = Field(description="Whether validation passed")
    issues: list[ValidationIssue] = Field(default_factory=list, description="List of issues found")
    error_count: int = Field(default=0, ge=0, description="Number of errors")
    warning_count: int = Field(default=0, ge=0, description="Number of warnings")
    info_count: int = Field(default=0, ge=0, description="Number of info messages")

    model_config = ConfigDict(frozen=False, extra="forbid")  # Allow mutation for building result

    def add_error(self, rule: str, message: str, section_name: str | None = None) -> None:
        """Add error issue."""
        self.issues.append(
            ValidationIssue(
                severity=Severity.ERROR,
                rule=rule,
                section_name=section_name,
                message=message,
            )
        )
        self.error_count += 1
        self.passed = False

    def add_warning(self, rule: str, message: str, section_name: str | None = None) -> None:
        """Add warning issue."""
        self.issues.append(
            ValidationIssue(
                severity=Severity.WARNING,
                rule=rule,
                section_name=section_name,
                message=message,
            )
        )
        self.warning_count += 1

    def add_info(self, rule: str, message: str, section_name: str | None = None) -> None:
        """Add informational issue (non-blocking)."""
        self.issues.append(
            ValidationIssue(
                severity=Severity.INFO,
                rule=rule,
                section_name=section_name,
                message=message,
            )
        )
        self.info_count += 1

    def get_error_summary(self) -> str:
        """Get summary of errors."""
        if not self.issues:
            return "No issues"

        lines = [
            f"Validation issues: {self.error_count} errors, {self.warning_count} warnings, {self.info_count} info\n"
        ]

        for issue in self.issues:
            if issue.severity == Severity.ERROR:
                prefix = "❌"
            elif issue.severity == Severity.WARNING:
                prefix = "⚠️"
            else:  # INFO
                prefix = "ℹ️"

            section = f" [{issue.section_name}]" if issue.section_name else ""
            lines.append(f"{prefix} {issue.rule}{section}: {issue.message}")

        return "\n".join(lines)


class HeuristicValidator:
    """Validates plans using heuristic rules (no LLM).

    Validates:
    1. Timing (no gaps, overlaps, negative durations)
    2. Templates (valid IDs, parameters)
    3. Poses (valid pose IDs)
    4. Energy (template matches section)
    5. Coverage (full song covered)

    Example:
        validator = HeuristicValidator(
            template_metadata=template_metadata,
            song_features=song_features
        )

        result = validator.validate(plan)

        if result.passed:
            print("Plan is valid")
        else:
            print(result.get_error_summary())
    """

    def __init__(
        self, template_metadata: list[dict[str, Any]], song_features: dict[str, Any]
    ) -> None:
        """Initialize heuristic validator.

        Args:
            template_metadata: Template metadata for checking IDs
            song_features: Audio features for coverage check
        """
        self.song_features = song_features

        # Load template metadata for validation
        self.template_metadata = {meta["template_id"]: meta for meta in template_metadata}

        # Get valid pose IDs
        self.valid_poses = {pose.value for pose in PoseLibrary}

        # Get valid categorical parameters
        self.valid_intensity = ["SMOOTH", "DRAMATIC", "INTENSE"]
        self.valid_speed = ["SLOW", "MODERATE", "FAST"]

        logger.debug("HeuristicValidator initialized")

    def validate(self, plan: AgentPlan) -> ValidationResult:
        """Validate plan against heuristic rules.

        Args:
            plan: Plan to validate

        Returns:
            ValidationResult with issues
        """
        logger.info("Running heuristic validation...")

        result = ValidationResult(passed=True)

        # Run validation rules
        self._validate_timing(plan, result)
        self._validate_templates(plan, result)
        self._validate_poses(plan, result)
        self._validate_parameters(plan, result)
        self._validate_channels(plan, result)
        self._validate_energy(plan, result)
        self._validate_coverage(plan, result)
        self._validate_variety(plan, result)
        self._validate_complexity(plan, result)  # Complexity

        logger.info(
            f"Validation complete: "
            f"{'PASSED' if result.passed else 'FAILED'} "
            f"({result.error_count} errors, {result.warning_count} warnings)"
        )

        return result

    # ========================================================================
    # Private Methods - Validation Rules
    # ========================================================================

    def _validate_timing(self, plan: AgentPlan, result: ValidationResult) -> None:
        """Validate timing constraints."""
        sections = plan.sections

        if not sections:
            result.add_error("timing", "No sections in plan")
            return

        # Sort by start_bar
        sorted_sections = sorted(sections, key=lambda s: s.start_bar)

        # Check first section starts at bar 1
        if sorted_sections[0].start_bar != 1:
            result.add_error(
                "timing",
                f"First section starts at bar {sorted_sections[0].start_bar}, should start at 1",
                sorted_sections[0].name,
            )

        # Check for gaps and overlaps
        for i in range(len(sorted_sections) - 1):
            current = sorted_sections[i]
            next_section = sorted_sections[i + 1]

            # Check duration
            if current.end_bar < current.start_bar:
                result.add_error(
                    "timing",
                    f"Negative duration: bars {current.start_bar}-{current.end_bar}",
                    current.name,
                )

            # Check gap
            if current.end_bar + 1 < next_section.start_bar:
                gap_bars = next_section.start_bar - current.end_bar - 1
                result.add_error(
                    "timing",
                    f"Gap of {gap_bars} bars between '{current.name}' and '{next_section.name}'",
                    current.name,
                )

            # Check overlap - BUT allow overlaps if targets are different (multi-layering)
            if current.end_bar >= next_section.start_bar:
                overlap_bars = current.end_bar - next_section.start_bar + 1

                result.add_info(
                    "timing",
                    f"Sections '{current.name}' and '{next_section.name}' overlap {overlap_bars} bars "
                    f"(layering - target conflicts checked in implementation validation)",
                    current.name,
                )

    def _validate_templates(self, plan: AgentPlan, result: ValidationResult) -> None:
        """Validate template IDs exist in library."""
        for section in plan.sections:
            # Plans have multiple templates per section (for layering)
            for template_id in section.templates:
                if template_id not in self.template_metadata:
                    result.add_error(
                        "template",
                        f"Template '{template_id}' not found in library",
                        section.name,
                    )
                    continue

                # Check template has metadata (only for valid templates)
                meta = self.template_metadata[template_id]
                if not meta:
                    result.add_warning(
                        "template",
                        f"Template '{template_id}' has incomplete metadata",
                        section.name,
                    )

    def _validate_poses(self, plan: AgentPlan, result: ValidationResult) -> None:
        """Validate pose IDs are valid."""
        for section in plan.sections:
            pose_id = section.base_pose

            if pose_id not in self.valid_poses:
                result.add_error(
                    "pose",
                    f"Invalid pose ID '{pose_id}'. Valid: {sorted(self.valid_poses)}",
                    section.name,
                )

    def _validate_parameters(self, plan: AgentPlan, result: ValidationResult) -> None:
        """Validate categorical parameters."""
        for section in plan.sections:
            params = section.params

            # Check intensity
            if "intensity" in params:
                intensity = params["intensity"]
                if intensity not in self.valid_intensity:
                    result.add_error(
                        "parameters",
                        f"Invalid intensity '{intensity}'. Valid: {self.valid_intensity}",
                        section.name,
                    )

            # Check speed
            if "speed" in params:
                speed = params["speed"]
                if speed not in self.valid_speed:
                    result.add_error(
                        "parameters",
                        f"Invalid speed '{speed}'. Valid: {self.valid_speed}",
                        section.name,
                    )

            # Check scale (if present - deprecated but still validate if used)
            if "scale" in params:
                scale = params["scale"]
                valid_scale = ["SMALL", "MEDIUM", "LARGE"]
                if scale not in valid_scale:
                    result.add_error(
                        "parameters",
                        f"Invalid scale '{scale}'. Valid: {valid_scale}",
                        section.name,
                    )

    def _validate_energy(self, plan: AgentPlan, result: ValidationResult) -> None:
        """Validate energy alignment between section and template."""
        for section in plan.sections:
            section_energy = section.energy_level

            # Plans have multiple templates per section
            # Check energy against each template
            for template_id in section.templates:
                # Skip if template not found (already reported)
                if template_id not in self.template_metadata:
                    continue

                meta = self.template_metadata[template_id]
                template_energy_range = meta.get("metadata", {}).get("energy_range", [0, 100])

                # Check if section energy is within template range
                if (
                    section_energy < template_energy_range[0]
                    or section_energy > template_energy_range[1]
                ):
                    result.add_warning(
                        "energy",
                        f"Energy mismatch: section={section_energy}, "
                        f"template range={template_energy_range}",
                        section.name,
                    )

    def _validate_coverage(self, plan: AgentPlan, result: ValidationResult) -> None:
        """Validate full song is covered."""
        bar_count = len(self.song_features["bars_s"])

        if not plan.sections:
            result.add_error("coverage", "No sections in plan")
            return

        # Sort sections
        sorted_sections = sorted(plan.sections, key=lambda s: s.start_bar)

        # Check last section covers end
        last_section = sorted_sections[-1]
        if last_section.end_bar < bar_count:
            uncovered_bars = bar_count - last_section.end_bar
            result.add_warning(
                "coverage",
                f"Song not fully covered: missing last {uncovered_bars} bars (total: {bar_count})",
                last_section.name,
            )

        # Check if coverage extends beyond song
        if last_section.end_bar > bar_count:
            extra_bars = last_section.end_bar - bar_count
            result.add_warning(
                "coverage",
                f"Plan extends {extra_bars} bars beyond song end",
                last_section.name,
            )

    def _validate_variety(self, plan: AgentPlan, result: ValidationResult) -> None:
        """Validate template variety (warning only)."""
        # Flatten all templates from all sections
        all_templates = [tid for section in plan.sections for tid in section.templates]
        unique_templates = set(all_templates)

        # Check for repeated templates in consecutive sections
        for i in range(len(plan.sections) - 1):
            # Check if any templates repeat between consecutive sections
            current_templates = set(plan.sections[i].templates)
            next_templates = set(plan.sections[i + 1].templates)
            overlap = current_templates & next_templates  # Intersection
            if overlap:
                result.add_warning(
                    "variety",
                    f"Templates {overlap} repeated in consecutive sections",
                    plan.sections[i].name,
                )

        # Check overall variety (compare unique templates to total template uses)
        variety_ratio = len(unique_templates) / len(all_templates) if all_templates else 0
        if variety_ratio < 0.5:
            result.add_warning(
                "variety",
                f"Low template variety: {len(unique_templates)} unique templates "
                f"across {len(all_templates)} template uses ({variety_ratio:.0%})",
            )

    def _validate_channels(self, plan: AgentPlan, result: ValidationResult) -> None:
        """Validate channel specifications.

        NOTE: Channel validation is not yet implemented. SectionPlan does not
        have a 'channels' attribute yet. This method is a placeholder.

        Checks (when implemented):
        - Channel appropriateness for energy level
        - Conflicts (e.g., closed shutter with gobo)
        """
        # Channel validation not implemented - SectionPlan has no channels attribute
        pass

    def _targets_conflict(self, target1: str, target2: str) -> bool:
        """Check if two targets have potential fixture conflicts.

        CRITICAL: Any overlapping semantic groups are conflicts, including superset+subset.
        For example:
        - "ALL" + "OUTER" = CONFLICT (OUTER fixtures would receive conflicting instructions)
        - "LEFT" + "ODD" = CONFLICT (MH1 would receive conflicting instructions)
        - "CENTER" + "LEFT" = CONFLICT (MH2 would receive conflicting instructions)

        Only NON-overlapping groups can layer simultaneously.
        Based on build_semantic_groups() logic, the disjoint pairs are:
        - "LEFT" + "RIGHT" = OK (completely disjoint by design)
        - "ODD" + "EVEN" = OK (completely disjoint by design)
        - "CENTER" + "OUTER" = OK (when n >= 4, completely disjoint)
        - "INNER" + "OUTER" = OK (when n >= 6, completely disjoint)
        - Individual fixtures that differ = OK (e.g., "MH1" + "MH2")

        Args:
            target1: First target identifier (e.g., "ALL", "ODD", "LEFT")
            target2: Second target identifier

        Returns:
            True if targets would cause fixture conflicts, False if layering is OK
        """
        # Normalize targets
        t1 = target1.upper()
        t2 = target2.upper()

        # Same target = conflict
        if t1 == t2:
            return True

        # ALL encompasses every other group, so ALL + anything else = conflict
        if t1 == "ALL" or t2 == "ALL":
            return True

        # Define the ONLY valid (non-overlapping) semantic group pairs
        # Based on build_semantic_groups() algorithm:
        # - LEFT/RIGHT: split array in half (disjoint by definition)
        # - ODD/EVEN: alternate indices (disjoint by definition)
        # - CENTER/OUTER: CENTER is middle 50%, OUTER is outer 25% (disjoint by definition)
        # - INNER/OUTER: INNER is middle 33%, OUTER is computed separately (disjoint when both exist)
        valid_pairs = [
            ("LEFT", "RIGHT"),  # Horizontal split: fixtures[0:n//2] vs fixtures[n//2:]
            ("ODD", "EVEN"),  # Parity split: fixtures[0::2] vs fixtures[1::2]
            ("CENTER", "OUTER"),  # Center vs edges (when n >= 4)
            ("INNER", "OUTER"),  # Inner vs outer (when n >= 6)
        ]

        # Check if this is a valid non-overlapping pair
        for pair1, pair2 in valid_pairs:
            if (t1 == pair1 and t2 == pair2) or (t1 == pair2 and t2 == pair1):
                return False  # No conflict - targets are disjoint by design

        # Check if both are individual fixture IDs (e.g., "MH1", "MH2")
        # Individual fixtures don't overlap unless they're the same (already checked above)
        known_groups = {"ALL", "LEFT", "RIGHT", "CENTER", "INNER", "OUTER", "ODD", "EVEN"}
        if t1 not in known_groups and t2 not in known_groups:
            return False  # Different individual fixtures don't conflict

        # Everything else overlaps and conflicts:
        # - LEFT/ODD, LEFT/EVEN, LEFT/CENTER, LEFT/OUTER (all share fixtures)
        # - RIGHT/ODD, RIGHT/EVEN, RIGHT/CENTER, RIGHT/OUTER (all share fixtures)
        # - ODD/CENTER, EVEN/CENTER (share fixtures)
        # - ODD/OUTER, EVEN/OUTER (share fixtures)
        # - CENTER/INNER (when both exist, they share fixtures)
        # - Any group + individual fixture (e.g., "LEFT" + "MH1")
        return True

    def _validate_complexity(self, plan: AgentPlan, result: ValidationResult) -> None:
        """Validate plan has appropriate complexity for engaging choreography.

        Checks for:
        - Multi-layer sections (overlapping targets)
        - Target variety (not just ALL)
        - Transition variety (mix of modes)

        Args:
            plan: Plan to validate
            result: ValidationResult to update
        """
        # Check for layering (overlapping sections)
        overlapping_count = self._count_overlapping_sections(plan)

        if overlapping_count == 0:
            result.add_warning(
                "complexity",
                "No multi-layer sections detected. Consider adding accent layers for richer choreography.",
            )
        elif overlapping_count < len(plan.sections) * 0.2:  # Less than 20%
            result.add_warning(
                "complexity",
                f"Only {overlapping_count} overlapping sections found. "
                "Consider more layering for depth and visual interest.",
            )

        # NOTE: SectionPlan doesn't have 'target' or 'transition_out'
        # Those are on ImplementationSection. Target/transition variety is checked
        # during implementation validation, not plan validation.
        # Plans should be checked for template variety and layering potential.

    def _count_overlapping_sections(self, plan: AgentPlan) -> int:
        """Count number of sections that overlap with others.

        Args:
            plan: Plan to analyze

        Returns:
            Number of overlapping sections
        """
        overlapping_count = 0

        for i, section1 in enumerate(plan.sections):
            for section2 in plan.sections[i + 1 :]:
                # Check if sections overlap in time
                if not (
                    section1.end_bar < section2.start_bar or section2.end_bar < section1.start_bar
                ):
                    # Plans don't have targets (implementation agent decides)
                    # Overlaps are allowed for layering
                    overlapping_count += 1
                    break  # Count each section only once

        return overlapping_count
