"""Tests for EnergyProfile models."""

from pydantic import ValidationError
import pytest


def test_macro_energy_enum():
    """Test MacroEnergy enum values."""
    from twinklr.core.agents.audio.profile.models import MacroEnergy

    assert MacroEnergy.LOW == "LOW"
    assert MacroEnergy.MED == "MED"
    assert MacroEnergy.HIGH == "HIGH"
    assert MacroEnergy.DYNAMIC == "DYNAMIC"
    assert list(MacroEnergy) == [
        MacroEnergy.LOW,
        MacroEnergy.MED,
        MacroEnergy.HIGH,
        MacroEnergy.DYNAMIC,
    ]


def test_energy_point_valid():
    """Test EnergyPoint with valid data."""
    from twinklr.core.agents.audio.profile.models import EnergyPoint

    point = EnergyPoint(t_ms=1000, energy_0_1=0.75)

    assert point.t_ms == 1000
    assert point.energy_0_1 == 0.75


def test_energy_point_t_ms_validation():
    """Test EnergyPoint t_ms must be >= 0."""
    from twinklr.core.agents.audio.profile.models import EnergyPoint

    # Valid: >= 0
    EnergyPoint(t_ms=0, energy_0_1=0.5)
    EnergyPoint(t_ms=1000, energy_0_1=0.5)

    # Invalid: < 0
    with pytest.raises(ValidationError):
        EnergyPoint(t_ms=-1, energy_0_1=0.5)


def test_energy_point_energy_validation():
    """Test EnergyPoint energy_0_1 must be in [0, 1]."""
    from twinklr.core.agents.audio.profile.models import EnergyPoint

    # Valid: [0, 1]
    EnergyPoint(t_ms=0, energy_0_1=0.0)
    EnergyPoint(t_ms=0, energy_0_1=0.5)
    EnergyPoint(t_ms=0, energy_0_1=1.0)

    # Invalid: < 0
    with pytest.raises(ValidationError):
        EnergyPoint(t_ms=0, energy_0_1=-0.1)

    # Invalid: > 1
    with pytest.raises(ValidationError):
        EnergyPoint(t_ms=0, energy_0_1=1.1)


def test_energy_point_frozen():
    """Test EnergyPoint is frozen (immutable)."""
    from twinklr.core.agents.audio.profile.models import EnergyPoint

    point = EnergyPoint(t_ms=1000, energy_0_1=0.75)

    with pytest.raises(ValidationError):
        point.energy_0_1 = 0.5


def test_energy_point_extra_forbid():
    """Test EnergyPoint forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import EnergyPoint

    with pytest.raises(ValidationError) as exc_info:
        EnergyPoint(t_ms=1000, energy_0_1=0.75, extra="not allowed")

    assert "extra" in str(exc_info.value).lower()


def test_energy_peak_valid():
    """Test EnergyPeak with valid data."""
    from twinklr.core.agents.audio.profile.models import EnergyPeak

    peak = EnergyPeak(start_ms=10000, end_ms=15000, energy=0.95)

    assert peak.start_ms == 10000
    assert peak.end_ms == 15000
    assert peak.energy == 0.95


def test_energy_peak_timing_validation():
    """Test EnergyPeak timing constraints."""
    from twinklr.core.agents.audio.profile.models import EnergyPeak

    # start_ms must be >= 0
    with pytest.raises(ValidationError):
        EnergyPeak(start_ms=-1, end_ms=1000, energy=0.9)

    # end_ms must be > 0
    with pytest.raises(ValidationError):
        EnergyPeak(start_ms=0, end_ms=0, energy=0.9)


def test_energy_peak_end_after_start():
    """Test EnergyPeak end_ms must be > start_ms."""
    from twinklr.core.agents.audio.profile.models import EnergyPeak

    # Valid: end > start
    EnergyPeak(start_ms=0, end_ms=1000, energy=0.9)
    EnergyPeak(start_ms=5000, end_ms=10000, energy=0.9)

    # Invalid: end <= start
    with pytest.raises(ValidationError) as exc_info:
        EnergyPeak(start_ms=1000, end_ms=1000, energy=0.9)
    assert "end_ms must be greater than start_ms" in str(exc_info.value).lower()

    with pytest.raises(ValidationError) as exc_info:
        EnergyPeak(start_ms=2000, end_ms=1000, energy=0.9)
    assert "end_ms must be greater than start_ms" in str(exc_info.value).lower()


def test_energy_peak_energy_validation():
    """Test EnergyPeak energy must be in [0, 1]."""
    from twinklr.core.agents.audio.profile.models import EnergyPeak

    # Valid: [0, 1]
    EnergyPeak(start_ms=0, end_ms=1000, energy=0.0)
    EnergyPeak(start_ms=0, end_ms=1000, energy=0.5)
    EnergyPeak(start_ms=0, end_ms=1000, energy=1.0)

    # Invalid: < 0
    with pytest.raises(ValidationError):
        EnergyPeak(start_ms=0, end_ms=1000, energy=-0.1)

    # Invalid: > 1
    with pytest.raises(ValidationError):
        EnergyPeak(start_ms=0, end_ms=1000, energy=1.1)


def test_energy_peak_frozen():
    """Test EnergyPeak is frozen (immutable)."""
    from twinklr.core.agents.audio.profile.models import EnergyPeak

    peak = EnergyPeak(start_ms=0, end_ms=1000, energy=0.9)

    with pytest.raises(ValidationError):
        peak.energy = 0.5


def test_energy_peak_extra_forbid():
    """Test EnergyPeak forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import EnergyPeak

    with pytest.raises(ValidationError) as exc_info:
        EnergyPeak(start_ms=0, end_ms=1000, energy=0.9, extra="not allowed")

    assert "extra" in str(exc_info.value).lower()


