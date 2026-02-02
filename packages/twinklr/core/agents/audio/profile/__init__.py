"""AudioProfile agent for song intent profiling.

The AudioProfile agent transforms raw audio analysis (SongBundle) into
a canonical song intent profile (AudioProfileModel) that provides stable,
high-quality understanding for downstream planning agents.

This is a "no-judge" agent that uses fail-fast validation rather than
iterative refinement.
"""

from twinklr.core.agents.audio.profile.context import shape_context
from twinklr.core.agents.audio.profile.models import (
    AssetUsage,
    AudioProfileModel,
    Contrast,
    CreativeGuidance,
    EnergyPeak,
    EnergyPoint,
    EnergyProfile,
    Issue,
    LyricProfile,
    MacroEnergy,
    MotionDensity,
    PlannerHints,
    Provenance,
    SectionEnergyProfile,
    Severity,
    SongIdentity,
    SongSectionRef,
    Structure,
)
from twinklr.core.agents.audio.profile.orchestrator import AudioProfileOrchestrator
from twinklr.core.agents.audio.profile.spec import get_audio_profile_spec
from twinklr.core.agents.audio.profile.validation import validate_audio_profile

__version__ = "1.0.0"

__all__ = [
    "AssetUsage",
    "AudioProfileModel",
    "AudioProfileOrchestrator",
    "Contrast",
    "CreativeGuidance",
    "EnergyPeak",
    "EnergyPoint",
    "EnergyProfile",
    "Issue",
    "LyricProfile",
    "MacroEnergy",
    "MotionDensity",
    "PlannerHints",
    "Provenance",
    "SectionEnergyProfile",
    "Severity",
    "SongIdentity",
    "SongSectionRef",
    "Structure",
    "get_audio_profile_spec",
    "shape_context",
    "validate_audio_profile",
]
