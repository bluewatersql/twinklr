"""Optional cached source separation and stem-derived planner features.

Demucs is imported only when the centrally configured stage is enabled. The cache
stores compact derived features rather than large waveforms, keyed solely by audio
content hash and model name as required by the D8 contract.
"""

from __future__ import annotations

from enum import StrEnum
import hashlib
import logging
import math
from pathlib import Path
import platform
from typing import Any, Protocol, cast

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.audio.cache_adapter import compute_audio_file_hash
from twinklr.core.audio.energy.builds_drops import detect_builds_and_drops
from twinklr.core.audio.energy.multiscale import extract_smoothed_energy
from twinklr.core.audio.harmonic.hpss import compute_onset_env
from twinklr.core.audio.utils import as_float_list, frames_to_time
from twinklr.core.caching import CacheKey, FSCache
from twinklr.core.config.models import StemSeparationConfig

logger = logging.getLogger(__name__)

STEMS_CACHE_VERSION = "1"
_STEM_HOP_LENGTH = 512
_STEM_FRAME_LENGTH = 2048


class StemStatus(StrEnum):
    """Truthful status surfaced in every audio-analysis result."""

    DISABLED_FULL_MIX_FALLBACK = "disabled_full_mix_fallback"
    AVAILABLE = "available"
    UNAVAILABLE_FULL_MIX_FALLBACK = "unavailable_full_mix_fallback"


class SeparatedStems(BaseModel):
    """Transient separator output; waveforms are never serialized into the cache."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    stems: dict[str, np.ndarray]
    sample_rate: int = Field(gt=0)
    device: str
    warnings: list[str] = Field(default_factory=list)


class StemFeatures(BaseModel):
    """Compact, JSON-safe stem features stored through the existing FSCache seam."""

    status: StemStatus
    model_name: str | None = None
    audio_hash: str | None = None
    cache_hit: bool = False
    device: str | None = None
    drum_onsets: list[float] = Field(default_factory=list)
    drum_onset_times_s: list[float] = Field(default_factory=list)
    bass_energy: list[float] = Field(default_factory=list)
    bass_energy_times_s: list[float] = Field(default_factory=list)
    vocal_segments: list[dict[str, float]] = Field(default_factory=list)
    vocal_presence_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    vocal_gate_open: bool | None = None
    fallback_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @property
    def available(self) -> bool:
        """Whether separated signals are valid for downstream consumers."""
        return self.status == StemStatus.AVAILABLE


class StemSeparator(Protocol):
    """Dependency-injection seam for model-free unit tests."""

    def separate(self, audio_path: Path, model_name: str) -> SeparatedStems:
        """Separate one audio file into named source waveforms."""
        ...


class DemucsStemSeparator:
    """Lazy adapter around canonical Demucs 4.1.0."""

    def separate(self, audio_path: Path, model_name: str) -> SeparatedStems:
        if platform.system() == "Darwin" and platform.machine() == "x86_64":
            raise RuntimeError(
                "Intel macOS stems are unsupported because Demucs 4.1.0 conflicts with "
                "Twinklr's NumPy 2 requirement; using the explicit full-mix fallback"
            )

        separator_type = _load_demucs_separator()
        device = _demucs_default_device()
        warnings: list[str] = []
        try:
            _, sources, sample_rate = _run_demucs(
                separator_type, audio_path, model_name=model_name, device=device
            )
        except RuntimeError as error:
            if device != "mps":
                raise
            warning = f"Demucs MPS separation failed ({error}); retrying once on CPU"
            logger.warning(warning)
            warnings.append(warning)
            device = "cpu"
            _, sources, sample_rate = _run_demucs(
                separator_type, audio_path, model_name=model_name, device=device
            )

        return SeparatedStems(
            stems={name: _tensor_to_numpy(audio) for name, audio in sources.items()},
            sample_rate=sample_rate,
            device=device,
            warnings=warnings,
        )


def _load_demucs_separator() -> type[Any]:
    """Import Demucs only on the explicitly enabled path."""
    try:
        from demucs.api import Separator
    except ImportError as error:
        raise ImportError(
            "Demucs is not installed; install the optional stems extra with "
            "`uv sync --package twinklr-core --extra stems`"
        ) from error
    return cast("type[Any]", Separator)


def _demucs_default_device() -> str:
    """Reuse Demucs's own CLI selection (CUDA, then MPS, then CPU)."""
    from demucs.separate import get_parser

    return str(get_parser().get_default("device"))


