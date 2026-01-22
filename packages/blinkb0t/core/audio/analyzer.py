"""Audio analyzer - extracts musical features from audio files.

This module provides the AudioAnalyzer class which replaces the old
process_song() module function. It follows the manager pattern where
configuration is provided at initialization.

Example:
    analyzer = AudioAnalyzer(app_config, job_config)
    features = analyzer.analyze("song.mp3")
"""

from __future__ import annotations

import logging
from typing import Any

import librosa
import numpy as np

# Import all the analysis modules
from blinkb0t.core.audio.advanced.tension import compute_tension_curve
from blinkb0t.core.audio.cache import (
    load_cached_features,
    save_cached_features,
)
from blinkb0t.core.audio.energy.builds_drops import detect_builds_and_drops
from blinkb0t.core.audio.energy.multiscale import extract_smoothed_energy
from blinkb0t.core.audio.harmonic.chords import detect_chords
from blinkb0t.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
from blinkb0t.core.audio.harmonic.key import detect_musical_key, extract_chroma
from blinkb0t.core.audio.harmonic.pitch import extract_pitch_tracking
from blinkb0t.core.audio.rhythm.beats import (
    compute_beats,
    detect_downbeats_phase_aligned,
    detect_time_signature,
)
from blinkb0t.core.audio.rhythm.tempo import detect_tempo_changes
from blinkb0t.core.audio.spectral.bands import extract_dynamic_features
from blinkb0t.core.audio.spectral.basic import extract_spectral_features
from blinkb0t.core.audio.spectral.vocals import detect_vocals
from blinkb0t.core.audio.structure.sections import detect_song_sections
from blinkb0t.core.audio.timeline.builder import build_timeline_export
from blinkb0t.core.audio.validation.validator import validate_features
from blinkb0t.core.config.models import AppConfig, JobConfig
from blinkb0t.core.utils.checkpoint import CheckpointManager, CheckpointType

logger = logging.getLogger(__name__)


