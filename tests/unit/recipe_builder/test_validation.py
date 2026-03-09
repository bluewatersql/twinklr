"""Tests for recipe_builder validation module."""

from __future__ import annotations

from twinklr.core.recipe_builder.models import (
    MetadataEnrichmentCandidate,
    RecipeCandidate,
)
from twinklr.core.recipe_builder.validation import (
    validate_all,
    validate_metadata_candidate,
    validate_recipe_candidate,
)
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


def _make_recipe_candidate(recipe_id: str = "new_recipe_v1") -> RecipeCandidate:
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
        recipe_id=recipe_id,
        name="New Recipe",
        description="A valid new recipe for testing",
        recipe_version="1.0.0",
        effect_family="twinkle",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["twinkle"],
        timing=TimingHints(bars_min=4, bars_max=16),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(layer,),
        provenance=RecipeProvenance(source="generated"),
        style_markers=StyleMarkers(complexity=0.5, energy_affinity=EnergyTarget.MED),
    )
    return RecipeCandidate(
        candidate_id="cand_test_001",
        source_opportunity_id="opp_test",
        recipe=recipe,
    )


def _make_metadata_candidate(
    target_recipe_id: str = "test_twinkle_v1",
    patch: dict | None = None,
) -> MetadataEnrichmentCandidate:
    return MetadataEnrichmentCandidate(
        candidate_id="enr_test_001",
        target_recipe_id=target_recipe_id,
        proposed_metadata_patch={"tags": ["test"]} if patch is None else patch,
    )


# --- RecipeCandidate validation ---


def test_validate_recipe_candidate_passes(sample_recipe):
    candidate = _make_recipe_candidate()
    result = validate_recipe_candidate(candidate, [sample_recipe])
    assert result.passed
    assert result.candidate_id == candidate.candidate_id


def test_validate_recipe_candidate_duplicate_id(sample_recipe):
    candidate = _make_recipe_candidate(recipe_id=sample_recipe.recipe_id)
    result = validate_recipe_candidate(candidate, [sample_recipe])
    assert not result.passed
    error_checks = [i.check_name for i in result.issues if i.severity == "error"]
    assert "duplicate_check" in error_checks


def test_validate_recipe_candidate_unknown_effect_type(sample_recipe):
    layer = RecipeLayer(
        layer_index=0,
        layer_name="bg",
        layer_depth=VisualDepth.BACKGROUND,
        effect_type="WeirdEffectXYZ",
        blend_mode=BlendMode.NORMAL,
        mix=1.0,
        density=0.5,
    )
    recipe = EffectRecipe(
        recipe_id="weird_recipe_v1",
        name="Weird",
        description="Uses unknown effect",
        recipe_version="1.0.0",
        effect_family="weird",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["weird"],
        timing=TimingHints(bars_min=4, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(layer,),
        provenance=RecipeProvenance(source="generated"),
        style_markers=StyleMarkers(complexity=0.5, energy_affinity=EnergyTarget.MED),
    )
    candidate = RecipeCandidate(
        candidate_id="cand_weird",
        source_opportunity_id="opp_test",
        recipe=recipe,
    )
    result = validate_recipe_candidate(candidate, [sample_recipe])
    warning_checks = [i.check_name for i in result.issues if i.severity == "warning"]
    assert "effect_handler_compatibility" in warning_checks


def test_validate_recipe_candidate_missing_tags_warning(sample_recipe):
    layer = RecipeLayer(
        layer_index=0,
        layer_name="bg",
        layer_depth=VisualDepth.BACKGROUND,
        effect_type="On",
        blend_mode=BlendMode.NORMAL,
        mix=1.0,
        density=0.5,
    )
    recipe = EffectRecipe(
        recipe_id="no_tags_recipe_v1",
        name="No Tags",
        description="Recipe without tags",
        recipe_version="1.0.0",
        effect_family="test",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=[],
        timing=TimingHints(bars_min=4, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(layer,),
        provenance=RecipeProvenance(source="generated"),
        style_markers=StyleMarkers(complexity=0.5, energy_affinity=EnergyTarget.MED),
    )
    candidate = RecipeCandidate(
        candidate_id="cand_notags",
        source_opportunity_id="opp_test",
        recipe=recipe,
    )
    result = validate_recipe_candidate(candidate, [sample_recipe])
    warning_checks = [i.check_name for i in result.issues if i.severity == "warning"]
    assert "metadata_completeness" in warning_checks


# --- MetadataEnrichmentCandidate validation ---


def test_validate_metadata_candidate_passes(sample_recipe):
    candidate = _make_metadata_candidate(target_recipe_id=sample_recipe.recipe_id)
    result = validate_metadata_candidate(candidate, [sample_recipe])
    assert result.passed


def test_validate_metadata_candidate_missing_target(sample_recipe):
    candidate = _make_metadata_candidate(target_recipe_id="nonexistent_recipe")
    result = validate_metadata_candidate(candidate, [sample_recipe])
    assert not result.passed
    error_checks = [i.check_name for i in result.issues if i.severity == "error"]
    assert "target_exists" in error_checks


def test_validate_metadata_candidate_structural_field(sample_recipe):
    candidate = _make_metadata_candidate(
        target_recipe_id=sample_recipe.recipe_id,
        patch={"layers": [], "tags": ["ok"]},
    )
    result = validate_metadata_candidate(candidate, [sample_recipe])
    assert not result.passed
    error_checks = [i.check_name for i in result.issues if i.severity == "error"]
    assert "patch_structural_fields" in error_checks


def test_validate_metadata_candidate_empty_patch(sample_recipe):
    candidate = _make_metadata_candidate(
        target_recipe_id=sample_recipe.recipe_id,
        patch={},
    )
    result = validate_metadata_candidate(candidate, [sample_recipe])
    assert not result.passed
    error_checks = [i.check_name for i in result.issues if i.severity == "error"]
    assert "patch_not_empty" in error_checks


# --- validate_all ---


def test_validate_all_returns_report(sample_recipe):
    recipe_candidate = _make_recipe_candidate()
    metadata_candidate = _make_metadata_candidate(
        target_recipe_id=sample_recipe.recipe_id,
    )
    report = validate_all([recipe_candidate], [metadata_candidate], [sample_recipe])
    assert len(report.recipe_candidate_results) == 1
    assert len(report.metadata_candidate_results) == 1


def test_validate_all_issue_counts(sample_recipe):
    recipe_candidate = _make_recipe_candidate()
    report = validate_all([recipe_candidate], [], [sample_recipe])
    assert "error" in report.issue_counts
    assert "warning" in report.issue_counts
    assert "info" in report.issue_counts