def _run_demucs(
    separator_type: type[Any],
    audio_path: Path,
    *,
    model_name: str,
    device: str,
) -> tuple[object, dict[str, object], int]:
    separator = separator_type(model=model_name, device=device)
    original, sources = separator.separate_audio_file(audio_path)
    return original, sources, int(separator.samplerate)


def make_stems_cache_key(audio_hash: str, model_name: str) -> CacheKey:
    """Return the exact audio-hash + model-name cache identity."""
    fingerprint = hashlib.sha256(f"{audio_hash}:{model_name}".encode()).hexdigest()
    return CacheKey(
        domain="audio",
        step_id="audio.stems",
        step_version=STEMS_CACHE_VERSION,
        input_fingerprint=fingerprint,
    )


async def analyze_stems(
    audio_path: Path,
    cache: FSCache,
    config: StemSeparationConfig,
    *,
    separator: StemSeparator | None = None,
) -> StemFeatures:
    """Load or derive cached features, degrading loudly to the full mix."""
    if not config.enabled:
        return StemFeatures(
            status=StemStatus.DISABLED_FULL_MIX_FALLBACK,
            model_name=config.model_name,
            fallback_reason="Stems are disabled by configuration",
        )

    audio_hash = await compute_audio_file_hash(str(audio_path))
    key = make_stems_cache_key(audio_hash, config.model_name)
    cached = await cache.load(key, StemFeatures)
    if cached is not None and cached.status == StemStatus.AVAILABLE:
        return cached.model_copy(
            update={
                "cache_hit": True,
                "vocal_gate_open": (cached.vocal_presence_pct >= config.vocal_presence_threshold),
            }
        )

    active_separator = separator or DemucsStemSeparator()
    try:
        separated = active_separator.separate(audio_path, config.model_name)
        result = _derive_stem_features(separated, audio_hash, config)
    except (ImportError, KeyError, OSError, RuntimeError, ValueError) as error:
        reason = f"Stem separation unavailable; using full-mix fallback: {error}"
        logger.warning(reason)
        return StemFeatures(
            status=StemStatus.UNAVAILABLE_FULL_MIX_FALLBACK,
            model_name=config.model_name,
            audio_hash=audio_hash,
            fallback_reason=reason,
            warnings=[reason],
        )

    await cache.store(key, result)
    return result


def _derive_stem_features(
    separated: SeparatedStems,
    audio_hash: str,
    config: StemSeparationConfig,
) -> StemFeatures:
    missing = {"drums", "bass", "vocals"}.difference(separated.stems)
    if missing:
        raise KeyError(f"Demucs result omitted required stems: {sorted(missing)}")

    drums = _as_mono(separated.stems["drums"])
    bass = _as_mono(separated.stems["bass"])
    vocals = _as_mono(separated.stems["vocals"])
    onset_env = compute_onset_env(
        drums,
        separated.sample_rate,
        hop_length=_STEM_HOP_LENGTH,
    )
    onset_times = frames_to_time(
        np.arange(len(onset_env)),
        sr=separated.sample_rate,
        hop_length=_STEM_HOP_LENGTH,
    )
    bass_result = extract_smoothed_energy(
        bass,
        separated.sample_rate,
        hop_length=_STEM_HOP_LENGTH,
        frame_length=_STEM_FRAME_LENGTH,
    )
    vocal_segments = _vocal_segments(vocals, separated.sample_rate)
    duration_s = len(vocals) / separated.sample_rate
    vocal_duration_s = sum(segment["duration_s"] for segment in vocal_segments)
    vocal_presence_pct = min(1.0, vocal_duration_s / duration_s) if duration_s else 0.0

    return StemFeatures(
        status=StemStatus.AVAILABLE,
        model_name=config.model_name,
        audio_hash=audio_hash,
        device=separated.device,
        drum_onsets=as_float_list(onset_env, 5),
        drum_onset_times_s=as_float_list(onset_times, 3),
        bass_energy=[float(value) for value in bass_result["raw"]],
        bass_energy_times_s=[float(value) for value in bass_result["times_s"]],
        vocal_segments=vocal_segments,
        vocal_presence_pct=vocal_presence_pct,
        vocal_gate_open=vocal_presence_pct >= config.vocal_presence_threshold,
        warnings=separated.warnings,
    )


