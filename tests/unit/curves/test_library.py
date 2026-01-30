"""Tests for curve library."""

from __future__ import annotations

import pytest

from twinklr.core.curves.library import CurveLibrary, build_default_registry
from twinklr.core.curves.semantics import CurveKind


class TestCurveLibrary:
    """Tests for CurveLibrary enum."""

    def test_basic_wave_values(self) -> None:
        """Basic wave curve values exist."""
        assert CurveLibrary.LINEAR.value == "linear"
        assert CurveLibrary.HOLD.value == "hold"
        assert CurveLibrary.SINE.value == "sine"
        assert CurveLibrary.PULSE.value == "pulse"
        assert CurveLibrary.COSINE.value == "cosine"
        assert CurveLibrary.TRIANGLE.value == "triangle"
        assert CurveLibrary.SQUARE.value == "square"

    def test_smooth_transition_values(self) -> None:
        """Smooth transition curve values exist."""
        assert CurveLibrary.S_CURVE.value == "s_curve"
        assert CurveLibrary.SMOOTH_STEP.value == "smooth_step"
        assert CurveLibrary.SMOOTHER_STEP.value == "smoother_step"

    def test_easing_sine_values(self) -> None:
        """Easing sine curve values exist."""
        assert CurveLibrary.EASE_IN_SINE.value == "ease_in_sine"
        assert CurveLibrary.EASE_OUT_SINE.value == "ease_out_sine"
        assert CurveLibrary.EASE_IN_OUT_SINE.value == "ease_in_out_sine"

    def test_easing_quad_values(self) -> None:
        """Easing quad curve values exist."""
        assert CurveLibrary.EASE_IN_QUAD.value == "ease_in_quad"
        assert CurveLibrary.EASE_OUT_QUAD.value == "ease_out_quad"
        assert CurveLibrary.EASE_IN_OUT_QUAD.value == "ease_in_out_quad"

    def test_easing_cubic_values(self) -> None:
        """Easing cubic curve values exist."""
        assert CurveLibrary.EASE_IN_CUBIC.value == "ease_in_cubic"
        assert CurveLibrary.EASE_OUT_CUBIC.value == "ease_out_cubic"
        assert CurveLibrary.EASE_IN_OUT_CUBIC.value == "ease_in_out_cubic"

    def test_easing_back_values(self) -> None:
        """Easing back curve values exist."""
        assert CurveLibrary.EASE_IN_BACK.value == "ease_in_back"
        assert CurveLibrary.EASE_OUT_BACK.value == "ease_out_back"
        assert CurveLibrary.EASE_IN_OUT_BACK.value == "ease_in_out_back"

    def test_bounce_values(self) -> None:
        """Bounce curve values exist."""
        assert CurveLibrary.BOUNCE_IN.value == "bounce_in"
        assert CurveLibrary.BOUNCE_OUT.value == "bounce_out"

    def test_elastic_values(self) -> None:
        """Elastic curve values exist."""
        assert CurveLibrary.ELASTIC_IN.value == "elastic_in"
        assert CurveLibrary.ELASTIC_OUT.value == "elastic_out"

    def test_musical_values(self) -> None:
        """Musical curve values exist."""
        assert CurveLibrary.MUSICAL_ACCENT.value == "musical_accent"
        assert CurveLibrary.MUSICAL_SWELL.value == "musical_swell"
        assert CurveLibrary.BEAT_PULSE.value == "beat_pulse"

    def test_noise_values(self) -> None:
        """Noise curve values exist."""
        assert CurveLibrary.MOVEMENT_PERLIN_NOISE.value == "movement_perlin_noise"

    def test_parametric_values(self) -> None:
        """Parametric curve values exist."""
        assert CurveLibrary.BEZIER.value == "bezier"
        assert CurveLibrary.LISSAJOUS.value == "lissajous"

    def test_advanced_easing_values(self) -> None:
        """Advanced easing curve values exist."""
        assert CurveLibrary.ANTICIPATE.value == "anticipate"
        assert CurveLibrary.OVERSHOOT.value == "overshoot"

    def test_movement_values(self) -> None:
        """Movement curve values exist."""
        assert CurveLibrary.MOVEMENT_LINEAR.value == "movement_linear"
        assert CurveLibrary.MOVEMENT_HOLD.value == "movement_hold"
        assert CurveLibrary.MOVEMENT_SINE.value == "movement_sine"
        assert CurveLibrary.MOVEMENT_TRIANGLE.value == "movement_triangle"
        assert CurveLibrary.MOVEMENT_PULSE.value == "movement_pulse"

    def test_is_string_enum(self) -> None:
        """CurveLibrary is a string enum."""
        assert isinstance(CurveLibrary.LINEAR, str)
        assert CurveLibrary.LINEAR == "linear"


