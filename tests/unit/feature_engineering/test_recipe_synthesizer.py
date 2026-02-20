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
        effect_family=effect_family,
        motion_class=motion_class,
        color_class=color_class,
        energy_class=energy_class,
        continuity_class=continuity_class,
        spatial_class=spatial_class,
    )


def test_synthesize_single_strand_sweep() -> None:
    mined = _make_mined(effect_family="single_strand", motion_class="sweep", role="rhythm_driver")
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="synth_single_strand_sweep_v1")
    assert isinstance(recipe, EffectRecipe)
    assert recipe.recipe_id == "synth_single_strand_sweep_v1"
    assert recipe.template_type == GroupTemplateType.RHYTHM
    assert recipe.layers[0].effect_type == "SingleStrand"
    assert MotionVerb.SWEEP in recipe.layers[0].motion
    assert recipe.provenance.source == "mined"
    assert "uuid-test-1" in recipe.provenance.mined_template_ids


def test_synthesize_shimmer_pulse() -> None:
    mined = _make_mined(effect_family="shimmer", motion_class="pulse", role="accent_hit")
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="synth_shimmer_pulse_v1")
    assert recipe.template_type == GroupTemplateType.ACCENT
    assert recipe.layers[0].effect_type == "Shimmer"
    assert MotionVerb.PULSE in recipe.layers[0].motion


def test_synthesize_color_wash_static_base() -> None:
    mined = _make_mined(
        effect_family="color_wash", motion_class="static", role="base_fill",
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
    mined_low = _make_mined(energy_class="low")
    recipe_low = RecipeSynthesizer().synthesize(mined_low, recipe_id="test_low")
    assert recipe_low.layers[0].density <= 0.4

    mined_high = _make_mined(energy_class="high")
    recipe_high = RecipeSynthesizer().synthesize(mined_high, recipe_id="test_high")
    assert recipe_high.layers[0].density >= 0.7


def test_synthesize_unknown_role_defaults_to_rhythm() -> None:
    mined = _make_mined(role=None)
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="test_no_role")
    assert recipe.template_type == GroupTemplateType.RHYTHM
