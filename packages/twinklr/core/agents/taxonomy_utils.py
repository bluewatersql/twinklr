"""Utilities for extracting taxonomy enum values for prompt injection.

Ensures prompts always use the source-of-truth enum values from taxonomy.py
and issues.py.
"""

from typing import Any


def get_taxonomy_dict() -> dict[str, list[str]]:
    """Get dictionary of taxonomy enum names to value lists.

    Extracts all enum values from the taxonomy and issues modules for dynamic
    injection into prompts, preventing hardcoded enum drift.

    Returns:
        Dict mapping enum class names to lists of their string values.
        Example: {"LayerRole": ["BASE", "RHYTHM", ...],
                  "IssueCategory": ["SCHEMA", "TIMING", ...], ...}
    """
    from enum import Enum

    from twinklr.core.agents.issues import (
        IssueCategory,
        IssueEffort,
        IssueScope,
        IssueSeverity,
        SuggestedAction,
    )
    from twinklr.core.agents.taxonomy import (
        BlendMode,
        ChoreographyStyle,
        EnergyTarget,
        LayerRole,
        MotionDensity,
        TargetRole,
        TimingDriver,
    )

    taxonomy: dict[str, list[str]] = {}

    # Extract choreography taxonomy enums
    choreography_enums: list[type[Enum]] = [
        LayerRole,
        BlendMode,
        TimingDriver,
        TargetRole,
        EnergyTarget,
        ChoreographyStyle,
        MotionDensity,
    ]

    # Extract issue taxonomy enums (for judge agents)
    issue_enums: list[type[Enum]] = [
        IssueCategory,
        IssueSeverity,
        IssueEffort,
        IssueScope,
        SuggestedAction,
    ]

    for enum_class in choreography_enums + issue_enums:
        taxonomy[enum_class.__name__] = [e.value for e in enum_class]  # type: ignore[misc]

    return taxonomy


def inject_taxonomy(variables: dict[str, Any]) -> dict[str, Any]:
    """Inject taxonomy enum values into prompt variables.

    Args:
        variables: Existing prompt variables

    Returns:
        Variables dict with 'taxonomy' key added containing enum values
    """
    if "taxonomy" not in variables:
        variables = {**variables, "taxonomy": get_taxonomy_dict()}
    return variables
