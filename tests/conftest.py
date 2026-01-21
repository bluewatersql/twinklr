"""Shared pytest fixtures for blinkb0t tests.

This module provides common fixtures used across multiple test files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
    CurveGenerator,
    CustomCurveProvider,
    NativeCurveProvider,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner


@pytest.fixture
def dmx_curve_mapper() -> DMXCurveMapper:
    """Create a DMXCurveMapper with empty curve library for testing.

    Returns:
        DMXCurveMapper instance ready for use in tests
    """
    # Create empty curve library (tests can add curves if needed)
    curve_library = CurveLibrary()

    # Optionally load presets if they exist (for integration tests)
    presets_path = (
        Path(__file__).parent.parent
        / "packages"
        / "blinkb0t"
        / "core"
        / "domains"
        / "sequencing"
        / "curves"
        / "data"
        / "v1"
        / "presets.json"
    )
    if presets_path.exists():
        import json

        with presets_path.open("r") as f:
            presets_data = json.load(f)
        curve_library.load_from_dict(presets_data)

    # Initialize curve engine components
    native_provider = NativeCurveProvider()
    custom_provider = CustomCurveProvider()
    curve_generator = CurveGenerator(
        library=curve_library,
        native_provider=native_provider,
        custom_provider=custom_provider,
    )
    curve_normalizer = CurveNormalizer()
    native_curve_tuner = NativeCurveTuner()

    # Create mapper
    return DMXCurveMapper(
        generator=curve_generator,
        normalizer=curve_normalizer,
        tuner=native_curve_tuner,
    )
