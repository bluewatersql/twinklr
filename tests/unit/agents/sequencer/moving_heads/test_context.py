"""Tests for MovingHeadPlanningContext model (V2)."""

import json
from pathlib import Path

import pytest

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
    SectionEnergyProfile,
    SongIdentity,
    SongSectionRef,
    Structure,
)
from twinklr.core.agents.sequencer.moving_heads.context import (
    FixtureContext,
    MovingHeadPlanningContext,
)


def create_minimal_audio_profile(
    title: str = "Test Song",
    artist: str = "Test Artist",
    duration_ms: int = 180000,
    bpm: float = 120.0,
    time_signature: str = "4/4",
    sections: list[SongSectionRef] | None = None,
) -> AudioProfileModel:
    """Create a minimal AudioProfileModel for testing.

    Provides all required fields with sensible defaults.
    """
    if sections is None:
        sections = [
            SongSectionRef(section_id="intro", name="intro", start_ms=0, end_ms=30000),
            SongSectionRef(section_id="verse_1", name="verse", start_ms=30000, end_ms=90000),
            SongSectionRef(section_id="outro", name="outro", start_ms=90000, end_ms=duration_ms),
        ]

    song_identity = SongIdentity(
        title=title,
        artist=artist,
        duration_ms=duration_ms,
        bpm=bpm,
        time_signature=time_signature,
    )

    structure = Structure(sections=sections, structure_confidence=0.9)

    # Create minimal section energy profiles (one per section)
    section_profiles = [
        SectionEnergyProfile(
            section_id=sec.section_id,
            start_ms=sec.start_ms,
            end_ms=sec.end_ms,
            energy_curve=[
                EnergyPoint(t_ms=sec.start_ms, energy_0_1=0.5),
                EnergyPoint(t_ms=(sec.start_ms + sec.end_ms) // 2, energy_0_1=0.6),
                EnergyPoint(t_ms=sec.end_ms - 1, energy_0_1=0.5),
            ],
            mean_energy=0.55,
            peak_energy=0.6,
        )
        for sec in sections
    ]

    energy_profile = EnergyProfile(
        macro_energy=MacroEnergy.MED,
        section_profiles=section_profiles,
        peaks=[],
        overall_mean=0.5,
        energy_confidence=0.8,
    )

    lyric_profile = LyricProfile(
        has_plain_lyrics=False,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=0.0,
        phoneme_confidence=0.0,
    )

    creative_guidance = CreativeGuidance(
        recommended_layer_count=2,
        recommended_contrast=Contrast.MED,
        recommended_motion_density=MotionDensity.MED,
        recommended_asset_usage=AssetUsage.SPARSE,
    )

    planner_hints = PlannerHints()

    return AudioProfileModel(
        song_identity=song_identity,
        structure=structure,
        energy_profile=energy_profile,
        lyric_profile=lyric_profile,
        creative_guidance=creative_guidance,
        planner_hints=planner_hints,
    )


@pytest.fixture
def song_sections() -> list[SongSectionRef]:
    """Sample sections for a 3-minute song."""
    return [
        SongSectionRef(section_id="intro", name="intro", start_ms=0, end_ms=15000),
        SongSectionRef(section_id="verse_1", name="verse", start_ms=15000, end_ms=45000),
        SongSectionRef(section_id="chorus_1", name="chorus", start_ms=45000, end_ms=75000),
        SongSectionRef(section_id="verse_2", name="verse", start_ms=75000, end_ms=105000),
        SongSectionRef(section_id="chorus_2", name="chorus", start_ms=105000, end_ms=135000),
        SongSectionRef(section_id="outro", name="outro", start_ms=135000, end_ms=180000),
    ]


@pytest.fixture
def audio_profile(song_sections: list[SongSectionRef]) -> AudioProfileModel:
    """Minimal audio profile for testing."""
    return create_minimal_audio_profile(sections=song_sections)


@pytest.fixture
def fixture_context() -> FixtureContext:
    """Sample fixture configuration."""
    return FixtureContext(
        count=4,
        groups=[
            {"id": "left_pair", "fixtures": [1, 2], "position": "left"},
            {"id": "right_pair", "fixtures": [3, 4], "position": "right"},
        ],
    )


@pytest.fixture
def available_templates() -> list[str]:
    """Sample template IDs."""
    return [
        "sweep_lr_fan_pulse",
        "circle_fan_hold",
        "pendulum_chevron_breathe",
        "figure_eight_chase",
    ]


@pytest.fixture
def planning_context(
    audio_profile: AudioProfileModel,
    fixture_context: FixtureContext,
    available_templates: list[str],
) -> MovingHeadPlanningContext:
    """Complete planning context for testing."""
    return MovingHeadPlanningContext(
        audio_profile=audio_profile,
        fixtures=fixture_context,
        available_templates=available_templates,
    )


class TestFixtureContext:
    """Tests for FixtureContext model."""

    def test_create_fixture_context(self) -> None:
        """Test creating a fixture context."""
        ctx = FixtureContext(count=4, groups=[])

        assert ctx.count == 4
        assert ctx.groups == []

    def test_fixture_context_frozen(self) -> None:
        """Test fixture context is immutable."""
        from pydantic import ValidationError

        ctx = FixtureContext(count=4, groups=[])

        with pytest.raises(ValidationError):
            ctx.count = 8  # type: ignore[misc]


class TestMovingHeadPlanningContext:
    """Tests for MovingHeadPlanningContext model."""

    def test_create_context(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test creating a planning context."""
        assert planning_context.audio_profile is not None
        assert planning_context.fixtures.count == 4
        assert len(planning_context.available_templates) == 4

    def test_has_lyrics_without_lyrics(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test has_lyrics property when no lyrics."""
        assert planning_context.has_lyrics is False

    def test_song_title(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test song_title property."""
        assert planning_context.song_title == "Test Song"

    def test_song_artist(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test song_artist property."""
        assert planning_context.song_artist == "Test Artist"

    def test_duration_ms(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test duration_ms property."""
        assert planning_context.duration_ms == 180000

    def test_tempo(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test tempo property."""
        assert planning_context.tempo == 120.0

    def test_time_signature(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test time_signature property."""
        assert planning_context.time_signature == "4/4"

    def test_sections(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test sections property returns audio profile sections."""
        sections = planning_context.sections

        assert len(sections) == 6
        assert sections[0].name == "intro"
        assert sections[-1].name == "outro"

    def test_total_bars_calculation(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test total_bars computed field.

        At 120 BPM in 4/4 time:
        - 1 bar = 4 beats
        - 1 beat = 500ms (60000ms / 120 BPM)
        - 1 bar = 2000ms
        - 180000ms / 2000ms = 90 bars
        """
        assert planning_context.total_bars == 90

    def test_for_prompt_structure(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test for_prompt returns expected structure."""
        prompt_data = planning_context.for_prompt()

        assert "audio_profile" in prompt_data
        assert "song_structure" in prompt_data
        assert "beat_grid" in prompt_data
        assert "fixtures" in prompt_data
        assert "available_templates" in prompt_data

    def test_for_prompt_beat_grid(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test for_prompt beat grid values."""
        prompt_data = planning_context.for_prompt()
        beat_grid = prompt_data["beat_grid"]

        assert beat_grid["tempo"] == 120.0
        assert beat_grid["time_signature"] == "4/4"
        assert beat_grid["total_bars"] == 90

    def test_for_prompt_song_structure(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test for_prompt song structure has sections with bar positions."""
        prompt_data = planning_context.for_prompt()
        song_structure = prompt_data["song_structure"]

        assert "sections" in song_structure
        assert len(song_structure["sections"]) == 6
        assert song_structure["total_bars"] == 90

        # Check first section has bar positions
        intro = song_structure["sections"][0]
        assert intro["name"] == "intro"
        assert "start_bar" in intro
        assert "end_bar" in intro
        assert intro["start_bar"] == 1  # 0ms -> bar 1

    def test_for_prompt_fixtures(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test for_prompt fixtures format."""
        prompt_data = planning_context.for_prompt()
        fixtures = prompt_data["fixtures"]

        assert fixtures["count"] == 4
        assert len(fixtures["groups"]) == 2

    def test_for_prompt_templates(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test for_prompt includes templates."""
        prompt_data = planning_context.for_prompt()

        assert prompt_data["available_templates"] == [
            "sweep_lr_fan_pulse",
            "circle_fan_hold",
            "pendulum_chevron_breathe",
            "figure_eight_chase",
        ]

    def test_ms_to_bar_conversion(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test milliseconds to bar conversion.

        At 120 BPM in 4/4:
        - 0ms -> bar 1
        - 2000ms (1 bar) -> bar 2
        - 15000ms -> bar 8 (approximately, 15000/2000 = 7.5 + 1 = 8)
        """
        # Test start of song
        assert planning_context._ms_to_bar(0) == 1

        # Test after 1 bar (2000ms at 120 BPM, 4/4)
        assert planning_context._ms_to_bar(2000) == 2

    def test_macro_plan_stub(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test macro_plan is None by default (stubbed for future)."""
        assert planning_context.macro_plan is None


class TestContextFromRealFixture:
    """Tests using real audio profile fixture."""

    @pytest.fixture
    def real_audio_profile(self) -> AudioProfileModel:
        """Load real audio profile from fixture."""
        fixture_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "fixtures"
            / "audio_profile"
            / "audio_profile_model.json"
        )

        if not fixture_path.exists():
            pytest.skip(f"Fixture not found: {fixture_path}")

        with fixture_path.open() as f:
            data = json.load(f)

        return AudioProfileModel(**data)

    def test_create_from_real_fixture(self, real_audio_profile: AudioProfileModel) -> None:
        """Test creating context from real audio profile fixture."""
        context = MovingHeadPlanningContext(
            audio_profile=real_audio_profile,
            fixtures=FixtureContext(count=4, groups=[]),
            available_templates=["template_a", "template_b"],
        )

        assert context.song_title == "Need A Favor"
        assert context.tempo is not None
        assert context.tempo > 0
        assert len(context.sections) > 0

    def test_for_prompt_with_real_fixture(self, real_audio_profile: AudioProfileModel) -> None:
        """Test for_prompt with real audio profile."""
        context = MovingHeadPlanningContext(
            audio_profile=real_audio_profile,
            fixtures=FixtureContext(count=4, groups=[]),
            available_templates=["template_a"],
        )

        prompt_data = context.for_prompt()

        # Should produce valid structure
        assert prompt_data["beat_grid"]["total_bars"] > 0
        assert len(prompt_data["song_structure"]["sections"]) > 0
