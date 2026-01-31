"""Unit tests for section detection Pydantic models."""


from pydantic import ValidationError
import pytest

from twinklr.core.audio.structure.models import Section, SectionDiagnostics, SectioningPreset


class TestSection:
    """Tests for Section model."""

    def test_valid_section(self):
        """Test creating a valid section."""
        section = Section(
            section_id=0,
            start_s=0.0,
            end_s=15.5,
            label="intro",
            confidence=0.85,
            energy=0.3,
            repetition=0.2,
        )
        assert section.section_id == 0
        assert section.start_s == 0.0
        assert section.end_s == 15.5
        assert section.label == "intro"
        assert section.confidence == 0.85
        assert section.energy == 0.3
        assert section.repetition == 0.2
        assert section.duration_s == 15.5

    def test_section_with_context_flags(self):
        """Test section with drop/build flags."""
        section = Section(
            section_id=1,
            start_s=15.5,
            end_s=30.0,
            label="chorus",
            energy=0.8,
            repetition=0.9,
            has_drop=True,
            has_build=False,
        )
        assert section.has_drop is True
        assert section.has_build is False

    def test_section_with_optional_fields(self):
        """Test section with vocal_density and harmonic_complexity."""
        section = Section(
            section_id=2,
            start_s=30.0,
            end_s=45.0,
            label="verse",
            energy=0.5,
            repetition=0.6,
            vocal_density=0.8,
            harmonic_complexity=0.4,
        )
        assert section.vocal_density == 0.8
        assert section.harmonic_complexity == 0.4

    def test_section_end_before_start_fails(self):
        """Test that end_s must be > start_s."""
        with pytest.raises(ValidationError, match=r"end_s.*must be greater than start_s"):
            Section(
                section_id=0,
                start_s=10.0,
                end_s=5.0,  # Invalid: end before start
                label="verse",
                energy=0.5,
                repetition=0.5,
            )

    def test_section_end_equals_start_fails(self):
        """Test that end_s must be strictly greater than start_s."""
        with pytest.raises(ValidationError, match=r"end_s.*must be greater than start_s"):
            Section(
                section_id=0,
                start_s=10.0,
                end_s=10.0,  # Invalid: zero duration
                label="verse",
                energy=0.5,
                repetition=0.5,
            )

    def test_section_invalid_label(self):
        """Test that invalid labels are rejected."""
        with pytest.raises(ValidationError):
            Section(
                section_id=0,
                start_s=0.0,
                end_s=10.0,
                label="invalid_label",  # type: ignore
                energy=0.5,
                repetition=0.5,
            )

    def test_section_confidence_out_of_range(self):
        """Test that confidence must be in [0, 1]."""
        with pytest.raises(ValidationError):
            Section(
                section_id=0,
                start_s=0.0,
                end_s=10.0,
                label="verse",
                confidence=1.5,  # Invalid: > 1
                energy=0.5,
                repetition=0.5,
            )

    def test_section_energy_out_of_range(self):
        """Test that energy must be in [0, 1]."""
        with pytest.raises(ValidationError):
            Section(
                section_id=0,
                start_s=0.0,
                end_s=10.0,
                label="verse",
                energy=-0.1,  # Invalid: < 0
                repetition=0.5,
            )

    def test_section_is_frozen(self):
        """Test that Section is immutable (frozen)."""
        section = Section(
            section_id=0,
            start_s=0.0,
            end_s=10.0,
            label="verse",
            energy=0.5,
            repetition=0.5,
        )
        with pytest.raises((ValidationError, AttributeError)):
            section.label = "chorus"  # type: ignore

    def test_section_duration_property(self):
        """Test duration_s computed property."""
        section = Section(
            section_id=0,
            start_s=10.5,
            end_s=25.3,
            label="chorus",
            energy=0.7,
            repetition=0.8,
        )
        assert section.duration_s == pytest.approx(14.8)


