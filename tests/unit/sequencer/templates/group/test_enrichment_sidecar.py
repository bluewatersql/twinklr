"""Tests for EnrichmentSidecar model."""

from __future__ import annotations

from twinklr.core.sequencer.templates.group.enrichment import EnrichmentSidecar
from twinklr.core.sequencer.templates.group.recipe import (
    ModelAffinity,
    MotifCompatibility,
)


def test_empty_sidecar() -> None:
    """Sidecar with no enrichment data is valid."""
    sidecar = EnrichmentSidecar(recipe_id="gtpl_base_starfield_slow")
    assert sidecar.recipe_id == "gtpl_base_starfield_slow"
    assert sidecar.model_affinities == []
    assert sidecar.motif_compatibility == []


def test_sidecar_with_affinities() -> None:
    sidecar = EnrichmentSidecar(
        recipe_id="r1",
        model_affinities=[
            ModelAffinity(model_type="megatree", score=0.9),
            ModelAffinity(model_type="arch", score=0.6),
        ],
    )
    assert len(sidecar.model_affinities) == 2
    assert sidecar.model_affinities[0].model_type == "megatree"


def test_sidecar_with_motif_compat() -> None:
    sidecar = EnrichmentSidecar(
        recipe_id="r1",
        motif_compatibility=[
            MotifCompatibility(motif_id="grid", score=0.85, reason="grid match"),
        ],
    )
    assert len(sidecar.motif_compatibility) == 1


def test_sidecar_roundtrip() -> None:
    sidecar = EnrichmentSidecar(
        recipe_id="test_rt",
        model_affinities=[ModelAffinity(model_type="matrix", score=0.7)],
        motif_compatibility=[
            MotifCompatibility(motif_id="wave", score=0.5, reason="partial"),
        ],
    )
    data = sidecar.model_dump()
    restored = EnrichmentSidecar.model_validate(data)
    assert restored == sidecar
