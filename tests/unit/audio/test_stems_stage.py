"""Discriminating tests for the optional cached stems analysis stage."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import time
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.audio.stems import (
    DemucsStemSeparator,
    SeparatedStems,
    StemFeatures,
    StemStatus,
    analyze_stems,
    apply_stem_consumers,
    make_stems_cache_key,
    stem_result_matches_config,
)
from twinklr.core.caching import FSCache
from twinklr.core.config.models import AppConfig, StemSeparationConfig
from twinklr.core.io import RealFileSystem, absolute_path


class StubSeparator:
    """Weight-free separator used to prove cache and feature behavior."""

    def __init__(self, stems: dict[str, np.ndarray]) -> None:
        self.stems = stems
        self.calls = 0

    def separate(self, audio_path: Path, model_name: str) -> SeparatedStems:
        self.calls += 1
        return SeparatedStems(stems=self.stems, sample_rate=8_000, device="stub")


def _synthetic_stems(*, vocals: bool = True) -> dict[str, np.ndarray]:
    sample_rate = 8_000
    duration_s = 12
    t = np.arange(sample_rate * duration_s, dtype=np.float32) / sample_rate
    drums = np.zeros_like(t)
    for beat_s in np.arange(0.5, duration_s, 0.5):
        start = int(beat_s * sample_rate)
        drums[start : start + 160] = 0.9
    bass = np.linspace(0.01, 1.0, len(t), dtype=np.float32)
    vocal = (0.4 * np.sin(2 * np.pi * 220 * t)).astype(np.float32) if vocals else np.zeros_like(t)
    return {"drums": drums, "bass": bass, "vocals": vocal, "other": np.zeros_like(t)}


def test_stems_stage_disabled_by_default() -> None:
    """The heavyweight stage must remain opt-in."""
    assert StemSeparationConfig().enabled is False


@pytest.mark.asyncio
async def test_stems_cache_key_is_audio_hash_plus_model(tmp_path: Path) -> None:
    """Same audio/model hits; changing either explicit key input misses."""
    first_audio = tmp_path / "first.wav"
    first_audio.write_bytes(b"first-audio")
    second_audio = tmp_path / "second.wav"
    second_audio.write_bytes(b"second-audio")
    cache = FSCache(RealFileSystem(), absolute_path(tmp_path / "cache"))
    separator = StubSeparator(_synthetic_stems())
    enabled = StemSeparationConfig(enabled=True, model_name="htdemucs")

    first = await analyze_stems(first_audio, cache, enabled, separator=separator)
    repeat = await analyze_stems(first_audio, cache, enabled, separator=separator)
    other_model = await analyze_stems(
        first_audio,
        cache,
        enabled.model_copy(update={"model_name": "htdemucs_ft"}),
        separator=separator,
    )
    other_audio = await analyze_stems(second_audio, cache, enabled, separator=separator)

    expected_fingerprint = hashlib.sha256(f"{first.audio_hash}:htdemucs".encode()).hexdigest()
    assert make_stems_cache_key(first.audio_hash, "htdemucs").input_fingerprint == (
        expected_fingerprint
    )
    assert first.cache_hit is False
    assert repeat.cache_hit is True
    assert other_model.cache_hit is False
    assert other_audio.cache_hit is False
    assert separator.calls == 3


@pytest.mark.asyncio
async def test_fallback_sets_status_flag(tmp_path: Path) -> None:
    """Unavailable separation records a result-visible full-mix fallback."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    cache = FSCache(RealFileSystem(), absolute_path(tmp_path / "cache"))

    class MissingSeparator:
        def separate(self, audio_path: Path, model_name: str) -> SeparatedStems:
            raise ImportError("demucs is unavailable")

    stem_result = await analyze_stems(
        audio,
        cache,
        StemSeparationConfig(enabled=True),
        separator=MissingSeparator(),
    )
    features = apply_stem_consumers(
        stem_result,
        full_mix_beat_confidence=0.25,
        beats_s=[0.5, 1.0],
        full_mix_builds_drops={"builds": [], "drops": [], "statistics": {}},
        full_mix_vocal_segments=[],
        full_mix_vocal_statistics={"vocal_coverage_pct": 0.0},
        tempo_bpm=120.0,
        beats_per_bar=4,
    )

    assert stem_result.status == StemStatus.UNAVAILABLE_FULL_MIX_FALLBACK
    assert features["stems"]["status"] == "unavailable_full_mix_fallback"
    assert features["rhythm"]["source"] == "full_mix"
    assert features["energy"]["build_drop_source"] == "full_mix"
    assert features["vocals_source"] == "full_mix"
    assert "demucs is unavailable" in features["stems"]["fallback_reason"]


