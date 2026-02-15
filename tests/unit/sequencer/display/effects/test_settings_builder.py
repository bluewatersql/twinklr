"""Tests for SettingsStringBuilder value curve methods."""

from __future__ import annotations

from twinklr.core.sequencer.display.effects.settings_builder import (
    SettingsStringBuilder,
)


class TestSettingsStringBuilderValueCurves:
    """Tests for add_value_curve and add_value_curves."""

    def test_add_value_curve(self) -> None:
        """add_value_curve appends E_VALUECURVE_ key."""
        b = SettingsStringBuilder()
        b.add("E_SLIDER_Speed", 50)
        b.add_value_curve(
            "Speed", "Active=TRUE|Id=ID_VALUECURVE_Speed|Type=Custom|Values=0.00:0.50;1.00:0.50|"
        )
        result = b.build()
        assert "E_SLIDER_Speed=50" in result
        assert "E_VALUECURVE_Speed=Active=TRUE" in result

    def test_add_value_curves_bulk(self) -> None:
        """add_value_curves adds multiple curves."""
        b = SettingsStringBuilder()
        curves = {
            "Speed": "Active=TRUE|Id=S|Type=Custom|",
            "Count": "Active=TRUE|Id=C|Type=Custom|",
        }
        b.add_value_curves(curves)
        result = b.build()
        assert "E_VALUECURVE_Speed=Active=TRUE" in result
        assert "E_VALUECURVE_Count=Active=TRUE" in result

    def test_chaining(self) -> None:
        """add_value_curve returns self for chaining."""
        b = SettingsStringBuilder()
        result = b.add_value_curve("X", "curve").add_value_curve("Y", "curve2")
        assert result is b
        assert "E_VALUECURVE_X=curve" in b.build()
        assert "E_VALUECURVE_Y=curve2" in b.build()

    def test_empty_curves_dict(self) -> None:
        """add_value_curves with empty dict adds nothing."""
        b = SettingsStringBuilder()
        b.add("E_SLIDER_Speed", 50)
        b.add_value_curves({})
        result = b.build()
        assert result == "E_SLIDER_Speed=50"
