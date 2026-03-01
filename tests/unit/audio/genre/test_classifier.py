"""Unit tests for GenreClassifier.

Tests are written first (TDD) before the implementation. They cover:
- Feature-driven genre classification heuristics
- All GenreFamily enum values being reachable
- Confidence scores in valid range
- GenreResult being a frozen dataclass
- features_used tuple being populated
"""

from __future__ import annotations

import dataclasses

import pytest

from twinklr.core.audio.genre import GenreClassifier, GenreFamily, GenreResult


class TestGenreFamily:
    """Tests for GenreFamily enum."""

    def test_all_members_have_string_values(self) -> None:
        """All GenreFamily members must be non-empty strings."""
        for member in GenreFamily:
            assert isinstance(member.value, str)
            assert len(member.value) > 0

    def test_expected_families_present(self) -> None:
        """Core genre families must all exist."""
        expected = {
            "electronic",
            "rock",
            "pop",
            "classical",
            "hiphop",
            "country",
            "jazz",
            "holiday",
            "unknown",
        }
        actual = {m.value for m in GenreFamily}
        assert expected == actual

    def test_all_genre_families_reachable(self) -> None:
        """Every GenreFamily value must be reachable via the classifier using crafted inputs."""
        # electronic: fast tempo, high onset rate, low harmonic ratio
        result_electronic = GenreClassifier().classify(
            tempo=135.0,
            spectral_centroid_mean=5000.0,
            spectral_bandwidth_mean=3000.0,
            onset_rate=8.0,
            harmonic_ratio=0.2,
            chroma_std=0.3,
            dynamic_range=6.0,
            duration_ms=200_000,
        )
        assert result_electronic.primary == GenreFamily.ELECTRONIC

        # rock: fast tempo, mid-high onset rate, low harmonic ratio, wide bandwidth
        result_rock = GenreClassifier().classify(
            tempo=145.0,
            spectral_centroid_mean=4500.0,
            spectral_bandwidth_mean=3800.0,
            onset_rate=6.0,
            harmonic_ratio=0.25,
            chroma_std=0.35,
            dynamic_range=18.0,
            duration_ms=220_000,
        )
        assert result_rock.primary == GenreFamily.ROCK

        # classical: slow tempo, low onset rate, high harmonic ratio, high dynamic range
        result_classical = GenreClassifier().classify(
            tempo=60.0,
            spectral_centroid_mean=1200.0,
            spectral_bandwidth_mean=1000.0,
            onset_rate=0.5,
            harmonic_ratio=0.9,
            chroma_std=0.25,
            dynamic_range=40.0,
            duration_ms=300_000,
        )
        assert result_classical.primary == GenreFamily.CLASSICAL

        # pop: medium tempo, balanced features, low chroma_std
        result_pop = GenreClassifier().classify(
            tempo=110.0,
            spectral_centroid_mean=2800.0,
            spectral_bandwidth_mean=2200.0,
            onset_rate=3.0,
            harmonic_ratio=0.55,
            chroma_std=0.15,
            dynamic_range=12.0,
            duration_ms=210_000,
        )
        assert result_pop.primary == GenreFamily.POP

        # hiphop: mid tempo, heavy bass emphasis (low centroid), medium onset
        result_hiphop = GenreClassifier().classify(
            tempo=90.0,
            spectral_centroid_mean=800.0,
            spectral_bandwidth_mean=1400.0,
            onset_rate=4.5,
            harmonic_ratio=0.35,
            chroma_std=0.2,
            dynamic_range=10.0,
            duration_ms=195_000,
        )
        assert result_hiphop.primary == GenreFamily.HIPHOP

        # jazz: medium tempo, high chroma_std (tonal variety)
        result_jazz = GenreClassifier().classify(
            tempo=100.0,
            spectral_centroid_mean=2500.0,
            spectral_bandwidth_mean=2000.0,
            onset_rate=2.5,
            harmonic_ratio=0.65,
            chroma_std=0.7,
            dynamic_range=20.0,
            duration_ms=280_000,
        )
        assert result_jazz.primary == GenreFamily.JAZZ

        # country: medium tempo, mid centroid, medium harmonic ratio, guitar strumming onset
        result_country = GenreClassifier().classify(
            tempo=100.0,
            spectral_centroid_mean=2000.0,
            spectral_bandwidth_mean=1800.0,
            onset_rate=3.5,
            harmonic_ratio=0.6,
            chroma_std=0.3,
            dynamic_range=15.0,
            duration_ms=190_000,
        )
        assert result_country.primary == GenreFamily.COUNTRY

        # holiday: slow tempo, high harmonic ratio, low onset rate (similar to classical but different)
        result_holiday = GenreClassifier().classify(
            tempo=70.0,
            spectral_centroid_mean=1800.0,
            spectral_bandwidth_mean=1500.0,
            onset_rate=1.0,
            harmonic_ratio=0.75,
            chroma_std=0.2,
            dynamic_range=12.0,
            duration_ms=170_000,
        )
        assert result_holiday.primary == GenreFamily.HOLIDAY

        # unknown: default / zero / ambiguous features
        result_unknown = GenreClassifier().classify(
            tempo=0.0,
            spectral_centroid_mean=0.0,
            spectral_bandwidth_mean=0.0,
            onset_rate=0.0,
            harmonic_ratio=0.0,
            chroma_std=0.0,
            dynamic_range=0.0,
            duration_ms=0,
        )
        assert result_unknown.primary == GenreFamily.UNKNOWN


