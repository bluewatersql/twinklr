"""Propensity Miner output models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EffectModelAffinity(BaseModel):
    """Positive affinity between an effect family and a display model type."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effect_family: str = Field(description="Effect family (e.g. single_strand, bars).")
    model_type: str = Field(description="Display model type (e.g. megatree, arch, matrix).")
    frequency: float = Field(ge=0.0, le=1.0, description="How often this pairing appears.")
    exclusivity: float = Field(
        ge=0.0, le=1.0, description="How exclusive this effect is to this model type."
    )
    corpus_support: int = Field(ge=0, description="Number of corpus instances supporting this.")


class EffectModelAntiAffinity(BaseModel):
    """Negative affinity — effect family rarely/never seen on this model type."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effect_family: str = Field(description="Effect family.")
    model_type: str = Field(description="Display model type.")
    corpus_support: int = Field(ge=0, description="Number of corpus instances checked.")


class PropensityIndex(BaseModel):
    """Complete effect-to-model propensity index from corpus mining."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="v1.0.0")
    affinities: tuple[EffectModelAffinity, ...] = Field(
        description="Positive effect-model affinities."
    )
    anti_affinities: tuple[EffectModelAntiAffinity, ...] = Field(
        default=(), description="Negative effect-model affinities."
    )