@pytest.mark.asyncio
async def test_drum_onsets_feed_accent_confidence(tmp_path: Path) -> None:
    """Drum-stem evidence changes the planner-facing beat/accent confidence."""
    result = await _analyze_fixture(tmp_path, vocals=True)
    consumers = _apply_fixture_consumers(result)

    assert consumers["rhythm"]["source"] == "drum_stem"
    assert consumers["rhythm"]["full_mix_beat_confidence"] == 0.1
    assert consumers["rhythm"]["beat_confidence"] > 0.1
    assert consumers["rhythm"]["accent_confidence"] > 0.5


@pytest.mark.asyncio
async def test_bass_energy_feeds_builds_drops(tmp_path: Path) -> None:
    """The build/drop detector receives bass energy when stems are present."""
    result = await _analyze_fixture(tmp_path, vocals=True)
    captured: dict[str, np.ndarray] = {}

    def fake_detector(**kwargs: object) -> dict[str, object]:
        captured["energy_curve"] = np.asarray(kwargs["energy_curve"])
        return {"builds": [{"start_s": 1.0}], "drops": [], "statistics": {}}

    with patch("twinklr.core.audio.stems.detect_builds_and_drops", side_effect=fake_detector):
        consumers = _apply_fixture_consumers(result)

    assert consumers["energy"]["build_drop_source"] == "bass_stem"
    assert consumers["energy"]["builds"] == [{"start_s": 1.0}]
    assert captured["energy_curve"].tolist() == pytest.approx(result.bass_energy)


@pytest.mark.asyncio
async def test_vocal_presence_selects_stem_consumer(tmp_path: Path) -> None:
    """The vocal stem supersedes the full-mix detector when separation succeeds."""
    result = await _analyze_fixture(tmp_path, vocals=True)
    consumers = _apply_fixture_consumers(result)

    assert consumers["vocals_source"] == "vocal_stem"
    assert consumers["vocals"] == result.vocal_segments
    assert consumers["vocal_gate_open"] is True
    assert consumers["full_mix_vocals"] == [{"start_s": 9.0, "end_s": 10.0}]


@pytest.mark.asyncio
async def test_instrumental_fixture_gates_off_transcription(tmp_path: Path) -> None:
    """Synthetic instrumental separation closes the explicit WhisperX gate."""
    result = await _analyze_fixture(tmp_path, vocals=False)
    consumers = _apply_fixture_consumers(result)

    assert result.vocal_presence_pct == 0.0
    assert consumers["vocals_source"] == "vocal_stem"
    assert consumers["vocal_gate_open"] is False


@pytest.mark.asyncio
async def test_vocal_fixture_gates_on_transcription(tmp_path: Path) -> None:
    """Synthetic separated vocals open the explicit WhisperX gate."""
    result = await _analyze_fixture(tmp_path, vocals=True)
    consumers = _apply_fixture_consumers(result)

    assert result.vocal_presence_pct > 0.05
    assert consumers["vocal_gate_open"] is True


def test_mps_failure_retries_once_on_cpu() -> None:
    """The canonical Demucs MPS choice has an explicit CPU safety fallback."""
    constructed_devices: list[str] = []

    class FakeTensor:
        def detach(self) -> FakeTensor:
            return self

        def cpu(self) -> FakeTensor:
            return self

        def numpy(self) -> np.ndarray:
            return np.zeros(8_000, dtype=np.float32)

    class FakeDemucsApi:
        samplerate = 8_000

        def __init__(self, *, model: str, device: str) -> None:
            constructed_devices.append(device)
            self.device = device

        def separate_audio_file(self, audio_path: Path) -> tuple[object, dict[str, FakeTensor]]:
            if self.device == "mps":
                raise RuntimeError("MPS kernel unsupported")
            stems = {name: FakeTensor() for name in ("drums", "bass", "vocals", "other")}
            return object(), stems

    with (
        patch("twinklr.core.audio.stems._demucs_default_device", return_value="mps"),
        patch("twinklr.core.audio.stems._load_demucs_separator", return_value=FakeDemucsApi),
    ):
        result = DemucsStemSeparator().separate(Path("fixture.wav"), "htdemucs")

    assert constructed_devices == ["mps", "cpu"]
    assert result.device == "cpu"
    assert any("mps" in warning.lower() and "cpu" in warning.lower() for warning in result.warnings)


