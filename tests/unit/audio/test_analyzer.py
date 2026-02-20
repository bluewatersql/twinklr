"""Tests for AudioAnalyzer orchestration."""

from __future__ import annotations

import tempfile

import numpy as np
import pytest

from twinklr.core.audio.analyzer import AudioAnalyzer


class TestAudioAnalyzer:
    """Tests for AudioAnalyzer class."""

    def test_static_minimal_features_structure(self) -> None:
        """_minimal_features returns expected structure."""
        y = np.zeros(22050, dtype=np.float32)  # 1 second
        result = AudioAnalyzer._minimal_features(
            audio_path="/test/path.mp3",
            y=y,
            sr=22050,
            duration=1.0,
        )

        assert result["schema_version"] == "2.3"
        assert result["audio_path"] == "/test/path.mp3"
        assert result["sr"] == 22050
        assert result["duration_s"] == 1.0
        assert result["tempo_bpm"] == 0.0
        assert result["beats_s"] == []
        assert result["bars_s"] == []
        assert "warnings" in result