def test_section_energy_profile_valid():
    """Test SectionEnergyProfile with valid data."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        SectionEnergyProfile,
    )

    curve = [
        EnergyPoint(t_ms=0, energy_0_1=0.3),
        EnergyPoint(t_ms=5000, energy_0_1=0.7),
        EnergyPoint(t_ms=10000, energy_0_1=0.9),
    ]

    profile = SectionEnergyProfile(
        section_id="chorus_1",
        start_ms=0,
        end_ms=10000,
        energy_curve=curve,
        mean_energy=0.63,
        peak_energy=0.9,
        characteristics=["building", "peak"],
    )

    assert profile.section_id == "chorus_1"
    assert profile.start_ms == 0
    assert profile.end_ms == 10000
    assert len(profile.energy_curve) == 3
    assert profile.mean_energy == 0.63
    assert profile.peak_energy == 0.9
    assert profile.characteristics == ["building", "peak"]


def test_section_energy_profile_minimal_curve():
    """Test SectionEnergyProfile with minimum curve points."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        SectionEnergyProfile,
    )

    # Minimum 3 points per spec
    curve = [
        EnergyPoint(t_ms=0, energy_0_1=0.5),
        EnergyPoint(t_ms=5000, energy_0_1=0.6),
        EnergyPoint(t_ms=10000, energy_0_1=0.5),
    ]

    profile = SectionEnergyProfile(
        section_id="verse_1",
        start_ms=0,
        end_ms=10000,
        energy_curve=curve,
        mean_energy=0.53,
        peak_energy=0.6,
    )

    assert len(profile.energy_curve) == 3


def test_section_energy_profile_frozen():
    """Test SectionEnergyProfile is frozen (immutable)."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        SectionEnergyProfile,
    )

    curve = [
        EnergyPoint(t_ms=0, energy_0_1=0.5),
        EnergyPoint(t_ms=5000, energy_0_1=0.6),
        EnergyPoint(t_ms=10000, energy_0_1=0.5),
    ]

    profile = SectionEnergyProfile(
        section_id="verse_1",
        start_ms=0,
        end_ms=10000,
        energy_curve=curve,
        mean_energy=0.53,
        peak_energy=0.6,
    )

    # Should NOT be able to modify (frozen)
    with pytest.raises(ValidationError):
        profile.mean_energy = 0.7


def test_section_energy_profile_extra_forbid():
    """Test SectionEnergyProfile forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        SectionEnergyProfile,
    )

    curve = [
        EnergyPoint(t_ms=0, energy_0_1=0.5),
        EnergyPoint(t_ms=5000, energy_0_1=0.6),
        EnergyPoint(t_ms=10000, energy_0_1=0.5),
    ]

    with pytest.raises(ValidationError) as exc_info:
        SectionEnergyProfile(
            section_id="verse_1",
            start_ms=0,
            end_ms=10000,
            energy_curve=curve,
            mean_energy=0.53,
            peak_energy=0.6,
            extra="not allowed",
        )

    assert "extra" in str(exc_info.value).lower()