def test_intel_macos_reports_explicit_unavailable_fallback() -> None:
    """The marker exclusion has a matching runtime explanation, not a silent import miss."""
    with (
        patch("twinklr.core.audio.stems.platform.system", return_value="Darwin"),
        patch("twinklr.core.audio.stems.platform.machine", return_value="x86_64"),
        pytest.raises(RuntimeError, match=r"Intel macOS.*NumPy 2.*full-mix fallback"),
    ):
        DemucsStemSeparator().separate(Path("fixture.wav"), "htdemucs")


def test_unavailable_result_is_never_accepted_as_fresh_enabled_cache() -> None:
    """Installing Demucs after a fallback retries separation instead of serving stale status."""
    config = StemSeparationConfig(enabled=True, model_name="htdemucs")
    unavailable = StemFeatures(
        status=StemStatus.UNAVAILABLE_FULL_MIX_FALLBACK,
        model_name="htdemucs",
        fallback_reason="missing dependency",
    )
    available = unavailable.model_copy(
        update={"status": StemStatus.AVAILABLE, "vocal_gate_open": False}
    )
    disabled = StemFeatures(status=StemStatus.DISABLED_FULL_MIX_FALLBACK)

    assert stem_result_matches_config(unavailable.model_dump(mode="json"), config) is False
    assert stem_result_matches_config(available.model_dump(mode="json"), config) is True
    assert stem_result_matches_config({}, StemSeparationConfig()) is False
    assert (
        stem_result_matches_config(disabled.model_dump(mode="json"), StemSeparationConfig()) is True
    )
    assert (
        stem_result_matches_config(
            available.model_dump(mode="json", exclude={"vocal_gate_open"}), config
        )
        is False
    )


def test_outer_cache_version_stays_threshold_agnostic() -> None:
    """Threshold freshness is content-validated without fragmenting separation identity."""
    app_config = AppConfig()
    analyzer = object.__new__(AudioAnalyzer)
    analyzer.app_config = app_config
    initial_version = analyzer._audio_cache_version()
    enhancements = app_config.audio_processing.enhancements
    updated_enhancements = enhancements.model_copy(
        update={"stems": enhancements.stems.model_copy(update={"vocal_presence_threshold": 0.75})}
    )
    analyzer.app_config = app_config.model_copy(
        update={
            "audio_processing": app_config.audio_processing.model_copy(
                update={"enhancements": updated_enhancements}
            )
        }
    )

    assert analyzer._audio_cache_version() == initial_version


@pytest.mark.asyncio
async def test_outer_cache_rejects_true_gate_after_threshold_closes(tmp_path: Path) -> None:
    """A raised threshold rebuilds consumers but reuses successful separation."""
    await _assert_threshold_change_reuses_separation(
        tmp_path,
        initial_threshold=0.05,
        updated_threshold=0.5,
        initial_gate=True,
        updated_gate=False,
    )


@pytest.mark.asyncio
async def test_outer_cache_rejects_false_gate_after_threshold_opens(tmp_path: Path) -> None:
    """A lowered threshold rebuilds consumers but reuses successful separation."""
    await _assert_threshold_change_reuses_separation(
        tmp_path,
        initial_threshold=0.5,
        updated_threshold=0.05,
        initial_gate=False,
        updated_gate=True,
    )


def test_short_audio_retains_stem_consumer_provenance() -> None:
    """The short-file fast path must not contradict an available stem result."""
    stem_features = StemFeatures(
        status=StemStatus.AVAILABLE,
        model_name="htdemucs",
        vocal_segments=[{"start_s": 0.0, "end_s": 1.0, "duration_s": 1.0}],
        vocal_presence_pct=0.2,
        vocal_gate_open=True,
    )

    features = AudioAnalyzer._minimal_features(
        "short.wav",
        np.zeros(8_000, dtype=np.float32),
        8_000,
        1.0,
        stem_features,
    )

    assert features["stems"]["status"] == "available"
    assert features["rhythm"]["source"] == "drum_stem"
    assert features["energy"]["build_drop_source"] == "bass_stem"
    assert features["vocals_source"] == "vocal_stem"
    assert features["vocal_gate_open"] is True


@pytest.mark.local_only
def test_real_separation_smoke() -> None:
    """Owner-run Demucs smoke; never downloads weights in the default suite."""
    audio_path = os.environ.get("TWINKLR_REAL_STEMS_AUDIO")
    if not audio_path:
        pytest.skip("Set TWINKLR_REAL_STEMS_AUDIO to a short local fixture song")

    started = time.perf_counter()
    result = DemucsStemSeparator().separate(Path(audio_path), "htdemucs")
    elapsed_s = time.perf_counter() - started

    assert {"drums", "bass", "vocals", "other"}.issubset(result.stems)
    assert elapsed_s < 1_200, "separation exceeded 10x the two-minute MPS expectation"


