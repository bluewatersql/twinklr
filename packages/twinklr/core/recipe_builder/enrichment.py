"""Metadata-only enrichment for existing recipes.

Identifies recipes with incomplete metadata (tags, model_affinities,
motif_compatibility, descriptions) and generates enrichment patches.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from twinklr.core.recipe_builder.models import MetadataEnrichmentCandidate
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

logger = logging.getLogger(__name__)

_STRUCTURAL_FIELDS = frozenset(
    {
        "layers",
        "palette_spec",
        "timing",
        "template_type",
        "visual_intent",
        "recipe_version",
        "recipe_id",
    }
)

_ALLOWED_PATCH_FIELDS = frozenset(
    {
        "tags",
        "model_affinities",
        "motif_compatibility",
        "style_markers",
        "description",
        "effect_family",
    }
)

_GENERIC_DESCRIPTION_THRESHOLD = 40


def generate_enrichments(
    library_recipes: list[EffectRecipe],
) -> list[MetadataEnrichmentCandidate]:
    """Generate metadata enrichment candidates for recipes with gaps.

    Scans each library recipe for missing or incomplete metadata fields
    and proposes patches. Only metadata fields are touched — structural
    fields (layers, timing, etc.) are never modified.

    Args:
        library_recipes: All recipes in the catalog.

    Returns:
        List of MetadataEnrichmentCandidate for recipes needing enrichment.
    """
    candidates: list[MetadataEnrichmentCandidate] = []

    for recipe in library_recipes:
        patch = _build_metadata_patch(recipe)

        if not patch:
            continue

        candidate = MetadataEnrichmentCandidate(
            candidate_id=f"enr_{uuid4().hex[:12]}",
            target_recipe_id=recipe.recipe_id,
            proposed_metadata_patch=patch,
            rationale=f"Enriching recipe '{recipe.name}' — missing: {', '.join(patch.keys())}",
            confidence=0.6,
        )
        candidates.append(candidate)

    logger.info(
        "Enrichment: %d of %d recipes need metadata patches",
        len(candidates),
        len(library_recipes),
    )
    return candidates


def _build_metadata_patch(recipe: EffectRecipe) -> dict[str, Any]:
    """Build a metadata-only patch for a single recipe.

    Returns an empty dict if no enrichment is needed.
    """
    patch: dict[str, Any] = {}

    # Tags: ensure effect_family and energy are tagged
    expected_tags = {
        recipe.effect_family,
        recipe.style_markers.energy_affinity.value.lower(),
        recipe.template_type.value.lower(),
    }
    existing_tags = set(recipe.tags)
    missing_tags = expected_tags - existing_tags
    if missing_tags and recipe.tags:
        patch["tags"] = list(recipe.tags) + sorted(missing_tags)
    elif not recipe.tags:
        patch["tags"] = sorted(expected_tags | {"generated" if recipe.provenance.source == "generated" else recipe.provenance.source})

    # Effect family: fix "unknown"
    if recipe.effect_family == "unknown" and recipe.layers:
        primary_effect = recipe.layers[0].effect_type
        inferred_family = primary_effect.lower().replace(" ", "_")
        patch["effect_family"] = inferred_family

    # Description: flag very short ones
    if len(recipe.description) < _GENERIC_DESCRIPTION_THRESHOLD:
        layer_desc = ", ".join(layer.effect_type for layer in recipe.layers)
        energy = recipe.style_markers.energy_affinity.value.lower()
        patch["description"] = (
            f"{recipe.template_type.value} recipe with {energy} energy "
            f"using {layer_desc}. {recipe.description}"
        )

    # Safety: strip structural fields, keep only allowed
    for field in _STRUCTURAL_FIELDS:
        patch.pop(field, None)
    patch = {k: v for k, v in patch.items() if k in _ALLOWED_PATCH_FIELDS}

    return patch