class AudioAnalyzer:
    """Analyzes audio files to extract musical features.

    Provides comprehensive audio analysis including:
    - Tempo, beats, bars, downbeats
    - Energy at multiple temporal scales
    - Spectral characteristics
    - Dynamic features (frequency bands, transients)
    - Song structure (sections with labels)
    - Harmonic analysis (key, chords, pitch)
    - Unified timeline for lighting synchronization

    Results are cached to avoid reprocessing the same audio file.
    """

    def __init__(self, app_config: AppConfig, job_config: JobConfig):
        """Initialize audio analyzer with configuration.

        Args:
            app_config: Application configuration (audio processing settings)
            job_config: Job configuration (checkpoint settings)
        """
        self.app_config = app_config
        self.job_config = job_config
        self.checkpoint_manager = CheckpointManager(job_config=job_config)

    def analyze(
        self,
        audio_path: str,
        *,
        force_reprocess: bool = False,
    ) -> dict[str, Any]:
        """Analyze audio file to extract musical features.

        Checks checkpoint and cache before reprocessing. Results are saved
        to both checkpoint (per-job) and cache (global).

        Args:
            audio_path: Path to audio file (mp3, wav, etc.)
            force_reprocess: If True, skip cache and reprocess

        Returns:
            Comprehensive feature dictionary with schema_version 2.3

        Example:
            analyzer = AudioAnalyzer(app_config, job_config)
            features = analyzer.analyze("song.mp3")
            tempo = features["tempo_bpm"]
            beats = features["beats_s"]
        """
        # Check checkpoint first

        checkpoint = self.checkpoint_manager.read_checkpoint(CheckpointType.AUDIO)
        if checkpoint:
            logger.debug("Using checkpointed features")
            return checkpoint

        # Check cache (unless forcing reprocess)
        if not force_reprocess:
            cached = load_cached_features(audio_path, "features", app_config=self.app_config)
            if cached:
                logger.debug("Using cached features")
                self.checkpoint_manager.write_checkpoint(CheckpointType.AUDIO, cached)
                return cached

        # Process audio
        logger.info(f"Analyzing audio: {audio_path}")
        features = self._process_audio(audio_path)

        # Save to cache and checkpoint
        save_cached_features(audio_path, "features", features, app_config=self.app_config)
        self.checkpoint_manager.write_checkpoint(CheckpointType.AUDIO, features)

        return features

    def _process_audio(self, audio_path: str) -> dict[str, Any]:
        """Process audio file (internal implementation).

        Args:
            audio_path: Path to audio file

        Returns:
            Feature dictionary
        """
        hop_length = int(self.app_config.audio_processing.hop_length)
        frame_length = int(self.app_config.audio_processing.frame_length)

        # Load audio
        y, sr_raw = librosa.load(audio_path, sr=None, mono=True)
        sr = int(sr_raw)  # Ensure sr is int
        duration = float(len(y)) / float(sr)

        # Handle very short audio
        if duration < 10.0:
            logger.warning(f"Audio too short ({duration:.1f}s) for meaningful analysis")
            return self._minimal_features(audio_path, y, sr, duration)

        # HPSS decomposition - do this first to get onset envelope
        harmonic, percussive = compute_hpss(y)
        onset_env = compute_onset_env(percussive, sr, hop_length=hop_length)

        # Core rhythm analysis - uses onset envelope
        tempo_bpm, beat_frames = compute_beats(onset_env=onset_env, sr=sr, hop_length=hop_length)
        time_sig_result = detect_time_signature(beat_frames=beat_frames, onset_env=onset_env)
        time_sig_label = time_sig_result["time_signature"]
        # Extract beats_per_bar from time signature (e.g., "4/4" -> 4, "3/4" -> 3)
        beats_per_bar = int(time_sig_label.split("/")[0])

        # Convert beat frames to times
        beats_s = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).tolist()

        # Detect downbeats - need to extract chroma first for the function
        chroma = extract_chroma(y, sr, hop_length=hop_length)
        downbeat_result = detect_downbeats_phase_aligned(
            beat_frames=beat_frames,
            sr=sr,
            hop_length=hop_length,
            onset_env=onset_env,
            chroma_cqt=chroma,
            beats_per_bar=beats_per_bar,
        )
        bars_s = [db["time_s"] for db in downbeat_result["downbeats"]]
        downbeats_idx = [db["beat_index"] for db in downbeat_result["downbeats"]]

        # Energy analysis
        energy_result = extract_smoothed_energy(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )
        rms_norm = energy_result["raw"]
        rms_times_s = energy_result["times_s"]

        builds_drops = detect_builds_and_drops(
            energy_curve=rms_norm,
            times_s=rms_times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=tempo_bpm,
        )
        builds = builds_drops["builds"]
        drops = builds_drops["drops"]

        # Spectral analysis
        spectral_features = extract_spectral_features(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )
        dynamic_features = extract_dynamic_features(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )

        # Extract numpy arrays for vocals detection before removing _np dict
        spectral_centroid_np = spectral_features["_np"]["centroid_norm"]
        spectral_flatness_np = spectral_features["_np"]["flatness_norm"]

        # Vocal detection - needs spectral features and HPSS components
        # Use numpy arrays extracted earlier (before _np dict removal)
        vocal_result = detect_vocals(
            y_harm=harmonic,
            y_perc=percussive,
            spectral_centroid=spectral_centroid_np,
            spectral_flatness=spectral_flatness_np,
            times_s=np.asarray(spectral_features["times_s"]),
            sr=sr,
        )
        # Extract just the segments list for backward compatibility
        vocal_regions = vocal_result["vocal_segments"]

        # Harmonic analysis (chroma already computed above for downbeat detection)
        key_result = detect_musical_key(y, sr, hop_length=hop_length)
        chords = detect_chords(
            chroma_cqt=chroma,
            beat_frames=beat_frames,
            sr=sr,
            hop_length=hop_length,
        )
        pitch = extract_pitch_tracking(y, sr, hop_length=hop_length)

        # Structure analysis
        sections = detect_song_sections(y, sr, hop_length=hop_length)
        tempo_changes = detect_tempo_changes(y, sr, hop_length=hop_length)

        # Tension curve
        tension = compute_tension_curve(
            chroma_cqt=chroma,
            energy_curve=rms_norm,
            spectral_flatness=spectral_features["spectral_flatness"],
            onset_env=onset_env,
            times_s=rms_times_s,
            key_info=key_result,
            sr=sr,
            hop_length=hop_length,
        )

        # Remove _np dicts before final assembly (they contain numpy arrays)
        spectral_features.pop("_np", None)
        dynamic_features.pop("_np", None)

        # Build timeline
        timeline_export = build_timeline_export(
            y=y,
            sr=sr,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=spectral_features["brightness"],
            flatness_norm=spectral_features["spectral_flatness"],
            motion_norm=dynamic_features["motion"],
            chroma_cqt=chroma,
            beats_s=beats_s,
            downbeats_s=bars_s,
            section_bounds_s=sections["boundary_times_s"],
            y_harm=harmonic,
            y_perc=percussive,
        )

        # Assemble results
        features = {
            "schema_version": "2.3",
            "audio_path": audio_path,
            "sr": sr,
            "duration_s": duration,
            "tempo_bpm": tempo_bpm,
            "beats_s": beats_s,
            "bars_s": bars_s,
            "time_signature": time_sig_result,  # Full result dict from detect_time_signature
            "assumptions": {
                "time_signature": time_sig_label,
                "beats_per_bar": beats_per_bar,
            },
            "rhythm": {
                "beat_confidence": time_sig_result.get("confidence", 0.0),
                "downbeats": [int(i) for i in downbeats_idx],
            },
            "energy": {
                "rms_norm": rms_norm.tolist() if isinstance(rms_norm, np.ndarray) else rms_norm,
                "times_s": rms_times_s.tolist()
                if isinstance(rms_times_s, np.ndarray)
                else rms_times_s,
                "builds": builds,
                "drops": drops,
            },
            "spectral": spectral_features,
            "dynamics": dynamic_features,
            "vocals": vocal_regions,
            "harmonic": {
                "chroma": chroma.tolist() if isinstance(chroma, np.ndarray) else chroma,
                "key": key_result,
                "chords": chords,
                "pitch": pitch,
            },
            "structure": sections,
            "tempo_analysis": tempo_changes,
            "tension": tension,
            "timeline": timeline_export["timeline"],  # Extract timeline from export result
            "composites": timeline_export["composites"],  # Add composites at top level
        }

        # Validate
        validation_warnings = validate_features(features)
        if validation_warnings:
            logger.warning(f"Feature validation warnings: {validation_warnings}")

        return features

    @staticmethod
    def _minimal_features(
        audio_path: str, y: np.ndarray, sr: int, duration: float
    ) -> dict[str, Any]:
        """Generate minimal features for very short audio.

        Args:
            audio_path: Path to audio file
            y: Audio samples
            sr: Sample rate
            duration: Duration in seconds

        Returns:
            Minimal feature dictionary
        """
        return {
            "schema_version": "2.3",
            "audio_path": audio_path,
            "sr": sr,
            "duration_s": duration,
            "tempo_bpm": 0.0,
            "beats_s": [],
            "bars_s": [],
            "energy": {"rms_norm": [], "times_s": []},
            "time_signature": {"time_signature": "4/4", "confidence": 0.0, "method": "default"},
            "assumptions": {"time_signature": "4/4 (default)", "beats_per_bar": 4},
            "rhythm": {"beat_confidence": [], "downbeats": []},
            "spectral": {},
            "dynamics": {},
            "structure": {"sections": [], "boundary_times_s": [0.0, duration]},
            "tempo_analysis": {},
            "key": {"key": "C", "mode": "major", "confidence": 0.0},
            "warnings": ["Audio too short for meaningful analysis"],
        }
