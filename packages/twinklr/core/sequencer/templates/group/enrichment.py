"""EnrichmentSidecar — optional FE-computed metadata stored separately.

Fields like ``motif_compatibility`` and ``model_affinities`` are recomputable
by the FE pipeline and not needed by planning or rendering. They live in
``.enrichment/`` sidecar files alongside the main recipe JSON.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.group.recipe import (
    ModelAffinity,
    MotifCompatibility,
)


class EnrichmentSidecar(BaseModel):
    """Sidecar data for a single recipe.

    Stored at ``data/templates/.enrichment/{recipe_id}.json``.
    Recomputed by the FE pipeline; never needed at runtime.

    Attributes:
        recipe_id: ID of the recipe this enrichment belongs to.
        model_affinities: Per-model-type affinity scores.
        motif_compatibility: Per-motif compatibility scores.
    """

    model_config = ConfigDict(extra="forbid")

    recipe_id: str = Field(description="Recipe this enrichment belongs to")
    model_affinities: list[ModelAffinity] = Field(
        default_factory=list,
        description="Model type affinity scores",
    )
    motif_compatibility: list[MotifCompatibility] = Field(
        default_factory=list,
        description="Motif compatibility scores",
    )
