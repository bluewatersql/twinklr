from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.validation._core.io import load_json
from scripts.validation._core.models import ValidationIssue, ValidationResult


@dataclass(frozen=True)
class MHPlanValidationPaths:
    """Paths for MH plan validation artifacts."""

    raw_plan_path: Path
    implementation_path: Path
    evaluation_path: Path


def _issue(
    severity: str,
    category: str,
    message: str,
    *,
    artifact: str | None = None,
    section_id: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        category=category,
        message=message,
        artifact=artifact,
        section_id=section_id,
    )


def validate_raw_plan_structure(raw_plan: dict[str, Any]) -> list[ValidationIssue]:
    """Validate raw MH plan structure."""
    sections = raw_plan.get("sections")
    if sections is None:
        return [_issue("ERROR", "RAW_PLAN_STRUCTURE", "No 'sections' key in raw plan")]
    if not isinstance(sections, list):
        return [_issue("ERROR", "RAW_PLAN_STRUCTURE", "'sections' is not a list in raw plan")]
    if not sections:
        return [_issue("ERROR", "RAW_PLAN_STRUCTURE", "Empty sections list in raw plan")]
    return []


def validate_channel_specifications(raw_plan: dict[str, Any]) -> list[ValidationIssue]:
    """Validate channel specifications in raw plan sections."""
    issues: list[ValidationIssue] = []
    sections = raw_plan.get("sections", [])
    sections_with_channels = 0

    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            issues.append(_issue("ERROR", "RAW_PLAN_CHANNELS", f"Section {index} is not an object"))
            continue
        section_name = str(section.get("name", f"Section {index + 1}"))
        channels = section.get("channels")
        if channels is None:
            issues.append(
                _issue("WARNING", "RAW_PLAN_CHANNELS", f"Section '{section_name}': No channel specifications")
            )
            continue
        if isinstance(channels, dict):
            sections_with_channels += 1
        else:
            issues.append(
                _issue("ERROR", "RAW_PLAN_CHANNELS", f"Section '{section_name}': channels is not an object")
            )

    if sections and sections_with_channels == 0:
        issues.append(_issue("ERROR", "RAW_PLAN_CHANNELS", "No sections have channel specifications"))
    return issues


def validate_raw_plan_timing(raw_plan: dict[str, Any]) -> list[ValidationIssue]:
    """Validate bar timing in raw plan."""
    issues: list[ValidationIssue] = []
    for index, section in enumerate(raw_plan.get("sections", [])):
        if not isinstance(section, dict):
            continue
        section_name = str(section.get("name", f"Section {index + 1}"))
        start_bar = section.get("start_bar")
        end_bar = section.get("end_bar")
        if start_bar is None or end_bar is None:
            issues.append(
                _issue("ERROR", "RAW_PLAN_TIMING", f"Section '{section_name}': Missing start_bar or end_bar")
            )
            continue
        if not isinstance(start_bar, (int, float)) or not isinstance(end_bar, (int, float)):
            issues.append(
                _issue("ERROR", "RAW_PLAN_TIMING", f"Section '{section_name}': Invalid bar types")
            )
            continue
        if end_bar <= start_bar:
            issues.append(
                _issue(
                    "ERROR",
                    "RAW_PLAN_TIMING",
                    f"Section '{section_name}': end_bar ({end_bar}) <= start_bar ({start_bar})",
                )
            )
    return issues


def validate_implementation_structure(implementation: dict[str, Any]) -> list[ValidationIssue]:
    """Validate MH implementation plan structure."""
    sections = implementation.get("sections")
    if sections is None:
        return [_issue("ERROR", "IMPLEMENTATION_STRUCTURE", "No 'sections' key in implementation")]
    if not isinstance(sections, list):
        return [_issue("ERROR", "IMPLEMENTATION_STRUCTURE", "'sections' is not a list in implementation")]
    if not sections:
        return [_issue("ERROR", "IMPLEMENTATION_STRUCTURE", "Empty sections list in implementation")]

    issues: list[ValidationIssue] = []
    required_fields = ("name", "start_ms", "end_ms", "template_id")
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            issues.append(_issue("ERROR", "IMPLEMENTATION_STRUCTURE", f"Section {index} is not an object"))
            continue
        section_name = str(section.get("name", f"Section {index + 1}"))
        for field in required_fields:
            if field not in section:
                issues.append(
                    _issue(
                        "ERROR",
                        "IMPLEMENTATION_STRUCTURE",
                        f"Section '{section_name}': Missing '{field}'",
                    )
                )
    return issues


