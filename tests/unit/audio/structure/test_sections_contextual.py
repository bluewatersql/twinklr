"""Tests for context-aware section detection improvements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from twinklr.core.audio.structure.sections import (
    detect_song_sections,
    label_section_contextual,
)

if TYPE_CHECKING:
    import numpy as np


class TestContextAwareLabling:
    """Tests for label_section_contextual function."""

    def test_pre_chorus_detection(self) -> None:
        """Section preceded by build and before chorus labeled as pre_chorus."""
        sections = [
            {"start_s": 0.0, "end_s": 20.0, "energy_rank": 0.3, "repeat_count": 0},
            {"start_s": 20.0, "end_s": 35.0, "energy_rank": 0.7, "repeat_count": 0},
            {"start_s": 35.0, "end_s": 55.0, "energy_rank": 0.9, "repeat_count": 3},
        ]

        builds = [{"start_s": 15.0, "end_s": 20.0}]

        label = label_section_contextual(
            idx=1,
            sections=sections,
            chords=[],
            builds=builds,
            drops=[],
            vocal_segments=[],
            energy_rank=0.7,
            repeat_count=0,
            max_similarity=0.5,
            relative_pos=0.2,
            duration=100.0,
        )

        assert label == "pre_chorus"

    def test_breakdown_detection(self) -> None:
        """Section with drop, low vocals, low energy labeled as breakdown."""
        label = label_section_contextual(
            idx=2,
            sections=[
                {"start_s": 0.0, "end_s": 20.0, "energy_rank": 0.5, "repeat_count": 0},
                {"start_s": 20.0, "end_s": 40.0, "energy_rank": 0.8, "repeat_count": 0},
                {"start_s": 40.0, "end_s": 50.0, "energy_rank": 0.3, "repeat_count": 0},
            ],
            chords=[],
            builds=[],
            drops=[{"time_s": 41.0}],
            vocal_segments=[],
            energy_rank=0.3,
            repeat_count=0,
            max_similarity=0.4,
            relative_pos=0.4,
            duration=100.0,
        )

        assert label == "breakdown"

    def test_instrumental_detection(self) -> None:
        """Section with low vocals and moderate energy labeled as instrumental."""
        label = label_section_contextual(
            idx=2,
            sections=[
                {"start_s": 0.0, "end_s": 20.0, "energy_rank": 0.5, "repeat_count": 0},
                {"start_s": 20.0, "end_s": 40.0, "energy_rank": 0.8, "repeat_count": 0},
                {"start_s": 40.0, "end_s": 60.0, "energy_rank": 0.6, "repeat_count": 0},
            ],
            chords=[],
            builds=[],
            drops=[],
            vocal_segments=[],  # No vocals
            energy_rank=0.6,
            repeat_count=0,
            max_similarity=0.4,
            relative_pos=0.5,
            duration=100.0,
        )

        assert label == "instrumental"

    def test_chorus_with_drop(self) -> None:
        """Repeated section with drop labeled as chorus."""
        label = label_section_contextual(
            idx=2,
            sections=[
                {"start_s": 0.0, "end_s": 20.0, "energy_rank": 0.5, "repeat_count": 0},
                {"start_s": 20.0, "end_s": 40.0, "energy_rank": 0.8, "repeat_count": 0},
                {"start_s": 40.0, "end_s": 60.0, "energy_rank": 0.7, "repeat_count": 2},
            ],
            chords=[],
            builds=[],
            drops=[{"time_s": 41.0}],
            vocal_segments=[],
            energy_rank=0.7,
            repeat_count=2,
            max_similarity=0.9,
            relative_pos=0.5,
            duration=100.0,
        )

        assert label == "chorus"

    def test_bridge_with_complex_chords(self) -> None:
        """Late section with diverse harmony labeled as bridge."""
        chords = [
            {"time_s": 60.0, "chord": "C:maj"},
            {"time_s": 62.0, "chord": "F#:dim"},
            {"time_s": 64.0, "chord": "Bb:maj"},
            {"time_s": 66.0, "chord": "E:min"},
            {"time_s": 68.0, "chord": "A:7"},
        ]

        label = label_section_contextual(
            idx=3,
            sections=[
                {"start_s": 0.0, "end_s": 20.0, "energy_rank": 0.5, "repeat_count": 0},
                {"start_s": 20.0, "end_s": 40.0, "energy_rank": 0.8, "repeat_count": 0},
                {"start_s": 40.0, "end_s": 60.0, "energy_rank": 0.7, "repeat_count": 2},
                {"start_s": 60.0, "end_s": 70.0, "energy_rank": 0.6, "repeat_count": 0},
            ],
            chords=chords,
            builds=[],
            drops=[],
            vocal_segments=[],
            energy_rank=0.6,
            repeat_count=0,
            max_similarity=0.6,
            relative_pos=0.65,
            duration=100.0,
        )

        assert label == "bridge"


class TestMultiFeatureDetection:
    """Tests for multi-feature section detection."""

    def test_accepts_context_parameters(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function accepts all context parameters without error."""
        import librosa

        # Create mock context data
        beats_s = [0.5, 1.0, 1.5, 2.0, 2.5]
        bars_s = [0.0, 2.0, 4.0]
        builds = [{"start_s": 10.0, "end_s": 15.0}]
        drops = [{"time_s": 15.5}]
        vocal_segments = [{"start_s": 5.0, "end_s": 20.0}]
        chords = [{"time_s": 0.0, "chord": "C:maj"}]

        rms = librosa.feature.rms(y=long_audio, hop_length=hop_length)[0]
        chroma = librosa.feature.chroma_cqt(y=long_audio, sr=sample_rate, hop_length=hop_length)

        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            rms_for_energy=rms,
            chroma_cqt=chroma,
            beats_s=beats_s,
            bars_s=bars_s,
            builds=builds,
            drops=drops,
            vocal_segments=vocal_segments,
            chords=chords,
        )

        assert "sections" in result
        assert "meta" in result
        assert "method" in result["meta"]  # Changed from "improvements"

    def test_backward_compatible_without_context(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function works without context parameters (backward compatible)."""
        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        assert "sections" in result
        assert len(result["sections"]) > 0

    def test_subsections_have_subsection_field(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Subsections have 'subsection' field when split."""
        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        # Check if any sections have subsection field
        has_subsections = any("subsection" in s for s in result["sections"])

        # This might not always be true (depends on audio), so we just verify
        # the field exists when subsections are detected
        if has_subsections:
            for section in result["sections"]:
                if "subsection" in section:
                    assert section["subsection"] in {"a", "b"}
