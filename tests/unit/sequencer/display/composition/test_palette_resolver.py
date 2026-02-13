"""Unit tests for PaletteResolver.

Tests the conversion of PaletteRef (from planning) to ResolvedPalette
(for rendering) via the theming PaletteCatalog.
"""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.display.composition.palette_resolver import (
    PaletteResolver,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.theming.catalog import PaletteCatalog
from twinklr.core.sequencer.theming.models import ColorStop, PaletteDefinition


def _make_catalog() -> PaletteCatalog:
    """Build a small test catalog."""
    cat = PaletteCatalog()
    cat.register(
        PaletteDefinition(
            palette_id="core.christmas_traditional",
            title="Christmas Traditional",
            description="Classic red/green/white.",
            stops=[
                ColorStop(hex="#E53935", name="red"),
                ColorStop(hex="#43A047", name="green"),
                ColorStop(hex="#F5F1E8", name="warm_white", weight=0.8),
                ColorStop(hex="#FFFFFF", name="white", weight=0.4),
            ],
        )
    )
    cat.register(
        PaletteDefinition(
            palette_id="core.mono_cool",
            title="Mono Cool",
            description="Cool monochrome.",
            stops=[
                ColorStop(hex="#FFFFFF", name="white"),
                ColorStop(hex="#B3E5FC", name="ice_light"),
                ColorStop(hex="#2979FF", name="blue_accent", weight=0.4),
            ],
        )
    )
    cat.register(
        PaletteDefinition(
            palette_id="spec.fire_ice",
            title="Fire & Ice",
            description="Warm/cool split.",
            stops=[
                ColorStop(hex="#FF1744", name="hot_red"),
                ColorStop(hex="#FF9100", name="amber"),
                ColorStop(hex="#00E5FF", name="cyan"),
                ColorStop(hex="#2979FF", name="blue"),
                ColorStop(hex="#FFFFFF", name="white", weight=0.5),
            ],
        )
    )
    return cat


def _make_default() -> ResolvedPalette:
    """Default fallback palette."""
    return ResolvedPalette(
        colors=["#FF0000", "#00FF00"],
        active_slots=[1, 2],
    )


class TestPaletteResolverLookup:
    """Tests for catalog-backed palette resolution."""

    def test_resolves_known_palette_id(self) -> None:
        resolver = PaletteResolver(catalog=_make_catalog(), default=_make_default())
        ref = PaletteRef(palette_id="core.christmas_traditional")
        result = resolver.resolve(ref)

        # Should extract hex colors from stops (weight >= threshold)
        assert "#E53935" in result.colors
        assert "#43A047" in result.colors
        # Active slots should match the number of included colors
        assert len(result.active_slots) == len(result.colors)
        # Slots are 1-indexed
        assert result.active_slots[0] == 1

    def test_resolves_mono_cool(self) -> None:
        resolver = PaletteResolver(catalog=_make_catalog(), default=_make_default())
        ref = PaletteRef(palette_id="core.mono_cool")
        result = resolver.resolve(ref)

        assert "#FFFFFF" in result.colors
        assert "#B3E5FC" in result.colors

    def test_resolves_five_color_palette(self) -> None:
        resolver = PaletteResolver(catalog=_make_catalog(), default=_make_default())
        ref = PaletteRef(palette_id="spec.fire_ice")
        result = resolver.resolve(ref)

        # All 5 stops included
        assert len(result.colors) == 5
        assert result.active_slots == [1, 2, 3, 4, 5]

    def test_unknown_palette_returns_default(self) -> None:
        resolver = PaletteResolver(catalog=_make_catalog(), default=_make_default())
        ref = PaletteRef(palette_id="nonexistent.palette")
        result = resolver.resolve(ref)

        assert result == _make_default()

    def test_none_ref_returns_default(self) -> None:
        resolver = PaletteResolver(catalog=_make_catalog(), default=_make_default())
        result = resolver.resolve(None)

        assert result == _make_default()


class TestPaletteResolverColorOrder:
    """Color ordering and slot assignment."""

    def test_colors_follow_stop_order(self) -> None:
        """Colors should be in the same order as palette stops."""
        resolver = PaletteResolver(catalog=_make_catalog(), default=_make_default())
        ref = PaletteRef(palette_id="core.christmas_traditional")
        result = resolver.resolve(ref)

        # First color should be the first stop
        assert result.colors[0] == "#E53935"

    def test_active_slots_are_sequential(self) -> None:
        resolver = PaletteResolver(catalog=_make_catalog(), default=_make_default())
        ref = PaletteRef(palette_id="spec.fire_ice")
        result = resolver.resolve(ref)

        assert result.active_slots == list(range(1, len(result.colors) + 1))

    def test_max_eight_colors(self) -> None:
        """Palette should cap at 8 colors (xLights max)."""
        cat = PaletteCatalog()
        cat.register(
            PaletteDefinition(
                palette_id="test.many_colors",
                title="Many Colors",
                description="Too many stops.",
                stops=[
                    ColorStop(hex=f"#FF{i:02X}00", name=f"color_{i}")
                    for i in range(10)
                ],
            )
        )
        resolver = PaletteResolver(catalog=cat, default=_make_default())
        ref = PaletteRef(palette_id="test.many_colors")
        result = resolver.resolve(ref)

        assert len(result.colors) <= 8
        assert len(result.active_slots) <= 8


class TestPaletteResolverImmutability:
    """Resolved palettes should be frozen (immutable)."""

    def test_resolved_palette_is_frozen(self) -> None:
        resolver = PaletteResolver(catalog=_make_catalog(), default=_make_default())
        ref = PaletteRef(palette_id="core.christmas_traditional")
        result = resolver.resolve(ref)

        with pytest.raises(ValidationError):  # Pydantic frozen model
            result.colors = ["#000000"]  # type: ignore[misc]

    def test_same_ref_returns_equal_palette(self) -> None:
        """Multiple resolves of same ref should produce equal results."""
        resolver = PaletteResolver(catalog=_make_catalog(), default=_make_default())
        ref = PaletteRef(palette_id="core.mono_cool")

        result1 = resolver.resolve(ref)
        result2 = resolver.resolve(ref)

        assert result1 == result2
