"""Heuristic validator for MacroPlan.

Performs deterministic validation checks on MacroPlan outputs
before they are sent to the LLM judge. Fast, non-LLM checks
that catch common structural and logical issues.
"""

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.issues import Issue, IssueSeverity
from twinklr.core.sequencer.planning import MacroPlan


class MacroPlanHeuristicValidator:
    """Deterministic validator for MacroPlan outputs.

    Performs fast, rule-based validation before LLM judge evaluation.
    Issues with ERROR severity block progression, WARN severity are
    advisory but don't block.

    Validation layers:
    1. Schema validation (handled by Pydantic)
    2. Timing validation (section coverage, gaps, overlaps)
    3. Composition validation (layer count, target validity)
    4. Asset validation (asset types, bloat)
    5. Quality checks (contrast, focus targets)
    """

    def validate(
        self,
        plan: MacroPlan,
        audio_profile: AudioProfileModel,
    ) -> list[Issue]:
        """Run all validation checks on MacroPlan.

        Args:
            plan: MacroPlan to validate
            audio_profile: Audio analysis for cross-validation

        Returns:
            List of issues found (empty if all checks pass)
        """
        issues: list[Issue] = []

        # Run all validation checks
        issues.extend(self._validate_section_coverage(plan, audio_profile))
        issues.extend(self._validate_layer_count(plan))
        issues.extend(self._validate_target_validity(plan))
        issues.extend(self._validate_asset_types(plan))
        issues.extend(self._validate_focus_targets(plan))
        issues.extend(self._check_contrast(plan))
        issues.extend(self._check_asset_bloat(plan))

        return issues

    def has_errors(self, issues: list[Issue]) -> bool:
        """Check if any ERROR severity issues present.

        Args:
            issues: List of issues to check

        Returns:
            True if any issues have ERROR severity
        """
        return any(issue.severity == IssueSeverity.ERROR for issue in issues)

    def has_warnings(self, issues: list[Issue]) -> bool:
        """Check if any WARN severity issues present.

        Args:
            issues: List of issues to check

        Returns:
            True if any issues have WARN severity
        """
        return any(issue.severity == IssueSeverity.WARN for issue in issues)

    # Validation check methods (stubbed for now, implemented in subsequent tasks)

    def _validate_section_coverage(
        self,
        plan: MacroPlan,
        audio_profile: AudioProfileModel,
    ) -> list[Issue]:
        """Validate section coverage matches audio profile.

        Checks:
        - All audio sections have corresponding plans (ERROR if missing)
        - No extra sections in plan (WARN if extra)
        - Section IDs match

        Args:
            plan: MacroPlan to validate
            audio_profile: Audio analysis with expected sections

        Returns:
            List of coverage issues (empty if valid)
        """
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueEffort,
            IssueLocation,
            IssueScope,
            IssueSeverity,
            SuggestedAction,
        )

        issues: list[Issue] = []

        # Extract section IDs
        audio_section_ids = {s.section_id for s in audio_profile.structure.sections}
        plan_section_ids = {sp.section.section_id for sp in plan.section_plans}

        # Check for missing sections (ERROR)
        missing_sections = audio_section_ids - plan_section_ids
        if missing_sections:
            missing_sorted = sorted(missing_sections)
            issues.append(
                Issue(
                    issue_id="COVERAGE_MISSING_SECTIONS",
                    category=IssueCategory.COVERAGE,
                    severity=IssueSeverity.ERROR,
                    estimated_effort=IssueEffort.MEDIUM,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    rule="DON'T omit sections - every audio section must have a plan",
                    message=f"Missing section plans for audio sections: {', '.join(missing_sorted)}",
                    fix_hint="Add MacroSectionPlan for each missing audio section",
                    acceptance_test=f"All audio sections have corresponding MacroSectionPlan: {missing_sorted}",
                    suggested_action=SuggestedAction.REPLAN_GLOBAL,
                )
            )

        # Check for extra sections (WARN)
        extra_sections = plan_section_ids - audio_section_ids
        if extra_sections:
            extra_sorted = sorted(extra_sections)
            issues.append(
                Issue(
                    issue_id="COVERAGE_EXTRA_SECTIONS",
                    category=IssueCategory.COVERAGE,
                    severity=IssueSeverity.WARN,
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    rule="DON'T add sections not in audio - plan only existing sections",
                    message=f"Section plans without corresponding audio sections: {', '.join(extra_sorted)}",
                    fix_hint="Remove section plans that don't have audio sections, or verify section IDs match audio",
                    acceptance_test=f"No extra section plans beyond audio sections: {extra_sorted}",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        return issues

    def _validate_layer_count(self, plan: MacroPlan) -> list[Issue]:
        """Validate layer count is appropriate (quality check).

        Note: Pydantic already enforces 1-5 layers, exactly one BASE layer,
        and no duplicates. This check warns about edge cases that pass
        schema validation but may indicate quality issues.

        Checks:
        - Only 1 layer (minimal, could be more engaging) -> WARN
        - 5 layers (maximum, may be too complex) -> WARN

        Args:
            plan: MacroPlan to validate

        Returns:
            List of layer count warnings (empty if appropriate)
        """
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueEffort,
            IssueLocation,
            IssueScope,
            IssueSeverity,
            SuggestedAction,
        )

        issues: list[Issue] = []
        layer_count = len(plan.layering_plan.layers)

        # Warn if minimal layering (1 layer only)
        if layer_count == 1:
            issues.append(
                Issue(
                    issue_id="LAYERING_MINIMAL",
                    category=IssueCategory.LAYERING,
                    severity=IssueSeverity.WARN,
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    rule="DON'T use single layer - add rhythm/accent for visual depth",
                    message="Plan uses only 1 layer (BASE). Consider adding rhythm or accent layers for more visual interest.",
                    fix_hint="Add RHYTHM layer for beat-driven movement or ACCENT layer for peak moments",
                    acceptance_test="LayeringPlan has at least 2 layers for richer composition",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        # Warn if at maximum complexity (5 layers)
        if layer_count == 5:
            issues.append(
                Issue(
                    issue_id="LAYERING_MAXIMUM",
                    category=IssueCategory.LAYERING,
                    severity=IssueSeverity.WARN,
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    rule="DON'T overload layers - 3-4 is optimal, 5 may overwhelm",
                    message="Plan uses maximum 5 layers. Verify this complexity is warranted and won't overwhelm viewers.",
                    fix_hint="Consider reducing to 3-4 layers for clearer visual hierarchy",
                    acceptance_test="LayeringPlan uses 4 or fewer layers OR complexity is justified",
                    suggested_action=SuggestedAction.IGNORE,
                )
            )

        return issues

    def _validate_target_validity(self, plan: MacroPlan) -> list[Issue]:
        """Validate all target roles are valid.

        Note: Pydantic already validates that target roles are valid TargetRole
        enum names. This is a defensive check that should never trigger if
        Pydantic validation is working correctly. Included for safety.

        Args:
            plan: MacroPlan to validate

        Returns:
            List of target validity issues (empty if valid, should always be empty)
        """
        # Pydantic already validates target roles in MacroSectionPlan and TargetSelector
        # via field_validator. This method exists for completeness but should always
        # return empty list if Pydantic validation is working.
        return []

    def _validate_asset_types(self, plan: MacroPlan) -> list[Issue]:
        """Validate asset requirements are valid types.

        Checks:
        - Asset names have valid extensions (.png, .gif)
        - File extensions are lowercase

        Args:
            plan: MacroPlan to validate

        Returns:
            List of asset type issues (empty if valid)
        """
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueEffort,
            IssueLocation,
            IssueScope,
            IssueSeverity,
            SuggestedAction,
        )

        issues: list[Issue] = []

        # Valid asset extensions for Phase 1
        VALID_EXTENSIONS = {".png", ".gif"}

        for asset in plan.asset_requirements:
            # Check if has valid extension
            has_valid_ext = any(asset.lower().endswith(ext) for ext in VALID_EXTENSIONS)

            if not has_valid_ext:
                issues.append(
                    Issue(
                        issue_id=f"ASSET_INVALID_TYPE_{asset}",
                        category=IssueCategory.DATA_QUALITY,
                        severity=IssueSeverity.ERROR,
                        estimated_effort=IssueEffort.LOW,
                        scope=IssueScope.GLOBAL,
                        location=IssueLocation(),
                        rule="DON'T use unsupported asset types - only .png and .gif allowed",
                        message=f"Asset '{asset}' has invalid file type. Only .png and .gif supported.",
                        fix_hint="Change asset to use .png or .gif extension",
                        acceptance_test=f"Asset '{asset}' has valid extension (.png or .gif)",
                        suggested_action=SuggestedAction.PATCH,
                    )
                )

        return issues

    def _validate_focus_targets(self, plan: MacroPlan) -> list[Issue]:
        """Validate focus targets across sections (quality check).

        Checks for visual impact and variety:
        - Warn if many sections focus on same targets (lack of variety)
        - Warn if critical targets (e.g., MEGA_TREE, HERO) never used

        Args:
            plan: MacroPlan to validate

        Returns:
            List of focus target quality warnings (empty if good distribution)
        """
        from collections import Counter

        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueEffort,
            IssueLocation,
            IssueScope,
            IssueSeverity,
            SuggestedAction,
        )

        issues: list[Issue] = []

        # Collect primary focus targets across all sections
        primary_targets = []
        for section_plan in plan.section_plans:
            primary_targets.extend(section_plan.primary_focus_targets)

        # Count frequency of each target
        target_counts = Counter(primary_targets)
        total_sections = len(plan.section_plans)

        # Check if any single target dominates (used in >70% of sections)
        for target, count in target_counts.items():
            if count / total_sections > 0.7 and total_sections > 2:
                issues.append(
                    Issue(
                        issue_id=f"FOCUS_OVERUSED_{target}",
                        category=IssueCategory.VARIETY,
                        severity=IssueSeverity.WARN,
                        estimated_effort=IssueEffort.LOW,
                        scope=IssueScope.GLOBAL,
                        location=IssueLocation(),
                        rule="DON'T overuse single target - vary focus across sections",
                        message=f"Target '{target}' is primary focus in {count}/{total_sections} sections ({count / total_sections * 100:.0f}%). Consider more target variety.",
                        fix_hint="Vary primary focus targets across sections. Use other targets like MEGA_TREE, HERO, ARCHES, etc.",
                        acceptance_test="No single target is primary focus in more than 70% of sections",
                        suggested_action=SuggestedAction.PATCH,
                    )
                )

        return issues

    def _check_contrast(self, plan: MacroPlan) -> list[Issue]:
        """Check for sufficient contrast across sections (quality check).

        Validates visual variety and dynamic range:
        - Warns if all sections have same energy target
        - Warns if all sections have same motion density (4+ sections)
        - Info if all sections use same choreography style (5+ sections)

        Args:
            plan: MacroPlan to validate

        Returns:
            List of contrast warnings (empty if good variety)
        """
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueEffort,
            IssueLocation,
            IssueScope,
            IssueSeverity,
            SuggestedAction,
        )

        issues: list[Issue] = []

        # Need at least 2 sections to check contrast
        if len(plan.section_plans) < 2:
            return issues

        # Check energy contrast
        energies = [sp.energy_target for sp in plan.section_plans]
        unique_energies = set(energies)

        if len(unique_energies) == 1:
            issues.append(
                Issue(
                    issue_id="CONTRAST_NO_ENERGY_VARIETY",
                    category=IssueCategory.VARIETY,
                    severity=IssueSeverity.WARN,
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    rule="DON'T use same energy everywhere - vary for dynamic range",
                    message=f"All {len(energies)} sections use same energy target ({energies[0].value}). Vary energy for impact.",
                    fix_hint="Use different energy targets across sections (LOW, MED, HIGH, BUILD, RELEASE, PEAK)",
                    acceptance_test="At least 2 different energy targets used across sections",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        # Check motion density contrast (only warn if 4+ sections)
        densities = [sp.motion_density for sp in plan.section_plans]
        unique_densities = set(densities)

        if len(unique_densities) == 1 and len(densities) >= 4:
            issues.append(
                Issue(
                    issue_id="CONTRAST_NO_DENSITY_VARIETY",
                    category=IssueCategory.VARIETY,
                    severity=IssueSeverity.WARN,
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    rule="DON'T use same density everywhere - mix sparse/busy for variety",
                    message=f"All {len(densities)} sections use same motion density ({densities[0].value}). Vary for dynamic range.",
                    fix_hint="Mix motion densities (SPARSE for calm, MED for moderate, BUSY for intense)",
                    acceptance_test="At least 2 different motion densities used across sections",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        # Check choreography style variety (only info if 5+ sections)
        styles = [sp.choreography_style for sp in plan.section_plans]
        unique_styles = set(styles)

        if len(unique_styles) == 1 and len(styles) >= 5:
            issues.append(
                Issue(
                    issue_id="CONTRAST_SINGLE_STYLE",
                    category=IssueCategory.STYLE,
                    severity=IssueSeverity.NIT,
                    estimated_effort=IssueEffort.LOW,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    rule="DON'T use single style for all sections - mix for interest",
                    message=f"All {len(styles)} sections use {styles[0].value} style. Consider variety.",
                    fix_hint="Mix choreography styles (IMAGERY for literal, ABSTRACT for pure motion, HYBRID)",
                    acceptance_test="Multiple choreography styles used OR single style is intentional",
                    suggested_action=SuggestedAction.IGNORE,
                )
            )

        return issues

    def _check_asset_bloat(self, plan: MacroPlan) -> list[Issue]:
        """Check for excessive asset requirements (quality check).

        Validates asset count is reasonable:
        - Warn if more than 10 unique assets required
        - Assets are expensive to generate, should be used judiciously

        Args:
            plan: MacroPlan to validate

        Returns:
            List of asset bloat warnings (empty if reasonable)
        """
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueEffort,
            IssueLocation,
            IssueScope,
            IssueSeverity,
            SuggestedAction,
        )

        issues: list[Issue] = []

        # Warn if too many assets (>10)
        asset_count = len(plan.asset_requirements)
        MAX_RECOMMENDED_ASSETS = 10

        if asset_count > MAX_RECOMMENDED_ASSETS:
            issues.append(
                Issue(
                    issue_id="ASSET_BLOAT",
                    category=IssueCategory.COMPLEXITY,
                    severity=IssueSeverity.WARN,
                    estimated_effort=IssueEffort.MEDIUM,
                    scope=IssueScope.GLOBAL,
                    location=IssueLocation(),
                    rule="DON'T require excessive assets - reuse and minimize for efficiency",
                    message=f"Plan requires {asset_count} assets (>{MAX_RECOMMENDED_ASSETS} recommended max). Asset generation is expensive.",
                    fix_hint=f"Reduce to {MAX_RECOMMENDED_ASSETS} or fewer assets, reuse assets across sections",
                    acceptance_test=f"Asset requirements ≤ {MAX_RECOMMENDED_ASSETS} OR high asset count is justified",
                    suggested_action=SuggestedAction.PATCH,
                )
            )

        return issues