def validate_implementation_timing(implementation: dict[str, Any]) -> list[ValidationIssue]:
    """Validate millisecond timing for implementation sections."""
    issues: list[ValidationIssue] = []
    zero_duration_count = 0
    for index, section in enumerate(implementation.get("sections", [])):
        if not isinstance(section, dict):
            continue
        section_name = str(section.get("name", f"Section {index + 1}"))
        start_ms = section.get("start_ms")
        end_ms = section.get("end_ms")
        if start_ms is None or end_ms is None:
            issues.append(
                _issue(
                    "ERROR",
                    "IMPLEMENTATION_TIMING",
                    f"Section '{section_name}': Missing start_ms or end_ms",
                )
            )
            continue
        if not isinstance(start_ms, (int, float)) or not isinstance(end_ms, (int, float)):
            issues.append(
                _issue(
                    "ERROR",
                    "IMPLEMENTATION_TIMING",
                    f"Section '{section_name}': Invalid timing types",
                )
            )
            continue
        duration_ms = end_ms - start_ms
        if duration_ms == 0:
            zero_duration_count += 1
            issues.append(
                _issue(
                    "ERROR",
                    "IMPLEMENTATION_TIMING",
                    f"Section '{section_name}': Zero duration ({start_ms}ms)",
                )
            )
        elif duration_ms < 0:
            issues.append(
                _issue(
                    "ERROR",
                    "IMPLEMENTATION_TIMING",
                    f"Section '{section_name}': Negative duration (start={start_ms}ms, end={end_ms}ms)",
                )
            )
    if zero_duration_count > 0:
        issues.append(
            _issue(
                "ERROR",
                "IMPLEMENTATION_TIMING",
                f"CRITICAL: {zero_duration_count} sections have zero duration",
            )
        )
    return issues


def validate_template_references(implementation: dict[str, Any]) -> list[ValidationIssue]:
    """Validate template references in implementation sections."""
    issues: list[ValidationIssue] = []
    missing_count = 0
    for index, section in enumerate(implementation.get("sections", [])):
        if not isinstance(section, dict):
            continue
        section_name = str(section.get("name", f"Section {index + 1}"))
        if not section.get("template_id"):
            missing_count += 1
            issues.append(
                _issue(
                    "WARNING",
                    "TEMPLATE_REFERENCES",
                    f"Section '{section_name}': No template_id specified",
                )
            )
    if missing_count > 0:
        issues.append(
            _issue(
                "WARNING",
                "TEMPLATE_REFERENCES",
                f"{missing_count} sections without template_id",
            )
        )
    return issues


def validate_beat_alignment(plan: dict[str, Any]) -> list[ValidationIssue]:
    """Check `period_bars` values align to beat grid for MH instructions."""
    issues: list[ValidationIssue] = []
    time_signature = "4/4"
    for section in plan.get("sections", []):
        if isinstance(section, dict) and "time_signature" in section:
            time_signature = str(section["time_signature"])
            break
    beats_per_bar = int(time_signature.split("/")[0]) if "/" in time_signature else 4

    for section in plan.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_name = str(section.get("name", f"Section {section.get('section_id')}"))
        instructions = section.get("instructions", [])
        if not isinstance(instructions, list):
            continue
        for instruction in instructions:
            if not isinstance(instruction, dict):
                continue
            movement = instruction.get("movement")
            if not isinstance(movement, dict):
                continue
            period_bars = movement.get("period_bars")
            if not isinstance(period_bars, (int, float)):
                continue
            beats_per_cycle = float(period_bars) * beats_per_bar
            quantized_beats = round(beats_per_cycle)
            error = abs(beats_per_cycle - quantized_beats)
            if error > 0.1:
                pattern_name = movement.get("pattern")
                issues.append(
                    _issue(
                        "WARNING",
                        "BEAT_ALIGNMENT",
                        (
                            f"Section '{section_name}': Pattern '{pattern_name}' has "
                            f"period_bars={period_bars:.4f} ({beats_per_cycle:.2f} beats) "
                            f"not aligned to beat grid (error: {error:.2f} beats)"
                        ),
                    )
                )
    return issues