def apply_stem_consumers(
    stem_features: StemFeatures,
    *,
    full_mix_beat_confidence: float,
    beats_s: list[float],
    full_mix_builds_drops: dict[str, Any],
    full_mix_vocal_segments: list[dict[str, float]],
    full_mix_vocal_statistics: dict[str, Any],
    tempo_bpm: float,
    beats_per_bar: int,
) -> dict[str, Any]:
    """Select the three consumer substrates while retaining full-mix evidence."""
    if not stem_features.available:
        return {
            "stems": stem_features.model_dump(mode="json"),
            "rhythm": {
                "source": "full_mix",
                "beat_confidence": full_mix_beat_confidence,
                "full_mix_beat_confidence": full_mix_beat_confidence,
                "accent_confidence": full_mix_beat_confidence,
            },
            "energy": {
                "build_drop_source": "full_mix",
                "builds": full_mix_builds_drops.get("builds", []),
                "drops": full_mix_builds_drops.get("drops", []),
                "build_drop_statistics": full_mix_builds_drops.get("statistics", {}),
            },
            "vocals": full_mix_vocal_segments,
            "vocals_statistics": full_mix_vocal_statistics,
            "vocals_source": "full_mix",
            "full_mix_vocals": full_mix_vocal_segments,
            "full_mix_vocals_statistics": full_mix_vocal_statistics,
            "vocal_gate_open": None,
        }

    accent_confidence = _beat_aligned_drum_confidence(
        stem_features.drum_onsets,
        stem_features.drum_onset_times_s,
        beats_s,
    )
    beat_confidence = float(np.clip((full_mix_beat_confidence + accent_confidence) / 2, 0, 1))
    stem_builds_drops = detect_builds_and_drops(
        energy_curve=np.asarray(stem_features.bass_energy, dtype=np.float32),
        times_s=np.asarray(stem_features.bass_energy_times_s, dtype=np.float32),
        onset_env=np.asarray(stem_features.drum_onsets, dtype=np.float32),
        beats_s=beats_s,
        tempo_bpm=tempo_bpm,
        beats_per_bar=beats_per_bar,
    )
    stem_vocal_statistics = _stem_vocal_statistics(stem_features)
    return {
        "stems": stem_features.model_dump(mode="json"),
        "rhythm": {
            "source": "drum_stem",
            "beat_confidence": beat_confidence,
            "full_mix_beat_confidence": full_mix_beat_confidence,
            "accent_confidence": accent_confidence,
            "drum_onsets": stem_features.drum_onsets,
            "drum_onset_times_s": stem_features.drum_onset_times_s,
        },
        "energy": {
            "build_drop_source": "bass_stem",
            "builds": stem_builds_drops.get("builds", []),
            "drops": stem_builds_drops.get("drops", []),
            "build_drop_statistics": stem_builds_drops.get("statistics", {}),
            "full_mix_builds": full_mix_builds_drops.get("builds", []),
            "full_mix_drops": full_mix_builds_drops.get("drops", []),
            "bass_energy": stem_features.bass_energy,
            "bass_energy_times_s": stem_features.bass_energy_times_s,
        },
        "vocals": stem_features.vocal_segments,
        "vocals_statistics": stem_vocal_statistics,
        "vocals_source": "vocal_stem",
        "full_mix_vocals": full_mix_vocal_segments,
        "full_mix_vocals_statistics": full_mix_vocal_statistics,
        "vocal_gate_open": stem_features.vocal_gate_open,
    }


