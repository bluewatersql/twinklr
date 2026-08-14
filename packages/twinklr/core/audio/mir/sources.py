"""Selectable producers for the timing and structure consumed through BeatGrid."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import importlib
import math
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, cast

import librosa
import numpy as np

from twinklr.core.audio.rhythm.beats import (
    compute_beats,
    detect_downbeats_phase_aligned,
    detect_time_signature,
)
from twinklr.core.audio.structure.sections import detect_song_sections
from twinklr.core.config.models import RhythmSourceName, StructureSourceName

Importer = Callable[[str], ModuleType]


class MissingMIRDependencyError(RuntimeError):
    """An explicitly selected optional MIR backend is not locally available."""


@dataclass(frozen=True)
class MIRInput:
    """Precomputed audio substrate shared by MIR source implementations."""

    audio_path: Path
    audio: np.ndarray
    sample_rate: int
    hop_length: int
    onset_envelope: np.ndarray
    chroma: np.ndarray
    genre: str | None = None
    harmonic_audio: np.ndarray | None = None
    rms: np.ndarray | None = None
    stft_magnitude: np.ndarray | None = None
    builds: list[dict[str, Any]] = field(default_factory=list)
    drops: list[dict[str, Any]] = field(default_factory=list)
    vocal_segments: list[dict[str, Any]] = field(default_factory=list)
    chords: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RhythmAnalysis:
    """Normalized beat/downbeat truth emitted by a rhythm source."""

    tempo_bpm: float
    beats_s: list[float]
    downbeats_s: list[float]
    beats_per_bar: int
    beat_confidence: float
    downbeat_confidence: float
    source: str
    source_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StructureAnalysis:
    """Normalized labeled-section truth emitted by a structure source."""

    sections: list[dict[str, Any]]
    boundary_times_s: list[float]
    source: str
    source_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


class RhythmSource(Protocol):
    """Source capability required for BeatGrid rhythm truth."""

    name: str
    version: str

    def analyze_rhythm(self, inputs: MIRInput) -> RhythmAnalysis: ...


class StructureSource(Protocol):
    """Source capability required for labeled structural truth."""

    name: str
    version: str

    def analyze_structure(self, inputs: MIRInput, rhythm: RhythmAnalysis) -> StructureAnalysis: ...


def _clean_times(values: Any) -> list[float]:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    return sorted({float(value) for value in array if math.isfinite(float(value)) and value >= 0.0})


def _tempo_from_beats(beats_s: list[float]) -> float:
    differences = np.diff(np.asarray(beats_s, dtype=np.float64))
    positive = differences[differences > 1e-6]
    return 60.0 / float(np.median(positive)) if positive.size else 120.0


def _beats_per_bar(beats_s: list[float], downbeats_s: list[float]) -> int:
    if len(beats_s) < 2 or len(downbeats_s) < 2:
        return 4
    beat_array = np.asarray(beats_s)
    indices = [int(np.argmin(np.abs(beat_array - downbeat))) for downbeat in downbeats_s]
    gaps = np.diff(np.asarray(indices, dtype=int))
    positive = gaps[gaps > 0]
    return max(1, round(float(np.median(positive)))) if positive.size else 4


class DSPSource:
    """The existing librosa + Twinklr phase-voting/structure implementation."""

    name = "dsp"
    version = "twinklr-dsp-v1"

    def analyze_rhythm(self, inputs: MIRInput) -> RhythmAnalysis:
        tempo_bpm, beat_frames = compute_beats(
            onset_env=inputs.onset_envelope,
            sr=inputs.sample_rate,
            hop_length=inputs.hop_length,
        )
        signature = detect_time_signature(beat_frames=beat_frames, onset_env=inputs.onset_envelope)
        beats_per_bar = int(str(signature["time_signature"]).split("/")[0])
        downbeats = detect_downbeats_phase_aligned(
            beat_frames=beat_frames,
            sr=inputs.sample_rate,
            hop_length=inputs.hop_length,
            onset_env=inputs.onset_envelope,
            chroma_cqt=inputs.chroma,
            beats_per_bar=beats_per_bar,
        )
        beats_s = librosa.frames_to_time(
            beat_frames, sr=inputs.sample_rate, hop_length=inputs.hop_length
        ).tolist()
        return RhythmAnalysis(
            tempo_bpm=tempo_bpm,
            beats_s=[float(value) for value in beats_s],
            downbeats_s=[float(item["time_s"]) for item in downbeats["downbeats"]],
            beats_per_bar=beats_per_bar,
            beat_confidence=float(signature.get("confidence", 0.0)),
            downbeat_confidence=float(downbeats.get("phase_confidence", 0.0)),
            source=self.name,
            source_version=self.version,
            metadata={"time_signature": signature, "downbeat_meta": downbeats},
        )

    def analyze_structure(self, inputs: MIRInput, rhythm: RhythmAnalysis) -> StructureAnalysis:
        result = detect_song_sections(
            inputs.audio,
            inputs.sample_rate,
            hop_length=inputs.hop_length,
            genre=inputs.genre,
            rms_for_energy=inputs.rms,
            chroma_cqt=inputs.chroma,
            beats_s=rhythm.beats_s,
            bars_s=rhythm.downbeats_s,
            builds=inputs.builds,
            drops=inputs.drops,
            vocal_segments=inputs.vocal_segments,
            chords=inputs.chords,
            onset_env=inputs.onset_envelope,
            stft_mag=inputs.stft_magnitude,
            y_harm=inputs.harmonic_audio,
        )
        return StructureAnalysis(
            sections=list(result["sections"]),
            boundary_times_s=[float(value) for value in result["boundary_times_s"]],
            source=self.name,
            source_version=self.version,
            metadata=dict(result.get("meta", {})),
        )


class BeatThisSource:
    """CPJKU beat-this 1.1 adapter (minimal postprocessor; no madmom DBN)."""

    name = "beat_this"
    version = "1.1.0"

    def __init__(
        self,
        *,
        predictor: Callable[[np.ndarray, int], tuple[Any, Any]] | None = None,
        importer: Importer = importlib.import_module,
        checkpoint_path: Path | None = None,
    ) -> None:
        self._predictor = predictor
        self._importer = importer
        self._checkpoint_path = checkpoint_path

    def _load_predictor(self) -> Callable[[np.ndarray, int], tuple[Any, Any]]:
        if self._predictor is not None:
            return self._predictor
        try:
            module = self._importer("beat_this.inference")
        except ImportError as error:
            raise MissingMIRDependencyError(
                "beat-this is selected but unavailable; run `uv sync --extra mir-beats`. "
                "The default DSP source requires no model dependency."
            ) from error
        checkpoint = self._checkpoint_path
        if checkpoint is None:
            configured = os.getenv("TWINKLR_BEAT_THIS_CHECKPOINT")
            checkpoint = Path(configured).expanduser() if configured else None
        if checkpoint is None:
            cached = Path.home() / ".cache/torch/hub/checkpoints/beat_this-final0.ckpt"
            if cached.is_file():
                checkpoint = cached
        if checkpoint is None or not checkpoint.is_file():
            raise MissingMIRDependencyError(
                "beat-this 1.1.0 is installed but its local final0 checkpoint is unavailable. "
                "Download the upstream checkpoint separately, then set "
                "TWINKLR_BEAT_THIS_CHECKPOINT to that file; Twinklr never downloads model "
                "weights during an offline analysis or test run."
            )
        predictor = cast(
            "Callable[[np.ndarray, int], tuple[Any, Any]]",
            module.Audio2Beats(checkpoint_path=str(checkpoint), device="cpu", dbn=False),
        )
        return predictor

    def analyze_rhythm(self, inputs: MIRInput) -> RhythmAnalysis:
        # Upstream Audio2Beats returns (beats, downbeats), in that order.
        beats_raw, downbeats_raw = self._load_predictor()(inputs.audio, inputs.sample_rate)
        beats_s = _clean_times(beats_raw)
        downbeats_s = _clean_times(downbeats_raw)
        return RhythmAnalysis(
            tempo_bpm=_tempo_from_beats(beats_s),
            beats_s=beats_s,
            downbeats_s=downbeats_s,
            beats_per_bar=_beats_per_bar(beats_s, downbeats_s),
            beat_confidence=1.0,
            downbeat_confidence=1.0,
            source=self.name,
            source_version=self.version,
            metadata={"postprocessor": "minimal", "dbn": False},
        )


class AllInOneSource:
    """all-in-one-mlx 1.0.6 labeled-section adapter for Apple Silicon."""

    name = "allinone"
    version = "1.0.6"

    def __init__(
        self,
        *,
        analyzer: Callable[[Path], Any] | None = None,
        importer: Importer = importlib.import_module,
    ) -> None:
        self._analyzer = analyzer
        self._importer = importer

    def _load_analyzer(self) -> Callable[[Path], Any]:
        if self._analyzer is not None:
            return self._analyzer
        try:
            module = self._importer("allin1_mlx")
        except ImportError as error:
            raise MissingMIRDependencyError(
                "all-in-one-mlx is selected but unavailable. Version 1.0.6 requires "
                "librosa>=0.11 while Twinklr currently pins librosa<0.11; use an isolated "
                "model environment until the Phase 4 ML-chain upgrade resolves that conflict."
            ) from error
        return cast("Callable[[Path], Any]", module.analyze)

    def analyze_structure(
        self, inputs: MIRInput, rhythm: RhythmAnalysis | None = None
    ) -> StructureAnalysis:
        result = self._load_analyzer()(inputs.audio_path)
        if isinstance(result, list):
            if len(result) != 1:
                raise ValueError("all-in-one-mlx returned an unexpected result count")
            result = result[0]
        sections = [
            {
                "section_id": index,
                "start_s": float(item.start),
                "end_s": float(item.end),
                "duration_s": float(item.end) - float(item.start),
                "label": str(item.label),
                "similarity": 0.0,
                "repeat_count": 0,
                "energy_rank": 0.5,
                "energy": 0.5,
                "repetition": 0.5,
                "confidence": 1.0,
                "label_confidence": 1.0,
                "boundary_strength_in": 1.0,
                "boundary_strength_out": 1.0,
            }
            for index, item in enumerate(result.segments)
        ]
        boundaries = sorted(
            {
                *(float(item.start) for item in result.segments),
                *(float(item.end) for item in result.segments),
            }
        )
        return StructureAnalysis(
            sections=sections,
            boundary_times_s=boundaries,
            source=self.name,
            source_version=self.version,
            metadata={"model": "harmonix-all", "runtime": "mlx"},
        )


def create_rhythm_source(name: RhythmSourceName) -> RhythmSource:
    """Construct a configured rhythm implementation without importing optional packages."""
    if name is RhythmSourceName.DSP:
        return DSPSource()
    if name is RhythmSourceName.BEAT_THIS:
        return BeatThisSource()
    raise ValueError(f"Unsupported rhythm source: {name}")


def create_structure_source(name: StructureSourceName) -> StructureSource:
    """Construct a configured structure implementation without importing optional packages."""
    if name is StructureSourceName.DSP:
        return DSPSource()
    if name is StructureSourceName.ALLINONE:
        return AllInOneSource()
    raise ValueError(f"Unsupported structure source: {name}")
