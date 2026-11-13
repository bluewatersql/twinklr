"""Tests for the event-intensity to brightness mapping."""

from __future__ import annotations

from itertools import pairwise

import pytest

from twinklr.core.sequencer.display.brightness import (
    MIN_RESTING_BRIGHTNESS,
    MIN_VISIBLE_BRIGHTNESS,
    event_brightness_percent,
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


def test_event_brightness_matches_the_intensity_mapping() -> None:
    assert event_brightness_percent(0.2) == 48
    assert event_brightness_percent(1.0) == 100


def test_palette_brightness_composes_with_intensity() -> None:
    # 80% of 0.48
    assert event_brightness_percent(0.2, palette_brightness=80) == 38


def test_dim_palette_cannot_go_below_the_visible_floor() -> None:
    floor = round(MIN_VISIBLE_BRIGHTNESS * 100)
    assert event_brightness_percent(0.0, palette_brightness=20) == floor
    assert event_brightness_percent(1.0, palette_brightness=10) == floor


def test_role_scale_dims_the_lit_brightness() -> None:
    """A resting group keeps its declared ratio to the lead."""
    lead = event_brightness_percent(0.8)
    rest = event_brightness_percent(0.8, scale=0.15)
    assert lead == 87
    assert rest == 13


def test_role_scale_has_its_own_floor() -> None:
    assert event_brightness_percent(0.0, scale=0.01) == round(MIN_RESTING_BRIGHTNESS * 100)