def stem_result_matches_config(stored_status: dict[str, Any], config: StemSeparationConfig) -> bool:
    """Reject pre-stage, fallback, wrong-mode, and wrong-model SongBundle caches."""
    if not stored_status:
        return False
    status = stored_status.get("status")
    if config.enabled:
        if status != StemStatus.AVAILABLE or stored_status.get("model_name") != config.model_name:
            return False
        stored_gate = stored_status.get("vocal_gate_open")
        if not isinstance(stored_gate, bool):
            return False
        try:
            vocal_presence_pct = float(stored_status["vocal_presence_pct"])
        except (KeyError, TypeError, ValueError):
            return False
        if not math.isfinite(vocal_presence_pct) or not 0.0 <= vocal_presence_pct <= 1.0:
            return False
        expected_gate = vocal_presence_pct >= config.vocal_presence_threshold
        return stored_gate is expected_gate
    return status == StemStatus.DISABLED_FULL_MIX_FALLBACK


def _beat_aligned_drum_confidence(
    onset_values: list[float], onset_times_s: list[float], beats_s: list[float]
) -> float:
    onset = np.asarray(onset_values, dtype=np.float32)
    times = np.asarray(onset_times_s, dtype=np.float32)
    if onset.size == 0 or times.size == 0 or not beats_s:
        return 0.0
    peak = float(np.max(onset))
    if peak <= 1e-9:
        return 0.0
    aligned: list[float] = []
    for beat in beats_s:
        window = onset[np.abs(times - beat) <= 0.1]
        aligned.append(float(np.max(window)) / peak if window.size else 0.0)
    return float(np.clip(np.mean(aligned), 0, 1))


def _vocal_segments(vocals: np.ndarray, sample_rate: int) -> list[dict[str, float]]:
    import librosa

    rms = librosa.feature.rms(
        y=vocals,
        frame_length=_STEM_FRAME_LENGTH,
        hop_length=_STEM_HOP_LENGTH,
    )[0]
    if rms.size == 0 or float(np.max(rms)) <= 1e-6:
        return []
    threshold = max(0.005, float(np.max(rms)) * 0.15)
    active = rms >= threshold
    times = frames_to_time(np.arange(len(rms)), sr=sample_rate, hop_length=_STEM_HOP_LENGTH)
    segments: list[dict[str, float]] = []
    start: int | None = None
    for index, is_active in enumerate(active):
        if is_active and start is None:
            start = index
        elif not is_active and start is not None:
            _append_vocal_segment(segments, float(times[start]), float(times[index]))
            start = None
    if start is not None:
        _append_vocal_segment(segments, float(times[start]), len(vocals) / sample_rate)
    return segments


def _append_vocal_segment(segments: list[dict[str, float]], start_s: float, end_s: float) -> None:
    if end_s > start_s:
        segments.append({"start_s": start_s, "end_s": end_s, "duration_s": end_s - start_s})


def _stem_vocal_statistics(features: StemFeatures) -> dict[str, float | int]:
    total_duration = sum(segment["duration_s"] for segment in features.vocal_segments)
    return {
        "vocal_coverage_pct": features.vocal_presence_pct,
        "vocal_segment_count": len(features.vocal_segments),
        "avg_segment_duration_s": (
            total_duration / len(features.vocal_segments) if features.vocal_segments else 0.0
        ),
        "total_vocal_duration_s": total_duration,
    }


def _tensor_to_numpy(audio: object) -> np.ndarray:
    detach = getattr(audio, "detach", None)
    if callable(detach):
        audio = detach().cpu().numpy()
    return np.asarray(audio, dtype=np.float32)


def _as_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio
    if audio.ndim == 2:
        return np.asarray(np.mean(audio, axis=0, dtype=np.float32), dtype=np.float32)
    raise ValueError(f"Expected mono/stereo stem audio, got shape {audio.shape}")
