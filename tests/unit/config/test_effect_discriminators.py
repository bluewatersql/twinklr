"""Per-path behavioral discriminators for the public config ledger."""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import numpy as np
from pydantic import BaseModel, SecretStr
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.audio.enhancement_factory import EnhancementServiceFactory
from twinklr.core.audio.mir.sources import RhythmAnalysis
from twinklr.core.audio.models import LyricsBundle, LyricWord
from twinklr.core.audio.models.enums import StageStatus
from twinklr.core.config.fixtures import FixtureGroup, Pose
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder
from twinklr.core.sequencer.moving_heads.handlers.wheels import (
    DefaultColorHandler,
    DefaultGoboHandler,
    DefaultShutterHandler,
)


def _alternate(path: str, value: Any) -> Any:
    if value is None and path in {
        "app.project_root",
        "app.audio_processing.enhancements.acoustid_api_key",
        "app.audio_processing.enhancements.genius_access_token",
        "job.assets.asset_base_path",
        "job.output_dir",
        "job.project_name",
    }:
        return "effect-probe"
    if isinstance(value, bool):
        return not value
    if isinstance(value, Enum):
        return next(member for member in type(value) if member != value)
    if isinstance(value, SecretStr):
        return SecretStr("effect-probe-secret")
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="python")
        first = next(iter(payload))
        payload[first] = _alternate(f"{path}.{first}", payload[first])
        return type(value).model_validate(payload)
    if value is None:
        return 1.0
    if isinstance(value, int):
        return value - 1 if value > 1 else value + 1
    if isinstance(value, float):
        return value / 2 if value else 0.5
    if isinstance(value, str):
        alternatives = {
            "low": "medium",
            "medium": "high",
            "high": "low",
            "minimal": "standard",
            "standard": "full",
            "full": "minimal",
            "yaml": "json",
            "json": "yaml",
            "INFO": "DEBUG",
        }
        return alternatives.get(value, f"{value}-effect-probe")
    if isinstance(value, dict):
        changed = dict(value)
        first = next(iter(changed))
        changed[first] = _alternate(f"{path}.{first}", changed[first])
        return changed
    raise AssertionError(f"no valid discriminator value for {value!r}")


def _changed_config(path: str) -> AppConfig | JobConfig:
    root_name, *parts = path.split(".")
    root: AppConfig | JobConfig = AppConfig() if root_name == "app" else JobConfig()
    payload = root.model_dump(mode="python")
    target: dict[str, Any] = payload
    for part in parts[:-1]:
        target = target[part]
    leaf = parts[-1]
    target[leaf] = _alternate(path, target[leaf])
    return type(root).model_validate(payload)


_FACTORY_EFFECT_PATHS = (
    "app.audio_processing.enhancements",
    *(
        f"app.audio_processing.enhancements.{field}"
        for field in (
            "enable_metadata",
            "enable_lyrics",
            "enable_acoustid",
            "enable_musicbrainz",
            "enable_lyrics_lookup",
            "enable_whisperx",
            "lyrics_require_timed",
            "lyrics_min_coverage",
            "lyrics_language",
            "whisperx_model",
            "whisperx_device",
            "whisperx_batch_size",
            "whisperx_return_char_alignments",
            "acoustid_api_key",
            "genius_access_token",
            "musicbrainz_rate_limit_rps",
            "musicbrainz_timeout_s",
            "http_max_retries",
            "http_timeout_s",
        )
    ),
)


def _with_factory_prerequisites(config: AppConfig, config_path: str) -> AppConfig:
    payload = config.model_dump(mode="python")
    enhancements = payload["audio_processing"]["enhancements"]
    if config_path.endswith("acoustid_api_key"):
        enhancements["enable_acoustid"] = True
    if config_path.endswith("genius_access_token"):
        enhancements["enable_lyrics_lookup"] = True
    if config_path.endswith(
        (
            "musicbrainz_rate_limit_rps",
            "musicbrainz_timeout_s",
            "http_max_retries",
            "http_timeout_s",
        )
    ):
        enhancements["enable_musicbrainz"] = True
    return AppConfig.model_validate(payload)


