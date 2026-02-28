"""Vocabulary extension model contracts.

Corpus-derived compound motion and energy terms discovered from
multi-layer effect stack signatures.  These are sidecar enrichments
that do not modify the core EffectPhrase schema.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CompoundMotionTerm(BaseModel):
    """A compound motion term discovered from stack patterns.

    Attributes:
        term: Compound term name (e.g. "dual_chase").
        description: Human-readable description.
        component_families: Effect families that compose this term.
        component_roles: Layer roles for each component (e.g. "base", "accent").
        motion_axis: Primary motion direction of the compound.
        corpus_support: Number of occurrences in the corpus.
        canonical_signature: Stack signature this term maps from.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    term: str = Field(description="Compound term name")
    description: str = Field(description="Human-readable description")
    component_families: tuple[str, ...] = Field(description="Effect families composing this term")
    component_roles: tuple[str, ...] = Field(description="Layer roles for each component")
    motion_axis: str = Field(description="Primary motion direction")
    corpus_support: int = Field(ge=0, description="Occurrence count in corpus")
    canonical_signature: str = Field(description="Stack signature this maps from")


class CompoundEnergyTerm(BaseModel):
    """A compound energy term from stack combinations.

    Attributes:
        term: Compound term name (e.g. "wash_burst").
        description: Human-readable description.
        base_energy: Energy class of the base layer.
        accent_energy: Energy class of the accent layer.
        combined_energy: Resulting perceived energy level.
        corpus_support: Number of occurrences in the corpus.
        canonical_signature: Stack signature this maps from.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    term: str = Field(description="Compound term name")
    description: str = Field(description="Human-readable description")
    base_energy: str = Field(description="Energy class of base layer")
    accent_energy: str = Field(description="Energy class of accent layer")
    combined_energy: str = Field(description="Resulting perceived energy")
    corpus_support: int = Field(ge=0, description="Occurrence count")
    canonical_signature: str = Field(description="Stack signature this maps from")


class VocabularyExtensions(BaseModel):
    """Corpus-derived vocabulary extensions.

    Attributes:
        schema_version: Schema version string.
        compound_motion_terms: Discovered compound motion terms.
        compound_energy_terms: Discovered compound energy terms.
        total_stack_signatures_analyzed: Total unique signatures processed.
        total_multi_layer_stacks: Total multi-layer stacks in input.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="v1.0.0")
    compound_motion_terms: tuple[CompoundMotionTerm, ...] = Field(
        default=(),
        description="Discovered compound motion terms",
    )
    compound_energy_terms: tuple[CompoundEnergyTerm, ...] = Field(
        default=(),
        description="Discovered compound energy terms",
    )
    total_stack_signatures_analyzed: int = Field(
        default=0, ge=0, description="Total unique signatures processed"
    )
    total_multi_layer_stacks: int = Field(
        default=0, ge=0, description="Total multi-layer stacks in input"
    )
