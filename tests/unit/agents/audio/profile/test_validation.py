"""Tests for heuristic validation of AudioProfileModel."""


def test_validate_valid_profile():
    """Test validation passes for valid AudioProfileModel."""
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
    from twinklr.core.agents.audio.profile.validation import validate_audio_profile

    profile = AudioProfileModel(
        run_id="test",
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0",
            framework_version="1.0.0",
            temperature=0.7,
        ),
        song_identity=SongIdentity(duration_ms=60000, bpm=120.0),
        structure=Structure(
            sections=[
                SongSectionRef(section_id="v1", name="Verse 1", start_ms=0, end_ms=30000),
                SongSectionRef(section_id="c1", name="Chorus", start_ms=30000, end_ms=60000),
            ],
            structure_confidence=0.9,
        ),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.MED,
            section_profiles=[
                SectionEnergyProfile(
                    section_id="v1",
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
            peaks=[EnergyPeak(start_ms=25000, end_ms=30000, energy=0.6)],
            overall_mean=0.5,
            energy_confidence=0.85,
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
            recommended_contrast=Contrast.MED,
            recommended_motion_density=MotionDensity.MED,
            recommended_asset_usage=AssetUsage.SPARSE,
        ),
        planner_hints=PlannerHints(),
    )

    errors = validate_audio_profile(profile)
    assert errors == []


def test_validate_sections_not_monotonic():
    """Test validation detects non-monotonic sections."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        AudioProfileModel,
        Contrast,
        CreativeGuidance,
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
    from twinklr.core.agents.audio.profile.validation import validate_audio_profile

    profile = AudioProfileModel(
        run_id="test",
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0",
            framework_version="1.0.0",
            temperature=0.7,
        ),
        song_identity=SongIdentity(duration_ms=60000),
        structure=Structure(
            sections=[
                SongSectionRef(section_id="c1", name="Chorus", start_ms=30000, end_ms=60000),
                SongSectionRef(
                    section_id="v1", name="Verse 1", start_ms=0, end_ms=30000
                ),  # Out of order
            ],
            structure_confidence=0.9,
        ),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.LOW,
            section_profiles=[
                SectionEnergyProfile(
                    section_id="c1",
                    start_ms=30000,
                    end_ms=60000,
                    energy_curve=[
                        EnergyPoint(t_ms=30000, energy_0_1=0.4),
                        EnergyPoint(t_ms=45000, energy_0_1=0.4),
                        EnergyPoint(t_ms=60000, energy_0_1=0.4),
                    ],
                    mean_energy=0.4,
                    peak_energy=0.4,
                ),
            ],
            peaks=[],
            overall_mean=0.4,
            energy_confidence=0.8,
        ),
        lyric_profile=LyricProfile(
            has_plain_lyrics=False,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=0.0,
            phoneme_confidence=0.0,
        ),
        creative_guidance=CreativeGuidance(
            recommended_layer_count=1,
            recommended_contrast=Contrast.LOW,
            recommended_motion_density=MotionDensity.SPARSE,
            recommended_asset_usage=AssetUsage.NONE,
        ),
        planner_hints=PlannerHints(),
    )

    errors = validate_audio_profile(profile)
    assert len(errors) > 0
    assert any("monotonic" in err.lower() or "order" in err.lower() for err in errors)


def test_validate_sections_overlapping():
    """Test validation detects overlapping sections."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        AudioProfileModel,
        Contrast,
        CreativeGuidance,
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
    from twinklr.core.agents.audio.profile.validation import validate_audio_profile

    profile = AudioProfileModel(
        run_id="test",
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0",
            framework_version="1.0.0",
            temperature=0.7,
        ),
        song_identity=SongIdentity(duration_ms=100000),
        structure=Structure(
            sections=[
                SongSectionRef(section_id="v1", name="Verse", start_ms=0, end_ms=30000),
                SongSectionRef(
                    section_id="c1", name="Chorus", start_ms=25000, end_ms=60000
                ),  # Overlaps v1
            ],
            structure_confidence=0.9,
        ),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.LOW,
            section_profiles=[
                SectionEnergyProfile(
                    section_id="v1",
                    start_ms=0,
                    end_ms=30000,
                    energy_curve=[
                        EnergyPoint(t_ms=0, energy_0_1=0.4),
                        EnergyPoint(t_ms=15000, energy_0_1=0.4),
                        EnergyPoint(t_ms=30000, energy_0_1=0.4),
                    ],
                    mean_energy=0.4,
                    peak_energy=0.4,
                ),
            ],
            peaks=[],
            overall_mean=0.4,
            energy_confidence=0.8,
        ),
        lyric_profile=LyricProfile(
            has_plain_lyrics=False,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=0.0,
            phoneme_confidence=0.0,
        ),
        creative_guidance=CreativeGuidance(
            recommended_layer_count=1,
            recommended_contrast=Contrast.LOW,
            recommended_motion_density=MotionDensity.SPARSE,
            recommended_asset_usage=AssetUsage.NONE,
        ),
        planner_hints=PlannerHints(),
    )

    errors = validate_audio_profile(profile)
    assert len(errors) > 0
    assert any("overlap" in err.lower() for err in errors)


