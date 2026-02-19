"""Style Fingerprint output models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TransitionStyleProfile(BaseModel):
    """Transition style preferences extracted from corpus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    preferred_gap_ms: float = Field(ge=0.0, description="Preferred gap between effects in ms.")
    overlap_tendency: float = Field(
        ge=0.0, le=1.0, description="0=sharp cuts, 1=heavy overlaps."
    )
    variety_score: float = Field(
        ge=0.0, le=1.0, description="0=repetitive transitions, 1=highly varied."
    )


class ColorStyleProfile(BaseModel):
    """Color usage preferences extracted from corpus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    palette_complexity: float = Field(
        ge=0.0, le=1.0, description="0=monochrome, 1=full spectrum."
    )
    contrast_preference: float = Field(
        ge=0.0, le=1.0, description="Preferred contrast level between sections."
    )
    temperature_preference: float = Field(
        ge=0.0, le=1.0, description="0=cool tones, 1=warm tones."
    )


class TimingStyleProfile(BaseModel):
    """Timing preferences extracted from corpus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    beat_alignment_strictness: float = Field(
        ge=0.0, le=1.0, description="How strictly effects align to beats."
    )
    density_preference: float = Field(
        ge=0.0, le=1.0, description="0=sparse, 1=busy."
    )
    section_change_aggression: float = Field(
        ge=0.0, le=1.0, description="0=subtle section changes, 1=dramatic."
    )


class LayeringStyleProfile(BaseModel):
    """Layering preferences extracted from corpus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mean_layers: float = Field(ge=0.0, description="Average number of concurrent layers.")
    max_layers: int = Field(ge=0, description="Maximum concurrent layers observed.")
    blend_mode_preference: str = Field(description="Most common blend mode (normal, add, screen).")


class StyleFingerprint(BaseModel):
    """Complete creator/package style fingerprint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    creator_id: str = Field(description="Creator or package identifier.")
    recipe_preferences: dict[str, float] = Field(
        default_factory=dict,
        description="Effect family -> preference weight (0-1).",
    )
    transition_style: TransitionStyleProfile
    color_tendencies: ColorStyleProfile
    timing_style: TimingStyleProfile
    layering_style: LayeringStyleProfile
    corpus_sequence_count: int = Field(
        ge=0, description="Number of sequences used to build this fingerprint."
    )


class StyleEvolution(BaseModel):
    """Directional style evolution parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: Literal[
        "more_complex",
        "simpler",
        "warmer",
        "cooler",
        "higher_energy",
        "calmer",
    ] = Field(description="Evolution direction.")
    intensity: float = Field(
        ge=0.0, le=1.0, description="How strongly to apply the evolution (0=none, 1=full)."
    )


class StyleBlend(BaseModel):
    """Blended style from base + optional accent fingerprint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_style: StyleFingerprint = Field(description="Primary style.")
    accent_style: StyleFingerprint | None = Field(
        default=None, description="Secondary style to mix in."
    )
    blend_ratio: float = Field(
        ge=0.0, le=1.0, description="0.0=pure base, 1.0=pure accent."
    )
    evolution_params: StyleEvolution | None = Field(
        default=None, description="Optional directional evolution."
    )