class TestGenreResult:
    """Tests for GenreResult dataclass."""

    def test_genre_result_is_frozen_dataclass(self) -> None:
        """GenreResult must be a frozen dataclass."""
        assert dataclasses.is_dataclass(GenreResult)
        assert GenreResult.__dataclass_params__.frozen  # type: ignore[attr-defined]

    def test_genre_result_fields(self) -> None:
        """GenreResult must have required fields with correct types."""
        result = GenreClassifier().classify(
            tempo=120.0,
            spectral_centroid_mean=3000.0,
            spectral_bandwidth_mean=2000.0,
            onset_rate=4.0,
            harmonic_ratio=0.5,
            chroma_std=0.2,
            dynamic_range=12.0,
            duration_ms=200_000,
        )
        assert isinstance(result.primary, GenreFamily)
        assert isinstance(result.confidence, float)
        assert isinstance(result.scores, dict)
        assert isinstance(result.features_used, tuple)

    def test_genre_result_is_immutable(self) -> None:
        """GenreResult must be immutable (frozen)."""
        result = GenreClassifier().classify(
            tempo=120.0,
            spectral_centroid_mean=3000.0,
            spectral_bandwidth_mean=2000.0,
            onset_rate=4.0,
            harmonic_ratio=0.5,
            chroma_std=0.2,
            dynamic_range=12.0,
            duration_ms=200_000,
        )
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            result.primary = GenreFamily.UNKNOWN  # type: ignore[misc]


class TestConfidenceScores:
    """Tests for confidence and score ranges."""

    def test_confidence_between_zero_and_one(self) -> None:
        """Confidence must always be in [0.0, 1.0]."""
        classifier = GenreClassifier()
        test_cases = [
            {
                "tempo": 135.0,
                "spectral_centroid_mean": 5000.0,
                "spectral_bandwidth_mean": 3000.0,
                "onset_rate": 8.0,
                "harmonic_ratio": 0.2,
                "chroma_std": 0.3,
                "dynamic_range": 6.0,
                "duration_ms": 200_000,
            },
            {
                "tempo": 60.0,
                "spectral_centroid_mean": 1200.0,
                "spectral_bandwidth_mean": 1000.0,
                "onset_rate": 0.5,
                "harmonic_ratio": 0.9,
                "chroma_std": 0.25,
                "dynamic_range": 40.0,
                "duration_ms": 300_000,
            },
            {
                "tempo": 0.0,
                "spectral_centroid_mean": 0.0,
                "spectral_bandwidth_mean": 0.0,
                "onset_rate": 0.0,
                "harmonic_ratio": 0.0,
                "chroma_std": 0.0,
                "dynamic_range": 0.0,
                "duration_ms": 0,
            },
        ]
        for kwargs in test_cases:
            result = classifier.classify(**kwargs)  # type: ignore[arg-type]
            assert 0.0 <= result.confidence <= 1.0, (
                f"Confidence {result.confidence} out of range for input {kwargs}"
            )

    def test_scores_dict_has_all_genres(self) -> None:
        """Scores dict must contain an entry for every GenreFamily except UNKNOWN."""
        result = GenreClassifier().classify(
            tempo=120.0,
            spectral_centroid_mean=3000.0,
            spectral_bandwidth_mean=2000.0,
            onset_rate=4.0,
            harmonic_ratio=0.5,
            chroma_std=0.2,
            dynamic_range=12.0,
            duration_ms=200_000,
        )
        for family in GenreFamily:
            if family != GenreFamily.UNKNOWN:
                assert family.value in result.scores, f"Missing score for genre '{family.value}'"

    def test_all_scores_between_zero_and_one(self) -> None:
        """Each individual genre score must be in [0.0, 1.0]."""
        result = GenreClassifier().classify(
            tempo=120.0,
            spectral_centroid_mean=3000.0,
            spectral_bandwidth_mean=2000.0,
            onset_rate=4.0,
            harmonic_ratio=0.5,
            chroma_std=0.2,
            dynamic_range=12.0,
            duration_ms=200_000,
        )
        for genre, score in result.scores.items():
            assert 0.0 <= score <= 1.0, f"Score for '{genre}' is {score}, out of [0, 1]"