def test_validate_sections_exceed_duration():
    """Test validation detects sections beyond song duration."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        AudioProfileModel,
        Contrast,
        CreativeGuidance,
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
    from twinklr.core.agents.audio.profile.validation import validate_audio_profile

    profile = AudioProfileModel(
        run_id="test",
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0",
            framework_version="1.0.0",
            temperature=0.7,
        ),
        song_identity=SongIdentity(duration_ms=60000),
        structure=Structure(
            sections=[
                SongSectionRef(
                    section_id="v1", name="Verse", start_ms=0, end_ms=70000
                ),  # Beyond duration
            ],
            structure_confidence=0.9,
        ),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.LOW,
            section_profiles=[
                SectionEnergyProfile(
                    section_id="v1",
                    start_ms=0,
                    end_ms=70000,
                    energy_curve=[
                        EnergyPoint(t_ms=0, energy_0_1=0.4),
                        EnergyPoint(t_ms=35000, energy_0_1=0.4),
                        EnergyPoint(t_ms=70000, energy_0_1=0.4),
                    ],
                    mean_energy=0.4,
                    peak_energy=0.4,
                ),
            ],
            peaks=[],
            overall_mean=0.4,
            energy_confidence=0.8,
        ),
        lyric_profile=LyricProfile(
            has_plain_lyrics=False,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=0.0,
            phoneme_confidence=0.0,
        ),
        creative_guidance=CreativeGuidance(
            recommended_layer_count=1,
            recommended_contrast=Contrast.LOW,
            recommended_motion_density=MotionDensity.SPARSE,
            recommended_asset_usage=AssetUsage.NONE,
        ),
        planner_hints=PlannerHints(),
    )

    errors = validate_audio_profile(profile)
    assert len(errors) > 0
    assert any("duration" in err.lower() or "exceeds" in err.lower() for err in errors)


def test_validate_lyric_consistency():
    """Test validation detects lyric field inconsistencies."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        AudioProfileModel,
        Contrast,
        CreativeGuidance,
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
    from twinklr.core.agents.audio.profile.validation import validate_audio_profile

    profile = AudioProfileModel(
        run_id="test",
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0",
            framework_version="1.0.0",
            temperature=0.7,
        ),
        song_identity=SongIdentity(duration_ms=60000),
        structure=Structure(
            sections=[
                SongSectionRef(section_id="v1", name="Verse", start_ms=0, end_ms=60000),
            ],
            structure_confidence=0.9,
        ),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.LOW,
            section_profiles=[
                SectionEnergyProfile(
                    section_id="v1",
                    start_ms=0,
                    end_ms=60000,
                    energy_curve=[
                        EnergyPoint(t_ms=0, energy_0_1=0.4),
                        EnergyPoint(t_ms=30000, energy_0_1=0.4),
                        EnergyPoint(t_ms=60000, energy_0_1=0.4),
                    ],
                    mean_energy=0.4,
                    peak_energy=0.4,
                ),
            ],
            peaks=[],
            overall_mean=0.4,
            energy_confidence=0.8,
        ),
        lyric_profile=LyricProfile(
            has_plain_lyrics=False,
            has_timed_words=True,  # Invalid: requires has_plain_lyrics=True
            has_phonemes=False,
            lyric_confidence=0.0,
            phoneme_confidence=0.0,
        ),
        creative_guidance=CreativeGuidance(
            recommended_layer_count=1,
            recommended_contrast=Contrast.LOW,
            recommended_motion_density=MotionDensity.SPARSE,
            recommended_asset_usage=AssetUsage.NONE,
        ),
        planner_hints=PlannerHints(),
    )

    errors = validate_audio_profile(profile)
    assert len(errors) > 0
    assert any("timed_words" in err.lower() and "plain_lyrics" in err.lower() for err in errors)


