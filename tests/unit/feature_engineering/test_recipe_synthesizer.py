"""Tests for RecipeSynthesizer (MinedTemplate to EffectRecipe)."""

from __future__ import annotations

from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateKind,
)
from twinklr.core.feature_engineering.recipe_synthesizer import RecipeSynthesizer
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.vocabulary import (
    GroupTemplateType,
    MotionVerb,
)


def _make_mined(
    *,
    effect_family: str = "single_strand",
    motion_class: str = "sweep",
    color_class: str = "palette",
    energy_class: str = "mid",
    continuity_class: str = "rhythmic",
    spatial_class: str = "single_target",
    role: str | None = "rhythm_driver",
    taxonomy_labels: tuple[str, ...] = (),
    template_kind: TemplateKind = TemplateKind.CONTENT,
) -> MinedTemplate:
    sig = f"{effect_family}|{motion_class}|{color_class}|{energy_class}|{continuity_class}|{spatial_class}"
    if role:
        sig += f"|{role}"
    return MinedTemplate(
        template_id="uuid-test-1",
        template_kind=template_kind,
        template_signature=sig,
        support_count=25,
        distinct_pack_count=5,
        support_ratio=0.4,
        cross_pack_stability=0.8,
        onset_sync_mean=0.7,
        role=role,
        taxonomy_labels=taxonomy_labels,
        effect_family=effect_family,
        motion_class=motion_class,
        color_class=color_class,
        energy_class=energy_class,
        continuity_class=continuity_class,
        spatial_class=spatial_class,
    )


def _primary_layer(recipe: EffectRecipe):
    """Return the primary effect layer (skipping wash underlays)."""
    for layer in recipe.layers:
        if layer.layer_name != "Wash":
            return layer
    return recipe.layers[-1]


# ── Existing behaviour (explicit role) ─────────────────────────────────────


def test_synthesize_single_strand_sweep() -> None:
    mined = _make_mined(effect_family="single_strand", motion_class="sweep", role="rhythm_driver")
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="synth_single_strand_sweep_v1")
    assert isinstance(recipe, EffectRecipe)
    assert recipe.recipe_id == "synth_single_strand_sweep_v1"
    assert recipe.template_type == GroupTemplateType.RHYTHM
    primary = _primary_layer(recipe)
    assert primary.effect_type == "SingleStrand"
    assert MotionVerb.SWEEP in primary.motion
    assert recipe.provenance.source == "mined"
    assert "uuid-test-1" in recipe.provenance.mined_template_ids


def test_synthesize_shimmer_pulse() -> None:
    mined = _make_mined(effect_family="shimmer", motion_class="pulse", role="accent_hit")
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="synth_shimmer_pulse_v1")
    assert recipe.template_type == GroupTemplateType.ACCENT
    primary = _primary_layer(recipe)
    assert primary.effect_type == "Shimmer"
    assert MotionVerb.PULSE in primary.motion


def test_synthesize_color_wash_static_base() -> None:
    mined = _make_mined(
        effect_family="color_wash",
        motion_class="static",
        role="base_fill",
        energy_class="low",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="synth_color_wash_static_v1")
    assert recipe.template_type == GroupTemplateType.BASE
    assert recipe.layers[0].effect_type == "ColorWash"


def test_synthesize_preserves_provenance() -> None:
    mined = _make_mined()
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_prov")
    assert recipe.provenance.source == "mined"
    assert recipe.provenance.mined_template_ids == ["uuid-test-1"]


def test_synthesize_maps_color_class_to_palette_spec() -> None:
    mined_mono = _make_mined(color_class="mono")
    recipe_mono = RecipeSynthesizer().synthesize(mined_mono, recipe_id="test_mono")
    assert recipe_mono.palette_spec.mode.value in ("MONOCHROME",)

    mined_palette = _make_mined(color_class="palette")
    recipe_palette = RecipeSynthesizer().synthesize(mined_palette, recipe_id="test_palette")
    assert recipe_palette.palette_spec.mode.value in ("DICHROME", "TRIAD", "ANALOGOUS")


def test_synthesize_maps_energy_class_to_density() -> None:
    mined_low = _make_mined(energy_class="low", role="base_fill")
    recipe_low = RecipeSynthesizer().synthesize(mined_low, recipe_id="test_low")
    primary_low = _primary_layer(recipe_low)
    assert primary_low.density <= 0.4

    mined_high = _make_mined(energy_class="high")
    recipe_high = RecipeSynthesizer().synthesize(mined_high, recipe_id="test_high")
    primary_high = _primary_layer(recipe_high)
    assert primary_high.density >= 0.7


def test_synthesize_unknown_role_defaults_to_rhythm() -> None:
    mined = _make_mined(role=None)
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_no_role")
    assert recipe.template_type == GroupTemplateType.RHYTHM


# ── Bug #1: Taxonomy-label lane inference ──────────────────────────────────


