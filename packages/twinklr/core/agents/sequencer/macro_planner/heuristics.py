"""
Heuristic validator for MacroPlan.

Performs deterministic validation checks on MacroPlan outputs
before they are sent to the LLM judge. Fast, non-LLM checks
that catch common structural and logical issues.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.issues import Issue, IssueLocation, IssueSeverity
from twinklr.core.sequencer.planning import MacroPlan
from twinklr.core.sequencer.vocabulary import TargetType


def _issue(**values: Any) -> Issue:
    """Build a deterministic issue with all strict response keys populated."""
    return Issue.model_validate({"generic_example": None, "targeted_actions": [], **values})


def _issue_location(**values: Any) -> IssueLocation:
    """Build a partial location through the all-required strict schema."""
    return IssueLocation.model_validate(
        {
            "section_id": None,
            "group_id": None,
            "effect_id": None,
            "bar_start": None,
            "bar_end": None,
            "field_path": None,
            **values,
        }
    )


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
    5. Quality checks (contrast, focus targets, motif cohesion, palette presence)
    """

    def validate(
        self,
        plan: MacroPlan,
        audio_profile: AudioProfileModel,
        *,
        motif_by_id: dict[str, object] | None = None,
        palette_ids: set[str] | None = None,
        display_groups: list[dict[str, Any]] | None = None,
    ) -> list[Issue]:
        """Run all validation checks on MacroPlan.

        Args:
            plan: MacroPlan to validate
            audio_profile: Audio analysis for cross-validation
            motif_by_id: Optional mapping of valid motif_id -> MotifSpec (or any object)
            palette_ids: Optional set of valid palette_id values

        Returns:
            List of issues found (empty if all checks pass)
        """
        issues: list[Issue] = []

        # Existing checks
        issues.extend(self._validate_section_coverage(plan, audio_profile))
        issues.extend(self._validate_layer_count(plan))
        issues.extend(self._validate_target_validity(plan, display_groups))
        issues.extend(self._validate_focus_targets(plan))
        issues.extend(self._check_contrast(plan))

        # NEW: palette + motifs
        issues.extend(self._validate_palette_plan(plan, palette_ids))
        issues.extend(self._validate_motif_ids(plan, motif_by_id))
        issues.extend(self._check_motif_cohesion(plan))

        return issues

    def has_errors(self, issues: list[Issue]) -> bool:
        return any(issue.severity == IssueSeverity.ERROR for issue in issues)

    def has_warnings(self, issues: list[Issue]) -> bool:
        return any(issue.severity == IssueSeverity.WARN for issue in issues)

    # -----------------------------
    # Existing methods (unchanged)
    # -----------------------------

    def _validate_section_coverage(
        self,
        plan: MacroPlan,
        audio_profile: AudioProfileModel,
    ) -> list[Issue]:
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueSeverity,
        )

        issues: list[Issue] = []

        audio_section_ids = {s.section_id for s in audio_profile.structure.sections}
        plan_section_ids = {sp.section.section_id for sp in plan.section_plans}

        missing_sections = audio_section_ids - plan_section_ids
        if missing_sections:
            missing_sorted = sorted(missing_sections)
            issues.append(
                _issue(
                    issue_id="COVERAGE_MISSING_SECTIONS",
                    category=IssueCategory.COVERAGE,
                    severity=IssueSeverity.ERROR,
                    location=_issue_location(),
                    rule="DON'T omit sections - every audio section must have a plan",
                    message=f"Missing section plans for audio sections: {', '.join(missing_sorted)}",
                    fix_hint="Add MacroSectionPlan for each missing audio section",
                    acceptance_test=f"All audio sections have corresponding MacroSectionPlan: {missing_sorted}",
                )
            )

        extra_sections = plan_section_ids - audio_section_ids
        if extra_sections:
            extra_sorted = sorted(extra_sections)
            issues.append(
                _issue(
                    issue_id="COVERAGE_EXTRA_SECTIONS",
                    category=IssueCategory.COVERAGE,
                    severity=IssueSeverity.WARN,
                    location=_issue_location(),
                    rule="DON'T add sections not in audio - plan only existing sections",
                    message=f"Section plans without corresponding audio sections: {', '.join(extra_sorted)}",
                    fix_hint="Remove section plans that don't have audio sections, or verify section IDs match audio",
                    acceptance_test=f"No extra section plans beyond audio sections: {extra_sorted}",
                )
            )

        return issues

    def _validate_layer_count(self, plan: MacroPlan) -> list[Issue]:
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueSeverity,
        )

        issues: list[Issue] = []
        layer_count = len(plan.layering_plan.layers)

        if layer_count == 1:
            issues.append(
                _issue(
                    issue_id="LAYERING_MINIMAL",
                    category=IssueCategory.LAYERING,
                    severity=IssueSeverity.WARN,
                    location=_issue_location(),
                    rule="DON'T use single layer - add rhythm/accent for visual depth",
                    message="Plan uses only 1 layer (BASE). Consider adding rhythm or accent layers for more visual interest.",
                    fix_hint="Add RHYTHM layer for beat-driven movement or ACCENT layer for peak moments",
                    acceptance_test="LayeringPlan has at least 2 layers for richer composition",
                )
            )

        if layer_count == 5:
            issues.append(
                _issue(
                    issue_id="LAYERING_MAXIMUM",
                    category=IssueCategory.LAYERING,
                    severity=IssueSeverity.WARN,
                    location=_issue_location(),
                    rule="DON'T overload layers - 3-4 is optimal, 5 may overwhelm",
                    message="Plan uses maximum 5 layers. Verify this complexity is warranted and won't overwhelm viewers.",
                    fix_hint="Consider reducing to 3-4 layers for clearer visual hierarchy",
                    acceptance_test="LayeringPlan uses 4 or fewer layers OR complexity is justified",
                )
            )

        return issues

    def _validate_target_validity(
        self,
        plan: MacroPlan,
        display_groups: list[dict[str, Any]] | None,
    ) -> list[Issue]:
        """Validate typed focus target IDs against display inventory."""
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueSeverity,
        )

        issues: list[Issue] = []
        if not display_groups:
            return issues

        valid_group_ids: set[str] = set()
        valid_zones: set[str] = set()
        valid_splits: set[str] = set()

        for group in display_groups:
            gid = str(group.get("id") or "").strip()
            if gid:
                valid_group_ids.add(gid)

            zone = group.get("zone")
            if zone:
                valid_zones.add(str(zone))
            tags = group.get("tags") or group.get("zones") or []
            if isinstance(tags, list):
                valid_zones.update(str(tag) for tag in tags if tag)

            splits = group.get("split_membership") or group.get("splits") or []
            if isinstance(splits, list):
                valid_splits.update(str(split) for split in splits if split)

        for sp in plan.section_plans:
            section_id = sp.section.section_id
            for target in [*sp.primary_focus_targets, *sp.secondary_targets]:
                if target.type == TargetType.GROUP and target.id not in valid_group_ids:
                    issues.append(
                        _issue(
                            issue_id=f"TARGET_GROUP_UNKNOWN_{section_id}_{target.id}",
                            category=IssueCategory.CONSTRAINT,
                            severity=IssueSeverity.ERROR,
                            location=_issue_location(section_id=section_id),
                            rule="DON'T reference group targets that are not in the display graph",
                            message=f"Section '{section_id}' uses unknown group target '{target.id}'.",
                            fix_hint="Use only group IDs listed in display layout.",
                            acceptance_test="All group focus targets exist in display group IDs.",
                        )
                    )
                elif target.type == TargetType.ZONE and target.id not in valid_zones:
                    issues.append(
                        _issue(
                            issue_id=f"TARGET_ZONE_UNKNOWN_{section_id}_{target.id}",
                            category=IssueCategory.CONSTRAINT,
                            severity=IssueSeverity.ERROR,
                            location=_issue_location(section_id=section_id),
                            rule="DON'T reference zone targets that are not in the display graph",
                            message=f"Section '{section_id}' uses unknown zone target '{target.id}'.",
                            fix_hint="Use only zone IDs listed in display zones.",
                            acceptance_test="All zone focus targets exist in display zone IDs.",
                        )
                    )
                elif target.type == TargetType.SPLIT and target.id not in valid_splits:
                    issues.append(
                        _issue(
                            issue_id=f"TARGET_SPLIT_UNKNOWN_{section_id}_{target.id}",
                            category=IssueCategory.CONSTRAINT,
                            severity=IssueSeverity.ERROR,
                            location=_issue_location(section_id=section_id),
                            rule="DON'T reference split targets that are not available in the display graph",
                            message=f"Section '{section_id}' uses unknown split target '{target.id}'.",
                            fix_hint="Use only split IDs listed in display splits.",
                            acceptance_test="All split focus targets exist in available split IDs.",
                        )
                    )

        # Layer target selectors must also use concrete display group IDs.
        for layer in plan.layering_plan.layers:
            for role_id in layer.target_selector.roles:
                if role_id not in valid_group_ids:
                    issues.append(
                        _issue(
                            issue_id=f"LAYER_TARGET_UNKNOWN_{layer.layer_index}_{role_id}",
                            category=IssueCategory.CONSTRAINT,
                            severity=IssueSeverity.ERROR,
                            location=_issue_location(
                                field_path=f"layering_plan.layers[{layer.layer_index}].target_selector.roles"
                            ),
                            rule="DON'T reference layer targets that are not concrete display group IDs",
                            message=(
                                f"Layer {layer.layer_index} references unknown target '{role_id}'. "
                                "Layer targets must use concrete display group IDs."
                            ),
                            fix_hint="Use only group IDs listed in display layout for layer target_selector.roles.",
                            acceptance_test=(
                                "Every layering_plan.layers[*].target_selector.roles entry exists in display group IDs."
                            ),
                        )
                    )

        return issues

    def _validate_focus_targets(self, plan: MacroPlan) -> list[Issue]:
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueSeverity,
        )

        issues: list[Issue] = []
        primary_targets: list[str] = []
        for section_plan in plan.section_plans:
            # Track focus variety by typed target identity
            primary_targets.extend(
                [f"{t.type.value}:{t.id}" for t in section_plan.primary_focus_targets]
            )

            # Split-only primary sets are valid but usually too abstract.
            # Encourage at least one group/zone anchor for readability.
            if all(t.type == TargetType.SPLIT for t in section_plan.primary_focus_targets):
                issues.append(
                    _issue(
                        issue_id=f"FOCUS_SPLIT_ONLY_{section_plan.section.section_id}",
                        category=IssueCategory.COORDINATION,
                        severity=IssueSeverity.WARN,
                        location=_issue_location(section_id=section_plan.section.section_id),
                        rule="DON'T use split-only primaries without a group or zone anchor",
                        message=(
                            f"Section '{section_plan.section.section_id}' primary_focus_targets are split-only; "
                            "intent may be too abstract for downstream emphasis."
                        ),
                        fix_hint="Add at least one group or zone target to primary_focus_targets.",
                        acceptance_test="Each split-only primary set includes at least one group or zone anchor.",
                    )
                )

        target_counts = Counter(primary_targets)
        total_sections = len(plan.section_plans)

        for target, count in target_counts.items():
            if total_sections > 2 and (count / total_sections) > 0.7:
                issues.append(
                    _issue(
                        issue_id=f"FOCUS_OVERUSED_{target}",
                        category=IssueCategory.VARIETY,
                        severity=IssueSeverity.WARN,
                        location=_issue_location(),
                        rule="DON'T overuse single target - vary focus across sections",
                        message=(
                            f"Target '{target}' is primary focus in {count}/{total_sections} sections "
                            f"({count / total_sections * 100:.0f}%). Consider more target variety."
                        ),
                        fix_hint="Vary primary focus targets across sections (group/zone/split) to avoid repetition.",
                        acceptance_test="No single target is primary focus in more than 70% of sections",
                    )
                )

        return issues

    def _check_contrast(self, plan: MacroPlan) -> list[Issue]:
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueSeverity,
        )

        issues: list[Issue] = []
        if len(plan.section_plans) < 2:
            return issues

        energies = [sp.energy_target for sp in plan.section_plans]
        if len(set(energies)) == 1:
            issues.append(
                _issue(
                    issue_id="CONTRAST_NO_ENERGY_VARIETY",
                    category=IssueCategory.VARIETY,
                    severity=IssueSeverity.WARN,
                    location=_issue_location(),
                    rule="DON'T use same energy everywhere - vary for dynamic range",
                    message=f"All {len(energies)} sections use same energy target ({energies[0].value}). Vary energy for impact.",
                    fix_hint="Use different energy targets across sections (LOW, MED, HIGH, BUILD, RELEASE, PEAK)",
                    acceptance_test="At least 2 different energy targets used across sections",
                )
            )

        densities = [sp.motion_density for sp in plan.section_plans]
        if len(densities) >= 4 and len(set(densities)) == 1:
            issues.append(
                _issue(
                    issue_id="CONTRAST_NO_DENSITY_VARIETY",
                    category=IssueCategory.VARIETY,
                    severity=IssueSeverity.WARN,
                    location=_issue_location(),
                    rule="DON'T use same density everywhere - mix sparse/busy for variety",
                    message=f"All {len(densities)} sections use same motion density ({densities[0].value}). Vary for dynamic range.",
                    fix_hint="Mix motion densities (SPARSE for calm, MED for moderate, BUSY for intense)",
                    acceptance_test="At least 2 different motion densities used across sections",
                )
            )

        styles = [sp.choreography_style for sp in plan.section_plans]
        if len(styles) >= 5 and len(set(styles)) == 1:
            issues.append(
                _issue(
                    issue_id="CONTRAST_SINGLE_STYLE",
                    category=IssueCategory.STYLE,
                    severity=IssueSeverity.NIT,
                    location=_issue_location(),
                    rule="DON'T use single style for all sections - mix for interest",
                    message=f"All {len(styles)} sections use {styles[0].value} style. Consider variety.",
                    fix_hint="Mix choreography styles (IMAGERY for literal, ABSTRACT for pure motion, HYBRID)",
                    acceptance_test="Multiple choreography styles used OR single style is intentional",
                )
            )

        return issues

    # -----------------------------
    # NEW: palette + motif checks
    # -----------------------------

    def _validate_palette_plan(self, plan: MacroPlan, palette_ids: set[str] | None) -> list[Issue]:
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueSeverity,
        )

        issues: list[Issue] = []

        global_story = getattr(plan, "global_story", None)
        palette_plan = (
            getattr(global_story, "palette_plan", None) if global_story is not None else None
        )
        primary = getattr(palette_plan, "primary", None) if palette_plan is not None else None

        if primary is None:
            issues.append(
                _issue(
                    issue_id="PALETTE_MISSING_PRIMARY",
                    category=IssueCategory.DATA_QUALITY,
                    severity=IssueSeverity.ERROR,
                    location=_issue_location(),
                    rule="DON'T omit palette - MacroPlan must specify a primary palette",
                    message="Global palette_plan.primary is missing.",
                    fix_hint="Set global_story.palette_plan.primary (PaletteRef) using a valid palette_id",
                    acceptance_test="MacroPlan.global_story.palette_plan.primary is present with palette_id",
                )
            )
            return issues

        primary_id = getattr(primary, "palette_id", None)
        if not primary_id:
            issues.append(
                _issue(
                    issue_id="PALETTE_PRIMARY_EMPTY",
                    category=IssueCategory.DATA_QUALITY,
                    severity=IssueSeverity.ERROR,
                    location=_issue_location(),
                    rule="DON'T use empty palette_id - must be a stable id",
                    message="Global palette_plan.primary.palette_id is empty.",
                    fix_hint="Set primary.palette_id to a valid palette id",
                    acceptance_test="Primary palette_id is a non-empty string",
                )
            )
            return issues

        if palette_ids is not None and primary_id not in palette_ids:
            issues.append(
                _issue(
                    issue_id="PALETTE_PRIMARY_UNKNOWN",
                    category=IssueCategory.DATA_QUALITY,
                    severity=IssueSeverity.ERROR,
                    location=_issue_location(),
                    rule="DON'T invent palette ids - must exist in palette catalog",
                    message=f"Primary palette_id '{primary_id}' is not in provided palette catalog.",
                    fix_hint="Pick a valid palette_id from palette_catalog/allowed palette ids",
                    acceptance_test="Primary palette_id exists in palette catalog",
                )
            )

        alternates = getattr(palette_plan, "alternates", None) if palette_plan is not None else None
        alternates_list = list(alternates or [])
        if len(alternates_list) > 6:
            issues.append(
                _issue(
                    issue_id="PALETTE_TOO_MANY_ALTERNATES",
                    category=IssueCategory.COMPLEXITY,
                    severity=IssueSeverity.WARN,
                    location=_issue_location(),
                    rule="DON'T over-specify palette alternates - keep small set for clarity",
                    message=f"Palette plan has {len(alternates_list)} alternates (>6). Consider reducing.",
                    fix_hint="Limit alternates to a small, intentional set (0-6).",
                    acceptance_test="Palette alternates count <= 6 OR justification provided",
                )
            )

        if palette_ids is not None:
            for alt in alternates_list:
                alt_id = getattr(alt, "palette_id", None)
                if alt_id and alt_id not in palette_ids:
                    issues.append(
                        _issue(
                            issue_id=f"PALETTE_ALT_UNKNOWN_{alt_id}",
                            category=IssueCategory.DATA_QUALITY,
                            severity=IssueSeverity.ERROR,
                            location=_issue_location(),
                            rule="DON'T invent palette ids - alternates must exist in palette catalog",
                            message=f"Alternate palette_id '{alt_id}' is not in provided palette catalog.",
                            fix_hint="Remove invalid alternate or choose a valid palette_id",
                            acceptance_test="All alternate palette_ids exist in palette catalog",
                        )
                    )

        # Optional: validate per-section palette overrides are known
        if palette_ids is not None:
            for sp in plan.section_plans:
                sec_pal = getattr(sp, "palette", None)
                if sec_pal is None:
                    continue
                sec_id = getattr(sec_pal, "palette_id", None)
                if sec_id and sec_id not in palette_ids:
                    issues.append(
                        _issue(
                            issue_id=f"PALETTE_SECTION_UNKNOWN_{sp.section.section_id}",
                            category=IssueCategory.DATA_QUALITY,
                            severity=IssueSeverity.ERROR,
                            location=_issue_location(section_id=sp.section.section_id),
                            rule="DON'T invent palette ids - section overrides must exist in palette catalog",
                            message=f"Section '{sp.section.section_id}' palette_id '{sec_id}' is not in provided palette catalog.",
                            fix_hint="Remove invalid section palette override or choose a valid palette_id",
                            acceptance_test="All section palette overrides use valid palette_ids",
                        )
                    )

        return issues

    def _validate_motif_ids(
        self, plan: MacroPlan, motif_by_id: dict[str, object] | None
    ) -> list[Issue]:
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueSeverity,
        )

        issues: list[Issue] = []

        for sp in plan.section_plans:
            section_id = sp.section.section_id
            motif_ids = list(getattr(sp, "motif_ids", []) or [])

            if not motif_ids:
                issues.append(
                    _issue(
                        issue_id=f"MOTIF_MISSING_{section_id}",
                        category=IssueCategory.COVERAGE,
                        severity=IssueSeverity.ERROR,
                        location=_issue_location(section_id=section_id),
                        rule="DON'T omit motifs - each section must include motif_ids for cohesion",
                        message=f"Section '{section_id}' has no motif_ids.",
                        fix_hint="Add 1-3 motif_ids from the Motif Catalog to this section plan",
                        acceptance_test="Each MacroSectionPlan has at least 1 motif_id",
                    )
                )
                continue

            if motif_by_id is not None:
                unknown = [m for m in motif_ids if m not in motif_by_id]
                if unknown:
                    issues.append(
                        _issue(
                            issue_id=f"MOTIF_UNKNOWN_{section_id}",
                            category=IssueCategory.DATA_QUALITY,
                            severity=IssueSeverity.ERROR,
                            location=_issue_location(section_id=section_id),
                            rule="DON'T invent motif_ids - must exist in Motif Catalog",
                            message=f"Section '{section_id}' references unknown motif_ids: {', '.join(sorted(set(unknown)))}",
                            fix_hint="Replace unknown motif_ids with valid ids from Motif Catalog",
                            acceptance_test="All motif_ids referenced by MacroSectionPlans exist in Motif Catalog",
                        )
                    )

        return issues

    def _check_motif_cohesion(self, plan: MacroPlan) -> list[Issue]:
        from twinklr.core.agents.issues import (
            IssueCategory,
            IssueSeverity,
        )

        issues: list[Issue] = []

        all_ids: list[str] = []
        for sp in plan.section_plans:
            all_ids.extend(list(getattr(sp, "motif_ids", []) or []))

        if not all_ids:
            return issues

        counts = Counter(all_ids)
        total_sections = len(plan.section_plans)

        # Recurrence heuristic: motifs used in >=3 sections
        recurring = {m: c for m, c in counts.items() if c >= 3}

        # Warn if not enough recurring anchors
        if total_sections >= 6 and len(recurring) < 2:
            issues.append(
                _issue(
                    issue_id="MOTIF_LOW_RECURRENCE",
                    category=IssueCategory.VARIETY,
                    severity=IssueSeverity.WARN,
                    location=_issue_location(),
                    rule="DON'T use all-unique motifs - ensure 2-4 recurring anchors for cohesion",
                    message=f"Motif recurrence is weak. Only {len(recurring)} motif(s) appear in 3+ sections.",
                    fix_hint="Choose 2–4 motif_ids to recur across multiple sections (repeat anchors).",
                    acceptance_test="At least 2 motif_ids recur across 3+ sections (for 6+ sections total)",
                )
            )

        # Warn if motif sprawl is high
        unique_count = len(counts)
        if total_sections >= 8 and unique_count > 8:
            issues.append(
                _issue(
                    issue_id="MOTIF_SPRAWL",
                    category=IssueCategory.COMPLEXITY,
                    severity=IssueSeverity.WARN,
                    location=_issue_location(),
                    rule="DON'T introduce too many motifs - keep a small vocabulary for clarity",
                    message=f"Plan uses {unique_count} unique motifs across {total_sections} sections. This may feel incoherent.",
                    fix_hint="Reduce unique motif_ids; reuse a smaller set of anchors across sections.",
                    acceptance_test="Unique motif_ids remain within a small set (<=8 for 8+ sections) OR justified",
                )
            )

        return issues
