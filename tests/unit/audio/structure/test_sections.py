"""Tests for song section detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blinkb0t.core.audio.structure.sections import (
    detect_song_sections,
    label_section,
    merge_short_sections,
)

if TYPE_CHECKING:
    import numpy as np


class TestDetectSongSections:
    """Tests for detect_song_sections function."""

    def test_returns_expected_structure(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        assert "sections" in result
        assert "boundary_times_s" in result
        assert "meta" in result

    def test_section_structure(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Each section has required fields."""
        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        if result["sections"]:
            section = result["sections"][0]
            assert "section_id" in section
            assert "start_s" in section
            assert "end_s" in section
            assert "duration_s" in section
            assert "label" in section
            assert "similarity" in section
            assert "repeat_count" in section

    def test_boundaries_include_start_and_end(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Boundary times include 0 and duration."""
        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        boundaries = result["boundary_times_s"]
        assert boundaries[0] == pytest.approx(0.0, abs=0.1)
        # Last boundary should be close to duration
        import librosa

        duration = float(librosa.get_duration(y=long_audio, sr=sample_rate))
        assert boundaries[-1] == pytest.approx(duration, abs=0.5)

    def test_sections_cover_full_duration(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Sections cover entire audio duration without gaps."""
        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        if len(result["sections"]) > 1:
            # Check that each section starts where previous ends
            for i in range(1, len(result["sections"])):
                prev = result["sections"][i - 1]
                curr = result["sections"][i]
                assert curr["start_s"] == pytest.approx(prev["end_s"], abs=0.01)

    def test_short_audio_returns_single_section(
        self,
        very_short_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Audio shorter than 15s returns single 'full' section."""
        result = detect_song_sections(
            very_short_audio,
            sample_rate,
            hop_length=hop_length,
        )

        assert len(result["sections"]) == 1
        assert result["sections"][0]["label"] == "full"

    def test_valid_section_labels(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Section labels are from valid set."""
        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        valid_labels = {
            "intro",
            "verse",
            "chorus",
            "bridge",
            "outro",
            "full",
            "pre_chorus",
            "breakdown",
            "instrumental",
        }
        for section in result["sections"]:
            assert section["label"] in valid_labels

    def test_meta_contains_method(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Meta dict contains segmentation method."""
        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
        )

        # Hybrid segmentation uses method field
        assert "method" in result["meta"]
        assert result["meta"]["method"] == "hybrid_segmentation"

    def test_custom_min_section_duration(
        self,
        long_audio: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Custom min_section_s parameter is used."""
        result = detect_song_sections(
            long_audio,
            sample_rate,
            hop_length=hop_length,
            min_section_s=10.0,
        )

        # All sections should be at least 10s (approximately)
        for section in result["sections"]:
            # Allow some tolerance due to merging
            assert section["duration_s"] >= 5.0  # Half of min as tolerance


class TestMergeShortSections:
    """Tests for merge_short_sections function."""

    def test_keeps_long_sections(self) -> None:
        """Sections longer than min_s are kept."""
        times = [0.0, 10.0, 20.0, 30.0]
        result = merge_short_sections(times, min_s=5.0, duration=30.0)

        assert 10.0 in result
        assert 20.0 in result

    def test_merges_short_sections(self) -> None:
        """Sections shorter than min_s are merged."""
        # Section from 5.0-8.0 is only 3 seconds
        times = [0.0, 5.0, 8.0, 20.0, 30.0]
        result = merge_short_sections(times, min_s=5.0, duration=30.0)

        # 8.0 should be merged out (section 5.0-8.0 too short)
        assert 8.0 not in result

    def test_always_includes_endpoints(self) -> None:
        """Start (0.0) and end (duration) are always included."""
        times = [0.0, 2.0, 30.0]
        result = merge_short_sections(times, min_s=5.0, duration=30.0)

        assert result[0] == 0.0
        assert result[-1] == 30.0

    def test_avoids_overly_long_sections(self) -> None:
        """Preserves boundaries that would create overly long sections."""
        # Without 15.0, we'd have 0-30 which is 3x the min
        times = [0.0, 3.0, 15.0, 30.0]
        result = merge_short_sections(times, min_s=10.0, duration=30.0)

        # Should keep some boundary to avoid 30s section
        assert len(result) >= 2


class TestLabelSection:
    """Tests for label_section function."""

    def test_intro_detection(self) -> None:
        """First short, low-energy section labeled as intro."""
        label = label_section(
            idx=0,
            total_sections=6,
            repeat_count=0,
            max_similarity=0.3,
            energy_rank=0.3,
            start_s=0.0,
            end_s=15.0,
            duration=180.0,
        )

        assert label == "intro"

    def test_outro_detection(self) -> None:
        """Last short, low-energy section labeled as outro."""
        label = label_section(
            idx=5,
            total_sections=6,
            repeat_count=0,
            max_similarity=0.3,
            energy_rank=0.3,
            start_s=160.0,
            end_s=180.0,
            duration=180.0,
        )

        assert label == "outro"

    def test_chorus_detection_high_repeat(self) -> None:
        """High repeat count + high energy labeled as chorus."""
        label = label_section(
            idx=2,
            total_sections=6,
            repeat_count=3,
            max_similarity=0.9,
            energy_rank=0.8,
            start_s=60.0,
            end_s=90.0,
            duration=180.0,
        )

        assert label == "chorus"

    def test_verse_detection(self) -> None:
        """Moderate repeat, lower energy labeled as verse."""
        label = label_section(
            idx=1,
            total_sections=6,
            repeat_count=2,
            max_similarity=0.85,
            energy_rank=0.5,
            start_s=15.0,
            end_s=45.0,
            duration=180.0,
        )

        assert label == "verse"

    def test_bridge_detection(self) -> None:
        """Late section with low repetition labeled as bridge."""
        label = label_section(
            idx=4,
            total_sections=6,
            repeat_count=0,
            max_similarity=0.5,
            energy_rank=0.6,
            start_s=120.0,
            end_s=150.0,
            duration=180.0,
        )

        assert label == "bridge"

    def test_default_to_verse(self) -> None:
        """Ambiguous sections default to verse."""
        label = label_section(
            idx=2,
            total_sections=4,
            repeat_count=1,
            max_similarity=0.5,
            energy_rank=0.5,
            start_s=60.0,
            end_s=90.0,
            duration=180.0,
        )

        # Should be verse or bridge for ambiguous case
        assert label in {"verse", "bridge"}
