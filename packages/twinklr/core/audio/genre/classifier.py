"""Rule-based genre classifier using audio feature heuristics.

Classifies audio into broad genre families using a weighted scoring approach
over extracted audio features such as tempo, spectral centroid, onset rate,
harmonic ratio, and tonal variety.

Example:
    classifier = GenreClassifier()
    result = classifier.classify(
        tempo=128.0,
        spectral_centroid_mean=4500.0,
        spectral_bandwidth_mean=3000.0,
        onset_rate=7.0,
        harmonic_ratio=0.2,
        chroma_std=0.3,
        dynamic_range=8.0,
        duration_ms=200_000,
    )
    print(result.primary)      # GenreFamily.ELECTRONIC
    print(result.confidence)   # e.g. 0.72
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum


class GenreFamily(StrEnum):
    """Broad genre family labels for audio classification.

    Values are lowercase strings suitable for storage and display.
    """

    ELECTRONIC = "electronic"
    ROCK = "rock"
    POP = "pop"
    CLASSICAL = "classical"
    HIPHOP = "hiphop"
    COUNTRY = "country"
    JAZZ = "jazz"
    HOLIDAY = "holiday"
    UNKNOWN = "unknown"


@dataclasses.dataclass(frozen=True)
class GenreResult:
    """Result of a genre classification.

    Attributes:
        primary: The highest-scoring genre family.
        confidence: Normalised confidence in the primary genre, in [0.0, 1.0].
        scores: Mapping of genre family value → normalised score for every
            non-UNKNOWN genre.
        features_used: Names of the input features that were consumed during
            classification.
    """

    primary: GenreFamily
    confidence: float
    scores: dict[str, float]
    features_used: tuple[str, ...]


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp *value* to the closed interval [*lo*, *hi*].

    Args:
        value: Value to clamp.
        lo: Lower bound (default 0.0).
        hi: Upper bound (default 1.0).

    Returns:
        Clamped float.
    """
    return max(lo, min(hi, value))


def _in_range(value: float, lo: float, hi: float) -> float:
    """Return 1.0 when *value* is inside [lo, hi], else a decayed score.

    The penalty outside the range is proportional to how far *value* overshoots
    the nearest boundary, capped at 0.0.

    Args:
        value: Feature value.
        lo: Lower bound of the ideal range.
        hi: Upper bound of the ideal range.

    Returns:
        Score in [0.0, 1.0].
    """
    if lo <= value <= hi:
        return 1.0
    span = max(hi - lo, 1.0)
    if value < lo:
        overshoot = (lo - value) / span
    else:
        overshoot = (value - hi) / span
    return _clamp(1.0 - overshoot)


