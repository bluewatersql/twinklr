"""Heuristic validator for MacroPlan V2 (Pattern B - class-based).

Validates the design-spec-compliant MacroPlan schema.
"""

import logging

from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
)
from twinklr.core.agents.sequencer.macro_planner.models import MacroPlan


class MacroPlanHeuristicValidator:
    """Heuristic validator for MacroPlan V2.

    Performs fast, deterministic quality checks:
    - Global story is present and non-empty
    - Sections are present and valid
    - Timing is valid (monotonic, non-overlapping, no gaps)
    - Display groups are specified
    """

    def __init__(self):
        """Initialize validator."""
        self.logger = logging.getLogger(__name__)

    def validate(self, plan: MacroPlan) -> list[Issue]:
        """Validate macro plan using heuristics.

        Args:
            plan: Macro plan to validate

        Returns:
            List of issues (empty if valid)
        """
        self.logger.info("Starting heuristic validation for MacroPlan V2")
        issues: list[Issue] = []

        # Global story validation
        issues.extend(self._check_global_story(plan))

        # Schema validation (fast)
        issues.extend(self._check_sections_present(plan))

        # If no sections, skip further checks
        if not plan.section_plans:
            self.logger.info(f"Validation complete: {len(issues)} issues found")
            return issues

        # Section-level validation
        issues.extend(self._check_display_groups(plan))

        # Timing validation (moderate)
        issues.extend(self._check_sections_monotonic(plan))
        issues.extend(self._check_sections_non_overlapping(plan))
        issues.extend(self._check_sections_no_gaps(plan))

        self.logger.info(f"Validation complete: {len(issues)} issues found")
        return issues

    def _check_global_story(self, plan: MacroPlan) -> list[Issue]:
        """Check that global story is present and complete."""
        issues = []

        # Check theme
        if not plan.global_story.theme or plan.global_story.theme.strip() == "":
            issues.append(
                Issue(
                    issue_id="schema-global-story-theme",
                    category=IssueCategory.SCHEMA,
                    severity=IssueSeverity.ERROR,
                    message="Global story theme is empty",
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    fix_hint="Provide a theme (e.g., 'Joyful celebration', 'Elegant sophistication')",
                    acceptance_test="global_story.theme is non-empty",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        # Check motifs
        if not plan.global_story.motifs:
            issues.append(
                Issue(
                    issue_id="schema-global-story-motifs",
                    category=IssueCategory.SCHEMA,
                    severity=IssueSeverity.ERROR,
                    message="Global story has no motifs",
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    fix_hint="Add at least one motif (e.g., 'Rising intensity', 'Call-and-response')",
                    acceptance_test="global_story.motifs has >= 1 item",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        # Check pacing_notes
        if not plan.global_story.pacing_notes or plan.global_story.pacing_notes.strip() == "":
            issues.append(
                Issue(
                    issue_id="schema-global-story-pacing",
                    category=IssueCategory.SCHEMA,
                    severity=IssueSeverity.ERROR,
                    message="Global story pacing_notes is empty",
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    fix_hint="Describe how energy evolves across the song",
                    acceptance_test="global_story.pacing_notes is non-empty",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        # Check color_story
        if not plan.global_story.color_story or plan.global_story.color_story.strip() == "":
            issues.append(
                Issue(
                    issue_id="schema-global-story-color",
                    category=IssueCategory.SCHEMA,
                    severity=IssueSeverity.ERROR,
                    message="Global story color_story is empty",
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    fix_hint="Describe the color palette and transitions",
                    acceptance_test="global_story.color_story is non-empty",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        return issues

    def _check_sections_present(self, plan: MacroPlan) -> list[Issue]:
        """Check that plan has sections."""
        if not plan.section_plans:
            return [
                Issue(
                    issue_id="schema-001",
                    category=IssueCategory.SCHEMA,
                    severity=IssueSeverity.ERROR,
                    message="Plan has no sections",
                    estimated_effort=IssueEffort.HIGH,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    fix_hint="Add at least one section to the plan",
                    acceptance_test="Plan has >= 1 section",
                    suggested_action=SuggestedAction.REPLAN_GLOBAL,
                )
            ]
        return []

    def _check_display_groups(self, plan: MacroPlan) -> list[Issue]:
        """Check that all sections have primary focus groups."""
        issues = []
        for i, section in enumerate(plan.section_plans):
            if not section.primary_focus_groups:
                issues.append(
                    Issue(
                        issue_id=f"schema-section-groups-{i}",
                        category=IssueCategory.SCHEMA,
                        severity=IssueSeverity.ERROR,
                        message=f"Section {i} ({section.section_name}) has no primary focus groups",
                        estimated_effort=IssueEffort.LOW,
                        scope=IssueScope.SECTION,
                        location=IssueLocation(section_id=section.section_id),
                        fix_hint="Add at least one primary focus group (e.g., 'mega_tree', 'roofline')",
                        acceptance_test="All sections have >= 1 primary_focus_group",
                        suggested_action=SuggestedAction.PATCH,
                    )
                )
        return issues

    def _check_sections_monotonic(self, plan: MacroPlan) -> list[Issue]:
        """Check that sections are in chronological order (start times increasing)."""
        issues = []
        for i in range(1, len(plan.section_plans)):
            prev_section = plan.section_plans[i - 1]
            curr_section = plan.section_plans[i]

            if curr_section.start_ms < prev_section.start_ms:
                issues.append(
                    Issue(
                        issue_id=f"timing-monotonic-{i}",
                        category=IssueCategory.TIMING,
                        severity=IssueSeverity.ERROR,
                        message=(
                            f"Section {i} ({curr_section.section_name}) starts "
                            f"before previous section. "
                            f"Current start: {curr_section.start_ms}ms, "
                            f"Previous start: {prev_section.start_ms}ms"
                        ),
                        estimated_effort=IssueEffort.LOW,
                        scope=IssueScope.SECTION,
                        location=IssueLocation(section_id=curr_section.section_id),
                        fix_hint="Sections must be in chronological order",
                        acceptance_test="All sections have monotonically increasing start times",
                        suggested_action=SuggestedAction.REPLAN_SECTION,
                    )
                )
        return issues

    def _check_sections_non_overlapping(self, plan: MacroPlan) -> list[Issue]:
        """Check that sections don't overlap."""
        issues = []
        for i in range(1, len(plan.section_plans)):
            prev_section = plan.section_plans[i - 1]
            curr_section = plan.section_plans[i]

            if curr_section.start_ms < prev_section.end_ms:
                issues.append(
                    Issue(
                        issue_id=f"timing-overlap-{i}",
                        category=IssueCategory.TIMING,
                        severity=IssueSeverity.ERROR,
                        message=(
                            f"Section {i} ({curr_section.section_name}) overlaps "
                            f"with previous section ({prev_section.section_name}). "
                            f"Current start: {curr_section.start_ms}ms, "
                            f"Previous end: {prev_section.end_ms}ms"
                        ),
                        estimated_effort=IssueEffort.LOW,
                        scope=IssueScope.SECTION,
                        location=IssueLocation(section_id=curr_section.section_id),
                        fix_hint=(
                            f"Adjust start_ms to be >= {prev_section.end_ms}ms "
                            "or adjust previous section's end_ms"
                        ),
                        acceptance_test="No overlapping sections",
                        suggested_action=SuggestedAction.PATCH,
                    )
                )
        return issues

    def _check_sections_no_gaps(self, plan: MacroPlan) -> list[Issue]:
        """Check that there are no gaps between sections."""
        issues = []
        for i in range(1, len(plan.section_plans)):
            prev_section = plan.section_plans[i - 1]
            curr_section = plan.section_plans[i]

            gap_ms = curr_section.start_ms - prev_section.end_ms
            if gap_ms > 0:
                issues.append(
                    Issue(
                        issue_id=f"timing-gap-{i}",
                        category=IssueCategory.TIMING,
                        severity=IssueSeverity.WARN,  # Warning, not error
                        message=(
                            f"Gap of {gap_ms}ms between section {i - 1} "
                            f"({prev_section.section_name}) and section {i} "
                            f"({curr_section.section_name})"
                        ),
                        estimated_effort=IssueEffort.LOW,
                        scope=IssueScope.SECTION,
                        location=IssueLocation(section_id=curr_section.section_id),
                        fix_hint=(
                            f"Consider adjusting timing to eliminate gap. "
                            f"Previous end: {prev_section.end_ms}ms, "
                            f"Current start: {curr_section.start_ms}ms"
                        ),
                        acceptance_test="No gaps between sections",
                        suggested_action=SuggestedAction.PATCH,
                    )
                )
        return issues