def test_validate_energy_timestamps_monotonic():
    """Test validation detects non-monotonic energy timestamps."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        AudioProfileModel,
        Contrast,
        CreativeGuidance,
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
    from twinklr.core.agents.audio.profile.validation import validate_audio_profile

    profile = AudioProfileModel(
        run_id="test",
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0",
            framework_version="1.0.0",
            temperature=0.7,
        ),
        song_identity=SongIdentity(duration_ms=60000),
        structure=Structure(
            sections=[
                SongSectionRef(section_id="v1", name="Verse", start_ms=0, end_ms=60000),
            ],
            structure_confidence=0.9,
        ),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.MED,
            section_profiles=[
                SectionEnergyProfile(
                    section_id="v1",
                    start_ms=0,
                    end_ms=60000,
                    energy_curve=[
                        EnergyPoint(t_ms=0, energy_0_1=0.5),
                        EnergyPoint(t_ms=30000, energy_0_1=0.6),
                        EnergyPoint(t_ms=20000, energy_0_1=0.7),  # Out of order
                    ],
                    mean_energy=0.6,
                    peak_energy=0.7,
                ),
            ],
            peaks=[],
            overall_mean=0.6,
            energy_confidence=0.8,
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

    errors = validate_audio_profile(profile)
    assert len(errors) > 0
    assert any(
        "energy" in err.lower() and ("monotonic" in err.lower() or "order" in err.lower())
        for err in errors
    )


def test_validate_energy_peaks_within_duration():
    """Test validation detects energy peaks beyond song duration."""
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
    from twinklr.core.agents.audio.profile.validation import validate_audio_profile

    profile = AudioProfileModel(
        run_id="test",
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0",
            framework_version="1.0.0",
            temperature=0.7,
        ),
        song_identity=SongIdentity(duration_ms=60000),
        structure=Structure(
            sections=[
                SongSectionRef(section_id="v1", name="Verse", start_ms=0, end_ms=60000),
            ],
            structure_confidence=0.9,
        ),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.MED,
            section_profiles=[
                SectionEnergyProfile(
                    section_id="v1",
                    start_ms=0,
                    end_ms=60000,
                    energy_curve=[
                        EnergyPoint(t_ms=0, energy_0_1=0.6),
                        EnergyPoint(t_ms=30000, energy_0_1=0.6),
                        EnergyPoint(t_ms=60000, energy_0_1=0.6),
                    ],
                    mean_energy=0.6,
                    peak_energy=0.6,
                ),
            ],
            peaks=[
                EnergyPeak(start_ms=55000, end_ms=70000, energy=0.9),  # Beyond duration
            ],
            overall_mean=0.6,
            energy_confidence=0.8,
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

    errors = validate_audio_profile(profile)
    assert len(errors) > 0
    assert any("peak" in err.lower() and "duration" in err.lower() for err in errors)


def test_validate_returns_list_of_strings():
    """Test validation returns list of error strings."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        AudioProfileModel,
        Contrast,
        CreativeGuidance,
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
    from twinklr.core.agents.audio.profile.validation import validate_audio_profile

    profile = AudioProfileModel(
        run_id="test",
        provenance=Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="audio_profile.v2",
            prompt_pack_version="1.0",
            framework_version="1.0.0",
            temperature=0.7,
        ),
        song_identity=SongIdentity(duration_ms=60000),
        structure=Structure(
            sections=[
                SongSectionRef(section_id="v1", name="Verse", start_ms=0, end_ms=60000),
            ],
            structure_confidence=0.9,
        ),
        energy_profile=EnergyProfile(
            macro_energy=MacroEnergy.LOW,
            section_profiles=[
                SectionEnergyProfile(
                    section_id="v1",
                    start_ms=0,
                    end_ms=60000,
                    energy_curve=[
                        EnergyPoint(t_ms=0, energy_0_1=0.4),
                        EnergyPoint(t_ms=30000, energy_0_1=0.4),
                        EnergyPoint(t_ms=60000, energy_0_1=0.4),
                    ],
                    mean_energy=0.4,
                    peak_energy=0.4,
                ),
            ],
            peaks=[],
            overall_mean=0.4,
            energy_confidence=0.8,
        ),
        lyric_profile=LyricProfile(
            has_plain_lyrics=False,
            has_timed_words=False,
            has_phonemes=False,
            lyric_confidence=0.0,
            phoneme_confidence=0.0,
        ),
        creative_guidance=CreativeGuidance(
            recommended_layer_count=1,
            recommended_contrast=Contrast.LOW,
            recommended_motion_density=MotionDensity.SPARSE,
            recommended_asset_usage=AssetUsage.NONE,
        ),
        planner_hints=PlannerHints(),
    )

    errors = validate_audio_profile(profile)
    assert isinstance(errors, list)
    assert all(isinstance(err, str) for err in errors)
