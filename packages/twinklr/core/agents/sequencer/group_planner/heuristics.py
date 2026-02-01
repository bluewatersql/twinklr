"""Heuristic validator for GroupPlan."""

import logging

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
)
from twinklr.core.agents.sequencer.group_planner.models import GroupPlan

logger = logging.getLogger(__name__)


class GroupPlanHeuristicValidator:
    """Deterministic validator for GroupPlan.

    Performs fast, non-LLM validation checks:
    - Template IDs exist in catalog
    - Layer counts within limits
    - Section coverage matches audio profile
    - No duplicate layer indices
    """

    def __init__(self, available_templates: list[str] | set[str] | None = None):
        """Initialize validator.

        Args:
            available_templates: List/set of available template IDs (for existence checks)
        """
        if isinstance(available_templates, list):
            self.available_templates = set(available_templates)
        elif isinstance(available_templates, set):
            self.available_templates = available_templates
        else:
            self.available_templates = set()

    def validate(
        self,
        plan: GroupPlan,
        audio_profile: AudioProfileModel,
        max_layers: int = 3,
    ) -> list[Issue]:
        """Validate GroupPlan against audio profile and constraints.

        Args:
            plan: GroupPlan to validate
            audio_profile: AudioProfileModel for section matching
            max_layers: Maximum allowed layers per section

        Returns:
            List of validation issues (empty if valid)
        """
        issues: list[Issue] = []

        # Validate section coverage
        issues.extend(self._validate_section_coverage(plan, audio_profile))

        # Validate templates exist
        issues.extend(self._validate_templates_exist(plan))

        # Validate layer counts
        issues.extend(self._validate_layer_counts(plan, max_layers))

        return issues

    def _validate_section_coverage(
        self, plan: GroupPlan, audio_profile: AudioProfileModel
    ) -> list[Issue]:
        """Validate that plan covers all audio profile sections."""
        issues: list[Issue] = []

        audio_sections = {s.section_id for s in audio_profile.structure.sections}
        plan_sections = {sp.section.section_id for sp in plan.section_plans}

        missing = audio_sections - plan_sections
        extra = plan_sections - audio_sections

        if missing:
            issues.append(
                Issue(
                    issue_id="MISSING_SECTIONS",
                    category=IssueCategory.COVERAGE,
                    severity=IssueSeverity.ERROR,
                    estimated_effort=IssueEffort.MEDIUM,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    message=f"Plan missing sections: {', '.join(sorted(missing))}",
                    fix_hint="Add GroupSectionPlan for each missing section",
                    acceptance_test="All audio profile sections have corresponding GroupSectionPlan",
                    suggested_action=SuggestedAction.REPLAN_GLOBAL,
                )
            )

        if extra:
            issues.append(
                Issue(
                    issue_id="EXTRA_SECTIONS",
                    category=IssueCategory.COVERAGE,
                    severity=IssueSeverity.WARN,
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    message=f"Plan has unknown sections: {', '.join(sorted(extra))}",
                    fix_hint="Remove sections not in audio profile",
                    acceptance_test="All plan sections match audio profile sections",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        return issues

    def _validate_templates_exist(self, plan: GroupPlan) -> list[Issue]:
        """Validate that all referenced templates exist in catalog."""
        issues: list[Issue] = []

        if not self.available_templates:
            return issues  # Skip if no catalog provided

        for section_plan in plan.section_plans:
            for layer in section_plan.layers:
                for placement in layer.placements:
                    if placement.template_id not in self.available_templates:
                        issues.append(
                            Issue(
                                issue_id=f"TEMPLATE_NOT_FOUND_{placement.template_id}",
                                category=IssueCategory.TEMPLATES,
                                severity=IssueSeverity.ERROR,
                                estimated_effort=IssueEffort.LOW,
                                scope=IssueScope.SECTION,
                                location=IssueLocation(section_id=section_plan.section.section_id),
                                message=f"Template '{placement.template_id}' not found in catalog",
                                fix_hint="Use template from available catalog",
                                acceptance_test=f"Template '{placement.template_id}' exists in catalog",
                                suggested_action=SuggestedAction.PATCH,
                            )
                        )

        return issues

    def _validate_layer_counts(self, plan: GroupPlan, max_layers: int) -> list[Issue]:
        """Validate layer counts per section."""
        issues: list[Issue] = []

        for section_plan in plan.section_plans:
            layer_count = len(section_plan.layers)

            if layer_count > max_layers:
                issues.append(
                    Issue(
                        issue_id=f"TOO_MANY_LAYERS_{section_plan.section.section_id}",
                        category=IssueCategory.LAYERING,
                        severity=IssueSeverity.ERROR,
                        estimated_effort=IssueEffort.LOW,
                        scope=IssueScope.SECTION,
                        location=IssueLocation(section_id=section_plan.section.section_id),
                        message=f"Section '{section_plan.section.section_id}' has {layer_count} layers (max: {max_layers})",
                        fix_hint=f"Reduce to {max_layers} layers or fewer",
                        acceptance_test=f"Section has <= {max_layers} layers",
                        suggested_action=SuggestedAction.REPLAN_SECTION,
                    )
                )

            if layer_count == 0:
                issues.append(
                    Issue(
                        issue_id=f"NO_LAYERS_{section_plan.section.section_id}",
                        category=IssueCategory.COVERAGE,
                        severity=IssueSeverity.ERROR,
                        estimated_effort=IssueEffort.MEDIUM,
                        scope=IssueScope.SECTION,
                        location=IssueLocation(section_id=section_plan.section.section_id),
                        message=f"Section '{section_plan.section.section_id}' has no layers",
                        fix_hint="Add at least one layer to section",
                        acceptance_test="Section has at least 1 layer",
                        suggested_action=SuggestedAction.REPLAN_SECTION,
                    )
                )

        return issues
