"""Tests for recipe_builder enrichment module."""

from __future__ import annotations

from twinklr.core.recipe_builder.enrichment import generate_enrichments
from twinklr.core.recipe_builder.models import MetadataEnrichmentCandidate
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    VisualDepth,
)


def test_generate_enrichments_returns_list(sample_recipes):
    candidates = generate_enrichments(sample_recipes)
    assert isinstance(candidates, list)


def test_generate_enrichments_returns_candidates(sample_recipes):
    candidates = generate_enrichments(sample_recipes)
    for c in candidates:
        assert isinstance(c, MetadataEnrichmentCandidate)


def test_generate_enrichments_candidate_id_format(sample_recipes):
    candidates = generate_enrichments(sample_recipes)
    for c in candidates:
        assert c.candidate_id.startswith("enr_")


def test_generate_enrichments_no_structural_fields(sample_recipes):
    structural = {
        "layers", "palette_spec", "timing", "template_type",
        "visual_intent", "recipe_version", "recipe_id",
    }
    candidates = generate_enrichments(sample_recipes)
    for c in candidates:
        for field in structural:
            assert field not in c.proposed_metadata_patch


def test_generate_enrichments_empty_list():
    candidates = generate_enrichments([])
    assert candidates == []


def test_generate_enrichments_fixes_unknown_family():
    """Recipe with unknown effect_family gets a family patch."""
    layer = RecipeLayer(
        layer_index=0,
        layer_name="bg",
        layer_depth=VisualDepth.BACKGROUND,
        effect_type="Fire",
        blend_mode=BlendMode.NORMAL,
        mix=1.0,
        density=0.5,
    )
    recipe = EffectRecipe(
        recipe_id="unknown_family_recipe",
        name="Unknown Family",
        description="A recipe with unknown effect family for testing enrichment",
        recipe_version="1.0.0",
        effect_family="unknown",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["test"],
        timing=TimingHints(bars_min=4, bars_max=16),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(layer,),
        provenance=RecipeProvenance(source="generated"),
        style_markers=StyleMarkers(complexity=0.5, energy_affinity=EnergyTarget.MED),
    )
    candidates = generate_enrichments([recipe])
    assert len(candidates) > 0
    patch = candidates[0].proposed_metadata_patch
    assert patch.get("effect_family") == "fire"


def test_generate_enrichments_adds_missing_tags():
    """Recipe with no tags gets tags from its metadata."""
    layer = RecipeLayer(
        layer_index=0,
        layer_name="bg",
        layer_depth=VisualDepth.BACKGROUND,
        effect_type="Twinkle",
        blend_mode=BlendMode.NORMAL,
        mix=1.0,
        density=0.5,
    )
    recipe = EffectRecipe(
        recipe_id="no_tags_recipe",
        name="No Tags",
        description="A recipe without any tags for testing enrichment patches",
        recipe_version="1.0.0",
        effect_family="twinkle",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=[],
        timing=TimingHints(bars_min=4, bars_max=16),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(layer,),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.3, energy_affinity=EnergyTarget.LOW),
    )
    candidates = generate_enrichments([recipe])
    tag_candidates = [c for c in candidates if "tags" in c.proposed_metadata_patch]
    assert len(tag_candidates) > 0
    tags = tag_candidates[0].proposed_metadata_patch["tags"]
    assert "twinkle" in tags
    assert "low" in tags
