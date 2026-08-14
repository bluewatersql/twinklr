"""Section detection reads pre-computed RMS on the timeline it indexes.

Section boundaries, beats and descriptors are all computed on the trimmed ("work")
signal, while callers hand in an RMS curve computed over the whole file. Passing
that curve through unchanged reads every section's energy from the wrong offset and
makes the fade-out time cross the trim boundary twice.
"""

from __future__ import annotations

from typing import Any

import librosa
import numpy as np
import pytest

from twinklr.core.audio.structure import orchestration, sections, segmentation
from twinklr.core.audio.structure.sections import (
    SongSectionDetector,
    align_rms_to_work_timeline,
)

SR = 22050
HOP = 512
LEADING_SILENCE_S = 5.0
FADE_START_S = 35.0  # leading silence + 30s of body


@pytest.fixture
def audio_with_leading_silence() -> np.ndarray:
    """5s of silence, 30s of three distinct sections, then a 6s fade-out."""

    def tone(freq: float, seconds: float, amp: float, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        t = np.linspace(0.0, seconds, int(SR * seconds), endpoint=False, dtype=np.float32)
        body = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * 2 * freq * t)
        pulse = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 2.0 * t))  # 120 BPM accents
        noise = rng.standard_normal(t.size).astype(np.float32) * 0.05
        return ((body * pulse + noise) * amp).astype(np.float32)

    silence = np.zeros(int(SR * LEADING_SILENCE_S), dtype=np.float32)
    fade = tone(330.0, 6.0, 0.5, 5)
    fade *= np.linspace(1.0, 0.0, fade.size, dtype=np.float32)

    return np.concatenate(
        [
            silence,
            tone(220.0, 10.0, 0.15, 1),
            tone(440.0, 10.0, 0.9, 2),
            tone(330.0, 10.0, 0.35, 3),
            fade,
        ]
    ).astype(np.float32)


def _full_file_rms(y: np.ndarray) -> np.ndarray:
    return librosa.feature.rms(y=y, hop_length=HOP)[0].astype(np.float32)


class TestAlignRmsToWorkTimeline:
    """The offset-correction helper itself."""

    def test_no_offset_passes_through(self) -> None:
        """Without trimming the curve is used as-is."""
        rms = np.arange(100, dtype=np.float32)
        out = align_rms_to_work_timeline(
            rms, sr=SR, hop_length=HOP, start_offset_s=0.0, duration_work=10.0
        )
        assert out is not None
        np.testing.assert_array_equal(out, rms)

    def test_slices_from_the_trim_offset(self) -> None:
        """With a trim offset the curve starts at the offset's frame."""
        rms = np.arange(2000, dtype=np.float32)
        offset_s = 5.0
        duration_work = 20.0

        out = align_rms_to_work_timeline(
            rms, sr=SR, hop_length=HOP, start_offset_s=offset_s, duration_work=duration_work
        )

        start_frame = int(librosa.time_to_frames(offset_s, sr=SR, hop_length=HOP))
        assert out is not None
        assert out[0] == pytest.approx(float(start_frame))
        assert len(out) == int(librosa.time_to_frames(duration_work, sr=SR, hop_length=HOP)) + 1

    def test_none_stays_none(self) -> None:
        """A missing curve stays missing (callers recompute from y_work)."""
        assert (
            align_rms_to_work_timeline(
                None, sr=SR, hop_length=HOP, start_offset_s=5.0, duration_work=10.0
            )
            is None
        )


class TestTrimOffsetWithPrecomputedRms:
    """A pre-computed RMS curve reaches the pipeline on the work timeline."""

    def test_section_energy_correct_with_leading_silence(
        self, audio_with_leading_silence: np.ndarray, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Descriptors read energy from the trimmed timeline, not the original one."""
        seen: dict[str, Any] = {}
        real = orchestration.compute_section_descriptors

        def spy(**kwargs: Any) -> Any:
            seen["rms"] = kwargs["rms_for_energy"]
            return real(**kwargs)

        monkeypatch.setattr(sections.orchestration, "compute_section_descriptors", spy)

        detector = SongSectionDetector()
        result = detector.detect(
            audio_with_leading_silence,
            SR,
            hop_length=HOP,
            rms_for_energy=_full_file_rms(audio_with_leading_silence),
        )

        assert result["meta"]["trim"]["used"] is True
        start_offset_s = result["meta"]["trim"]["start_offset_s"]
        assert start_offset_s == pytest.approx(LEADING_SILENCE_S, abs=0.5)

        y_work, _, _ = detector._trim_audio(
            audio_with_leading_silence, SR, len(audio_with_leading_silence) / SR
        )
        expected = librosa.feature.rms(y=y_work, hop_length=HOP)[0].astype(np.float32)

        got = np.asarray(seen["rms"], dtype=np.float32)
        assert len(got) == pytest.approx(len(expected), abs=1)
        # Ignore the first frames: y_work is reflect-padded where the original had silence.
        n = min(len(got), len(expected))
        np.testing.assert_allclose(got[4:n], expected[4:n], atol=1e-3)

    def test_fade_out_offset_applied_once(
        self, audio_with_leading_silence: np.ndarray, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fade is found where it is, not shifted by the trim offset."""
        seen: dict[str, Any] = {}
        real = segmentation.detect_fade_out_start

        def spy(*args: Any, **kwargs: Any) -> float | None:
            fade = real(*args, **kwargs)
            seen["fade_work_s"] = fade
            return fade

        monkeypatch.setattr(sections.segmentation, "detect_fade_out_start", spy)

        result = SongSectionDetector().detect(
            audio_with_leading_silence,
            SR,
            hop_length=HOP,
            rms_for_energy=_full_file_rms(audio_with_leading_silence),
        )

        start_offset_s = result["meta"]["trim"]["start_offset_s"]
        fade_work_s = seen["fade_work_s"]
        assert fade_work_s is not None, "fade-out missed: RMS tail was read off the wrong timeline"

        # One offset, applied once, when mapping the fade back to the original timeline.
        assert fade_work_s + start_offset_s == pytest.approx(FADE_START_S, abs=3.0)

        duration_s = len(audio_with_leading_silence) / SR
        assert max(result["boundary_times_s"]) <= duration_s + 1e-6