class GenreClassifier:
    """Rule-based classifier that maps audio features to a GenreFamily.

    Uses a weighted sum of heuristic sub-scores per genre, then normalises
    to produce a probability-like confidence value.

    All features are treated as soft hints; no single feature is decisive.
    """

    # Feature names consumed by classify()
    _FEATURE_NAMES: tuple[str, ...] = (
        "tempo",
        "spectral_centroid_mean",
        "spectral_bandwidth_mean",
        "onset_rate",
        "harmonic_ratio",
        "chroma_std",
        "dynamic_range",
        "duration_ms",
    )

    def classify(
        self,
        *,
        tempo: float,
        spectral_centroid_mean: float,
        spectral_bandwidth_mean: float,
        onset_rate: float,
        harmonic_ratio: float,
        chroma_std: float,
        dynamic_range: float,
        duration_ms: int,
    ) -> GenreResult:
        """Classify audio features into a GenreFamily.

        Uses rule-based heuristics to score each genre and returns the
        highest-scoring family together with normalised confidence.

        Args:
            tempo: Beats per minute.
            spectral_centroid_mean: Mean spectral centroid in Hz (brightness).
            spectral_bandwidth_mean: Mean spectral bandwidth in Hz (fullness).
            onset_rate: Onset events per second.
            harmonic_ratio: Proportion of harmonic vs. percussive energy, [0, 1].
            chroma_std: Standard deviation of chroma features (tonal variety).
            dynamic_range: Dynamic range in dB.
            duration_ms: Song duration in milliseconds.

        Returns:
            GenreResult with primary genre, confidence, per-genre scores, and
            feature names used.
        """
        # Guard: if all features are zero/absent return UNKNOWN immediately
        total_signal = (
            tempo
            + spectral_centroid_mean
            + spectral_bandwidth_mean
            + onset_rate
            + harmonic_ratio
            + chroma_std
            + dynamic_range
            + duration_ms
        )
        if total_signal == 0.0:
            empty_scores = {g.value: 0.0 for g in GenreFamily if g != GenreFamily.UNKNOWN}
            return GenreResult(
                primary=GenreFamily.UNKNOWN,
                confidence=0.0,
                scores=empty_scores,
                features_used=self._FEATURE_NAMES,
            )

        raw: dict[str, float] = {
            GenreFamily.ELECTRONIC.value: self._score_electronic(
                tempo, spectral_centroid_mean, onset_rate, harmonic_ratio, dynamic_range
            ),
            GenreFamily.ROCK.value: self._score_rock(
                tempo,
                spectral_centroid_mean,
                spectral_bandwidth_mean,
                onset_rate,
                harmonic_ratio,
                dynamic_range,
            ),
            GenreFamily.POP.value: self._score_pop(
                tempo, spectral_centroid_mean, onset_rate, harmonic_ratio, chroma_std
            ),
            GenreFamily.CLASSICAL.value: self._score_classical(
                tempo, spectral_centroid_mean, onset_rate, harmonic_ratio, dynamic_range
            ),
            GenreFamily.HIPHOP.value: self._score_hiphop(
                tempo, spectral_centroid_mean, onset_rate, harmonic_ratio
            ),
            GenreFamily.COUNTRY.value: self._score_country(
                tempo, spectral_centroid_mean, onset_rate, harmonic_ratio, chroma_std
            ),
            GenreFamily.JAZZ.value: self._score_jazz(
                tempo, spectral_centroid_mean, onset_rate, harmonic_ratio, chroma_std, dynamic_range
            ),
            GenreFamily.HOLIDAY.value: self._score_holiday(
                tempo, spectral_centroid_mean, onset_rate, harmonic_ratio, chroma_std, dynamic_range
            ),
        }

        total = sum(raw.values())
        if total <= 0.0:
            # All scores are zero — truly ambiguous
            normalised = dict.fromkeys(raw, 0.0)
            return GenreResult(
                primary=GenreFamily.UNKNOWN,
                confidence=0.0,
                scores=normalised,
                features_used=self._FEATURE_NAMES,
            )

        # Normalise scores to [0, 1]
        normalised = {k: _clamp(v / total) for k, v in raw.items()}

        best_key = max(normalised, key=lambda k: normalised[k])
        best_score = normalised[best_key]
        primary = GenreFamily(best_key)
        confidence = _clamp(best_score)

        return GenreResult(
            primary=primary,
            confidence=confidence,
            scores=normalised,
            features_used=self._FEATURE_NAMES,
        )

    # ------------------------------------------------------------------
    # Per-genre scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_electronic(
        tempo: float,
        centroid: float,
        onset_rate: float,
        harmonic_ratio: float,
        dynamic_range: float,
    ) -> float:
        """Score for electronic genre.

        Args:
            tempo: BPM.
            centroid: Spectral centroid mean in Hz.
            onset_rate: Onsets per second.
            harmonic_ratio: Harmonic-to-percussive ratio.
            dynamic_range: Dynamic range in dB.

        Returns:
            Raw (unnormalised) score.
        """
        score = 0.0
        # Tempo: ideal 120-160 BPM
        score += _in_range(tempo, 120.0, 160.0) * 2.0
        # High spectral brightness
        score += _in_range(centroid, 3500.0, 8000.0) * 1.5
        # High onset rate (percussive kicks/hats)
        score += _in_range(onset_rate, 5.0, 12.0) * 2.0
        # Low harmonic ratio (more percussive than harmonic)
        score += _in_range(1.0 - harmonic_ratio, 0.6, 1.0) * 1.5
        # Low dynamic range (mastered/compressed) — strong electronic signal
        score += _in_range(1.0 - dynamic_range / 40.0, 0.7, 1.0) * 2.0
        return score

    @staticmethod
    def _score_rock(
        tempo: float,
        centroid: float,
        bandwidth: float,
        onset_rate: float,
        harmonic_ratio: float,
        dynamic_range: float,
    ) -> float:
        """Score for rock genre.

        Args:
            tempo: BPM.
            centroid: Spectral centroid mean in Hz.
            bandwidth: Spectral bandwidth mean in Hz.
            onset_rate: Onsets per second.
            harmonic_ratio: Harmonic-to-percussive ratio.
            dynamic_range: Dynamic range in dB.

        Returns:
            Raw (unnormalised) score.
        """
        score = 0.0
        # Tempo: ideal 100-160 BPM
        score += _in_range(tempo, 100.0, 160.0) * 2.0
        # Wide bandwidth (guitars + drums)
        score += _in_range(bandwidth, 3000.0, 5000.0) * 1.5
        # Medium-high onset rate
        score += _in_range(onset_rate, 4.0, 9.0) * 2.0
        # Low harmonic ratio (distorted guitars are percussive)
        score += _in_range(1.0 - harmonic_ratio, 0.6, 0.85) * 1.5
        # Higher dynamic range than electronic
        score += _in_range(dynamic_range, 12.0, 25.0) * 1.0
        # Mid-high centroid
        score += _in_range(centroid, 3000.0, 6000.0) * 1.0
        return score

    @staticmethod
    def _score_pop(
        tempo: float,
        centroid: float,
        onset_rate: float,
        harmonic_ratio: float,
        chroma_std: float,
    ) -> float:
        """Score for pop genre.

        Args:
            tempo: BPM.
            centroid: Spectral centroid mean in Hz.
            onset_rate: Onsets per second.
            harmonic_ratio: Harmonic-to-percussive ratio.
            chroma_std: Chroma standard deviation (tonal variety).

        Returns:
            Raw (unnormalised) score.
        """
        score = 0.0
        # Tempo: ideal 90-130 BPM
        score += _in_range(tempo, 90.0, 130.0) * 2.0
        # Mid spectral centroid
        score += _in_range(centroid, 2000.0, 4000.0) * 1.5
        # Medium onset rate
        score += _in_range(onset_rate, 2.0, 5.0) * 1.5
        # Balanced harmonic ratio
        score += _in_range(harmonic_ratio, 0.4, 0.7) * 1.5
        # Low chroma std (predictable tonal content, verse/chorus repetition)
        score += _in_range(1.0 - chroma_std, 0.75, 1.0) * 2.0
        return score

    @staticmethod
    def _score_classical(
        tempo: float,
        centroid: float,
        onset_rate: float,
        harmonic_ratio: float,
        dynamic_range: float,
    ) -> float:
        """Score for classical genre.

        Args:
            tempo: BPM.
            centroid: Spectral centroid mean in Hz.
            onset_rate: Onsets per second.
            harmonic_ratio: Harmonic-to-percussive ratio.
            dynamic_range: Dynamic range in dB.

        Returns:
            Raw (unnormalised) score.
        """
        score = 0.0
        # Tempo: wide range but often slower
        score += _in_range(tempo, 40.0, 120.0) * 1.5
        # Low-mid spectral centroid
        score += _in_range(centroid, 500.0, 2000.0) * 2.0
        # Low onset rate (no drums)
        score += _in_range(onset_rate, 0.0, 2.0) * 2.5
        # High harmonic ratio (mostly harmonic instruments)
        score += _in_range(harmonic_ratio, 0.75, 1.0) * 3.0
        # High dynamic range (not compressed)
        score += _in_range(dynamic_range, 25.0, 60.0) * 2.0
        return score

    @staticmethod
    def _score_hiphop(
        tempo: float,
        centroid: float,
        onset_rate: float,
        harmonic_ratio: float,
    ) -> float:
        """Score for hip-hop genre.

        Args:
            tempo: BPM.
            centroid: Spectral centroid mean in Hz.
            onset_rate: Onsets per second.
            harmonic_ratio: Harmonic-to-percussive ratio.

        Returns:
            Raw (unnormalised) score.
        """
        score = 0.0
        # Tempo: ideal 70-110 BPM
        score += _in_range(tempo, 70.0, 110.0) * 2.5
        # Low spectral centroid (bass-heavy)
        score += _in_range(centroid, 300.0, 1500.0) * 2.5
        # Medium onset rate (beat-driven but not frantic)
        score += _in_range(onset_rate, 3.0, 7.0) * 2.0
        # Medium-low harmonic ratio (beats + samples)
        score += _in_range(harmonic_ratio, 0.2, 0.5) * 1.5
        return score

    @staticmethod
    def _score_country(
        tempo: float,
        centroid: float,
        onset_rate: float,
        harmonic_ratio: float,
        chroma_std: float,
    ) -> float:
        """Score for country genre.

        Args:
            tempo: BPM.
            centroid: Spectral centroid mean in Hz.
            onset_rate: Onsets per second.
            harmonic_ratio: Harmonic-to-percussive ratio.
            chroma_std: Chroma standard deviation.

        Returns:
            Raw (unnormalised) score.
        """
        score = 0.0
        # Tempo: medium (70-110 BPM)
        score += _in_range(tempo, 70.0, 110.0) * 2.0
        # Mid spectral centroid (guitar-like)
        score += _in_range(centroid, 1500.0, 2500.0) * 2.0
        # Low-medium onset rate
        score += _in_range(onset_rate, 1.0, 4.0) * 1.5
        # Medium harmonic ratio (acoustic instruments)
        score += _in_range(harmonic_ratio, 0.5, 0.75) * 2.0
        # Medium chroma std (some tonal variety, not as much as jazz)
        score += _in_range(chroma_std, 0.2, 0.45) * 1.5
        return score

    @staticmethod
    def _score_jazz(
        tempo: float,
        centroid: float,
        onset_rate: float,
        harmonic_ratio: float,
        chroma_std: float,
        dynamic_range: float,
    ) -> float:
        """Score for jazz genre.

        Args:
            tempo: BPM.
            centroid: Spectral centroid mean in Hz.
            onset_rate: Onsets per second.
            harmonic_ratio: Harmonic-to-percussive ratio.
            chroma_std: Chroma standard deviation (high = rich harmony).
            dynamic_range: Dynamic range in dB.

        Returns:
            Raw (unnormalised) score.
        """
        score = 0.0
        # Tempo: wide range
        score += _in_range(tempo, 60.0, 180.0) * 0.5
        # Mid spectral centroid
        score += _in_range(centroid, 1800.0, 3500.0) * 1.5
        # Low-medium onset rate
        score += _in_range(onset_rate, 1.5, 5.0) * 1.5
        # Medium-high harmonic ratio
        score += _in_range(harmonic_ratio, 0.5, 0.8) * 2.0
        # HIGH chroma std — jazz hallmark (extended chords, rich harmony)
        score += _in_range(chroma_std, 0.5, 1.0) * 3.0
        # Medium dynamic range
        score += _in_range(dynamic_range, 12.0, 30.0) * 1.0
        return score

    @staticmethod
    def _score_holiday(
        tempo: float,
        centroid: float,
        onset_rate: float,
        harmonic_ratio: float,
        chroma_std: float,
        dynamic_range: float,
    ) -> float:
        """Score for holiday/Christmas genre.

        Holiday music tends to be slow-to-medium tempo, harmonic, with low
        onset rate (bells, choir, orchestral) and short duration (carols).

        Args:
            tempo: BPM.
            centroid: Spectral centroid mean in Hz.
            onset_rate: Onsets per second.
            harmonic_ratio: Harmonic-to-percussive ratio.
            chroma_std: Chroma standard deviation.
            dynamic_range: Dynamic range in dB.

        Returns:
            Raw (unnormalised) score.
        """
        score = 0.0
        # Tempo: 60-90 BPM (carol-like)
        score += _in_range(tempo, 60.0, 90.0) * 2.5
        # Low-mid centroid (warm, orchestral/choral)
        score += _in_range(centroid, 1200.0, 2200.0) * 2.0
        # Low onset rate (no heavy percussion)
        score += _in_range(onset_rate, 0.5, 2.0) * 2.5
        # High harmonic ratio (choral/orchestral)
        score += _in_range(harmonic_ratio, 0.65, 0.85) * 2.0
        # Low chroma std (simple tonal content)
        score += _in_range(1.0 - chroma_std, 0.7, 1.0) * 1.5
        # Medium dynamic range
        score += _in_range(dynamic_range, 8.0, 20.0) * 1.0
        return score
