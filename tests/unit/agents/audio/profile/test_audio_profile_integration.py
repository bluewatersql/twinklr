"""Integration tests for complete AudioProfileModel."""

import pytest


def test_audio_profile_model_complete():
    """Test AudioProfileModel with all nested models."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        AudioProfileModel,
        Contrast,
        CreativeGuidance,
        EnergyPeak,
        EnergyPoint,
        EnergyProfile,
        LyricProfile,
        MacroEnergy,
        MotionDensity,
        PlannerHints,
        Provenance,
        SectionEnergyProfile,
        SongIdentity,
        SongSectionRef,
        Structure,
    )

    profile = AudioProfileModel(
        run_id="test_run_123",
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0",
            framework_version="1.0.0",
            temperature=0.7,
        ),
        song_identity=SongIdentity(
            title="Test Song",
            artist="Test Artist",
            duration_ms=180000,
            bpm=120.0,
        ),
        structure=Structure(
            sections=[
                SongSectionRef(
                    section_id="verse_1",
                    name="Verse 1",
                    start_ms=0,
                    end_ms=30000,
                ),
                SongSectionRef(
                    section_id="chorus_1",
                    name="Chorus 1",
                    start_ms=30000,
                    end_ms=60000,
                ),
            ],
            structure_confidence=0.9,
        ),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.DYNAMIC,
            section_profiles=[
                SectionEnergyProfile(
                    section_id="verse_1",
                    start_ms=0,
                    end_ms=30000,
                    energy_curve=[
                        EnergyPoint(t_ms=0, energy_0_1=0.4),
                        EnergyPoint(t_ms=15000, energy_0_1=0.5),
                        EnergyPoint(t_ms=30000, energy_0_1=0.6),
                    ],
                    mean_energy=0.5,
                    peak_energy=0.6,
                ),
            ],
            peaks=[EnergyPeak(start_ms=30000, end_ms=35000, energy=0.9)],
            overall_mean=0.6,
            energy_confidence=0.92,
        ),
        lyric_profile=LyricProfile(
            has_plain_lyrics=True,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=0.8,
            phoneme_confidence=0.0,
        ),
        creative_guidance=CreativeGuidance(
            recommended_layer_count=2,
            recommended_contrast=Contrast.HIGH,
            recommended_motion_density=MotionDensity.BUSY,
            recommended_asset_usage=AssetUsage.SPARSE,
            palette_color_guidance=["vibrant", "energetic"],
        ),
        planner_hints=PlannerHints(
            section_objectives={"verse_1": ["Subtle movement"], "chorus_1": ["High energy"]},
            avoid_patterns=["Repetitive patterns"],
        ),
    )

    # Verify top-level fields
    assert profile.run_id == "test_run_123"
    assert profile.schema_version == "2.0"
    assert profile.agent_id == "audio_profile.v2"

    # Verify nested models work
    assert profile.song_identity.title == "Test Song"
    assert len(profile.structure.sections) == 2
    assert profile.energy_profile.macro_energy == MacroEnergy.DYNAMIC
    assert profile.lyric_profile.has_plain_lyrics is True
    assert profile.creative_guidance.recommended_layer_count == 2
    assert len(profile.planner_hints.section_objectives) == 2


def test_audio_profile_model_validates_nested():
    """Test that AudioProfileModel validates nested models correctly."""
    from pydantic import ValidationError

    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        AudioProfileModel,
        Contrast,
        CreativeGuidance,
        EnergyProfile,
        LyricProfile,
        MacroEnergy,
        MotionDensity,
        PlannerHints,
        Provenance,
        SongIdentity,
        Structure,
    )

    # Invalid: duration_ms must be > 0
    with pytest.raises(ValidationError):
        AudioProfileModel(
            run_id="test",
            provenance=Provenance(
                provider_id="openai",
                model_id="gpt-5.2",
                prompt_pack="audio_profile.v2",
                prompt_pack_version="1.0",
                framework_version="1.0.0",
                temperature=0.7,
            ),
            song_identity=SongIdentity(duration_ms=0),  # Invalid
            structure=Structure(sections=[], structure_confidence=0.9),
            energy_profile=EnergyProfile(
                macro_energy=MacroEnergy.LOW,
                section_profiles=[],
                peaks=[],
                overall_mean=0.5,
                energy_confidence=0.9,
            ),
            lyric_profile=LyricProfile(
                has_plain_lyrics=False,
                has_timed_words=False,
                has_phonemes=False,
                lyric_confidence=0.0,
                phoneme_confidence=0.0,
            ),
            creative_guidance=CreativeGuidance(
                recommended_layer_count=2,
                recommended_contrast=Contrast.MED,
                recommended_motion_density=MotionDensity.MED,
                recommended_asset_usage=AssetUsage.SPARSE,
            ),
            planner_hints=PlannerHints(),
        )
