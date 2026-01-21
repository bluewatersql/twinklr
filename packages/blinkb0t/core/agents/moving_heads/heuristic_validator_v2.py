"""Heuristic validation for LLM choreography plans (v2).

Simplified validator for the template-driven paradigm where the LLM
selects template_id + preset_id rather than generating raw plans.

Key differences from v1:
- Validates LLMChoreographyPlan (not AgentPlan)
- No layering/complexity checks (single template per section)
- No pose/parameter/channel checks (templates handle these)
- Validates template_id and preset_id existence
- Validates energy alignment and coverage
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.agents.moving_heads.models_llm_plan import LLMChoreographyPlan

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """Validation issue severity."""

    ERROR = "error"  # Blocks progress
    WARNING = "warning"  # Noted but not blocking
    INFO = "info"  # Informational only


class ValidationIssue(BaseModel):
    """Single validation issue."""

    severity: Severity = Field(description="Issue severity level")
    rule: str = Field(description="Validation rule that triggered")
    section_name: str | None = Field(default=None, description="Section where issue occurred")
    message: str = Field(description="Human-readable issue description")

    model_config = ConfigDict(frozen=True, extra="forbid")


class ValidationResult(BaseModel):
    """Result of heuristic validation."""

    passed: bool = Field(description="Whether validation passed")
    issues: list[ValidationIssue] = Field(default_factory=list, description="List of issues found")
    error_count: int = Field(default=0, ge=0, description="Number of errors")
    warning_count: int = Field(default=0, ge=0, description="Number of warnings")
    info_count: int = Field(default=0, ge=0, description="Number of info messages")

    model_config = ConfigDict(frozen=False, extra="forbid")

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
        """Add informational issue."""
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
        """Get summary of all issues."""
        if not self.issues:
            return "No issues"

        lines = [
            f"Validation: {self.error_count} errors, "
            f"{self.warning_count} warnings, {self.info_count} info\n"
        ]

        for issue in self.issues:
            if issue.severity == Severity.ERROR:
                prefix = "[ERROR]"
            elif issue.severity == Severity.WARNING:
                prefix = "[WARN]"
            else:
                prefix = "[INFO]"

            section = f" [{issue.section_name}]" if issue.section_name else ""
            lines.append(f"{prefix} {issue.rule}{section}: {issue.message}")

        return "\n".join(lines)


class LLMPlanValidator:
    """Validates LLMChoreographyPlan using heuristic rules.

    Validates:
    1. Timing (no gaps, coverage)
    2. Templates (valid template_ids)
    3. Presets (valid preset_ids for templates)
    4. Energy (template matches section energy)
    5. Variety (template diversity)

    Example:
        validator = LLMPlanValidator(
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
        self,
        template_metadata: list[dict[str, Any]],
        song_features: dict[str, Any],
    ) -> None:
        """Initialize validator.

        Args:
            template_metadata: Template metadata list from context builder.
            song_features: Audio features including bars_s for coverage check.
        """
        self.song_features = song_features

        # Build template lookup
        self._templates: dict[str, dict[str, Any]] = {}
        self._presets: dict[str, set[str]] = {}

        for meta in template_metadata:
            template_id = meta["template_id"]
            self._templates[template_id] = meta

            # Build preset lookup for this template
            preset_ids = {p["preset_id"] for p in meta.get("presets", [])}
            self._presets[template_id] = preset_ids

        logger.debug(f"LLMPlanValidator initialized with {len(self._templates)} templates")

    def validate(self, plan: LLMChoreographyPlan) -> ValidationResult:
        """Validate plan against heuristic rules.

        Args:
            plan: LLMChoreographyPlan to validate.

        Returns:
            ValidationResult with issues.
        """
        logger.info("Running LLM plan validation...")

        result = ValidationResult(passed=True)

        # Run validation rules
        self._validate_timing(plan, result)
        self._validate_templates(plan, result)
        self._validate_presets(plan, result)
        self._validate_energy(plan, result)
        self._validate_coverage(plan, result)
        self._validate_variety(plan, result)

        logger.info(
            f"Validation complete: "
            f"{'PASSED' if result.passed else 'FAILED'} "
            f"({result.error_count} errors, {result.warning_count} warnings)"
        )

        return result

    def _validate_timing(self, plan: LLMChoreographyPlan, result: ValidationResult) -> None:
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
                f"First section starts at bar {sorted_sections[0].start_bar}, "
                f"should start at bar 1",
                sorted_sections[0].section_name,
            )

        # Check for gaps between sections
        for i in range(len(sorted_sections) - 1):
            current = sorted_sections[i]
            next_section = sorted_sections[i + 1]

            expected_next_start = current.end_bar + 1
            if next_section.start_bar > expected_next_start:
                gap_bars = next_section.start_bar - expected_next_start
                result.add_error(
                    "timing",
                    f"Gap of {gap_bars} bars between '{current.section_name}' "
                    f"(ends bar {current.end_bar}) and '{next_section.section_name}' "
                    f"(starts bar {next_section.start_bar})",
                    current.section_name,
                )

    def _validate_templates(self, plan: LLMChoreographyPlan, result: ValidationResult) -> None:
        """Validate template IDs exist."""
        for section in plan.sections:
            if section.template_id not in self._templates:
                available = sorted(self._templates.keys())[:5]
                result.add_error(
                    "template",
                    f"Template '{section.template_id}' not found. Available: {available}...",
                    section.section_name,
                )

    def _validate_presets(self, plan: LLMChoreographyPlan, result: ValidationResult) -> None:
        """Validate preset IDs exist for their templates."""
        for section in plan.sections:
            if section.preset_id is None:
                continue  # No preset is valid

            # Skip if template doesn't exist (already reported)
            if section.template_id not in self._templates:
                continue

            valid_presets = self._presets.get(section.template_id, set())

            if section.preset_id not in valid_presets:
                if valid_presets:
                    result.add_error(
                        "preset",
                        f"Preset '{section.preset_id}' not found for template "
                        f"'{section.template_id}'. Available: {sorted(valid_presets)}",
                        section.section_name,
                    )
                else:
                    result.add_error(
                        "preset",
                        f"Template '{section.template_id}' has no presets, "
                        f"but preset '{section.preset_id}' was specified",
                        section.section_name,
                    )

    def _validate_energy(self, plan: LLMChoreographyPlan, result: ValidationResult) -> None:
        """Validate energy alignment between section and template."""
        for section in plan.sections:
            # Skip if no energy specified or template doesn't exist
            if section.energy_level is None:
                continue
            if section.template_id not in self._templates:
                continue

            meta = self._templates[section.template_id]
            energy_range = meta.get("energy_range")

            if energy_range is None:
                continue  # No energy range to check

            min_energy, max_energy = energy_range

            # Check if section energy is within template range (with tolerance)
            tolerance = 15  # Allow some flexibility
            if section.energy_level < min_energy - tolerance:
                result.add_warning(
                    "energy",
                    f"Energy mismatch: section energy={section.energy_level}, "
                    f"template '{section.template_id}' range=({min_energy}, {max_energy})",
                    section.section_name,
                )
            elif section.energy_level > max_energy + tolerance:
                result.add_warning(
                    "energy",
                    f"Energy mismatch: section energy={section.energy_level}, "
                    f"template '{section.template_id}' range=({min_energy}, {max_energy})",
                    section.section_name,
                )

    def _validate_coverage(self, plan: LLMChoreographyPlan, result: ValidationResult) -> None:
        """Validate full song is covered."""
        bar_count = len(self.song_features.get("bars_s", []))

        if bar_count == 0:
            result.add_info("coverage", "No bar count in song features, skipping coverage check")
            return

        if not plan.sections:
            result.add_error("coverage", "No sections in plan")
            return

        # Check last section covers end
        sorted_sections = sorted(plan.sections, key=lambda s: s.end_bar, reverse=True)
        last_section = sorted_sections[0]

        if last_section.end_bar < bar_count:
            uncovered = bar_count - last_section.end_bar
            result.add_warning(
                "coverage",
                f"Song not fully covered: missing last {uncovered} bars "
                f"(song has {bar_count} bars, plan ends at bar {last_section.end_bar})",
                last_section.section_name,
            )

    def _validate_variety(self, plan: LLMChoreographyPlan, result: ValidationResult) -> None:
        """Validate template variety."""
        if len(plan.sections) < 3:
            return  # Not enough sections to check variety

        # Check for same template in 3+ consecutive sections
        consecutive_count = 1
        last_template = plan.sections[0].template_id

        for section in plan.sections[1:]:
            if section.template_id == last_template:
                consecutive_count += 1
                if consecutive_count >= 3:
                    result.add_warning(
                        "variety",
                        f"Template '{section.template_id}' used in {consecutive_count} "
                        f"consecutive sections - consider more variety",
                        section.section_name,
                    )
            else:
                consecutive_count = 1
                last_template = section.template_id

        # Check overall variety
        all_templates = [s.template_id for s in plan.sections]
        unique_templates = set(all_templates)
        variety_ratio = len(unique_templates) / len(all_templates)

        if variety_ratio < 0.3 and len(plan.sections) >= 4:
            result.add_warning(
                "variety",
                f"Low template variety: {len(unique_templates)} unique templates "
                f"across {len(all_templates)} sections ({variety_ratio:.0%})",
            )
