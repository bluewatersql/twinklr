"""Analysis warnings and status flags reach the caller.

`validate_features` used to be decorative: its checks read keys the analyzer never
wrote, and its result was logged at DEBUG and dropped. A warning nobody can see is
not a check, so these tests pin both halves — the checks read the current schema,
and the result arrives on SongBundle.warnings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.audio.energy.builds_drops import detect_builds_and_drops
from twinklr.core.audio.harmonic.hpss import HpssResult
from twinklr.core.audio.spectral.vocals import detect_vocals
from twinklr.core.config.models import AppConfig, JobConfig

SR = 22050
DURATION_S = 25.0


def _synthetic_song(path: Path) -> Path:
    """A short tonal song with clear beats, long enough for the full analysis path."""
    t = np.linspace(0.0, DURATION_S, int(SR * DURATION_S), endpoint=False, dtype=np.float32)

    chord = (
        0.5 * np.sin(2 * np.pi * 261.63 * t)
        + 0.3 * np.sin(2 * np.pi * 329.63 * t)
        + 0.3 * np.sin(2 * np.pi * 392.00 * t)
    )
    clicks = np.zeros_like(t)
    for i in range(int(DURATION_S * 2)):  # 120 BPM
        start = int(i * 0.5 * SR)
        clicks[start : start + int(0.01 * SR)] = 0.9

    accented = chord * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 2.0 * t)))
    sf.write(path, (accented + clicks).astype(np.float32), SR)
    return path


@pytest.fixture(scope="module")
def song_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Synthetic song written to disk once for the whole module."""
    return _synthetic_song(tmp_path_factory.mktemp("audio") / "song.wav")


def _analyzer(tmp_path: Path) -> AudioAnalyzer:
    app_config = AppConfig()
    app_config.cache_dir = str(tmp_path / "cache")
    return AudioAnalyzer(app_config, JobConfig())


@pytest.fixture(scope="module")
def real_features(song_path: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Features from one real analysis run."""
    return _analyzer(tmp_path_factory.mktemp("run"))._process_audio(str(song_path))


class TestWarningsReachTheCaller:
    """The validator's result is surfaced, not logged and dropped."""

    def test_process_audio_records_warnings(self, real_features: dict[str, Any]) -> None:
        """A real run carries its validation warnings in the features dict."""
        assert isinstance(real_features["warnings"], list)

    @pytest.mark.asyncio
    async def test_validator_result_reaches_caller(self, tmp_path: Path) -> None:
        """SongBundle.warnings carries what the validation produced."""
        analyzer = _analyzer(tmp_path)
        features = {
            "schema_version": "2.3",
            "sr": SR,
            "hop_length": 512,
            "duration_s": 3.0,
            "warnings": ["Low downbeat phase confidence: 0.11"],
        }

        with (
            patch.object(analyzer, "_process_audio", return_value=features),
            patch("twinklr.core.audio.cache_adapter.load_audio_features_async", return_value=None),
            patch("twinklr.core.audio.cache_adapter.save_audio_features_async"),
        ):
            bundle = await analyzer.analyze(str(tmp_path / "song.wav"))

        assert bundle.warnings == ["Low downbeat phase confidence: 0.11"]

    def test_no_spurious_key_warning_on_real_run(self, real_features: dict[str, Any]) -> None:
        """The every-run "Low key detection confidence: 0.00" warning is gone."""
        assert not any("Low key detection confidence" in w for w in real_features["warnings"]), (
            real_features["warnings"]
        )
        assert real_features["harmonic"]["key"]["confidence"] > 0.3

    def test_downbeat_meta_is_written(self, real_features: dict[str, Any]) -> None:
        """The downbeat check reads a key the analyzer actually writes."""
        meta = real_features["rhythm"]["downbeat_meta"]

        assert "phase_confidence" in meta
        assert 0.0 <= float(meta["phase_confidence"]) <= 1.0


class TestHpssStatusOnBundle:
    """A failed separation is visible on the analysis output."""

    def test_successful_run_flags_separated(self, real_features: dict[str, Any]) -> None:
        """A normal run records that separation happened."""
        assert real_features["harmonic"]["hpss"] == {"separated": True, "error": None}

    def test_hpss_failure_flags_and_warns(self, song_path: Path, tmp_path: Path) -> None:
        """A failed separation sets the flag and adds a warning for the caller."""
        y, _ = sf.read(song_path, dtype="float32")
        failed = HpssResult(harmonic=y.copy(), percussive=y.copy(), separated=False, error="boom")

        with patch("twinklr.core.audio.analyzer.compute_hpss", return_value=failed):
            features = _analyzer(tmp_path)._process_audio(str(song_path))

        assert features["harmonic"]["hpss"]["separated"] is False
        assert features["harmonic"]["hpss"]["error"] == "boom"
        assert any("HPSS separation failed" in w for w in features["warnings"])


class TestDetectedParametersAreThreaded:
    """Detected values reach the stages that need them."""

    def test_beats_per_bar_and_hop_are_passed_through(
        self, song_path: Path, tmp_path: Path
    ) -> None:
        """Builds get the detected beats_per_bar; vocals get the configured hop."""
        seen: dict[str, Any] = {}

        def builds_spy(**kwargs: Any) -> Any:
            seen["beats_per_bar"] = kwargs.get("beats_per_bar")
            return detect_builds_and_drops(**kwargs)

        def vocals_spy(**kwargs: Any) -> Any:
            seen["hop_length"] = kwargs.get("hop_length")
            return detect_vocals(**kwargs)

        with (
            patch("twinklr.core.audio.analyzer.detect_builds_and_drops", side_effect=builds_spy),
            patch("twinklr.core.audio.analyzer.detect_vocals", side_effect=vocals_spy),
        ):
            features = _analyzer(tmp_path)._process_audio(str(song_path))

        assert seen["beats_per_bar"] == features["assumptions"]["beats_per_bar"]
        assert seen["hop_length"] == 512  # the configured hop, not one inverted from times_s