class TestSectionDiagnostics:
    """Tests for SectionDiagnostics model."""

    def test_valid_diagnostics(self):
        """Test creating valid diagnostics."""
        diagnostics = SectionDiagnostics(
            tempo_bpm=120.0,
            beat_times_s=[0.0, 0.5, 1.0, 1.5, 2.0],
            duration_s=30.0,
            novelty=[0.1, 0.8, 0.3, 0.2, 0.4],
            repetition=[0.5, 0.6, 0.7, 0.6, 0.5],
            rms=[0.4, 0.5, 0.6, 0.5, 0.4],
            onset=[0.3, 0.7, 0.4, 0.3, 0.5],
            boundary_beats=[0, 2, 4],
            boundary_strengths=[1.0, 0.8, 0.6],
        )
        assert diagnostics.tempo_bpm == 120.0
        assert len(diagnostics.beat_times_s) == 5
        assert len(diagnostics.novelty) == 5
        assert diagnostics.boundary_beats == [0, 2, 4]

    def test_diagnostics_with_optional_fields(self):
        """Test diagnostics with bar times and SSM."""
        diagnostics = SectionDiagnostics(
            tempo_bpm=120.0,
            beat_times_s=[0.0, 0.5, 1.0],
            bar_times_s=[0.0, 2.0],
            duration_s=30.0,
            novelty=[0.1, 0.8, 0.3],
            repetition=[0.5, 0.6, 0.7],
            rms=[0.4, 0.5, 0.6],
            onset=[0.3, 0.7, 0.4],
            boundary_beats=[0, 2],
            boundary_strengths=[1.0, 0.8],
            ssm=[[1.0, 0.5, 0.3], [0.5, 1.0, 0.6], [0.3, 0.6, 1.0]],
        )
        assert diagnostics.bar_times_s == [0.0, 2.0]
        assert len(diagnostics.ssm) == 3  # type: ignore

    def test_diagnostics_curve_length_mismatch_fails(self):
        """Test that curves must match beat grid length."""
        with pytest.raises(ValidationError, match=r"Curve length.*must match beat grid"):
            SectionDiagnostics(
                tempo_bpm=120.0,
                beat_times_s=[0.0, 0.5, 1.0, 1.5],  # 4 beats
                duration_s=30.0,
                novelty=[0.1, 0.8, 0.3],  # 3 values - mismatch!
                repetition=[0.5, 0.6, 0.7, 0.6],
                rms=[0.4, 0.5, 0.6, 0.5],
                onset=[0.3, 0.7, 0.4, 0.3],
                boundary_beats=[0, 2],
                boundary_strengths=[1.0, 0.8],
            )


class TestSectioningPreset:
    """Tests for SectioningPreset model."""

    def test_valid_preset(self):
        """Test creating a valid preset."""
        preset = SectioningPreset(
            genre="edm",
            min_sections=12,
            max_sections=18,
            min_len_beats=16,
            novelty_L_beats=16,
            peak_delta=0.07,
            pre_avg=12,
            post_avg=12,
        )
        assert preset.genre == "edm"
        assert preset.min_sections == 12
        assert preset.max_sections == 18
        assert preset.min_len_beats == 16

    def test_preset_with_custom_context_weights(self):
        """Test preset with custom context weights."""
        preset = SectioningPreset(
            genre="pop",
            min_sections=14,
            max_sections=20,
            min_len_beats=12,
            novelty_L_beats=12,
            peak_delta=0.06,
            pre_avg=10,
            post_avg=10,
            context_weights={
                "drops_weight": 0.8,
                "builds_weight": 0.6,
                "vocals_weight": 0.9,
                "chords_weight": 0.5,
            },
        )
        assert preset.context_weights["drops_weight"] == 0.8
        assert preset.context_weights["vocals_weight"] == 0.9

    def test_preset_default_context_weights(self):
        """Test that context weights have sensible defaults."""
        preset = SectioningPreset(
            genre="test",
            min_sections=10,
            max_sections=20,
            min_len_beats=12,
            novelty_L_beats=12,
            peak_delta=0.05,
            pre_avg=10,
            post_avg=10,
        )
        assert "drops_weight" in preset.context_weights
        assert "builds_weight" in preset.context_weights
        assert 0.0 <= preset.context_weights["drops_weight"] <= 1.0

    def test_preset_max_less_than_min_fails(self):
        """Test that max_sections must be >= min_sections."""
        with pytest.raises(ValidationError, match=r"max_sections.*must be >= min_sections"):
            SectioningPreset(
                genre="test",
                min_sections=20,
                max_sections=10,  # Invalid: max < min
                min_len_beats=12,
                novelty_L_beats=12,
                peak_delta=0.05,
                pre_avg=10,
                post_avg=10,
            )

    def test_preset_invalid_context_weight(self):
        """Test that context weights must be in [0, 1]."""
        with pytest.raises(ValidationError, match=r"Weight.*must be in"):
            SectioningPreset(
                genre="test",
                min_sections=10,
                max_sections=20,
                min_len_beats=12,
                novelty_L_beats=12,
                peak_delta=0.05,
                pre_avg=10,
                post_avg=10,
                context_weights={
                    "drops_weight": 1.5,  # Invalid: > 1
                },
            )

    def test_preset_is_frozen(self):
        """Test that preset is immutable."""
        preset = SectioningPreset(
            genre="pop",
            min_sections=14,
            max_sections=20,
            min_len_beats=12,
            novelty_L_beats=12,
            peak_delta=0.06,
            pre_avg=10,
            post_avg=10,
        )
        with pytest.raises((ValidationError, AttributeError)):
            preset.min_sections = 10  # type: ignore