def test_taxonomy_texture_bed_infers_base() -> None:
    """Content template with texture_bed label → BASE lane."""
    mined = _make_mined(
        role=None,
        taxonomy_labels=("texture_bed",),
        energy_class="low",
        continuity_class="sustained",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_base_tax")
    assert recipe.template_type == GroupTemplateType.BASE


def test_taxonomy_accent_hit_infers_accent() -> None:
    """Content template with accent_hit label → ACCENT lane."""
    mined = _make_mined(
        role=None,
        taxonomy_labels=("accent_hit",),
        energy_class="burst",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_accent_tax")
    assert recipe.template_type == GroupTemplateType.ACCENT


def test_taxonomy_rhythm_driver_infers_rhythm() -> None:
    """Content template with rhythm_driver label → RHYTHM lane."""
    mined = _make_mined(
        role=None,
        taxonomy_labels=("rhythm_driver",),
        energy_class="mid",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_rhythm_tax")
    assert recipe.template_type == GroupTemplateType.RHYTHM


def test_energy_heuristic_low_sustained_infers_base() -> None:
    """No role, no taxonomy → low+sustained heuristic → BASE lane."""
    mined = _make_mined(
        role=None,
        taxonomy_labels=(),
        energy_class="low",
        continuity_class="sustained",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_heuristic_base")
    assert recipe.template_type == GroupTemplateType.BASE


def test_energy_heuristic_burst_infers_accent() -> None:
    """No role, no taxonomy → burst heuristic → ACCENT lane."""
    mined = _make_mined(
        role=None,
        taxonomy_labels=(),
        energy_class="burst",
        continuity_class="rhythmic",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_heuristic_accent")
    assert recipe.template_type == GroupTemplateType.ACCENT


# ── Bug #2: Effect family mapping ──────────────────────────────────────────


def test_real_families_all_mapped() -> None:
    """Every effect family from the real corpus has an explicit map entry."""
    from twinklr.core.feature_engineering.recipe_synthesizer import _EFFECT_TYPE_MAP

    real_families = [
        "bars", "butterfly", "candle", "circles", "color_wash", "curtain",
        "dmx", "faces", "fan", "fill", "fire", "fireworks", "galaxy",
        "garlands", "kaleidoscope", "lightning", "lines", "liquid", "marquee",
        "meteors", "morph", "moving_head", "off", "on", "pictures", "pinwheel",
        "plasma", "ripple", "shader", "shape", "shimmer", "shockwave",
        "single_strand", "sketch", "snow_storm", "snowflakes", "spirals",
        "spirograph", "state", "strobe", "tendrils", "text", "tree", "twinkle",
        "video", "vu_meter", "warp", "wave",
    ]
    for family in real_families:
        assert family in _EFFECT_TYPE_MAP, f"{family} missing from _EFFECT_TYPE_MAP"


# ── Bug #3: Multi-layer synthesis ──────────────────────────────────────────


def test_rhythm_recipe_has_wash_underlay() -> None:
    """RHYTHM recipes get a ColorWash background + primary effect."""
    mined = _make_mined(role="rhythm_driver", energy_class="mid")
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_layers")
    assert len(recipe.layers) >= 2
    assert recipe.layers[0].effect_type == "ColorWash"
    assert recipe.layers[0].layer_name == "Wash"
    assert recipe.layers[1].effect_type == "SingleStrand"


def test_base_recipe_is_single_layer() -> None:
    """BASE recipes stay single-layer (ambient effects)."""
    mined = _make_mined(role="base_fill", energy_class="low")
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_base_layers")
    assert len(recipe.layers) == 1


def test_high_energy_gets_sparkle_overlay() -> None:
    """High-energy non-sparkle recipes get a 3rd sparkle layer."""
    mined = _make_mined(role="rhythm_driver", energy_class="high", effect_family="bars")
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_sparkle")
    assert len(recipe.layers) == 3
    assert recipe.layers[2].layer_name == "Sparkle"
    assert recipe.layers[2].effect_type == "Twinkle"


def test_sparkle_family_skips_overlay() -> None:
    """Sparkle-type families don't get a redundant sparkle overlay."""
    mined = _make_mined(role="rhythm_driver", energy_class="high", effect_family="twinkle")
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_no_dupe")
    sparkle_layers = [ly for ly in recipe.layers if ly.layer_name == "Sparkle"]
    assert len(sparkle_layers) == 0


def test_style_markers_populated() -> None:
    """Synthesized recipes include StyleMarkers with complexity and energy."""
    mined = _make_mined(energy_class="high", effect_family="bars")
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_markers")
    assert recipe.style_markers is not None
    assert recipe.style_markers.complexity > 0
    assert recipe.style_markers.energy_affinity is not None


# ── Issue A: Wash-like families skip underlay ──────────────────────────────


def test_color_wash_rhythm_skips_underlay() -> None:
    """ColorWash in RHYTHM lane should NOT get a redundant wash underlay."""
    mined = _make_mined(
        effect_family="color_wash", motion_class="fade",
        role="rhythm_driver", energy_class="mid",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_wash_no_underlay")
    assert recipe.layers[0].effect_type == "ColorWash"
    assert recipe.layers[0].layer_name != "Wash"
    assert len(recipe.layers) == 1


def test_fill_accent_skips_underlay() -> None:
    """Fill in ACCENT lane should NOT get a redundant wash underlay."""
    mined = _make_mined(
        effect_family="fill", motion_class="static",
        role="accent_hit", energy_class="mid",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_fill_no_underlay")
    assert recipe.layers[0].effect_type == "Fill"
    assert recipe.layers[0].layer_name != "Wash"


def test_on_rhythm_skips_underlay() -> None:
    """On in RHYTHM lane should NOT get a wash underlay."""
    mined = _make_mined(
        effect_family="on", motion_class="static",
        role="rhythm_driver", energy_class="mid",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_on_no_underlay")
    assert recipe.layers[0].layer_name != "Wash"


# ── Issue B: Non-visual families skip all layering ─────────────────────────


def test_off_effect_single_layer() -> None:
    """Off effect should be a single layer regardless of lane or energy."""
    mined = _make_mined(
        effect_family="off", motion_class="static",
        role="accent_hit", energy_class="burst",
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_off_single")
    assert len(recipe.layers) == 1
    assert recipe.layers[0].effect_type == "Off"
    wash_layers = [ly for ly in recipe.layers if ly.layer_name == "Wash"]
    sparkle_layers = [ly for ly in recipe.layers if ly.layer_name == "Sparkle"]
    assert len(wash_layers) == 0
    assert len(sparkle_layers) == 0
