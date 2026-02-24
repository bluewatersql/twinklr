"""Tests for MotifAnnotator (recipe - motif compatibility scoring)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from twinklr.core.feature_engineering.models.motifs import (
    MinedMotif,
    MotifCatalog,
    MotifOccurrence,
)
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateKind,
)
from twinklr.core.feature_engineering.motif_annotator import MotifAnnotator
from twinklr.core.feature_engineering.recipe_synthesizer import RecipeSynthesizer

if TYPE_CHECKING:
    from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


def _make_recipe(*, recipe_id: str, template_ids: list[str]) -> EffectRecipe:
    """Build a minimal synthesized recipe."""
    mined = MinedTemplate(
        template_id=template_ids[0],
        template_kind=TemplateKind.CONTENT,
        template_signature="bars|sweep|palette|mid|rhythmic|single_target",
        support_count=25,
        distinct_pack_count=5,
        support_ratio=0.4,
        cross_pack_stability=0.8,
        onset_sync_mean=0.7,
        role="rhythm_driver",
        effect_family="bars",
        motion_class="sweep",
        color_class="palette",
        energy_class="mid",
        continuity_class="rhythmic",
        spatial_class="single_target",
    )
    return RecipeSynthesizer().synthesize(mined, recipe_id=recipe_id)


def _make_source_map(recipe_id: str, template_ids: list[str]) -> dict[str, list[str]]:
    """Build source_template_map for a single recipe."""
    return {recipe_id: template_ids}


def _make_motif(
    *,
    motif_id: str,
    template_ids: tuple[str, ...],
    support_count: int = 10,
) -> MinedMotif:
    return MinedMotif(
        motif_id=motif_id,
        motif_signature=f"span=4|{motif_id}_sig",
        bar_span=4,
        support_count=support_count,
        distinct_pack_count=3,
        distinct_sequence_count=5,
        template_ids=template_ids,
        taxonomy_labels=(),
        occurrences=(
            MotifOccurrence(
                package_id="pkg1",
                sequence_file_id="seq1",
                start_bar_index=0,
                end_bar_index=4,
                start_ms=0,
                end_ms=8000,
                phrase_count=3,
            ),
        ),
    )


def _make_catalog(motifs: list[MinedMotif]) -> MotifCatalog:
    return MotifCatalog(
        schema_version="v2.0.0",
        miner_version="motif_miner_v1",
        total_sequences=10,
        total_motifs=len(motifs),
        min_support_count=2,
        min_distinct_pack_count=1,
        min_distinct_sequence_count=2,
        motifs=tuple(motifs),
    )


# -- Basic scoring --


def test_single_template_exact_match() -> None:
    """Recipe built from template_A scores against motif containing template_A."""
    recipe = _make_recipe(recipe_id="r1", template_ids=["tpl_A"])
    motif = _make_motif(motif_id="m1", template_ids=("tpl_A", "tpl_B"))
    catalog = _make_catalog([motif])
    src_map = _make_source_map("r1", ["tpl_A"])

    annotated = MotifAnnotator().annotate([recipe], catalog, source_template_map=src_map)
    assert len(annotated) == 1
    assert len(annotated[0].motif_compatibility) == 1
    mc = annotated[0].motif_compatibility[0]
    assert mc.motif_id == "m1"
    assert mc.score > 0.0
    assert mc.score <= 1.0


def test_no_overlap_produces_no_compatibility() -> None:
    """Recipe with no template overlap gets no motif entries."""
    recipe = _make_recipe(recipe_id="r1", template_ids=["tpl_X"])
    motif = _make_motif(motif_id="m1", template_ids=("tpl_A", "tpl_B"))
    catalog = _make_catalog([motif])
    src_map = _make_source_map("r1", ["tpl_X"])

    annotated = MotifAnnotator().annotate([recipe], catalog, source_template_map=src_map)
    assert len(annotated[0].motif_compatibility) == 0


def test_full_overlap_scores_higher_than_partial() -> None:
    """Full template overlap (2/2) scores higher than partial (1/2)."""
    recipe_full = _make_recipe(recipe_id="r_full", template_ids=["tpl_A", "tpl_B"])
    recipe_partial = _make_recipe(recipe_id="r_partial", template_ids=["tpl_A"])
    motif = _make_motif(motif_id="m1", template_ids=("tpl_A", "tpl_B"))
    catalog = _make_catalog([motif])
    src_map = {"r_full": ["tpl_A", "tpl_B"], "r_partial": ["tpl_A"]}

    annotated = MotifAnnotator().annotate(
        [recipe_full, recipe_partial], catalog, source_template_map=src_map
    )
    full_score = annotated[0].motif_compatibility[0].score
    partial_score = annotated[1].motif_compatibility[0].score
    assert full_score > partial_score


def test_multiple_motifs_matched() -> None:
    """Recipe can match multiple motifs."""
    recipe = _make_recipe(recipe_id="r1", template_ids=["tpl_A"])
    m1 = _make_motif(motif_id="m1", template_ids=("tpl_A", "tpl_B"))
    m2 = _make_motif(motif_id="m2", template_ids=("tpl_A", "tpl_C", "tpl_D"))
    catalog = _make_catalog([m1, m2])
    src_map = _make_source_map("r1", ["tpl_A"])

    annotated = MotifAnnotator().annotate([recipe], catalog, source_template_map=src_map)
    assert len(annotated[0].motif_compatibility) == 2
    motif_ids = {mc.motif_id for mc in annotated[0].motif_compatibility}
    assert motif_ids == {"m1", "m2"}


def test_empty_catalog_returns_unmodified() -> None:
    """Empty motif catalog leaves recipes unchanged."""
    recipe = _make_recipe(recipe_id="r1", template_ids=["tpl_A"])
    catalog = _make_catalog([])

    annotated = MotifAnnotator().annotate([recipe], catalog)
    assert len(annotated[0].motif_compatibility) == 0


def test_preserves_existing_compatibility() -> None:
    """Pre-existing motif_compatibility entries are preserved."""
    from twinklr.core.sequencer.templates.group.recipe import MotifCompatibility

    recipe = _make_recipe(recipe_id="r1", template_ids=["tpl_A"])
    recipe = recipe.model_copy(
        update={
            "motif_compatibility": [
                MotifCompatibility(motif_id="builtin_m", score=0.9, reason="Builtin"),
            ],
        },
    )
    motif = _make_motif(motif_id="m1", template_ids=("tpl_A",))
    catalog = _make_catalog([motif])
    src_map = _make_source_map("r1", ["tpl_A"])

    annotated = MotifAnnotator().annotate([recipe], catalog, source_template_map=src_map)
    motif_ids = {mc.motif_id for mc in annotated[0].motif_compatibility}
    assert "builtin_m" in motif_ids
    assert "m1" in motif_ids


def test_reason_includes_overlap_info() -> None:
    """Reason string describes the template overlap."""
    recipe = _make_recipe(recipe_id="r1", template_ids=["tpl_A", "tpl_B"])
    motif = _make_motif(motif_id="m1", template_ids=("tpl_A", "tpl_B", "tpl_C"))
    catalog = _make_catalog([motif])
    src_map = _make_source_map("r1", ["tpl_A", "tpl_B"])

    annotated = MotifAnnotator().annotate([recipe], catalog, source_template_map=src_map)
    reason = annotated[0].motif_compatibility[0].reason
    assert "2" in reason
    assert "3" in reason


def test_no_source_map_skips_scoring() -> None:
    """Without source_template_map, recipes get no new motif entries."""
    recipe = _make_recipe(recipe_id="r1", template_ids=["tpl_A"])
    motif = _make_motif(motif_id="m1", template_ids=("tpl_A",))
    catalog = _make_catalog([motif])

    annotated = MotifAnnotator().annotate([recipe], catalog)
    assert len(annotated[0].motif_compatibility) == 0
