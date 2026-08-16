"""Deterministic validation for the typed MacroPlan contract."""

from __future__ import annotations

from typing import Any

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueLocation,
    IssueSeverity,
)
from twinklr.core.sequencer.planning import MacroPlan
from twinklr.core.sequencer.templates.group.models import PlanTarget
from twinklr.core.sequencer.vocabulary import TargetType


def _issue(
    issue_id: str,
    category: IssueCategory,
    severity: IssueSeverity,
    message: str,
    *,
    field_path: str | None = None,
    section_id: str | None = None,
) -> Issue:
    return Issue(
        issue_id=issue_id,
        category=category,
        severity=severity,
        location=IssueLocation(
            section_id=section_id,
            group_id=None,
            effect_id=None,
            bar_start=None,
            bar_end=None,
            field_path=field_path,
        ),
        rule="DON'T reference intent that is absent from the supplied catalogs or layout",
        message=message,
        fix_hint="Use an identifier supplied in the planner context.",
        acceptance_test="Every macro reference resolves against its supplied catalog or layout.",
        generic_example=None,
        targeted_actions=[],
    )


class MacroPlanHeuristicValidator:
    """Cross-validates a schema-valid MacroPlan against external inputs."""

    def validate(
        self,
        plan: MacroPlan,
        audio_profile: AudioProfileModel,
        *,
        motif_by_id: dict[str, object] | None = None,
        palette_ids: set[str] | None = None,
        theme_ids: set[str] | None = None,
        tag_ids: set[str] | None = None,
        display_groups: list[dict[str, Any]] | None = None,
    ) -> list[Issue]:
        issues = self._validate_section_coverage(plan, audio_profile)
        issues.extend(self._validate_target_validity(plan, display_groups))
        issues.extend(self._validate_palette_catalog(plan, palette_ids))
        issues.extend(self._validate_motif_catalog(plan, motif_by_id))
        issues.extend(self._validate_theme_catalog(plan, theme_ids, tag_ids))
        issues.extend(self._check_contrast(plan))
        return issues

    @staticmethod
    def has_errors(issues: list[Issue]) -> bool:
        return any(item.severity == IssueSeverity.ERROR for item in issues)

    @staticmethod
    def has_warnings(issues: list[Issue]) -> bool:
        return any(item.severity == IssueSeverity.WARN for item in issues)

    def _validate_section_coverage(
        self,
        plan: MacroPlan,
        audio_profile: AudioProfileModel,
    ) -> list[Issue]:
        expected_refs = list(audio_profile.structure.sections)
        actual_refs = [item.section for item in plan.sections]
        expected = {item.section_id for item in expected_refs}
        actual = {item.section_id for item in actual_refs}
        issues: list[Issue] = []
        expected_canonical = [
            (item.section_id, item.name, int(item.start_ms), int(item.end_ms))
            for item in expected_refs
        ]
        actual_canonical = [
            (item.section_id, item.name, int(item.start_ms), int(item.end_ms))
            for item in actual_refs
        ]
        if actual_canonical != expected_canonical:
            issues.append(
                _issue(
                    "COVERAGE_SECTION_MISMATCH",
                    IssueCategory.COVERAGE,
                    IssueSeverity.ERROR,
                    "Macro sections must exactly equal canonical audio sections in order "
                    f"(section_id, name, start_ms, end_ms); expected={expected_canonical}, "
                    f"actual={actual_canonical}",
                    field_path="sections",
                )
            )
        if missing := sorted(expected - actual):
            issues.append(
                _issue(
                    "COVERAGE_MISSING_SECTIONS",
                    IssueCategory.COVERAGE,
                    IssueSeverity.ERROR,
                    f"Missing macro sections: {missing}",
                    field_path="sections",
                )
            )
        if extra := sorted(actual - expected):
            issues.append(
                _issue(
                    "COVERAGE_EXTRA_SECTIONS",
                    IssueCategory.COVERAGE,
                    IssueSeverity.WARN,
                    f"Macro sections absent from audio profile: {extra}",
                    field_path="sections",
                )
            )
        return issues

    def _validate_target_validity(
        self,
        plan: MacroPlan,
        display_groups: list[dict[str, Any]] | None,
    ) -> list[Issue]:
        if not display_groups:
            return []
        groups: set[str] = set()
        zones: set[str] = set()
        splits: set[str] = set()
        for group in display_groups:
            if group_id := str(group.get("id") or "").strip():
                groups.add(group_id)
            for tag in group.get("tags") or []:
                zones.add(str(tag))
            for split in group.get("split_membership") or group.get("splits") or []:
                splits.add(str(split))

        issues: list[Issue] = []
        for section in plan.sections:
            section_id = section.section.section_id
            targets = [item.target for item in section.focal_roles]
            for pair in section.call_response_pairs:
                targets.extend((pair.call, pair.response))
            for target in targets:
                issues.extend(self._target_issue(target, section_id, groups, zones, splits))
        for assignment in plan.focal_arc:
            issues.extend(
                self._target_issue(
                    assignment.lead_target,
                    assignment.section_id,
                    groups,
                    zones,
                    splits,
                )
            )
        return issues

    @staticmethod
    def _target_issue(
        target: PlanTarget,
        section_id: str,
        groups: set[str],
        zones: set[str],
        splits: set[str],
    ) -> list[Issue]:
        allowed = {
            TargetType.GROUP: groups,
            TargetType.ZONE: zones,
            TargetType.SPLIT: splits,
        }[target.type]
        if target.id in allowed:
            return []
        return [
            _issue(
                f"TARGET_{target.type.value.upper()}_UNKNOWN_{section_id}_{target.id}",
                IssueCategory.CONSTRAINT,
                IssueSeverity.ERROR,
                f"Section '{section_id}' references unknown {target.type.value} '{target.id}'.",
                field_path="focal_roles/call_response_pairs/focal_arc",
                section_id=section_id,
            )
        ]

    def _validate_palette_catalog(
        self,
        plan: MacroPlan,
        palette_ids: set[str] | None,
    ) -> list[Issue]:
        if palette_ids is None:
            return []
        referenced = [item.palette.palette_id for item in plan.palette_arc]
        referenced.extend(
            item.palette_role.override.palette_id
            for item in plan.sections
            if item.palette_role.override is not None
        )
        return [
            _issue(
                f"PALETTE_UNKNOWN_{palette_id}",
                IssueCategory.CONSTRAINT,
                IssueSeverity.ERROR,
                f"Unknown palette_id '{palette_id}'.",
                field_path="palette_arc/palette_role.override",
            )
            for palette_id in referenced
            if palette_id not in palette_ids
        ]

    def _validate_motif_catalog(
        self,
        plan: MacroPlan,
        motif_by_id: dict[str, object] | None,
    ) -> list[Issue]:
        if motif_by_id is None:
            return []
        return [
            _issue(
                f"MOTIF_UNKNOWN_{thread.motif_id}",
                IssueCategory.CONSTRAINT,
                IssueSeverity.ERROR,
                f"Unknown motif_id '{thread.motif_id}'.",
                field_path="motif_continuity",
            )
            for thread in plan.motif_continuity
            if thread.motif_id not in motif_by_id
        ]

    def _validate_theme_catalog(
        self,
        plan: MacroPlan,
        theme_ids: set[str] | None,
        tag_ids: set[str] | None,
    ) -> list[Issue]:
        issues: list[Issue] = []
        for section in plan.sections:
            theme = section.theme
            if theme_ids is not None and theme.theme_id not in theme_ids:
                issues.append(
                    _issue(
                        f"THEME_UNKNOWN_{theme.theme_id}",
                        IssueCategory.CONSTRAINT,
                        IssueSeverity.ERROR,
                        f"Unknown theme_id '{theme.theme_id}'.",
                        field_path="sections/theme/theme_id",
                        section_id=section.section.section_id,
                    )
                )
            if tag_ids is not None:
                for tag in theme.tags:
                    if tag not in tag_ids:
                        issues.append(
                            _issue(
                                f"THEME_TAG_UNKNOWN_{tag}",
                                IssueCategory.CONSTRAINT,
                                IssueSeverity.ERROR,
                                f"Unknown theme tag '{tag}'.",
                                field_path="sections/theme/tags",
                                section_id=section.section.section_id,
                            )
                        )
        return issues

    def _check_contrast(self, plan: MacroPlan) -> list[Issue]:
        if len(plan.sections) < 2:
            return []
        dimensions = (
            {item.energy_target for item in plan.sections},
            {item.motion_density for item in plan.sections},
            {item.choreography_style for item in plan.sections},
        )
        if any(len(values) > 1 for values in dimensions):
            return []
        return [
            _issue(
                "CONTRAST_MONOTONE",
                IssueCategory.STYLE,
                IssueSeverity.WARN,
                "All sections use the same energy, density, and choreography style.",
                field_path="sections",
            )
        ]


__all__ = ["MacroPlanHeuristicValidator"]
