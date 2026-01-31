"""Unit tests for Lyrics agent models."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.audio.lyrics.models import (
    Issue,
    KeyPhrase,
    LyricContextModel,
    Provenance,
    Severity,
    SilentSection,
    StoryBeat,
)


class TestStoryBeat:
    """Test StoryBeat model validation."""

    def test_valid_story_beat(self):
        """Test valid story beat creation."""
        beat = StoryBeat(
            section_id="verse_1",
            timestamp_range=(1000, 5000),
            beat_type="setup",
            description="Hero begins journey to find missing star",
            visual_opportunity="Build from dim outline to bright hero spotlight",
        )

        assert beat.section_id == "verse_1"
        assert beat.timestamp_range == (1000, 5000)
        assert beat.beat_type == "setup"
        assert len(beat.description) >= 10
        assert len(beat.visual_opportunity) >= 10

    def test_all_beat_types_valid(self):
        """Test all allowed beat types."""
        valid_types = ["setup", "conflict", "climax", "resolution", "coda"]

        for beat_type in valid_types:
            beat = StoryBeat(
                section_id="test",
                timestamp_range=(1000, 2000),
                beat_type=beat_type,
                description="Test description here",
                visual_opportunity="Test visual hint here",
            )
            assert beat.beat_type == beat_type

    def test_invalid_beat_type(self):
        """Test invalid beat type raises error."""
        with pytest.raises(ValidationError, match=r"beat_type must be one of"):
            StoryBeat(
                section_id="verse_1",
                timestamp_range=(1000, 5000),
                beat_type="invalid_type",
                description="Test description",
                visual_opportunity="Test visual",
            )

    def test_negative_start_time(self):
        """Test negative start time raises error."""
        with pytest.raises(ValidationError, match=r"start_ms must be non-negative"):
            StoryBeat(
                section_id="verse_1",
                timestamp_range=(-1000, 5000),
                beat_type="setup",
                description="Test description",
                visual_opportunity="Test visual",
            )

    def test_end_before_start(self):
        """Test end_ms before start_ms raises error."""
        with pytest.raises(ValidationError, match=r"end_ms must be greater than start_ms"):
            StoryBeat(
                section_id="verse_1",
                timestamp_range=(5000, 1000),
                beat_type="setup",
                description="Test description",
                visual_opportunity="Test visual",
            )

    def test_end_equals_start(self):
        """Test end_ms equal to start_ms raises error."""
        with pytest.raises(ValidationError, match=r"end_ms must be greater than start_ms"):
            StoryBeat(
                section_id="verse_1",
                timestamp_range=(5000, 5000),
                beat_type="setup",
                description="Test description",
                visual_opportunity="Test visual",
            )

    def test_too_short_duration(self):
        """Test story beat shorter than 100ms raises error."""
        with pytest.raises(ValidationError, match=r"Story beat must be at least 100ms long"):
            StoryBeat(
                section_id="verse_1",
                timestamp_range=(5000, 5050),
                beat_type="setup",
                description="Test description",
                visual_opportunity="Test visual",
            )

    def test_description_too_short(self):
        """Test description shorter than 10 chars raises error."""
        with pytest.raises(ValidationError, match=r"String should have at least 10 characters"):
            StoryBeat(
                section_id="verse_1",
                timestamp_range=(1000, 5000),
                beat_type="setup",
                description="Short",
                visual_opportunity="Test visual opportunity",
            )

    def test_visual_opportunity_too_short(self):
        """Test visual_opportunity shorter than 10 chars raises error."""
        with pytest.raises(ValidationError, match=r"String should have at least 10 characters"):
            StoryBeat(
                section_id="verse_1",
                timestamp_range=(1000, 5000),
                beat_type="setup",
                description="Test description here",
                visual_opportunity="Short",
            )

    def test_story_beat_frozen(self):
        """Test StoryBeat is immutable (frozen)."""
        beat = StoryBeat(
            section_id="verse_1",
            timestamp_range=(1000, 5000),
            beat_type="setup",
            description="Test description",
            visual_opportunity="Test visual",
        )

        with pytest.raises(ValidationError):
            beat.beat_type = "climax"  # type: ignore[misc]


class TestKeyPhrase:
    """Test KeyPhrase model validation."""

    def test_valid_key_phrase(self):
        """Test valid key phrase creation."""
        phrase = KeyPhrase(
            text="Jingle bell rock",
            timestamp_ms=15000,
            section_id="chorus_1",
            visual_hint="Sharp white flash on 'rock' with mega tree burst",
            emphasis="HIGH",
        )

        assert phrase.text == "Jingle bell rock"
        assert phrase.timestamp_ms == 15000
        assert phrase.section_id == "chorus_1"
        assert len(phrase.visual_hint) >= 5
        assert phrase.emphasis == "HIGH"

    def test_all_emphasis_levels_valid(self):
        """Test all allowed emphasis levels."""
        valid_levels = ["LOW", "MED", "HIGH"]

        for emphasis in valid_levels:
            phrase = KeyPhrase(
                text="Test phrase",
                timestamp_ms=1000,
                section_id="test",
                visual_hint="Test visual hint",
                emphasis=emphasis,
            )
            assert phrase.emphasis == emphasis

    def test_default_emphasis(self):
        """Test default emphasis is MED."""
        phrase = KeyPhrase(
            text="Test phrase",
            timestamp_ms=1000,
            section_id="test",
            visual_hint="Test visual hint",
        )
        assert phrase.emphasis == "MED"

    def test_invalid_emphasis(self):
        """Test invalid emphasis raises error."""
        with pytest.raises(ValidationError, match=r"emphasis must be one of"):
            KeyPhrase(
                text="Test phrase",
                timestamp_ms=1000,
                section_id="test",
                visual_hint="Test visual hint",
                emphasis="EXTREME",
            )

    def test_empty_text(self):
        """Test empty text raises error."""
        with pytest.raises(ValidationError, match=r"String should have at least 1 character"):
            KeyPhrase(
                text="",
                timestamp_ms=1000,
                section_id="test",
                visual_hint="Test visual hint",
            )

    def test_negative_timestamp(self):
        """Test negative timestamp raises error."""
        with pytest.raises(ValidationError, match=r"Input should be greater than or equal to 0"):
            KeyPhrase(
                text="Test phrase",
                timestamp_ms=-100,
                section_id="test",
                visual_hint="Test visual hint",
            )

    def test_visual_hint_too_short(self):
        """Test visual_hint shorter than 5 chars raises error."""
        with pytest.raises(ValidationError, match=r"String should have at least 5 characters"):
            KeyPhrase(
                text="Test phrase",
                timestamp_ms=1000,
                section_id="test",
                visual_hint="Hi",
            )

    def test_key_phrase_frozen(self):
        """Test KeyPhrase is immutable (frozen)."""
        phrase = KeyPhrase(
            text="Test",
            timestamp_ms=1000,
            section_id="test",
            visual_hint="Test visual",
        )

        with pytest.raises(ValidationError):
            phrase.emphasis = "HIGH"  # type: ignore[misc]


class TestSilentSection:
    """Test SilentSection model validation."""

    def test_valid_silent_section(self):
        """Test valid silent section creation."""
        section = SilentSection(
            start_ms=10000,
            end_ms=15000,
            duration_ms=5000,
            section_id="intro",
        )

        assert section.start_ms == 10000
        assert section.end_ms == 15000
        assert section.duration_ms == 5000
        assert section.section_id == "intro"

    def test_silent_section_without_section_id(self):
        """Test silent section without section_id."""
        section = SilentSection(
            start_ms=10000,
            end_ms=15000,
            duration_ms=5000,
        )

        assert section.section_id is None

    def test_negative_start_ms(self):
        """Test negative start_ms raises error."""
        with pytest.raises(ValidationError, match=r"Input should be greater than or equal to 0"):
            SilentSection(
                start_ms=-1000,
                end_ms=5000,
                duration_ms=6000,
            )

    def test_end_before_start(self):
        """Test end_ms before start_ms raises error."""
        with pytest.raises(ValidationError, match=r"end_ms must be greater than start_ms"):
            SilentSection(
                start_ms=5000,
                end_ms=1000,
                duration_ms=4000,
            )

    def test_end_equals_start(self):
        """Test end_ms equal to start_ms raises error."""
        with pytest.raises(ValidationError, match=r"end_ms must be greater than start_ms"):
            SilentSection(
                start_ms=5000,
                end_ms=5000,
                duration_ms=0,
            )

    def test_duration_mismatch(self):
        """Test duration_ms not matching end_ms - start_ms raises error."""
        with pytest.raises(
            ValidationError,
            match=r"duration_ms must equal end_ms - start_ms, got 6000, expected 5000",
        ):
            SilentSection(
                start_ms=10000,
                end_ms=15000,
                duration_ms=6000,
            )

    def test_zero_duration(self):
        """Test zero duration raises error."""
        with pytest.raises(ValidationError, match=r"Input should be greater than 0"):
            SilentSection(
                start_ms=5000,
                end_ms=5000,
                duration_ms=0,
            )

    def test_silent_section_frozen(self):
        """Test SilentSection is immutable (frozen)."""
        section = SilentSection(
            start_ms=10000,
            end_ms=15000,
            duration_ms=5000,
        )

        with pytest.raises(ValidationError):
            section.duration_ms = 6000  # type: ignore[misc]


class TestLyricContextModel:
    """Test LyricContextModel validation."""

    def test_minimal_valid_model(self):
        """Test minimal valid lyric context model."""
        model = LyricContextModel(
            run_id="test-run-123",
            has_lyrics=False,
            vocal_coverage_pct=0.0,
        )

        assert model.run_id == "test-run-123"
        assert model.has_lyrics is False
        assert model.vocal_coverage_pct == 0.0
        assert model.themes == []
        assert model.mood_arc == "neutral"
        assert model.genre_markers == []
        assert model.has_narrative is False
        assert model.characters is None
        assert model.story_beats is None
        assert model.key_phrases == []
        assert model.recommended_visual_themes == []
        assert model.lyric_density == "MED"
        assert model.silent_sections == []
        assert model.provenance is None
        assert model.warnings == []

    def test_full_valid_model(self):
        """Test full valid lyric context model."""
        model = LyricContextModel(
            run_id="test-run-123",
            has_lyrics=True,
            themes=["redemption", "celebration", "hope"],
            mood_arc="somber → triumphant",
            genre_markers=["Christmas", "gospel", "traditional"],
            has_narrative=True,
            characters=["Santa", "Narrator"],
            story_beats=[
                StoryBeat(
                    section_id="verse_1",
                    timestamp_range=(1000, 10000),
                    beat_type="setup",
                    description="Santa begins his journey through the night",
                    visual_opportunity="Slow build from outline to full display",
                )
            ],
            key_phrases=[
                KeyPhrase(
                    text="Jingle bell rock",
                    timestamp_ms=15000,
                    section_id="chorus_1",
                    visual_hint="Sharp flash on 'rock'",
                    emphasis="HIGH",
                ),
                KeyPhrase(
                    text="Through the night",
                    timestamp_ms=25000,
                    section_id="verse_2",
                    visual_hint="Wave motion",
                    emphasis="MED",
                ),
                KeyPhrase(
                    text="Shining bright",
                    timestamp_ms=35000,
                    section_id="bridge",
                    visual_hint="Full brightness",
                    emphasis="HIGH",
                ),
                KeyPhrase(
                    text="Christmas time",
                    timestamp_ms=45000,
                    section_id="chorus_2",
                    visual_hint="Color pulse",
                    emphasis="MED",
                ),
                KeyPhrase(
                    text="Sleigh ride",
                    timestamp_ms=55000,
                    section_id="outro",
                    visual_hint="Sweep motion",
                    emphasis="LOW",
                ),
            ],
            recommended_visual_themes=[
                "Warm traditional colors",
                "Sweeping movements",
                "Star bursts",
            ],
            lyric_density="MED",
            vocal_coverage_pct=0.75,
            silent_sections=[
                SilentSection(
                    start_ms=0,
                    end_ms=5000,
                    duration_ms=5000,
                    section_id="intro",
                )
            ],
            provenance=Provenance(
                provider_id="openai",
                model_id="gpt-5.2",
                prompt_pack="lyrics",
                prompt_pack_version="2.0",
                framework_version="twinklr-agents-2.0",
                temperature=0.5,
            ),
        )

        assert model.has_lyrics is True
        assert len(model.themes) == 3
        assert len(model.story_beats) == 1  # type: ignore[arg-type]
        assert len(model.key_phrases) == 5
        assert len(model.silent_sections) == 1

    def test_themes_count_validation(self):
        """Test themes must be 2-5 items."""
        # Too few themes
        with pytest.raises(ValidationError, match=r"themes must contain 2-5 items, got 1"):
            LyricContextModel(
                run_id="test",
                has_lyrics=True,
                themes=["single_theme"],
                vocal_coverage_pct=0.5,
                key_phrases=[
                    KeyPhrase(
                        text="phrase1",
                        timestamp_ms=1000,
                        section_id="verse",
                        visual_hint="hint1",
                    )
                    for i in range(5)
                ],
                recommended_visual_themes=["theme1", "theme2", "theme3"],
            )

        # Too many themes
        with pytest.raises(ValidationError, match=r"themes must contain 2-5 items, got 6"):
            LyricContextModel(
                run_id="test",
                has_lyrics=True,
                themes=["theme1", "theme2", "theme3", "theme4", "theme5", "theme6"],
                vocal_coverage_pct=0.5,
                key_phrases=[
                    KeyPhrase(
                        text="phrase1",
                        timestamp_ms=1000,
                        section_id="verse",
                        visual_hint="hint1",
                    )
                    for i in range(5)
                ],
                recommended_visual_themes=["theme1", "theme2", "theme3"],
            )

    def test_key_phrases_count_validation(self):
        """Test key_phrases must be 5-10 items."""
        # Too few key phrases
        with pytest.raises(ValidationError, match=r"key_phrases must contain 5-10 items, got 3"):
            LyricContextModel(
                run_id="test",
                has_lyrics=True,
                themes=["theme1", "theme2"],
                vocal_coverage_pct=0.5,
                key_phrases=[
                    KeyPhrase(
                        text=f"phrase{i}",
                        timestamp_ms=1000 * i,
                        section_id="verse",
                        visual_hint=f"hint{i}",
                    )
                    for i in range(3)
                ],
                recommended_visual_themes=["theme1", "theme2", "theme3"],
            )

        # Too many key phrases
        with pytest.raises(ValidationError, match=r"key_phrases must contain 5-10 items, got 12"):
            LyricContextModel(
                run_id="test",
                has_lyrics=True,
                themes=["theme1", "theme2"],
                vocal_coverage_pct=0.5,
                key_phrases=[
                    KeyPhrase(
                        text=f"phrase{i}",
                        timestamp_ms=1000 * i,
                        section_id="verse",
                        visual_hint=f"hint{i}",
                    )
                    for i in range(12)
                ],
                recommended_visual_themes=["theme1", "theme2", "theme3"],
            )

    def test_visual_themes_count_validation(self):
        """Test recommended_visual_themes must be 3-5 items."""
        # Too few visual themes
        with pytest.raises(
            ValidationError, match=r"recommended_visual_themes must contain 3-5 items, got 2"
        ):
            LyricContextModel(
                run_id="test",
                has_lyrics=True,
                themes=["theme1", "theme2"],
                vocal_coverage_pct=0.5,
                key_phrases=[
                    KeyPhrase(
                        text=f"phrase{i}",
                        timestamp_ms=1000 * i,
                        section_id="verse",
                        visual_hint=f"hint{i}",
                    )
                    for i in range(5)
                ],
                recommended_visual_themes=["theme1", "theme2"],
            )

        # Too many visual themes
        with pytest.raises(
            ValidationError, match=r"recommended_visual_themes must contain 3-5 items, got 6"
        ):
            LyricContextModel(
                run_id="test",
                has_lyrics=True,
                themes=["theme1", "theme2"],
                vocal_coverage_pct=0.5,
                key_phrases=[
                    KeyPhrase(
                        text=f"phrase{i}",
                        timestamp_ms=1000 * i,
                        section_id="verse",
                        visual_hint=f"hint{i}",
                    )
                    for i in range(5)
                ],
                recommended_visual_themes=["t1", "t2", "t3", "t4", "t5", "t6"],
            )

    def test_lyric_density_validation(self):
        """Test lyric_density must be SPARSE/MED/DENSE."""
        with pytest.raises(ValidationError, match=r"lyric_density must be one of"):
            LyricContextModel(
                run_id="test",
                has_lyrics=True,
                vocal_coverage_pct=0.5,
                lyric_density="INVALID",
            )

    def test_vocal_coverage_range(self):
        """Test vocal_coverage_pct must be 0.0-1.0."""
        # Below minimum
        with pytest.raises(ValidationError, match=r"Input should be greater than or equal to 0"):
            LyricContextModel(
                run_id="test",
                has_lyrics=True,
                vocal_coverage_pct=-0.1,
            )

        # Above maximum
        with pytest.raises(ValidationError, match=r"Input should be less than or equal to 1"):
            LyricContextModel(
                run_id="test",
                has_lyrics=True,
                vocal_coverage_pct=1.5,
            )

    def test_model_forbids_extra_fields(self):
        """Test model forbids extra fields."""
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            LyricContextModel(
                run_id="test",
                has_lyrics=False,
                vocal_coverage_pct=0.0,
                extra_field="not_allowed",  # type: ignore[call-arg]
            )


class TestSeverityEnum:
    """Test Severity enum."""

    def test_severity_values(self):
        """Test all severity values."""
        assert Severity.INFO.value == "INFO"
        assert Severity.WARN.value == "WARN"
        assert Severity.ERROR.value == "ERROR"


class TestIssue:
    """Test Issue model."""

    def test_valid_issue(self):
        """Test valid issue creation."""
        issue = Issue(
            severity=Severity.WARN,
            code="LOW_COVERAGE",
            message="Lyric coverage below 50%",
            path="$.vocal_coverage_pct",
            hint="Consider marking as instrumental-heavy",
        )

        assert issue.severity == Severity.WARN
        assert issue.code == "LOW_COVERAGE"
        assert issue.message == "Lyric coverage below 50%"
        assert issue.path == "$.vocal_coverage_pct"
        assert issue.hint == "Consider marking as instrumental-heavy"

    def test_issue_frozen(self):
        """Test Issue is immutable (frozen)."""
        issue = Issue(
            severity=Severity.INFO,
            code="TEST",
            message="Test message",
        )

        with pytest.raises(ValidationError):
            issue.severity = Severity.ERROR  # type: ignore[misc]


class TestProvenance:
    """Test Provenance model."""

    def test_valid_provenance(self):
        """Test valid provenance creation."""
        provenance = Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="lyrics",
            prompt_pack_version="2.0",
            framework_version="twinklr-agents-2.0",
            temperature=0.5,
        )

        assert provenance.provider_id == "openai"
        assert provenance.model_id == "gpt-5.2"
        assert provenance.temperature == 0.5
        assert provenance.created_at is not None

    def test_provenance_frozen(self):
        """Test Provenance is immutable (frozen)."""
        provenance = Provenance(
            provider_id="openai",
            model_id="gpt-5.2",
            prompt_pack="lyrics",
            prompt_pack_version="2.0",
            framework_version="twinklr-agents-2.0",
            temperature=0.5,
        )

        with pytest.raises(ValidationError):
            provenance.temperature = 0.7  # type: ignore[misc]