async def _factory_snapshot(config: AppConfig) -> tuple[Any, ...]:
    factory = EnhancementServiceFactory()
    metadata = factory.create_metadata_pipeline(config)
    lyrics = factory.create_lyrics_pipeline(config)
    metadata_client = metadata.musicbrainz_client if metadata is not None else None
    acoustid_client = metadata.acoustid_client if metadata is not None else None
    genius = lyrics.providers.get("genius") if lyrics is not None else None
    http_clients = tuple(
        (client.config.timeout.read, client.retry_policy.max_attempts)
        for client in factory._http_clients
    )
    snapshot = (
        metadata.config.model_dump(mode="json") if metadata is not None else None,
        acoustid_client.api_key if acoustid_client is not None else None,
        metadata_client.rate_limiter.rate_per_second if metadata_client is not None else None,
        metadata_client.timeout.read if metadata_client is not None else None,
        lyrics.config.model_dump(mode="json") if lyrics is not None else None,
        tuple(sorted(lyrics.providers)) if lyrics is not None else None,
        genius.access_token if genius is not None else None,
        lyrics.whisperx_service is not None if lyrics is not None else None,
        http_clients,
    )
    await factory.aclose()
    return snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize("config_path", _FACTORY_EFFECT_PATHS, ids=_FACTORY_EFFECT_PATHS)
async def test_each_enhancement_factory_field_changes_constructed_services(
    config_path: str,
) -> None:
    """Each named enhancement knob changes a production service constructor result."""
    baseline = _with_factory_prerequisites(AppConfig(), config_path)
    changed = _with_factory_prerequisites(_changed_config(config_path), config_path)

    with patch("twinklr.core.audio.lyrics.whisperx_service.WhisperXImpl", return_value=object()):
        assert await _factory_snapshot(changed) != await _factory_snapshot(baseline)


_PHONEME_EFFECT_PATHS = tuple(
    f"app.audio_processing.enhancements.{field}"
    for field in (
        "enable_phonemes",
        "phoneme_min_duration_ms",
        "phoneme_vowel_weight",
        "phoneme_consonant_weight",
        "viseme_min_hold_ms",
        "viseme_min_burst_ms",
        "viseme_boundary_soften_ms",
        "viseme_mapping_version",
    )
)


