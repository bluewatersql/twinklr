"""Factory for creating DMXCurveMapper instances.

Extracted from MovingHeadSequencer to simplify initialization.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
    CurveGenerator,
    CustomCurveProvider,
    NativeCurveProvider,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def create_curve_mapper() -> DMXCurveMapper:
    """Create shared DMXCurveMapper

    Returns:
        DMXCurveMapper with curve presets loaded
    """
    # Create curve engine components
    native_provider = NativeCurveProvider()
    custom_provider = CustomCurveProvider()
    curve_generator = CurveGenerator(
        library=CurveLibrary(),
        native_provider=native_provider,
        custom_provider=custom_provider,
    )
    curve_normalizer = CurveNormalizer()
    native_curve_tuner = NativeCurveTuner()

    return DMXCurveMapper(
        generator=curve_generator,
        normalizer=curve_normalizer,
        tuner=native_curve_tuner,
    )
