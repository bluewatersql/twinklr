"""Genre classification for audio analysis.

Provides rule-based genre family classification from extracted audio features.

Example:
    from twinklr.core.audio.genre import GenreClassifier, GenreFamily, GenreResult

    result = GenreClassifier().classify(
        tempo=128.0,
        spectral_centroid_mean=4500.0,
        spectral_bandwidth_mean=3000.0,
        onset_rate=7.0,
        harmonic_ratio=0.2,
        chroma_std=0.3,
        dynamic_range=8.0,
        duration_ms=200_000,
    )
    print(result.primary)    # GenreFamily.ELECTRONIC
    print(result.confidence) # e.g. 0.68
"""

from twinklr.core.audio.genre.classifier import GenreClassifier, GenreFamily, GenreResult

__all__ = ["GenreClassifier", "GenreFamily", "GenreResult"]