async def _analyze_fixture(tmp_path: Path, *, vocals: bool) -> StemFeatures:
    audio = tmp_path / ("vocal.wav" if vocals else "instrumental.wav")
    audio.write_bytes(b"audio")
    cache = FSCache(RealFileSystem(), absolute_path(tmp_path / f"cache-{vocals}"))
    return await analyze_stems(
        audio,
        cache,
        StemSeparationConfig(enabled=True, vocal_presence_threshold=0.05),
        separator=StubSeparator(_synthetic_stems(vocals=vocals)),
    )


def _apply_fixture_consumers(result: StemFeatures) -> dict[str, object]:
    return apply_stem_consumers(
        result,
        full_mix_beat_confidence=0.1,
        beats_s=[float(value) for value in np.arange(0.5, 12.0, 0.5)],
        full_mix_builds_drops={"builds": [], "drops": [], "statistics": {}},
        full_mix_vocal_segments=[{"start_s": 9.0, "end_s": 10.0}],
        full_mix_vocal_statistics={"vocal_coverage_pct": 0.08},
        tempo_bpm=120.0,
        beats_per_bar=4,
    )


async def _assert_threshold_change_reuses_separation(
    tmp_path: Path,
    *,
    initial_threshold: float,
    updated_threshold: float,
    initial_gate: bool,
    updated_gate: bool,
) -> None:
    from twinklr.core.audio.models import LyricsBundle
    from twinklr.core.audio.models.enums import StageStatus
    from twinklr.core.audio.models.metadata import EmbeddedMetadata
    from twinklr.core.config.models import JobConfig

    audio = tmp_path / "threshold.wav"
    audio.write_bytes(b"audio")
    stems = _synthetic_stems(vocals=False)
    sample_rate = 8_000
    t = np.arange(sample_rate * 2, dtype=np.float32) / sample_rate
    stems["vocals"][: sample_rate * 2] = 0.4 * np.sin(2 * np.pi * 220 * t)
    separator = StubSeparator(stems)
    base_app_config = AppConfig(cache_dir=str(tmp_path / "bundle-cache"))
    initial_enhancements = base_app_config.audio_processing.enhancements.model_copy(
        update={
            "stems": StemSeparationConfig(
                enabled=True,
                vocal_presence_threshold=initial_threshold,
            )
        }
    )
    initial_app_config = base_app_config.model_copy(
        update={
            "audio_processing": base_app_config.audio_processing.model_copy(
                update={"enhancements": initial_enhancements}
            )
        }
    )
    updated_enhancements = initial_enhancements.model_copy(
        update={
            "stems": initial_enhancements.stems.model_copy(
                update={"vocal_presence_threshold": updated_threshold}
            )
        }
    )
    updated_app_config = base_app_config.model_copy(
        update={
            "audio_processing": base_app_config.audio_processing.model_copy(
                update={"enhancements": updated_enhancements}
            )
        }
    )
    gates: list[bool | None] = []

    class RecordingLyricsPipeline:
        async def resolve(self, **kwargs: object) -> LyricsBundle:
            gate = kwargs.get("vocal_gate_open")
            gates.append(gate if isinstance(gate, bool) else None)
            return LyricsBundle(schema_version="1.0.0", stage_status=StageStatus.SKIPPED)

    def minimal_process(
        audio_path: str,
        genre: str | None = None,
        stem_features: StemFeatures | None = None,
    ) -> dict[str, object]:
        del genre
        return AudioAnalyzer._minimal_features(
            audio_path,
            np.zeros(sample_rate, dtype=np.float32),
            sample_rate,
            1.0,
            stem_features,
        )

    async def run(app_config: AppConfig):
        analyzer = AudioAnalyzer(app_config, JobConfig(), stem_separator=separator)
        analyzer.metadata_pipeline = None
        analyzer.lyrics_pipeline = RecordingLyricsPipeline()
        with (
            patch.object(
                analyzer,
                "_extract_embedded_metadata_fast",
                new=AsyncMock(return_value=EmbeddedMetadata()),
            ),
            patch.object(analyzer, "_process_audio", side_effect=minimal_process),
        ):
            return await analyzer.analyze(str(audio))

    initial = await run(initial_app_config)
    refreshed = await run(updated_app_config)

    assert initial.features["vocal_gate_open"] is initial_gate
    assert refreshed.features["vocal_gate_open"] is updated_gate
    assert refreshed.features["stems"]["cache_hit"] is True
    assert gates == [initial_gate, updated_gate]
    assert separator.calls == 1
