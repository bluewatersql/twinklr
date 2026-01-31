"""Heuristic validation integration for evaluation reports."""

from __future__ import annotations

import datetime as dt
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (
    HeuristicValidationResult,
    HeuristicValidator,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.reporting.evaluation.models import ReportFlag, ReportFlagLevel, ValidationResult

logger = logging.getLogger(__name__)


def validate_plan_structure(
    plan: ChoreographyPlan,
    available_templates: list[str],
    song_structure: dict[str, Any],
) -> ValidationResult:
    """Validate plan structure using heuristic validator.

    Applies comprehensive structural validation:
    - Template existence checks
    - Timing validity (bar ranges, overlaps)
    - Section coverage
    - Segmentation validity
    - Parameter validation

    Args:
        plan: Choreography plan to validate
        available_templates: List of available template IDs
        song_structure: Song structure with sections and timing

    Returns:
        ValidationResult with errors and warnings

    Example:
        >>> result = validate_plan_structure(
        ...     plan=plan,
        ...     available_templates=["pendulum", "wave"],
        ...     song_structure={"sections": [...], "total_bars": 164}
        ... )
        >>> if not result.valid:
        ...     print(f"Validation failed: {result.errors}")
    """
    logger.debug(
        "Validating plan structure: %d sections, %d templates available",
        len(plan.sections),
        len(available_templates),
    )

    validator = HeuristicValidator(
        available_templates=available_templates,
        song_structure=song_structure,
    )

    heuristic_result: HeuristicValidationResult = validator.validate(plan)

    result = ValidationResult(
        valid=heuristic_result.valid,
        errors=heuristic_result.errors,
        warnings=heuristic_result.warnings,
        timestamp=datetime.now(dt.UTC).isoformat(),
    )

    if result.valid:
        logger.debug("Plan validation passed (%d warnings)", len(result.warnings))
    else:
        logger.warning("Plan validation failed (%d errors)", len(result.errors))

    return result


def validation_to_flags(validation: ValidationResult) -> list[ReportFlag]:
    """Convert validation result to report flags.

    Args:
        validation: Validation result to convert

    Returns:
        List of report flags

    Example:
        >>> validation = ValidationResult(valid=False, errors=["Template not found"], warnings=["Gap detected"])
        >>> flags = validation_to_flags(validation)
        >>> len(flags)
        2
    """
    flags: list[ReportFlag] = []

    # Convert errors to ERROR flags
    for error in validation.errors:
        flags.append(
            ReportFlag(
                level=ReportFlagLevel.ERROR,
                code="VALIDATION_ERROR",
                message=error,
                details={"source": "heuristic_validator", "timestamp": validation.timestamp},
            )
        )

    # Convert warnings to WARNING flags
    for warning in validation.warnings:
        flags.append(
            ReportFlag(
                level=ReportFlagLevel.WARNING,
                code="VALIDATION_WARNING",
                message=warning,
                details={"source": "heuristic_validator", "timestamp": validation.timestamp},
            )
        )

    return flags


def load_available_templates(template_dir: Path | None = None) -> list[str]:
    """Load list of available template IDs from template library.

    Args:
        template_dir: Optional directory containing templates (defaults to package templates)

    Returns:
        List of template IDs

    Example:
        >>> templates = load_available_templates()
        >>> "inner_pendulum_breathe" in templates
        True
    """
    # Import here to avoid circular dependencies
    from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
    from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY

    # Ensure built-in templates are loaded
    load_builtin_templates()

    # list_all() returns list[TemplateInfo], extract template_id
    return [info.template_id for info in REGISTRY.list_all()]
