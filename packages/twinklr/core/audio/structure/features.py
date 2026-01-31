"""Feature extraction for section detection.

Extracts multi-feature representations for song segmentation:
- MFCC (timbre)
- Chroma (harmony)
- Spectral contrast (texture)
- Tonnetz (tonal centroids)
- Spectral centroid (brightness)
- Onset envelope (transients)
"""

from __future__ import annotations

import librosa
import numpy as np


def standardize_block(x: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Standardize feature block (mean=0, std=1) per feature dimension.

    Args:
        x: Feature matrix (features × frames)
        eps: Small constant to avoid division by zero

    Returns:
        Standardized feature matrix
    """
    mu = np.mean(x, axis=1, keepdims=True)
    sd = np.std(x, axis=1, keepdims=True)
    sd = np.where(sd < eps, 1.0, sd)
    return (x - mu) / sd  # type: ignore[no-any-return]


def extract_beat_sync_features(
    y: np.ndarray,
    sr: int,
    hop_length: int,
    beat_frames: list[int],
    num_beats: int,
    chroma_cqt: np.ndarray | None = None,
) -> np.ndarray:
    """Extract beat-synchronized multi-feature representation.

    Combines multiple acoustic features for robust segmentation:
    - MFCC: Timbre characteristics
    - Chroma: Harmonic content
    - Spectral contrast: Texture
    - Tonnetz: Tonal centroid features
    - Spectral centroid: Brightness
    - Onset envelope: Transient information

    Features are weighted by relevance to segmentation and standardized.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length for STFT
        beat_frames: Beat frame indices
        num_beats: Number of beats
        chroma_cqt: Pre-computed chroma (optional, will compute if None)

    Returns:
        Feature matrix (features × beats) with normalized, weighted features
    """
    # STFT for basic spectral features
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop_length)).astype(np.float32)
    P_db = librosa.power_to_db(S**2).astype(np.float32)

    # MFCC: Timbre (13 coefficients)
    mfcc = librosa.feature.mfcc(S=P_db, sr=sr, n_mfcc=13).astype(np.float32)

    # Chroma: Harmony (12 pitch classes)
    if chroma_cqt is not None and chroma_cqt.shape[1] > 0:
        chroma = np.asarray(chroma_cqt, dtype=np.float32)
    else:
        chroma = librosa.feature.chroma_stft(S=S, sr=sr).astype(np.float32)

    # Spectral contrast: Texture (7 bands)
    try:
        contrast = librosa.feature.spectral_contrast(S=S, sr=sr).astype(np.float32)
    except Exception:
        contrast = np.zeros((7, mfcc.shape[1]), dtype=np.float32)

    # Spectral centroid: Brightness
    centroid = librosa.feature.spectral_centroid(S=S, sr=sr).astype(np.float32)

    # Onset envelope: Transient information
    onset_env = (
        librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
        .astype(np.float32)
        .reshape(1, -1)
    )

    # Tonnetz: Tonal centroid features (6 dimensions)
    try:
        y_harm = librosa.effects.harmonic(y)
        S_h = np.abs(librosa.stft(y_harm, n_fft=2048, hop_length=hop_length)).astype(np.float32)
        chroma_h = librosa.feature.chroma_stft(S=S_h, sr=sr).astype(np.float32)
        tonnetz = librosa.feature.tonnetz(chroma=chroma_h, sr=sr).astype(np.float32)
    except Exception:
        tonnetz = np.zeros((6, mfcc.shape[1]), dtype=np.float32)

    # Beat-synchronize all features
    mfcc_sync = librosa.util.sync(mfcc, beat_frames, aggregate=np.mean)[:, :num_beats]
    chroma_sync = librosa.util.sync(chroma, beat_frames, aggregate=np.mean)[:, :num_beats]
    contrast_sync = librosa.util.sync(contrast, beat_frames, aggregate=np.mean)[:, :num_beats]
    centroid_sync = librosa.util.sync(centroid, beat_frames, aggregate=np.mean)[:, :num_beats]
    onset_sync = librosa.util.sync(onset_env, beat_frames, aggregate=np.mean)[:, :num_beats]
    tonnetz_sync = librosa.util.sync(tonnetz, beat_frames, aggregate=np.mean)[:, :num_beats]

    # Combine features with weights (empirically tuned for segmentation)
    X = np.vstack(
        [
            standardize_block(mfcc_sync) * 1.0,
            standardize_block(chroma_sync) * 0.8,
            standardize_block(contrast_sync) * 0.6,
            standardize_block(tonnetz_sync) * 0.6,
            standardize_block(centroid_sync) * 0.4,
            standardize_block(onset_sync) * 0.6,
        ]
    ).astype(np.float32)

    # L2 normalize feature vectors
    norms = np.linalg.norm(X, axis=0, keepdims=True)
    norms = np.where(norms < 1e-8, 1.0, norms)
    X_normalized = X / norms

    return X_normalized  # type: ignore[no-any-return]