async def _phoneme_snapshot(config: AppConfig, monkeypatch: pytest.MonkeyPatch) -> Any:
    captured: dict[str, Any] = {}

    async def fake_to_thread(_function: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return type("Bundle", (), {"phonemes": (), "visemes": (), "confidence": 1.0})()

    monkeypatch.setattr("twinklr.core.audio.analyzer.asyncio.to_thread", fake_to_thread)
    lyrics = LyricsBundle(
        schema_version="3.0.0",
        stage_status=StageStatus.OK,
        words=[LyricWord(text="probe", start_ms=0, end_ms=500)],
    )
    result = await AudioAnalyzer(config, JobConfig())._extract_phonemes_if_enabled(lyrics, 500)
    return (result is not None, captured)


@pytest.mark.asyncio
@pytest.mark.parametrize("config_path", _PHONEME_EFFECT_PATHS, ids=_PHONEME_EFFECT_PATHS)
async def test_each_phoneme_field_changes_builder_call(
    config_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each phoneme/viseme knob changes the production bundle-builder seam."""
    baseline = await _phoneme_snapshot(AppConfig(), monkeypatch)
    changed = await _phoneme_snapshot(_changed_config(config_path), monkeypatch)

    assert changed != baseline


@pytest.mark.parametrize(
    ("config_path", "field", "configured"),
    (
        ("app.audio_processing", "hop_length", 256),
        ("app.audio_processing.hop_length", "hop_length", 256),
        ("app.audio_processing.frame_length", "frame_length", 1024),
    ),
    ids=(
        "app.audio_processing",
        "app.audio_processing.hop_length",
        "app.audio_processing.frame_length",
    ),
)
def test_audio_window_field_changes_energy_extraction_call(
    config_path: str, field: str, configured: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hop and frame sizes reach the production energy-extraction call."""
    config = AppConfig.model_validate({"audio_processing": {field: configured}})
    captured: dict[str, int] = {}

    class ProbeReachedError(RuntimeError):
        pass

    def record_energy_call(
        _audio: np.ndarray, _sample_rate: int, *, hop_length: int, frame_length: int
    ) -> dict[str, Any]:
        captured.update(hop_length=hop_length, frame_length=frame_length)
        raise ProbeReachedError

    audio = np.zeros(11_000, dtype=np.float32)
    rhythm = RhythmAnalysis(
        tempo_bpm=120.0,
        beats_s=[],
        downbeats_s=[],
        beats_per_bar=4,
        beat_confidence=1.0,
        downbeat_confidence=1.0,
        source="probe",
        source_version="1",
    )
    rhythm_source = SimpleNamespace(analyze_rhythm=lambda _inputs: rhythm)
    monkeypatch.setattr("twinklr.core.audio.analyzer.librosa.load", lambda *_a, **_k: (audio, 1000))
    monkeypatch.setattr(
        "twinklr.core.audio.analyzer.compute_hpss",
        lambda _audio: SimpleNamespace(
            harmonic=audio, percussive=audio, separated=True, error=None
        ),
    )
    monkeypatch.setattr(
        "twinklr.core.audio.analyzer.compute_onset_env", lambda *_a, **_k: np.zeros(8)
    )
    monkeypatch.setattr(
        "twinklr.core.audio.analyzer.extract_chroma", lambda *_a, **_k: np.zeros((12, 8))
    )
    monkeypatch.setattr(
        "twinklr.core.audio.analyzer.create_rhythm_source", lambda _name: rhythm_source
    )
    monkeypatch.setattr(
        "twinklr.core.audio.analyzer.create_structure_source", lambda _name: object()
    )
    monkeypatch.setattr("twinklr.core.audio.analyzer.extract_smoothed_energy", record_energy_call)

    with pytest.raises(ProbeReachedError):
        AudioAnalyzer(config, JobConfig())._process_audio("probe.wav")

    assert captured[field] == configured


_FIXTURE_INVARIANT_PATH = "fixture.fixtures[FixtureInstance].config.fixture_id"
FIXTURE_EFFECT_PATHS = tuple(
    path
    for path, disposition in CONFIG_EFFECTS.items()
    if path.startswith("fixture.")
    and disposition.kind is ConfigDispositionKind.EFFECT_TEST
    and path != _FIXTURE_INVARIANT_PATH
    and disposition.test_nodeid is not None
    and "test_fixture_field_changes_shipped_behavior_snapshot" in disposition.test_nodeid
)


def _fixture_group() -> FixtureGroup:
    shared = {
        "dmx_mapping": {
            "pan_channel": {"channel": 1},
            "tilt_channel": {"channel": 2},
            "dimmer_channel": {"channel": 3},
            "pan_fine_channel": {"channel": 4},
            "tilt_fine_channel": {"channel": 5},
            "use_16bit_pan_tilt": True,
            "shutter_channel": {"channel": 6},
            "shutter_default": 240,
            "shutter_map": {
                "closed": 1,
                "open": 241,
                "strobe_slow": 61,
                "strobe_medium": 121,
                "strobe_fast": 181,
            },
            "color_channel": {"channel": 7},
            "color_map": {"open": 2, "white": 3, "red": 19},
            "gobo_channel": {"channel": 8},
            "gobo_map": {"open": 4, "circles": 14},
        },
        "inversions": {
            "pan": True,
            "tilt": True,
            "dimmer": False,
            "shutter": False,
            "color": False,
            "gobo": False,
        },
        "pan_tilt_range": {"pan_range_deg": 500.0, "tilt_range_deg": 250.0},
        "orientation": {"pan_front_dmx": 120, "tilt_zero_dmx": 30},
        "limits": {"pan_min": 10, "pan_max": 245, "tilt_min": 11, "tilt_max": 244},
    }
    full = {**shared, "fixture_id": "A", "position": {"position_index": 2}}
    return FixtureGroup.model_validate(
        {
            "group_id": "probe-rig",
            "base_config": shared,
            "fixtures": [
                {"fixture_id": "A", "xlights_model_name": "Dmx A", "config": full},
                {
                    "fixture_id": "B",
                    "xlights_model_name": "Dmx B",
                    "position": {"position_index": 1},
                    "config_overrides": {},
                },
            ],
            "xlights_group": "GROUP - HEADS",
            "xlights_semantic_groups": {"LEFT": "GROUP - LEFT"},
        }
    )


def _fixture_parts(path: str) -> list[str | int]:
    parts: list[str | int] = []
    for raw in path.split(".")[1:]:
        if raw == "fixtures[FixtureInstance]":
            parts.extend(("fixtures", 0))
        elif raw == "fixtures[SimplifiedFixtureInstance]":
            parts.extend(("fixtures", 1))
        else:
            parts.append(raw)
    return parts


def _alternate_fixture(path: str, value: Any) -> Any:
    if path == "fixture.fixtures":
        return [
            *value,
            {
                "fixture_id": "C",
                "xlights_model_name": "Dmx C",
                "position": {"position_index": 3},
            },
        ]
    if path.endswith("config_overrides"):
        return {"inversions": {"pan": False}}
    if path == "fixture.fixtures[FixtureInstance].config":
        changed = dict(value)
        changed["dmx_mapping"] = dict(changed["dmx_mapping"])
        changed["dmx_mapping"]["pan_channel"] = {"channel": 9}
        return changed
    if path.endswith("position") and value is not None:
        return {"position_index": 1 if value["position_index"] != 1 else 2}
    if isinstance(value, list):
        changed = list(value)
        changed.append(value[0])
        return changed
    return _alternate(path, value)


def _changed_fixture(path: str) -> FixtureGroup:
    payload = _fixture_group().model_dump(mode="python")
    parts = _fixture_parts(path)
    target: Any = payload
    for part in parts[:-1]:
        target = target[part]
    leaf = parts[-1]
    target[leaf] = _alternate_fixture(path, target[leaf])
    return FixtureGroup.model_validate(payload)


def _fixture_snapshot(group: FixtureGroup) -> tuple[Any, ...]:
    segment = FixtureSegment(
        section_id="section",
        segment_id="segment",
        step_id="step",
        template_id="template",
        fixture_id="probe",
        t0_ms=0,
        t1_ms=1000,
        channels={
            channel: ChannelValue(channel=channel, static_dmx=100) for channel in ChannelName
        },
    )
    defaults_segment = segment.model_copy(update={"channels": {}})
    fixture_snapshots = []
    for fixture in group.expand_fixtures():
        mapping = fixture.config.dmx_mapping
        calibration = {"fixture_config": fixture.config}
        fixture_snapshots.append(
            (
                fixture.fixture_id,
                fixture.xlights_model_name,
                DmxSettingsBuilder(fixture).build_settings_string(segment),
                DmxSettingsBuilder(fixture).build_settings_string(defaults_segment),
                fixture.config.degrees_to_dmx(Pose(pan_deg=170, tilt_deg=90)),
                fixture.config.degrees_to_dmx(Pose(pan_deg=-170, tilt_deg=-90)),
                fixture.config.dmx_to_degrees(200, 180).model_dump(mode="json"),
                tuple(
                    DefaultColorHandler()
                    .generate({"preset": preset, "calibration": calibration}, 4)
                    .model_dump(mode="json")
                    for preset in ("white", "red")
                ),
                tuple(
                    DefaultShutterHandler()
                    .generate({"pattern": pattern, "calibration": calibration}, 4)
                    .model_dump(mode="json")
                    for pattern in (
                        "closed",
                        "open",
                        "strobe_slow",
                        "strobe_medium",
                        "strobe_fast",
                    )
                ),
                tuple(
                    DefaultGoboHandler()
                    .generate({"pattern": pattern, "calibration": calibration}, 4)
                    .model_dump(mode="json")
                    for pattern in ("open", "circles")
                ),
                mapping.use_16bit_pan_tilt,
            )
        )
    return (
        group.get_xlights_mapping(),
        rig_profile_from_fixture_group(group).model_dump(mode="json"),
        tuple(fixture_snapshots),
    )


@pytest.mark.parametrize("config_path", FIXTURE_EFFECT_PATHS, ids=FIXTURE_EFFECT_PATHS)
def test_fixture_field_changes_shipped_behavior_snapshot(config_path: str) -> None:
    """Every fixture path changes expansion, rig, conversion, handler, or export behavior."""
    assert _fixture_snapshot(_changed_fixture(config_path)) != _fixture_snapshot(_fixture_group())