def test_energy_profile_valid():
    """Test EnergyProfile with valid data."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPeak,
        EnergyPoint,
        EnergyProfile,
        MacroEnergy,
        SectionEnergyProfile,
    )

    section_profiles = [
        SectionEnergyProfile(
            section_id="verse_1",
            start_ms=0,
            end_ms=20000,
            energy_curve=[
                EnergyPoint(t_ms=0, energy_0_1=0.4),
                EnergyPoint(t_ms=10000, energy_0_1=0.5),
                EnergyPoint(t_ms=20000, energy_0_1=0.5),
            ],
            mean_energy=0.47,
            peak_energy=0.5,
        ),
        SectionEnergyProfile(
            section_id="chorus_1",
            start_ms=20000,
            end_ms=50000,
            energy_curve=[
                EnergyPoint(t_ms=20000, energy_0_1=0.7),
                EnergyPoint(t_ms=30000, energy_0_1=0.9),
                EnergyPoint(t_ms=40000, energy_0_1=0.85),
                EnergyPoint(t_ms=50000, energy_0_1=0.8),
            ],
            mean_energy=0.81,
            peak_energy=0.9,
            characteristics=["peak", "sustained"],
        ),
    ]

    peaks = [EnergyPeak(start_ms=25000, end_ms=35000, energy=0.9)]

    profile = EnergyProfile(
        macro_energy=MacroEnergy.DYNAMIC,
        section_profiles=section_profiles,
        peaks=peaks,
        overall_mean=0.64,
        energy_confidence=0.92,
    )

    assert profile.macro_energy == MacroEnergy.DYNAMIC
    assert len(profile.section_profiles) == 2
    assert len(profile.peaks) == 1
    assert profile.overall_mean == 0.64
    assert profile.energy_confidence == 0.92


def test_energy_profile_empty_peaks():
    """Test EnergyProfile with no peaks."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        EnergyProfile,
        MacroEnergy,
        SectionEnergyProfile,
    )

    section_profiles = [
        SectionEnergyProfile(
            section_id="verse_1",
            start_ms=0,
            end_ms=20000,
            energy_curve=[
                EnergyPoint(t_ms=0, energy_0_1=0.4),
                EnergyPoint(t_ms=10000, energy_0_1=0.4),
                EnergyPoint(t_ms=20000, energy_0_1=0.4),
            ],
            mean_energy=0.4,
            peak_energy=0.4,
        ),
    ]

    profile = EnergyProfile(
        macro_energy=MacroEnergy.LOW,
        section_profiles=section_profiles,
        peaks=[],
        overall_mean=0.4,
        energy_confidence=0.85,
    )

    assert len(profile.peaks) == 0


def test_energy_profile_not_frozen():
    """Test EnergyProfile is mutable."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        EnergyProfile,
        MacroEnergy,
        SectionEnergyProfile,
    )

    section_profiles = [
        SectionEnergyProfile(
            section_id="verse_1",
            start_ms=0,
            end_ms=20000,
            energy_curve=[
                EnergyPoint(t_ms=0, energy_0_1=0.4),
                EnergyPoint(t_ms=10000, energy_0_1=0.4),
                EnergyPoint(t_ms=20000, energy_0_1=0.4),
            ],
            mean_energy=0.4,
            peak_energy=0.4,
        ),
    ]

    profile = EnergyProfile(
        macro_energy=MacroEnergy.LOW,
        section_profiles=section_profiles,
        peaks=[],
        overall_mean=0.4,
        energy_confidence=0.85,
    )

    # Should be able to modify
    profile.macro_energy = MacroEnergy.MED
    assert profile.macro_energy == MacroEnergy.MED


def test_energy_profile_extra_forbid():
    """Test EnergyProfile forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        EnergyProfile,
        MacroEnergy,
        SectionEnergyProfile,
    )

    section_profiles = [
        SectionEnergyProfile(
            section_id="verse_1",
            start_ms=0,
            end_ms=20000,
            energy_curve=[
                EnergyPoint(t_ms=0, energy_0_1=0.4),
                EnergyPoint(t_ms=10000, energy_0_1=0.4),
                EnergyPoint(t_ms=20000, energy_0_1=0.4),
            ],
            mean_energy=0.4,
            peak_energy=0.4,
        ),
    ]

    with pytest.raises(ValidationError) as exc_info:
        EnergyProfile(
            macro_energy=MacroEnergy.LOW,
            section_profiles=section_profiles,
            peaks=[],
            overall_mean=0.4,
            energy_confidence=0.85,
            extra="not allowed",
        )

    assert "extra" in str(exc_info.value).lower()