def validate_evaluation_structure(evaluation: dict[str, Any]) -> list[ValidationIssue]:
    """Validate MH judge evaluation shape and score ranges."""
    issues: list[ValidationIssue] = []
    for field in ("overall_score", "pass_threshold", "channel_scoring"):
        if field not in evaluation:
            issues.append(_issue("ERROR", "EVALUATION_STRUCTURE", f"Missing '{field}' in evaluation"))

    overall_score = evaluation.get("overall_score")
    if overall_score is not None and (
        not isinstance(overall_score, (int, float)) or not (0 <= overall_score <= 100)
    ):
        issues.append(
            _issue(
                "ERROR",
                "EVALUATION_STRUCTURE",
                f"overall_score ({overall_score}) outside valid range (0-100)",
            )
        )

    channel_scoring = evaluation.get("channel_scoring")
    if channel_scoring is None:
        issues.append(
            _issue("ERROR", "EVALUATION_STRUCTURE", "channel_scoring is null (should contain channel evaluation)")
        )
        return issues

    if not isinstance(channel_scoring, dict):
        issues.append(_issue("ERROR", "EVALUATION_STRUCTURE", "channel_scoring is not an object"))
        return issues

    channel_fields = (
        "shutter_appropriateness",
        "color_appropriateness",
        "gobo_appropriateness",
        "visual_impact",
    )
    for field in channel_fields:
        score = channel_scoring.get(field)
        if score is None:
            issues.append(_issue("WARNING", "EVALUATION_STRUCTURE", f"Missing channel_scoring.{field}"))
            continue
        if field == "gobo_appropriateness" and score == 0:
            continue
        if not isinstance(score, (int, float)) or not (1 <= score <= 10):
            issues.append(
                _issue(
                    "ERROR",
                    "EVALUATION_STRUCTURE",
                    f"channel_scoring.{field} ({score}) outside valid range (1-10)",
                )
            )
    return issues


def cross_validate_plans(
    raw_plan: dict[str, Any], implementation: dict[str, Any]
) -> list[ValidationIssue]:
    """Cross-validate raw plan and implementation section coverage."""
    issues: list[ValidationIssue] = []
    raw_sections = raw_plan.get("sections", [])
    impl_sections = implementation.get("sections", [])

    if isinstance(raw_sections, list) and isinstance(impl_sections, list):
        if len(impl_sections) < len(raw_sections):
            issues.append(
                _issue(
                    "ERROR",
                    "CROSS_VALIDATION",
                    (
                        f"Implementation has FEWER sections ({len(impl_sections)}) than "
                        f"raw plan ({len(raw_sections)})"
                    ),
                )
            )

        raw_names = {str(s.get("name", "")) for s in raw_sections if isinstance(s, dict)}
        impl_names = {str(s.get("name", "")) for s in impl_sections if isinstance(s, dict)}
        missing_sections = []
        for raw_name in raw_names:
            if raw_name not in impl_names and not any(name.startswith(raw_name) for name in impl_names):
                missing_sections.append(raw_name)
        if missing_sections:
            issues.append(
                _issue(
                    "WARNING",
                    "CROSS_VALIDATION",
                    f"Raw plan sections not found in implementation: {', '.join(sorted(missing_sections))}",
                )
            )
    return issues


def run_mh_plan_validation(paths: MHPlanValidationPaths) -> ValidationResult:
    """Run MH plan validation using raw/implementation/evaluation artifacts."""
    result = ValidationResult()

    raw_plan: dict[str, Any] | None = None
    implementation: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None

    if not paths.raw_plan_path.exists():
        result.issues.append(
            _issue("ERROR", "FILE_MISSING", f"Raw plan not found: {paths.raw_plan_path}", artifact="raw_plan")
        )
    else:
        raw_plan = load_json(paths.raw_plan_path)
        result.artifacts_checked.append(str(paths.raw_plan_path))
        result.extend(validate_raw_plan_structure(raw_plan))
        result.extend(validate_channel_specifications(raw_plan))
        result.extend(validate_raw_plan_timing(raw_plan))

    if not paths.implementation_path.exists():
        result.issues.append(
            _issue(
                "ERROR",
                "FILE_MISSING",
                f"Implementation not found: {paths.implementation_path}",
                artifact="implementation",
            )
        )
    else:
        implementation = load_json(paths.implementation_path)
        result.artifacts_checked.append(str(paths.implementation_path))
        result.extend(validate_implementation_structure(implementation))
        result.extend(validate_implementation_timing(implementation))
        result.extend(validate_template_references(implementation))
        result.extend(validate_beat_alignment(implementation))

    if not paths.evaluation_path.exists():
        result.issues.append(
            _issue(
                "ERROR",
                "FILE_MISSING",
                f"Evaluation not found: {paths.evaluation_path}",
                artifact="evaluation",
            )
        )
    else:
        evaluation = load_json(paths.evaluation_path)
        result.artifacts_checked.append(str(paths.evaluation_path))
        result.extend(validate_evaluation_structure(evaluation))

    if raw_plan is not None and implementation is not None:
        result.extend(cross_validate_plans(raw_plan, implementation))

    result.stats["artifacts_checked_count"] = len(result.artifacts_checked)
    return result