class TestFeaturesUsed:
    """Tests for the features_used tuple."""

    def test_features_used_is_populated(self) -> None:
        """features_used must be a non-empty tuple of strings."""
        result = GenreClassifier().classify(
            tempo=120.0,
            spectral_centroid_mean=3000.0,
            spectral_bandwidth_mean=2000.0,
            onset_rate=4.0,
            harmonic_ratio=0.5,
            chroma_std=0.2,
            dynamic_range=12.0,
            duration_ms=200_000,
        )
        assert len(result.features_used) > 0
        for name in result.features_used:
            assert isinstance(name, str)
            assert len(name) > 0

    def test_features_used_contains_known_names(self) -> None:
        """features_used must reference the features that were actually consumed."""
        result = GenreClassifier().classify(
            tempo=120.0,
            spectral_centroid_mean=3000.0,
            spectral_bandwidth_mean=2000.0,
            onset_rate=4.0,
            harmonic_ratio=0.5,
            chroma_std=0.2,
            dynamic_range=12.0,
            duration_ms=200_000,
        )
        known_names = {
            "tempo",
            "spectral_centroid_mean",
            "spectral_bandwidth_mean",
            "onset_rate",
            "harmonic_ratio",
            "chroma_std",
            "dynamic_range",
            "duration_ms",
        }
        for name in result.features_used:
            assert name in known_names, f"Unexpected feature name '{name}' in features_used"


class TestHighTempoElectronicOrRock:
    """Test: high-tempo (128+) + high onset rate → electronic or rock."""

    @pytest.mark.parametrize(
        "tempo,onset_rate,expected_genres",
        [
            (130.0, 7.0, {GenreFamily.ELECTRONIC, GenreFamily.ROCK}),
            (140.0, 9.0, {GenreFamily.ELECTRONIC, GenreFamily.ROCK}),
            (155.0, 6.5, {GenreFamily.ELECTRONIC, GenreFamily.ROCK}),
        ],
    )
    def test_high_tempo_high_onset_is_electronic_or_rock(
        self,
        tempo: float,
        onset_rate: float,
        expected_genres: set[GenreFamily],
    ) -> None:
        """High-tempo + high onset rate must produce electronic or rock."""
        result = GenreClassifier().classify(
            tempo=tempo,
            spectral_centroid_mean=4500.0,
            spectral_bandwidth_mean=3000.0,
            onset_rate=onset_rate,
            harmonic_ratio=0.25,
            chroma_std=0.3,
            dynamic_range=10.0,
            duration_ms=200_000,
        )
        assert result.primary in expected_genres, (
            f"Expected electronic or rock for tempo={tempo}, onset_rate={onset_rate}; "
            f"got {result.primary}"
        )


class TestLowTempoHighHarmonicClassical:
    """Test: low-tempo + high harmonic ratio → classical."""

    @pytest.mark.parametrize(
        "tempo,harmonic_ratio",
        [
            (55.0, 0.92),
            (70.0, 0.88),
            (45.0, 0.95),
        ],
    )
    def test_low_tempo_high_harmonic_is_classical(
        self, tempo: float, harmonic_ratio: float
    ) -> None:
        """Low-tempo + high harmonic ratio must produce classical."""
        result = GenreClassifier().classify(
            tempo=tempo,
            spectral_centroid_mean=1100.0,
            spectral_bandwidth_mean=900.0,
            onset_rate=0.4,
            harmonic_ratio=harmonic_ratio,
            chroma_std=0.22,
            dynamic_range=42.0,
            duration_ms=350_000,
        )
        assert result.primary == GenreFamily.CLASSICAL, (
            f"Expected classical for tempo={tempo}, harmonic_ratio={harmonic_ratio}; "
            f"got {result.primary}"
        )


class TestMediumTempoBalancedPop:
    """Test: medium-tempo + balanced features → pop."""

    @pytest.mark.parametrize(
        "tempo",
        [100.0, 110.0, 120.0],
    )
    def test_medium_tempo_balanced_is_pop(self, tempo: float) -> None:
        """Medium-tempo + balanced features must produce pop."""
        result = GenreClassifier().classify(
            tempo=tempo,
            spectral_centroid_mean=2800.0,
            spectral_bandwidth_mean=2200.0,
            onset_rate=3.0,
            harmonic_ratio=0.55,
            chroma_std=0.15,
            dynamic_range=12.0,
            duration_ms=210_000,
        )
        assert result.primary == GenreFamily.POP, (
            f"Expected pop for tempo={tempo}; got {result.primary}"
        )