def test_section_energy_profile_timing_validation():
    """Test SectionEnergyProfile end_ms must be > start_ms."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        SectionEnergyProfile,
    )

    curve = [
        EnergyPoint(t_ms=0, energy_0_1=0.5),
        EnergyPoint(t_ms=5000, energy_0_1=0.6),
        EnergyPoint(t_ms=10000, energy_0_1=0.5),
    ]

    # Valid
    SectionEnergyProfile(
        section_id="test",
        start_ms=0,
        end_ms=10000,
        energy_curve=curve,
        mean_energy=0.53,
        peak_energy=0.6,
    )

    # Invalid: end <= start
    with pytest.raises(ValidationError) as exc_info:
        SectionEnergyProfile(
            section_id="test",
            start_ms=10000,
            end_ms=10000,
            energy_curve=curve,
            mean_energy=0.53,
            peak_energy=0.6,
        )
    assert "end_ms must be greater than start_ms" in str(exc_info.value).lower()


def test_section_energy_profile_characteristics_optional():
    """Test SectionEnergyProfile characteristics field is optional."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        SectionEnergyProfile,
    )

    curve = [
        EnergyPoint(t_ms=0, energy_0_1=0.5),
        EnergyPoint(t_ms=5000, energy_0_1=0.6),
        EnergyPoint(t_ms=10000, energy_0_1=0.5),
    ]

    # Without characteristics
    profile1 = SectionEnergyProfile(
        section_id="test",
        start_ms=0,
        end_ms=10000,
        energy_curve=curve,
        mean_energy=0.53,
        peak_energy=0.6,
    )
    assert profile1.characteristics == []

    # With characteristics
    profile2 = SectionEnergyProfile(
        section_id="test",
        start_ms=0,
        end_ms=10000,
        energy_curve=curve,
        mean_energy=0.53,
        peak_energy=0.6,
        characteristics=["building", "peak"],
    )
    assert profile2.characteristics == ["building", "peak"]


def test_section_energy_profile_curve_length_validation():
    """Test SectionEnergyProfile energy_curve length must be 3-15."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        SectionEnergyProfile,
    )

    # Too short (< 3)
    with pytest.raises(ValidationError):
        SectionEnergyProfile(
            section_id="test",
            start_ms=0,
            end_ms=10000,
            energy_curve=[
                EnergyPoint(t_ms=0, energy_0_1=0.5),
                EnergyPoint(t_ms=10000, energy_0_1=0.5),
            ],
            mean_energy=0.5,
            peak_energy=0.5,
        )

    # Too long (> 15)
    with pytest.raises(ValidationError):
        SectionEnergyProfile(
            section_id="test",
            start_ms=0,
            end_ms=160000,
            energy_curve=[EnergyPoint(t_ms=i * 10000, energy_0_1=0.5) for i in range(16)],
            mean_energy=0.5,
            peak_energy=0.5,
        )


def test_energy_profile_confidence_validation():
    """Test EnergyProfile confidence must be in [0, 1]."""
    from twinklr.core.agents.audio.profile.models import (
        EnergyPoint,
        EnergyProfile,
        MacroEnergy,
        SectionEnergyProfile,
    )

    section_profiles = [
        SectionEnergyProfile(
            section_id="v1",
            start_ms=0,
            end_ms=10000,
            energy_curve=[
                EnergyPoint(t_ms=0, energy_0_1=0.5),
                EnergyPoint(t_ms=5000, energy_0_1=0.5),
                EnergyPoint(t_ms=10000, energy_0_1=0.5),
            ],
            mean_energy=0.5,
            peak_energy=0.5,
        ),
    ]

    # Valid
    EnergyProfile(
        macro_energy=MacroEnergy.LOW,
        section_profiles=section_profiles,
        peaks=[],
        overall_mean=0.5,
        energy_confidence=0.0,
    )
    EnergyProfile(
        macro_energy=MacroEnergy.LOW,
        section_profiles=section_profiles,
        peaks=[],
        overall_mean=0.5,
        energy_confidence=1.0,
    )

    # Invalid: < 0
    with pytest.raises(ValidationError):
        EnergyProfile(
            macro_energy=MacroEnergy.LOW,
            section_profiles=section_profiles,
            peaks=[],
            overall_mean=0.5,
            energy_confidence=-0.1,
        )

    # Invalid: > 1
    with pytest.raises(ValidationError):
        EnergyProfile(
            macro_energy=MacroEnergy.LOW,
            section_profiles=section_profiles,
            peaks=[],
            overall_mean=0.5,
            energy_confidence=1.1,
        )
