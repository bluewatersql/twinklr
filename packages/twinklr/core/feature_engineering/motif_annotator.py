"""MotifAnnotator — cross-references recipes with mined motifs.

Populates ``EffectRecipe.motif_compatibility`` by checking which motifs
share template_ids with each recipe's provenance. The overlap ratio
(intersection / motif template count) produces the compatibility score.
"""

from __future__ import annotations

from twinklr.core.feature_engineering.models.motifs import MotifCatalog
from twinklr.core.sequencer.templates.group.recipe import (
    EffectRecipe,
    MotifCompatibility,
)


class MotifAnnotator:
    """Score recipe–motif compatibility via template overlap.

    For each recipe, finds every motif whose ``template_ids`` overlap with
    the recipe's ``provenance.mined_template_ids``. The score is the
    Jaccard-style overlap ratio: ``|intersection| / |motif.template_ids|``.
    """

    def annotate(
        self,
        recipes: list[EffectRecipe],
        catalog: MotifCatalog,
    ) -> list[EffectRecipe]:
        """Annotate recipes with motif compatibility scores.

        Args:
            recipes: Recipes to annotate (may already have compatibility entries).
            catalog: Mined motif catalog from the FE pipeline.

        Returns:
            New list of recipes with ``motif_compatibility`` populated.
            Pre-existing entries are preserved.
        """
        if not catalog.motifs:
            return list(recipes)

        result: list[EffectRecipe] = []
        for recipe in recipes:
            new_compat = self._score_recipe(recipe, catalog)
            if new_compat:
                merged = list(recipe.motif_compatibility) + new_compat
                recipe = recipe.model_copy(update={"motif_compatibility": merged})
            result.append(recipe)
        return result

    def _score_recipe(
        self,
        recipe: EffectRecipe,
        catalog: MotifCatalog,
    ) -> list[MotifCompatibility]:
        recipe_tpl_ids = set(recipe.provenance.mined_template_ids)
        if not recipe_tpl_ids:
            return []

        existing_motif_ids = {mc.motif_id for mc in recipe.motif_compatibility}
        matches: list[MotifCompatibility] = []

        for motif in catalog.motifs:
            if motif.motif_id in existing_motif_ids:
                continue
            motif_tpl_ids = set(motif.template_ids)
            if not motif_tpl_ids:
                continue
            overlap = recipe_tpl_ids & motif_tpl_ids
            if not overlap:
                continue
            score = len(overlap) / len(motif_tpl_ids)
            reason = (
                f"{len(overlap)}/{len(motif_tpl_ids)} templates shared "
                f"(span={motif.bar_span}, support={motif.support_count})"
            )
            matches.append(MotifCompatibility(
                motif_id=motif.motif_id,
                score=round(score, 4),
                reason=reason,
            ))

        matches.sort(key=lambda mc: mc.score, reverse=True)
        return matches
