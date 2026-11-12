"""The dimmer handler's three P1P-T5 repairs, at the level they happen.

P4-M2 is two composing bugs: `_resolve_static_dmx_value` multiplied a value that is
already DMX by 255, and the missing-intensity fallback substituted the *library
default's* params for the pattern's own. Together they turned `DimmerType.BLACKOUT`
into full brightness under every preset but MODERATE. P4-M1 applied the template's
declared anti-flicker floor, and P4-F8's renderer half gave SLOW and FAST their own
`DEFAULT_DIMMER_PARAMS` values. Both were reverted on 2026-11-12 at the owner's
request: only the rig calibration bounds the dimmer, and SLOW and FAST carry the
SMOOTH values.
"""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.handlers.dimmers.default import DefaultDimmerHandler
from twinklr.core.sequencer.moving_heads.libraries.dimmer import (
    DEFAULT_DIMMER_PARAMS,
    DimmerLibrary,
    DimmerType,
)

ALL_INTENSITIES = list(Intensity)


@pytest.fixture
def handler() -> DefaultDimmerHandler:
    return DefaultDimmerHandler()


def _generate(
    handler: DefaultDimmerHandler,
    dimmer_type: DimmerType,
    intensity: Intensity,
    **params: object,
):
    return handler.generate(
        params={"dimmer_pattern": DimmerLibrary.get_pattern(dimmer_type), **params},
        n_samples=16,
        cycles=1.0,
        intensity=intensity,
        min_norm=0.0,
        max_norm=1.0,
    )


def test_default_dimmer_params_covers_all_intensities() -> None:
    """Every Intensity has an entry, so a missing key cannot fall back silently."""
    assert set(DEFAULT_DIMMER_PARAMS) == set(Intensity)


@pytest.mark.parametrize("intensity", [Intensity.SLOW, Intensity.FAST])
def test_slow_and_fast_carry_the_smooth_values(intensity: Intensity) -> None:
    """P4-F8 reverted: SLOW and FAST render the SMOOTH dimmer, the accepted look."""
    assert DEFAULT_DIMMER_PARAMS[intensity] == DEFAULT_DIMMER_PARAMS[Intensity.SMOOTH]


def test_a_missing_library_entry_is_an_error_not_a_silent_substitution(
    handler: DefaultDimmerHandler, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard on the gap P4-F8 came through: an Intensity with no library entry
    used to resolve to SMOOTH, so the plan's request disappeared without a word."""
    monkeypatch.setattr(
        "twinklr.core.sequencer.moving_heads.handlers.dimmers.default.DEFAULT_DIMMER_PARAMS",
        {key: value for key, value in DEFAULT_DIMMER_PARAMS.items() if key is not Intensity.FAST},
    )

    with pytest.raises(ValueError, match="no entry for"):
        _generate(handler, DimmerType.PULSE, Intensity.FAST)


def test_static_dmx_value_treats_max_intensity_as_dmx(handler: DefaultDimmerHandler) -> None:
    """The unit bug itself: `max_intensity` is DMX in [0,255], not normalized."""
    assert handler._resolve_static_dmx_value(128) == 128
    assert handler._resolve_static_dmx_value(0) == 0
    assert handler._resolve_static_dmx_value(255) == 255


@pytest.mark.parametrize("intensity", ALL_INTENSITIES)
def test_blackout_is_zero_under_every_intensity(
    handler: DefaultDimmerHandler, intensity: Intensity
) -> None:
    """BLACKOUT declares only a SMOOTH entry; the other four used to fall back to
    `DEFAULT_DIMMER_PARAMS[SMOOTH]` (max_intensity=128) and emit 255."""
    result = _generate(handler, DimmerType.BLACKOUT, intensity)

    assert result.dimmer_static_dmx == 0


@pytest.mark.parametrize("intensity", ALL_INTENSITIES)
def test_blackout_ignores_the_anti_flicker_floor(
    handler: DefaultDimmerHandler, intensity: Intensity
) -> None:
    """The floor's documented exception, exercised explicitly rather than by luck.

    A rig calibrated with a 60-DMX floor must still let a blackout reach black.
    """
    result = _generate(
        handler,
        DimmerType.BLACKOUT,
        intensity,
        calibration={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255},
    )

    assert result.dimmer_static_dmx == 0
    assert result.clamp_min_dmx == 0


def test_hold_dimmer_still_full_at_smooth(handler: DefaultDimmerHandler) -> None:
    """HOLD's arithmetic changes with the unit fix (255*255 clamped, now 255 direct)
    even though its output does not. Re-tested for exactly that reason."""
    result = _generate(handler, DimmerType.HOLD, Intensity.SMOOTH)

    assert result.dimmer_static_dmx == 255


def test_template_floor_does_not_lift_the_dimmer_clamp(handler: DefaultDimmerHandler) -> None:
    """P4-M1 reverted: the template's declared floor and ceiling are not applied."""
    result = _generate(
        handler,
        DimmerType.PULSE,
        Intensity.SMOOTH,
        template_defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 240},
    )

    assert (result.clamp_min_dmx, result.clamp_max_dmx) == (0, 255)


def test_rig_calibration_alone_bounds_the_dimmer(handler: DefaultDimmerHandler) -> None:
    """With both declared, the rig calibration decides and the template is ignored."""
    result = _generate(
        handler,
        DimmerType.PULSE,
        Intensity.SMOOTH,
        template_defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255},
        calibration={"dimmer_floor_dmx": 20, "dimmer_ceiling_dmx": 200},
    )

    assert (result.clamp_min_dmx, result.clamp_max_dmx) == (20, 200)


def test_missing_floor_leaves_the_full_range(handler: DefaultDimmerHandler) -> None:
    result = _generate(handler, DimmerType.PULSE, Intensity.SMOOTH)

    assert (result.clamp_min_dmx, result.clamp_max_dmx) == (0, 255)


def test_fade_out_descends_and_fade_in_rises() -> None:
    """FADE_OUT named the same ascending LINEAR curve as FADE_IN and nothing inverted
    it, so it was a fade-in under another name. Only observable from P1P-T5 onwards,
    because until then no FADE_OUT step in the library was ever scheduled."""
    handler = DefaultDimmerHandler()

    fade_in = _generate(handler, DimmerType.FADE_IN, Intensity.SMOOTH).dimmer_curve
    fade_out = _generate(handler, DimmerType.FADE_OUT, Intensity.SMOOTH).dimmer_curve
    assert fade_in is not None and fade_out is not None

    assert fade_in[-1].v > fade_in[0].v
    assert fade_out[-1].v < fade_out[0].v


@pytest.mark.parametrize("intensity", ALL_INTENSITIES)
def test_pattern_without_its_own_table_uses_the_library_entry_for_that_intensity(
    handler: DefaultDimmerHandler, intensity: Intensity
) -> None:
    """PULSE declares no categorical params, so every intensity resolves to its own
    library entry (for SLOW and FAST that entry carries the SMOOTH values)."""
    result = _generate(handler, DimmerType.PULSE, intensity)

    assert result.max_intensity == DEFAULT_DIMMER_PARAMS[intensity].max_intensity
    assert result.period == DEFAULT_DIMMER_PARAMS[intensity].period
