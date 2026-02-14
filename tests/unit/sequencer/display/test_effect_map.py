"""Unit tests for template → effect type mapping."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.templates.effect_map import (
    EffectMapping,
    filter_valid_overrides,
    resolve_effect_type,
)


class TestResolveEffectType:
    """Tests for the resolve_effect_type function."""

    # Explicit map entries
    def test_explicit_base_wash(self) -> None:
        m = resolve_effect_type("gtpl_base_motif_abstract_ambient")
        assert m.effect_type == "Color Wash"

    def test_explicit_rhythm_chase(self) -> None:
        m = resolve_effect_type("gtpl_rhythm_alternate_ab")
        assert m.effect_type == "SingleStrand"

    def test_explicit_accent_burst(self) -> None:
        m = resolve_effect_type("gtpl_accent_burst_big")
        assert m.effect_type == "Shockwave"

    def test_explicit_spirals(self) -> None:
        m = resolve_effect_type("gtpl_base_motif_candy_stripes_ambient")
        assert m.effect_type == "Spirals"

    def test_explicit_snowflakes(self) -> None:
        m = resolve_effect_type("gtpl_base_snow_haze_low")
        assert m.effect_type == "Snowflakes"

    def test_explicit_meteors(self) -> None:
        m = resolve_effect_type("gtpl_accent_spark_shower_up")
        assert m.effect_type == "Meteors"

    # Keyword heuristic matches
    def test_keyword_chase(self) -> None:
        m = resolve_effect_type("gtpl_rhythm_chase_bounce")
        assert m.effect_type == "SingleStrand"

    def test_keyword_wash(self) -> None:
        m = resolve_effect_type("gtpl_base_wash_soft")
        assert m.effect_type == "Color Wash"

    def test_keyword_snow(self) -> None:
        m = resolve_effect_type("gtpl_base_snow_blizzard")
        assert m.effect_type == "Snowflakes"

    def test_keyword_sparkle(self) -> None:
        m = resolve_effect_type("gtpl_rhythm_sparkle_fast")
        assert m.effect_type == "Twinkle"

    def test_keyword_spiral(self) -> None:
        m = resolve_effect_type("gtpl_rhythm_spiral_double")
        assert m.effect_type == "Spirals"

    def test_keyword_fan(self) -> None:
        m = resolve_effect_type("gtpl_accent_fan_wide")
        assert m.effect_type == "Fan"

    def test_keyword_hit_fallback(self) -> None:
        m = resolve_effect_type("gtpl_accent_hit_color")
        assert m.effect_type == "On"

    # Fallback
    def test_unknown_template_fallback(self) -> None:
        m = resolve_effect_type("gtpl_unknown_thing_xyz")
        assert m.effect_type == "On"

    def test_completely_unknown(self) -> None:
        m = resolve_effect_type("something_random")
        assert m.effect_type == "On"


class TestEffectParameterDefaults:
    """Tests that template mappings provide non-empty, lane-appropriate defaults."""

    # -- Explicit map templates should have non-empty defaults ---------

    def test_explicit_templates_have_defaults(self) -> None:
        """All templates in the explicit map must carry defaults."""
        from twinklr.core.sequencer.display.templates.effect_map import _EXPLICIT_MAP

        for template_id, mapping in _EXPLICIT_MAP.items():
            assert mapping.defaults, (
                f"Template '{template_id}' has empty defaults — "
                f"add a preset profile for effect_type='{mapping.effect_type}'"
            )

    # -- Ambient vs drive vs hit must produce different parameters -----

    def test_spirals_ambient_vs_drive_differ(self) -> None:
        """Ambient spirals should be slower than drive spirals."""
        ambient = resolve_effect_type("gtpl_base_motif_candy_stripes_ambient")
        drive = resolve_effect_type("gtpl_rhythm_motif_candy_stripes_drive")

        assert ambient.effect_type == "Spirals"
        assert drive.effect_type == "Spirals"
        # Drive should have faster movement
        assert drive.defaults["movement"] > ambient.defaults["movement"]

    def test_color_wash_ambient_vs_drive_differ(self) -> None:
        """Drive washes should be faster than ambient."""
        ambient = resolve_effect_type("gtpl_base_motif_abstract_ambient")
        drive = resolve_effect_type("gtpl_rhythm_motif_abstract_drive")

        assert ambient.effect_type == "Color Wash"
        assert drive.effect_type == "Color Wash"
        assert drive.defaults["speed"] > ambient.defaults["speed"]

    def test_twinkle_ambient_vs_drive_differ(self) -> None:
        """Drive twinkle should have more density than ambient."""
        ambient = resolve_effect_type("gtpl_base_motif_sparkles_ambient")
        drive = resolve_effect_type("gtpl_rhythm_motif_sparkles_drive")

        assert ambient.effect_type == "Twinkle"
        assert drive.effect_type == "Twinkle"
        assert drive.defaults["count"] > ambient.defaults["count"]

    def test_fan_ambient_vs_hit_differ(self) -> None:
        """Hit fan should spin faster than ambient fan."""
        ambient = resolve_effect_type("gtpl_base_motif_radial_rays_ambient")
        hit_big = resolve_effect_type("gtpl_accent_motif_radial_rays_hit_big")

        assert ambient.effect_type == "Fan"
        assert hit_big.effect_type == "Fan"
        assert hit_big.defaults["revolutions"] > ambient.defaults["revolutions"]

    def test_shockwave_big_vs_small(self) -> None:
        """Big burst should have wider ring than small."""
        small = resolve_effect_type("gtpl_accent_burst_small")
        big = resolve_effect_type("gtpl_accent_burst_big")

        assert small.effect_type == "Shockwave"
        assert big.effect_type == "Shockwave"
        assert big.defaults["start_width"] > small.defaults["start_width"]

    def test_strobe_big_vs_small(self) -> None:
        """Big sparkle hit should have more strobes."""
        small = resolve_effect_type("gtpl_accent_motif_sparkles_hit_small")
        big = resolve_effect_type("gtpl_accent_motif_sparkles_hit_big")

        assert small.effect_type == "Strobe"
        assert big.effect_type == "Strobe"
        assert big.defaults["num_strobes"] > small.defaults["num_strobes"]

    def test_meteors_ambient_vs_hit(self) -> None:
        """Accent meteors should be faster than ambient."""
        accent = resolve_effect_type("gtpl_accent_spark_shower_up")
        assert accent.effect_type == "Meteors"
        assert accent.defaults["speed"] >= 20
        assert accent.defaults["direction"] == "Up"

    # -- Keyword resolution should also provide energy-aware defaults ---

    @pytest.mark.parametrize(
        ("template_id", "expected_type"),
        [
            ("gtpl_base_wash_soft", "Color Wash"),
            ("gtpl_rhythm_sparkle_fast", "Twinkle"),
            ("gtpl_accent_fan_wide", "Fan"),
        ],
    )
    def test_keyword_resolved_templates_have_defaults(
        self, template_id: str, expected_type: str
    ) -> None:
        """Keyword-resolved templates should also get lane-aware defaults."""
        m = resolve_effect_type(template_id)
        assert m.effect_type == expected_type
        assert m.defaults, (
            f"Keyword-resolved '{template_id}' has empty defaults"
        )

    # -- Rudolph plan coverage -----------------------------------------

    RUDOLPH_TEMPLATES = [
        "gtpl_base_motif_abstract_ambient",
        "gtpl_base_motif_bokeh_ambient",
        "gtpl_base_motif_sparkles_ambient",
        "gtpl_base_motif_radial_rays_ambient",
        "gtpl_rhythm_motif_candy_stripes_drive",
        "gtpl_rhythm_motif_sparkles_drive",
        "gtpl_rhythm_motif_abstract_drive",
        "gtpl_rhythm_sparkle_offbeat",
        "gtpl_accent_bell_single",
        "gtpl_accent_bell_double",
        "gtpl_accent_burst_small",
        "gtpl_accent_burst_big",
        "gtpl_accent_motif_sparkles_hit_small",
        "gtpl_accent_motif_sparkles_hit_big",
        "gtpl_accent_motif_radial_rays_hit_small",
        "gtpl_accent_motif_radial_rays_hit_big",
        "gtpl_accent_motif_candy_stripes_hit_small",
        "gtpl_accent_motif_candy_stripes_hit_big",
        "gtpl_accent_spark_shower_up",
    ]

    @pytest.mark.parametrize("template_id", RUDOLPH_TEMPLATES)
    def test_rudolph_plan_templates_have_defaults(self, template_id: str) -> None:
        """Every template used in the Rudolph plan must have parameter defaults."""
        m = resolve_effect_type(template_id)
        assert m.defaults, (
            f"Rudolph template '{template_id}' ({m.effect_type}) has no defaults"
        )


class TestFilterValidOverrides:
    """Tests that planning-level param_overrides are filtered out."""

    def test_planning_params_dropped(self) -> None:
        """LLM planning keys should be filtered out completely."""
        overrides = {
            "motif_bias": ["motif.radial_rays"],
            "beacon_color": "red",
            "decay": "fast",
            "feel": "rewind_chase_then_hold",
            "name_call_style": "distinct_color_pop",
        }
        result = filter_valid_overrides("Meteors", overrides)
        assert result == {}

    def test_valid_handler_keys_kept(self) -> None:
        """Handler-recognized keys should pass through."""
        overrides = {"count": 20, "speed": 30, "direction": "Up"}
        result = filter_valid_overrides("Meteors", overrides)
        assert result == {"count": 20, "speed": 30, "direction": "Up"}

    def test_mixed_valid_and_invalid(self) -> None:
        """Only valid keys survive when mixed with planning params."""
        overrides = {
            "count": 25,
            "motif_bias": "sparkles",
            "speed": 15,
            "beacon_color": "red",
        }
        result = filter_valid_overrides("Meteors", overrides)
        assert result == {"count": 25, "speed": 15}

    def test_on_effect_drops_everything(self) -> None:
        """On effect has no valid override keys — everything filtered."""
        overrides = {"decay": "fast", "sparkle_amount": "low"}
        result = filter_valid_overrides("On", overrides)
        assert result == {}

    def test_empty_overrides_returns_empty(self) -> None:
        """Empty overrides produce empty result."""
        result = filter_valid_overrides("Spirals", {})
        assert result == {}

    def test_unknown_effect_type_returns_empty(self) -> None:
        """Unknown effect type drops all overrides safely."""
        overrides = {"speed": 10}
        result = filter_valid_overrides("UnknownEffect", overrides)
        assert result == {}

    def test_spirals_valid_keys(self) -> None:
        """Spirals handler keys pass through."""
        overrides = {
            "palette_count": 5,
            "movement": 3.0,
            "rotation_speed": "slow",  # planning key, not handler key
        }
        result = filter_valid_overrides("Spirals", overrides)
        assert result == {"palette_count": 5, "movement": 3.0}

    def test_color_wash_valid_keys(self) -> None:
        """Color Wash handler keys pass through."""
        overrides = {
            "speed": 80,
            "shimmer": True,
            "density": 0.35,  # planning key
            "blur": 0.6,  # planning key
        }
        result = filter_valid_overrides("Color Wash", overrides)
        assert result == {"speed": 80, "shimmer": True}

    # -- Value validation tests ----------------------------------------

    def test_string_speed_rejected(self) -> None:
        """String value for numeric 'speed' key should be rejected."""
        overrides = {"speed": "fast", "count": 20}
        result = filter_valid_overrides("Meteors", overrides)
        assert result == {"count": 20}

    def test_normalized_float_speed_rejected(self) -> None:
        """Normalized 0-1 float for 'speed' should be rejected."""
        overrides = {"speed": 0.55, "count": 15}
        result = filter_valid_overrides("Meteors", overrides)
        assert result == {"count": 15}

    def test_valid_integer_speed_accepted(self) -> None:
        """Integer speed value in valid range should pass."""
        overrides = {"speed": 25}
        result = filter_valid_overrides("Meteors", overrides)
        assert result == {"speed": 25}

    def test_invalid_direction_rejected(self) -> None:
        """Planning direction value 'forward' should be rejected."""
        overrides = {"direction": "forward", "count": 10}
        result = filter_valid_overrides("Meteors", overrides)
        assert result == {"count": 10}

    def test_valid_direction_accepted(self) -> None:
        """Valid xLights direction 'Up' should pass."""
        overrides = {"direction": "Up"}
        result = filter_valid_overrides("Meteors", overrides)
        assert result == {"direction": "Up"}

    def test_boolean_rejects_string(self) -> None:
        """Boolean params should reject string values."""
        overrides = {"shimmer": "low", "speed": 50}
        result = filter_valid_overrides("Color Wash", overrides)
        assert result == {"speed": 50}

    def test_float_above_one_accepted(self) -> None:
        """Float values > 1.0 are valid xLights params (e.g., cycles)."""
        overrides = {"cycles": 2.5}
        result = filter_valid_overrides("Color Wash", overrides)
        assert result == {"cycles": 2.5}

    # -- Ripple/Fire/Pinwheel override tests ------------------------------

    def test_ripple_valid_keys(self) -> None:
        """Ripple handler keys pass through, planning keys dropped."""
        overrides = {
            "object_to_draw": "Star",
            "thickness": 30,
            "feel": "smooth",  # planning key
        }
        result = filter_valid_overrides("Ripple", overrides)
        assert result == {"object_to_draw": "Star", "thickness": 30}

    def test_ripple_invalid_movement_rejected(self) -> None:
        """Invalid Ripple movement value rejected."""
        overrides = {"movement": "Outward"}
        result = filter_valid_overrides("Ripple", overrides)
        assert result == {}

    def test_ripple_valid_movement_accepted(self) -> None:
        """Valid Ripple movement values accepted."""
        overrides = {"movement": "Implode"}
        result = filter_valid_overrides("Ripple", overrides)
        assert result == {"movement": "Implode"}

    def test_fire_valid_keys(self) -> None:
        """Fire handler keys pass through."""
        overrides = {
            "height": 80,
            "grow_with_music": True,
            "energy": "high",  # planning key
        }
        result = filter_valid_overrides("Fire", overrides)
        assert result == {"height": 80, "grow_with_music": True}

    def test_fire_invalid_location_rejected(self) -> None:
        """Invalid Fire location value rejected."""
        overrides = {"location": "Center"}
        result = filter_valid_overrides("Fire", overrides)
        assert result == {}

    def test_pinwheel_valid_keys(self) -> None:
        """Pinwheel handler keys pass through."""
        overrides = {
            "arms": 6,
            "twist": 120,
            "clockwise": True,
            "density": 0.5,  # planning key
        }
        result = filter_valid_overrides("Pinwheel", overrides)
        assert result == {"arms": 6, "twist": 120, "clockwise": True}

    def test_pinwheel_3d_choice_accepted(self) -> None:
        """Pinwheel 3d is a choice (not boolean), valid values accepted."""
        overrides = {"3d": "3D"}
        result = filter_valid_overrides("Pinwheel", overrides)
        assert result == {"3d": "3D"}

    def test_pinwheel_3d_invalid_rejected(self) -> None:
        """Pinwheel 3d rejects invalid string values."""
        overrides = {"3d": "flat"}
        result = filter_valid_overrides("Pinwheel", overrides)
        assert result == {}
