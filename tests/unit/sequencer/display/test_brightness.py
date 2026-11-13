"""Tests for the event-intensity to brightness mapping."""

from __future__ import annotations

from itertools import pairwise

import pytest

from twinklr.core.sequencer.display.brightness import (
    MIN_VISIBLE_BRIGHTNESS,
    intensity_to_brightness,
)


def test_zero_intensity_is_the_visible_floor() -> None:
    assert intensity_to_brightness(0.0) == MIN_VISIBLE_BRIGHTNESS


def test_full_intensity_is_full_brightness() -> None:
    assert intensity_to_brightness(1.0) == pytest.approx(1.0)


def test_mapping_is_strictly_increasing() -> None:
    levels = [intensity_to_brightness(i / 20) for i in range(21)]
    assert all(a < b for a, b in pairwise(levels))


def test_out_of_range_intensity_is_clamped() -> None:
    assert intensity_to_brightness(-0.5) == MIN_VISIBLE_BRIGHTNESS
    assert intensity_to_brightness(1.5) == pytest.approx(1.0)
