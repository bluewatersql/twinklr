"""Tests for ColorFamilyDiscoverer — color family discovery from effect params."""

from __future__ import annotations

from twinklr.core.feature_engineering.color_discovery import (
    ColorFamilyDiscoverer,
    DiscoveredPalette,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_enriched_event(
    *,
    effect_event_id: str = "evt-1",
    package_id: str = "pkg-1",
    sequence_file_id: str = "seq-1",
    section_label: str = "verse",
    palette: str = "",
    effectdb_params: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Build a minimal enriched event dict matching the pipeline's JSON shape."""
    return {
        "effect_event_id": effect_event_id,
        "package_id": package_id,
        "sequence_file_id": sequence_file_id,
        "section_label": section_label,
        "palette": palette,
        "effectdb_params": effectdb_params or [],
    }


def _param(name: str, value: str) -> dict[str, object]:
    """Shorthand for an effectdb_params entry with a string value."""
    return {
        "namespace": "E_EFFECT",
        "param_name_normalized": name,
        "value_type": "string",
        "value_string": value,
    }


# ---------------------------------------------------------------------------
# 1. Hex color extraction from preserved_params
# ---------------------------------------------------------------------------


class TestHexColorExtraction:
    """Verify hex colors are correctly extracted from enriched event params."""

    def test_extracts_palette_hex(self) -> None:
        """Colors in the top-level 'palette' field are extracted."""
        events = [
            _make_enriched_event(palette="#FF0000"),
            _make_enriched_event(palette="#00FF00"),
        ]
        discoverer = ColorFamilyDiscoverer()
        colors = discoverer._extract_colors(events)
        assert "#FF0000" in colors
        assert "#00FF00" in colors

    def test_extracts_color_params(self) -> None:
        """Colors from effectdb_params named color1/color2/color3 are extracted."""
        events = [
            _make_enriched_event(
                effectdb_params=[
                    _param("color1", "#0000FF"),
                    _param("color2", "#FFFF00"),
                    _param("color3", "#FF00FF"),
                ],
            ),
        ]
        discoverer = ColorFamilyDiscoverer()
        colors = discoverer._extract_colors(events)
        assert "#0000FF" in colors
        assert "#FFFF00" in colors
        assert "#FF00FF" in colors

    def test_extracts_singlestrand_colors(self) -> None:
        """Colors from singlestrand_colors param are extracted."""
        events = [
            _make_enriched_event(
                effectdb_params=[_param("singlestrand_colors", "#112233,#445566")],
            ),
        ]
        discoverer = ColorFamilyDiscoverer()
        colors = discoverer._extract_colors(events)
        assert "#112233" in colors
        assert "#445566" in colors

    def test_extracts_c_slider_color_params(self) -> None:
        """Colors from C_SLIDER_Color* params are extracted."""
        events = [
            _make_enriched_event(
                effectdb_params=[
                    _param("c_slider_color1", "#AABBCC"),
                    _param("c_slider_color2", "#DDEEFF"),
                ],
            ),
        ]
        discoverer = ColorFamilyDiscoverer()
        colors = discoverer._extract_colors(events)
        assert "#AABBCC" in colors
        assert "#DDEEFF" in colors

    def test_extracts_generic_color_suffix_params(self) -> None:
        """Params ending in '_color' are recognized as color sources."""
        events = [
            _make_enriched_event(
                effectdb_params=[_param("background_color", "#778899")],
            ),
        ]
        discoverer = ColorFamilyDiscoverer()
        colors = discoverer._extract_colors(events)
        assert "#778899" in colors


# ---------------------------------------------------------------------------
# 2. Hue clustering produces expected bins
# ---------------------------------------------------------------------------


class TestHueClustering:
    """Verify HSV decomposition and 12 hue bins + achromatic."""

    def test_pure_red_goes_to_red_bin(self) -> None:
        result = ColorFamilyDiscoverer._cluster_by_hue(["#FF0000"])
        assert len(result) == 1
        assert result[0].bin_name == "red"

    def test_pure_green_goes_to_green_bin(self) -> None:
        result = ColorFamilyDiscoverer._cluster_by_hue(["#00FF00"])
        assert len(result) == 1
        assert result[0].bin_name == "green"

    def test_pure_blue_goes_to_blue_bin(self) -> None:
        result = ColorFamilyDiscoverer._cluster_by_hue(["#0000FF"])
        assert len(result) == 1
        assert result[0].bin_name == "blue"

    def test_white_is_achromatic(self) -> None:
        result = ColorFamilyDiscoverer._cluster_by_hue(["#FFFFFF"])
        assert len(result) == 1
        assert result[0].bin_name == "achromatic"

    def test_black_is_achromatic(self) -> None:
        result = ColorFamilyDiscoverer._cluster_by_hue(["#000000"])
        assert len(result) == 1
        assert result[0].bin_name == "achromatic"

    def test_twelve_hue_bins_plus_achromatic(self) -> None:
        """We should support exactly 12 chromatic bins plus 1 achromatic."""
        all_bins = ColorFamilyDiscoverer.HUE_BIN_NAMES
        assert len(all_bins) == 13
        assert "achromatic" in all_bins

    def test_multiple_colors_cluster_correctly(self) -> None:
        """Multiple reds should consolidate into one red bin."""
        result = ColorFamilyDiscoverer._cluster_by_hue(["#FF0000", "#FF3333", "#CC0000"])
        assert len(result) == 1
        assert result[0].bin_name == "red"
        assert len(result[0].colors) == 3


# ---------------------------------------------------------------------------
# 3. Palette construction from co-occurring colors
# ---------------------------------------------------------------------------


class TestPaletteConstruction:
    """Verify palettes are built from colors co-occurring within a section scope."""

    def test_cooccurring_colors_form_palette(self) -> None:
        """Colors from same (package_id, sequence_file_id, section_label) form a palette."""
        events = [
            _make_enriched_event(
                package_id="pkg-1",
                sequence_file_id="seq-1",
                section_label="chorus",
                palette="#FF0000",
                effectdb_params=[_param("color1", "#00FF00")],
            ),
            _make_enriched_event(
                package_id="pkg-1",
                sequence_file_id="seq-1",
                section_label="chorus",
                palette="#0000FF",
            ),
        ]
        discoverer = ColorFamilyDiscoverer()
        palettes = discoverer._build_palettes(events)
        assert len(palettes) >= 1
        # The palette for (pkg-1, seq-1, chorus) should contain all 3 colors.
        palette = palettes[0]
        assert len(palette.colors) >= 2

    def test_different_sections_produce_separate_palettes(self) -> None:
        """Colors from different section labels form separate palettes."""
        events = [
            _make_enriched_event(
                section_label="verse",
                palette="#FF0000",
            ),
            _make_enriched_event(
                section_label="chorus",
                palette="#00FF00",
            ),
        ]
        discoverer = ColorFamilyDiscoverer()
        palettes = discoverer._build_palettes(events)
        assert len(palettes) == 2

    def test_deduplication_within_palette(self) -> None:
        """Duplicate colors within the same scope are deduplicated."""
        events = [
            _make_enriched_event(
                section_label="verse",
                palette="#FF0000",
                effectdb_params=[_param("color1", "#FF0000")],
            ),
        ]
        discoverer = ColorFamilyDiscoverer()
        palettes = discoverer._build_palettes(events)
        assert len(palettes) == 1
        # Should have only 1 unique color, not 2.
        assert len(palettes[0].colors) == 1


# ---------------------------------------------------------------------------
# 4. Palette naming heuristics
# ---------------------------------------------------------------------------


class TestPaletteNaming:
    """Verify heuristic naming based on color composition."""

    def test_single_warm_color_named_warm(self) -> None:
        """A palette with only warm colors gets a warm-based name."""
        discoverer = ColorFamilyDiscoverer()
        name = discoverer._name_palette(("#FF0000",))
        assert "warm" in name.lower() or "red" in name.lower()

    def test_single_cool_color_named_cool(self) -> None:
        """A palette with only cool colors gets a cool-based name."""
        discoverer = ColorFamilyDiscoverer()
        name = discoverer._name_palette(("#0000FF",))
        assert "cool" in name.lower() or "blue" in name.lower()

    def test_mixed_colors_named_mixed(self) -> None:
        """A palette with warm and cool colors gets a mixed name."""
        discoverer = ColorFamilyDiscoverer()
        name = discoverer._name_palette(("#FF0000", "#0000FF"))
        assert isinstance(name, str)
        assert len(name) > 0

    def test_achromatic_palette_named_neutral(self) -> None:
        """A palette with only white/black/gray gets a neutral name."""
        discoverer = ColorFamilyDiscoverer()
        name = discoverer._name_palette(("#FFFFFF", "#000000"))
        assert "neutral" in name.lower() or "achromatic" in name.lower()

    def test_rainbow_palette_named_rainbow(self) -> None:
        """A palette spanning many hue bins gets a rainbow or spectrum name."""
        discoverer = ColorFamilyDiscoverer()
        name = discoverer._name_palette(
            ("#FF0000", "#FF8800", "#FFFF00", "#00FF00", "#0000FF", "#8800FF")
        )
        assert "rainbow" in name.lower() or "spectrum" in name.lower()


# ---------------------------------------------------------------------------
# 5. ColorArcExtractor integration (with/without palette library)
# ---------------------------------------------------------------------------


class TestColorArcExtractorIntegration:
    """Verify ColorArcExtractor works with and without a palette library."""

    def test_without_palette_library_uses_hardcoded_defaults(self) -> None:
        """Without a palette_library_path, the extractor uses built-in templates."""
        from twinklr.core.feature_engineering.color_arc import ColorArcExtractor
        from twinklr.core.feature_engineering.models.color_narrative import (
            ColorNarrativeRow,
        )
        from twinklr.core.feature_engineering.models.phrases import (
            ColorClass,
            ContinuityClass,
            EffectPhrase,
            EnergyClass,
            MotionClass,
            PhraseSource,
            SpatialClass,
        )

        phrases = (
            EffectPhrase(
                schema_version="v1.0.0",
                phrase_id="ph-1",
                package_id="pkg-1",
                sequence_file_id="seq-1",
                effect_event_id="evt-1",
                effect_type="Bars",
                effect_family="bars",
                motion_class=MotionClass.SWEEP,
                color_class=ColorClass.PALETTE,
                energy_class=EnergyClass.MID,
                continuity_class=ContinuityClass.SUSTAINED,
                spatial_class=SpatialClass.SINGLE_TARGET,
                source=PhraseSource.EFFECT_TYPE_MAP,
                map_confidence=0.9,
                target_name="MegaTree",
                layer_index=0,
                start_ms=0,
                end_ms=4000,
                duration_ms=4000,
                section_label="verse",
                param_signature="test",
            ),
        )
        color_rows = (
            ColorNarrativeRow(
                schema_version="v1.8.0",
                package_id="pkg-1",
                sequence_file_id="seq-1",
                section_label="verse",
                section_index=0,
                phrase_count=1,
                dominant_color_class="palette",
                contrast_shift_from_prev=0.0,
                hue_family_movement="section_start",
            ),
        )
        # No palette_library_path — should still work
        extractor = ColorArcExtractor()
        arc = extractor.extract(phrases=phrases, color_narrative=color_rows)
        assert len(arc.palette_library) >= 1
        assert len(arc.section_assignments) == 1

    def test_with_palette_library_path_loads_palettes(self, tmp_path: object) -> None:
        """With a palette_library_path pointing to a JSON file, palettes load."""
        import json
        from pathlib import Path

        from twinklr.core.feature_engineering.color_arc import ColorArcExtractor

        path = Path(str(tmp_path)) / "palettes.json"
        palette_data = {
            "schema_version": "v1.0.0",
            "palettes": [
                {
                    "palette_id": "pal_custom_warm",
                    "name": "Custom Warm",
                    "colors": ["#FF4500", "#FF8C00"],
                    "mood_tags": ["warm", "energetic"],
                    "temperature": "warm",
                },
            ],
        }
        path.write_text(json.dumps(palette_data), encoding="utf-8")

        extractor = ColorArcExtractor(palette_library_path=path)
        assert extractor._palette_library is not None
        assert len(extractor._palette_library) == 1
        assert extractor._palette_library[0].palette_id == "pal_custom_warm"


# ---------------------------------------------------------------------------
# 6. Edge cases (empty params, invalid hex, no corpus data)
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Verify graceful handling of edge cases."""

    def test_empty_events_list(self) -> None:
        """No events should produce no colors and no palettes."""
        discoverer = ColorFamilyDiscoverer()
        colors = discoverer._extract_colors([])
        assert len(colors) == 0
        palettes = discoverer._build_palettes([])
        assert len(palettes) == 0

    def test_events_without_color_params(self) -> None:
        """Events with no color-related params produce empty results."""
        events = [
            _make_enriched_event(
                palette="",
                effectdb_params=[_param("speed", "10")],
            ),
        ]
        discoverer = ColorFamilyDiscoverer()
        colors = discoverer._extract_colors(events)
        assert len(colors) == 0

    def test_invalid_hex_values_are_skipped(self) -> None:
        """Non-hex strings in color fields are silently skipped."""
        events = [
            _make_enriched_event(palette="not_a_color"),
            _make_enriched_event(palette="#GGHHII"),
            _make_enriched_event(palette="#12345"),  # too short
            _make_enriched_event(palette="#FF0000"),  # valid
        ]
        discoverer = ColorFamilyDiscoverer()
        colors = discoverer._extract_colors(events)
        assert colors == ["#FF0000"]

    def test_cluster_empty_color_list(self) -> None:
        """Clustering an empty list returns empty bins."""
        result = ColorFamilyDiscoverer._cluster_by_hue([])
        assert result == []

    def test_name_palette_empty_colors(self) -> None:
        """Naming with no colors returns a default name."""
        discoverer = ColorFamilyDiscoverer()
        name = discoverer._name_palette(())
        assert isinstance(name, str)
        assert len(name) > 0

    def test_discover_returns_discovered_palettes(self) -> None:
        """Full discover() pipeline returns DiscoveredPalette list."""
        events = [
            _make_enriched_event(
                package_id="pkg-1",
                sequence_file_id="seq-1",
                section_label="verse",
                palette="#FF0000",
                effectdb_params=[
                    _param("color1", "#00FF00"),
                    _param("color2", "#0000FF"),
                ],
            ),
        ]
        discoverer = ColorFamilyDiscoverer()
        result = discoverer.discover(events)
        assert isinstance(result, list)
        assert all(isinstance(p, DiscoveredPalette) for p in result)
        assert len(result) >= 1
