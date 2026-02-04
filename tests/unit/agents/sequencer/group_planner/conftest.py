"""Shared fixtures for group_planner tests."""

import pytest

from twinklr.core.sequencer.theming import ThemeRef, ThemeScope


@pytest.fixture
def default_theme_ref() -> ThemeRef:
    """Default ThemeRef for tests."""
    return ThemeRef(
        theme_id="christmas.test_theme",
        scope=ThemeScope.SECTION,
        tags=["test"],
        palette_id=None,
    )


# Convenience constant for inline use
DEFAULT_THEME = ThemeRef(
    theme_id="christmas.test_theme",
    scope=ThemeScope.SECTION,
    tags=["test"],
    palette_id=None,
)