class TestBuildDefaultRegistry:
    """Tests for build_default_registry function."""

    def test_returns_registry(self) -> None:
        """Returns a CurveRegistry instance."""
        from twinklr.core.curves.registry import CurveRegistry

        registry = build_default_registry()
        assert isinstance(registry, CurveRegistry)

    def test_all_library_curves_registered(self) -> None:
        """All CurveLibrary curves are registered."""
        registry = build_default_registry()
        for curve in CurveLibrary:
            defn = registry.get(curve.value)
            assert defn is not None
            assert defn.curve_id == curve.value

    def test_dimmer_curves_have_dimmer_kind(self) -> None:
        """Non-movement curves have DIMMER_ABSOLUTE kind."""
        registry = build_default_registry()
        defn = registry.get(CurveLibrary.LINEAR.value)
        assert defn.kind == CurveKind.DIMMER_ABSOLUTE

    def test_movement_curves_have_movement_kind(self) -> None:
        """Movement curves have MOVEMENT_OFFSET kind."""
        registry = build_default_registry()
        defn = registry.get(CurveLibrary.MOVEMENT_SINE.value)
        assert defn.kind == CurveKind.MOVEMENT_OFFSET

    def test_default_samples_is_64(self) -> None:
        """Default samples is 64."""
        registry = build_default_registry()
        defn = registry.get(CurveLibrary.SINE.value)
        assert defn.default_samples == 64

    @pytest.mark.parametrize(
        "curve_id",
        [
            CurveLibrary.LINEAR.value,
            CurveLibrary.SINE.value,
            CurveLibrary.EASE_IN_OUT_CUBIC.value,
            CurveLibrary.BOUNCE_OUT.value,
        ],
    )
    def test_curves_can_generate_points(self, curve_id: str) -> None:
        """Curves can generate valid points."""
        registry = build_default_registry()
        defn = registry.get(curve_id)
        points = registry.resolve(defn)
        assert len(points) == 64
        for p in points:
            assert 0.0 <= p.t <= 1.0
            assert 0.0 <= p.v <= 1.0

    def test_linear_generates_ramp(self) -> None:
        """Linear curve generates ascending ramp."""
        registry = build_default_registry()
        defn = registry.get(CurveLibrary.LINEAR.value)
        points = registry.resolve(defn, n_samples=4)
        # Should be ascending
        assert points[0].v < points[-1].v

    def test_hold_generates_constant(self) -> None:
        """Hold curve generates constant value."""
        registry = build_default_registry()
        defn = registry.get(CurveLibrary.HOLD.value)
        points = registry.resolve(defn, n_samples=4)
        # All values should be 1.0 (default)
        for p in points:
            assert p.v == pytest.approx(1.0)

    def test_sine_generates_wave(self) -> None:
        """Sine curve generates wave pattern."""
        registry = build_default_registry()
        defn = registry.get(CurveLibrary.SINE.value)
        points = registry.resolve(defn, n_samples=8)
        # Should have variation
        values = [p.v for p in points]
        assert max(values) > min(values)
