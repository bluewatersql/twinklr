"""Unit tests for EffectDB and Palette registries."""

from __future__ import annotations

from twinklr.core.sequencer.display.export.effectdb_registry import (
    EffectDBRegistry,
)
from twinklr.core.sequencer.display.palette.registry import PaletteDBRegistry


class TestEffectDBRegistry:
    """Tests for the EffectDBRegistry."""

    def test_reserve_zero(self) -> None:
        reg = EffectDBRegistry(reserve_zero=True)
        assert len(reg) == 1
        assert reg.get_entries()[0] == ""

    def test_no_reserve_zero(self) -> None:
        reg = EffectDBRegistry(reserve_zero=False)
        assert len(reg) == 0

    def test_register_returns_index(self) -> None:
        reg = EffectDBRegistry()
        idx = reg.register("E_SLIDER_Speed=50")
        assert idx == 1  # 0 is reserved

    def test_dedup(self) -> None:
        reg = EffectDBRegistry()
        idx1 = reg.register("E_SLIDER_Speed=50")
        idx2 = reg.register("E_SLIDER_Speed=50")
        assert idx1 == idx2
        assert len(reg) == 2  # reserved + one entry

    def test_different_entries(self) -> None:
        reg = EffectDBRegistry()
        idx1 = reg.register("E_SLIDER_Speed=50")
        idx2 = reg.register("E_SLIDER_Speed=75")
        assert idx1 != idx2
        assert len(reg) == 3  # reserved + two entries


class TestPaletteDBRegistry:
    """Tests for the PaletteDBRegistry."""

    def test_register(self) -> None:
        reg = PaletteDBRegistry()
        idx = reg.register("C_BUTTON_Palette1=#FF0000")
        assert idx == 0

    def test_dedup(self) -> None:
        reg = PaletteDBRegistry()
        idx1 = reg.register("C_BUTTON_Palette1=#FF0000")
        idx2 = reg.register("C_BUTTON_Palette1=#FF0000")
        assert idx1 == idx2
        assert len(reg) == 1

    def test_different_entries(self) -> None:
        reg = PaletteDBRegistry()
        idx1 = reg.register("C_BUTTON_Palette1=#FF0000")
        idx2 = reg.register("C_BUTTON_Palette1=#00FF00")
        assert idx1 != idx2
        assert len(reg) == 2
