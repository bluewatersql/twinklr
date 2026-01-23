"""End-to-end integration tests for audio analysis pipeline.

These tests use real librosa processing to verify the full pipeline works correctly.
They are slower than unit tests but ensure components integrate properly.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any
import wave

import numpy as np
import pytest


class TestAudioPipelineIntegration:
    """Integration tests for the full audio analysis pipeline."""

    @pytest.fixture
    def sample_rate(self) -> int:
        """Standard sample rate."""
        return 22050

    @pytest.fixture
    def hop_length(self) -> int:
        """Standard hop length."""
        return 512

    @pytest.fixture
    def frame_length(self) -> int:
        """Standard frame length."""
        return 2048

    @pytest.fixture
    def test_audio_path(self, sample_rate: int) -> str:
        """Create a synthetic test audio file (20 seconds)."""
        duration = 20.0
        n_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, n_samples)

        # Create multi-component audio:
        # - Base harmonic (440Hz)
        # - Beat modulation at ~120 BPM (2Hz)
        # - Energy variation (sections)
        audio = np.sin(2 * np.pi * 440 * t)  # A4
        audio += 0.5 * np.sin(2 * np.pi * 880 * t)  # A5 (harmonic)

        # Beat modulation
        beat_freq = 2.0  # 120 BPM
        audio *= 0.5 + 0.5 * np.sin(2 * np.pi * beat_freq * t)

        # Energy sections
        # 0-6s: intro (quieter)
        # 6-14s: main (louder)
        # 14-20s: outro (quieter)
        envelope = np.ones(n_samples)
        intro_end = int(6 * sample_rate)
        outro_start = int(14 * sample_rate)
        envelope[:intro_end] = 0.5
        envelope[outro_start:] = 0.5
        audio *= envelope

        # Normalize
        audio = audio / np.max(np.abs(audio)) * 0.8
        audio = audio.astype(np.float32)

        # Write to WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            with wave.open(f.name, "w") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                audio_int = (audio * 32767).astype(np.int16)
                wav.writeframes(audio_int.tobytes())
            return f.name

    @pytest.mark.integration
    def test_hpss_and_onset_pipeline(
        self,
        test_audio_path: str,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Test HPSS and onset detection pipeline."""
        import librosa

        from blinkb0t.core.audio.harmonic.hpss import compute_hpss, compute_onset_env

        y, sr = librosa.load(test_audio_path, sr=sample_rate, mono=True)

        # HPSS
        y_harm, y_perc = compute_hpss(y)
        assert len(y_harm) == len(y)
        assert len(y_perc) == len(y)

        # Onset envelope
        onset_env = compute_onset_env(y_perc, sr, hop_length=hop_length)
        assert len(onset_env) > 0
        assert np.max(onset_env) > 0  # Should have some onsets

        Path(test_audio_path).unlink()

    @pytest.mark.integration
    def test_beat_detection_pipeline(
        self,
        test_audio_path: str,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Test beat and tempo detection pipeline."""
        import librosa

        from blinkb0t.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
        from blinkb0t.core.audio.harmonic.key import extract_chroma
        from blinkb0t.core.audio.rhythm.beats import (
            compute_beats,
            detect_downbeats_phase_aligned,
            detect_time_signature,
        )

        y, sr = librosa.load(test_audio_path, sr=sample_rate, mono=True)

        # Get onset envelope
        _, y_perc = compute_hpss(y)
        onset_env = compute_onset_env(y_perc, sr, hop_length=hop_length)

        # Beat detection
        tempo, beat_frames = compute_beats(
            onset_env=onset_env,
            sr=sr,
            hop_length=hop_length,
        )

        assert tempo > 0
        assert len(beat_frames) > 5  # Should detect multiple beats

        # Time signature
        time_sig = detect_time_signature(
            beat_frames=beat_frames,
            onset_env=onset_env,
        )
        assert time_sig["time_signature"] in {"2/4", "3/4", "4/4", "6/8"}

        # Downbeats
        chroma = extract_chroma(y, sr, hop_length=hop_length)
        downbeats = detect_downbeats_phase_aligned(
            beat_frames=beat_frames,
            sr=sr,
            hop_length=hop_length,
            onset_env=onset_env,
            chroma_cqt=chroma,
            beats_per_bar=4,
        )
        assert "downbeats" in downbeats
        assert 0 <= downbeats["phase"] < 4

        Path(test_audio_path).unlink()

    @pytest.mark.integration
    def test_energy_analysis_pipeline(
        self,
        test_audio_path: str,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Test energy analysis pipeline including builds/drops."""
        import librosa

        from blinkb0t.core.audio.energy.builds_drops import detect_builds_and_drops
        from blinkb0t.core.audio.energy.multiscale import extract_smoothed_energy
        from blinkb0t.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
        from blinkb0t.core.audio.rhythm.beats import compute_beats

        y, sr = librosa.load(test_audio_path, sr=sample_rate, mono=True)

        # Energy extraction
        energy = extract_smoothed_energy(y, sr, hop_length=hop_length, frame_length=frame_length)
        assert "raw" in energy
        assert "phrase_level" in energy
        assert len(energy["raw"]) > 0

        # Get rhythm info for builds/drops
        _, y_perc = compute_hpss(y)
        onset_env = compute_onset_env(y_perc, sr, hop_length=hop_length)
        tempo, beat_frames = compute_beats(onset_env=onset_env, sr=sr, hop_length=hop_length)
        beats_s = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).tolist()

        # Builds/drops detection
        energy_np = energy["_np"]["rms_norm"]
        times_np = energy["_np"]["times_s"]

        builds_drops = detect_builds_and_drops(
            energy_curve=energy_np,
            times_s=times_np,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=tempo,
        )

        assert "builds" in builds_drops
        assert "drops" in builds_drops
        assert "profile" in builds_drops

        Path(test_audio_path).unlink()

    @pytest.mark.integration
    def test_spectral_analysis_pipeline(
        self,
        test_audio_path: str,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Test spectral feature extraction pipeline."""
        import librosa

        from blinkb0t.core.audio.spectral.bands import extract_dynamic_features
        from blinkb0t.core.audio.spectral.basic import extract_spectral_features

        y, sr = librosa.load(test_audio_path, sr=sample_rate, mono=True)

        # Spectral features
        spectral = extract_spectral_features(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )
        assert "brightness" in spectral
        assert "fullness" in spectral
        assert "spectral_flatness" in spectral
        assert len(spectral["brightness"]) > 0

        # Dynamic features (frequency bands)
        dynamic = extract_dynamic_features(y, sr, hop_length=hop_length, frame_length=frame_length)
        assert "bass_energy" in dynamic
        assert "mid_energy" in dynamic
        assert "high_energy" in dynamic
        assert "transients" in dynamic

        Path(test_audio_path).unlink()

    @pytest.mark.integration
    def test_harmonic_analysis_pipeline(
        self,
        test_audio_path: str,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Test harmonic analysis pipeline (key, chords)."""
        import librosa

        from blinkb0t.core.audio.harmonic.chords import detect_chords
        from blinkb0t.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
        from blinkb0t.core.audio.harmonic.key import detect_musical_key, extract_chroma
        from blinkb0t.core.audio.rhythm.beats import compute_beats

        y, sr = librosa.load(test_audio_path, sr=sample_rate, mono=True)

        # Key detection
        key = detect_musical_key(y, sr, hop_length=hop_length)
        assert key["key"] in {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"}
        assert key["mode"] in {"major", "minor"}

        # Chroma extraction
        chroma = extract_chroma(y, sr, hop_length=hop_length)
        assert chroma.shape[0] == 12

        # Get beats for chord detection
        _, y_perc = compute_hpss(y)
        onset_env = compute_onset_env(y_perc, sr, hop_length=hop_length)
        _, beat_frames = compute_beats(onset_env=onset_env, sr=sr, hop_length=hop_length)

        # Chord detection
        chords = detect_chords(
            chroma_cqt=chroma,
            beat_frames=beat_frames,
            sr=sr,
            hop_length=hop_length,
        )
        assert "chords" in chords
        assert len(chords["chords"]) == len(beat_frames)

        Path(test_audio_path).unlink()

    @pytest.mark.integration
    def test_structure_analysis_pipeline(
        self,
        test_audio_path: str,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Test structure analysis pipeline (sections)."""
        import librosa

        from blinkb0t.core.audio.structure.sections import detect_song_sections

        y, sr = librosa.load(test_audio_path, sr=sample_rate, mono=True)

        sections = detect_song_sections(y, sr, hop_length=hop_length)

        assert "sections" in sections
        assert "boundary_times_s" in sections
        assert len(sections["sections"]) >= 1

        # Check section coverage
        if len(sections["sections"]) > 1:
            first = sections["sections"][0]
            last = sections["sections"][-1]
            assert first["start_s"] == pytest.approx(0.0, abs=0.5)
            # Last section end should be close to duration
            duration = librosa.get_duration(y=y, sr=sr)
            assert last["end_s"] == pytest.approx(duration, abs=1.0)

        Path(test_audio_path).unlink()

    @pytest.mark.integration
    def test_timeline_builder_pipeline(
        self,
        test_audio_path: str,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Test timeline builder with real features."""
        import librosa

        from blinkb0t.core.audio.energy.multiscale import extract_smoothed_energy
        from blinkb0t.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
        from blinkb0t.core.audio.harmonic.key import extract_chroma
        from blinkb0t.core.audio.rhythm.beats import compute_beats
        from blinkb0t.core.audio.spectral.bands import extract_dynamic_features
        from blinkb0t.core.audio.spectral.basic import extract_spectral_features
        from blinkb0t.core.audio.timeline.builder import build_timeline_export

        y, sr = librosa.load(test_audio_path, sr=sample_rate, mono=True)

        # Extract all required features
        y_harm, y_perc = compute_hpss(y)
        onset_env = compute_onset_env(y_perc, sr, hop_length=hop_length)

        energy = extract_smoothed_energy(y, sr, hop_length=hop_length, frame_length=frame_length)
        spectral = extract_spectral_features(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )
        dynamic = extract_dynamic_features(y, sr, hop_length=hop_length, frame_length=frame_length)
        chroma = extract_chroma(y, sr, hop_length=hop_length)

        _, beat_frames = compute_beats(onset_env=onset_env, sr=sr, hop_length=hop_length)
        beats_s = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).tolist()

        # Build timeline
        timeline = build_timeline_export(
            y=y,
            sr=sr,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=energy["_np"]["rms_norm"],
            brightness_norm=spectral["_np"]["centroid_norm"],
            flatness_norm=spectral["_np"]["flatness_norm"],
            motion_norm=dynamic["_np"]["motion_norm"],
            chroma_cqt=chroma,
            beats_s=beats_s,
            downbeats_s=beats_s[::4],  # Every 4th beat
            section_bounds_s=[0.0, 10.0, 20.0],
            y_harm=y_harm,
            y_perc=y_perc,
        )

        assert "timeline" in timeline
        assert "composites" in timeline
        assert "show_intensity" in timeline["composites"]
        assert len(timeline["composites"]["show_intensity"]) > 0

        Path(test_audio_path).unlink()

    @pytest.mark.integration
    def test_full_feature_extraction_pipeline(
        self,
        test_audio_path: str,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Test complete feature extraction flow (simulating AudioAnalyzer)."""
        import librosa

        from blinkb0t.core.audio.energy.builds_drops import detect_builds_and_drops
        from blinkb0t.core.audio.energy.multiscale import extract_smoothed_energy
        from blinkb0t.core.audio.harmonic.chords import detect_chords
        from blinkb0t.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
        from blinkb0t.core.audio.harmonic.key import detect_musical_key, extract_chroma
        from blinkb0t.core.audio.rhythm.beats import (
            compute_beats,
            detect_downbeats_phase_aligned,
            detect_time_signature,
        )
        from blinkb0t.core.audio.spectral.bands import extract_dynamic_features
        from blinkb0t.core.audio.spectral.basic import extract_spectral_features
        from blinkb0t.core.audio.structure.sections import detect_song_sections
        from blinkb0t.core.audio.validation.validator import validate_features

        y, sr = librosa.load(test_audio_path, sr=sample_rate, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)

        # Step 1: HPSS
        _, y_perc = compute_hpss(y)
        onset_env = compute_onset_env(y_perc, sr, hop_length=hop_length)

        # Step 2: Rhythm
        tempo, beat_frames = compute_beats(onset_env=onset_env, sr=sr, hop_length=hop_length)
        time_sig = detect_time_signature(beat_frames=beat_frames, onset_env=onset_env)
        beats_per_bar = int(time_sig["time_signature"].split("/")[0])

        beats_s = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).tolist()
        chroma = extract_chroma(y, sr, hop_length=hop_length)
        downbeats = detect_downbeats_phase_aligned(
            beat_frames=beat_frames,
            sr=sr,
            hop_length=hop_length,
            onset_env=onset_env,
            chroma_cqt=chroma,
            beats_per_bar=beats_per_bar,
        )
        bars_s = [db["time_s"] for db in downbeats["downbeats"]]

        # Step 3: Energy
        energy = extract_smoothed_energy(y, sr, hop_length=hop_length, frame_length=frame_length)
        builds_drops = detect_builds_and_drops(
            energy_curve=energy["_np"]["rms_norm"],
            times_s=energy["_np"]["times_s"],
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=tempo,
        )

        # Step 4: Spectral
        spectral = extract_spectral_features(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )
        dynamic = extract_dynamic_features(y, sr, hop_length=hop_length, frame_length=frame_length)

        # Step 5: Harmonic
        key = detect_musical_key(y, sr, hop_length=hop_length)
        chords = detect_chords(
            chroma_cqt=chroma, beat_frames=beat_frames, sr=sr, hop_length=hop_length
        )

        # Step 6: Structure
        sections = detect_song_sections(y, sr, hop_length=hop_length)

        # Assemble result (simplified)
        features: dict[str, Any] = {
            "schema_version": "2.3",
            "sr": sr,
            "duration_s": duration,
            "tempo_bpm": tempo,
            "beats_s": beats_s,
            "bars_s": bars_s,
            "time_signature": time_sig,
            "key": key,
            "rhythm": {"downbeat_meta": {"phase_confidence": downbeats["phase_confidence"]}},
            "energy": {"builds": builds_drops["builds"], "drops": builds_drops["drops"]},
            "spectral": spectral,
            "dynamics": dynamic,
            "harmonic": {"chords": chords},
            "structure": sections,
        }

        # Validate
        _ = validate_features(features)

        # Should be a valid feature set
        assert features["tempo_bpm"] > 0
        assert len(features["beats_s"]) > 0
        assert features["key"]["key"] in {
            "C",
            "C#",
            "D",
            "D#",
            "E",
            "F",
            "F#",
            "G",
            "G#",
            "A",
            "A#",
            "B",
        }

        Path(test_audio_path).unlink()
