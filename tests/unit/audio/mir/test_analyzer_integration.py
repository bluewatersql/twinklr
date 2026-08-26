from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.audio.mir.sources import (
    DSPSource,
    MissingMIRDependencyError,
    RhythmAnalysis,
    StructureAnalysis,
)
from twinklr.core.config.models import (
    AppConfig,
    AudioProcessingConfig,
    RhythmSourceName,
    StructureSourceName,
)


class _RhythmSource:
    name = "beat_this"

    def analyze_rhythm(self, inputs: object) -> RhythmAnalysis:
        beats = [0.5 * index for index in range(1, 25)]
        return RhythmAnalysis(
            tempo_bpm=120.0,
            beats_s=beats,
            downbeats_s=beats[::4],
            beats_per_bar=4,
            beat_confidence=1.0,
            downbeat_confidence=1.0,
            source=self.name,
            source_version="test",
        )


class _StructureSource:
    name = "allinone"

    def analyze_structure(self, inputs: object, rhythm: RhythmAnalysis) -> StructureAnalysis:
        return StructureAnalysis(
            sections=[
                {"start_s": 0.0, "end_s": 6.0, "label": "verse"},
                {"start_s": 6.0, "end_s": 12.0, "label": "chorus"},
            ],
            boundary_times_s=[0.0, 6.0, 12.0],
            source=self.name,
            source_version="test",
        )


def _write_short_audio(tmp_path: Path) -> Path:
    sample_rate = 22050
    audio_path = tmp_path / "short.wav"
    sf.write(audio_path, np.zeros(sample_rate, dtype=np.float32), sample_rate)
    return audio_path


def _analyzer_with_sources(
    rhythm_source: RhythmSourceName, structure_source: StructureSourceName
) -> AudioAnalyzer:
    analyzer = object.__new__(AudioAnalyzer)
    analyzer.app_config = AppConfig(
        audio_processing=AudioProcessingConfig(
            rhythm_source=rhythm_source,
            structure_source=structure_source,
        )
    )
    return analyzer


def test_short_audio_dsp_path_reports_truthful_source_provenance(tmp_path: Path) -> None:
    analyzer = _analyzer_with_sources(RhythmSourceName.DSP, StructureSourceName.DSP)

    result = analyzer._process_audio(str(_write_short_audio(tmp_path)))

    assert result["analysis_sources"] == {
        "rhythm": {"name": DSPSource.name, "version": DSPSource.version},
        "structure": {"name": DSPSource.name, "version": DSPSource.version},
    }


@pytest.mark.parametrize(
    ("config_path", "rhythm", "structure", "expected"),
    (
        (
            "app.audio_processing.rhythm_source",
            RhythmSourceName.BEAT_THIS,
            StructureSourceName.DSP,
            ("rhythm", RhythmSourceName.BEAT_THIS),
        ),
        (
            "app.audio_processing.structure_source",
            RhythmSourceName.DSP,
            StructureSourceName.ALLINONE,
            ("structure", StructureSourceName.ALLINONE),
        ),
    ),
    ids=(
        "app.audio_processing.rhythm_source",
        "app.audio_processing.structure_source",
    ),
)
def test_audio_source_field_changes_production_factory_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config_path: str,
    rhythm: RhythmSourceName,
    structure: StructureSourceName,
    expected: tuple[str, object],
) -> None:
    """Each source selector reaches its matching production source factory."""
    captured: dict[str, object] = {}

    def rhythm_factory(name: object) -> DSPSource:
        captured["rhythm"] = name
        return DSPSource()

    def structure_factory(name: object) -> DSPSource:
        captured["structure"] = name
        return DSPSource()

    monkeypatch.setattr("twinklr.core.audio.analyzer.create_rhythm_source", rhythm_factory)
    monkeypatch.setattr("twinklr.core.audio.analyzer.create_structure_source", structure_factory)
    analyzer = _analyzer_with_sources(rhythm, structure)

    analyzer._process_audio(str(_write_short_audio(tmp_path)))

    assert captured[expected[0]] == expected[1], config_path


def test_short_audio_selected_beat_this_fails_loudly_when_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analyzer = _analyzer_with_sources(RhythmSourceName.BEAT_THIS, StructureSourceName.DSP)

    class _UnavailableRhythm:
        name = "beat_this"
        version = "1.1.0"

        def analyze_rhythm(self, inputs: object) -> RhythmAnalysis:
            raise MissingMIRDependencyError("beat-this checkpoint unavailable")

    monkeypatch.setattr(
        "twinklr.core.audio.analyzer.create_rhythm_source", lambda name: _UnavailableRhythm()
    )

    with pytest.raises(MissingMIRDependencyError, match="checkpoint unavailable"):
        analyzer._process_audio(str(_write_short_audio(tmp_path)))


def test_short_audio_selected_allinone_fails_loudly_when_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analyzer = _analyzer_with_sources(RhythmSourceName.DSP, StructureSourceName.ALLINONE)

    class _UnavailableStructure:
        name = "allinone"
        version = "1.0.6"

        def analyze_structure(self, inputs: object, rhythm: RhythmAnalysis) -> StructureAnalysis:
            raise MissingMIRDependencyError("all-in-one dependency unavailable")

    monkeypatch.setattr(
        "twinklr.core.audio.analyzer.create_structure_source",
        lambda name: _UnavailableStructure(),
    )

    with pytest.raises(MissingMIRDependencyError, match="dependency unavailable"):
        analyzer._process_audio(str(_write_short_audio(tmp_path)))


def test_selected_sources_feed_one_feature_truth_and_preserve_custom_analysis(
    tmp_path: Path, monkeypatch
) -> None:
    sample_rate = 22050
    time = np.arange(sample_rate * 12, dtype=np.float32) / sample_rate
    audio = (0.2 * np.sin(2.0 * np.pi * 220.0 * time)).astype(np.float32)
    audio_path = tmp_path / "fixture.wav"
    sf.write(audio_path, audio, sample_rate)

    analyzer = object.__new__(AudioAnalyzer)
    analyzer.app_config = AppConfig(
        audio_processing=AudioProcessingConfig(
            rhythm_source=RhythmSourceName.BEAT_THIS,
            structure_source=StructureSourceName.ALLINONE,
        )
    )
    monkeypatch.setattr(
        "twinklr.core.audio.analyzer.create_rhythm_source", lambda name: _RhythmSource()
    )
    monkeypatch.setattr(
        "twinklr.core.audio.analyzer.create_structure_source", lambda name: _StructureSource()
    )

    result = analyzer._process_audio(str(audio_path))

    assert result["beats_s"] == [0.5 * index for index in range(1, 25)]
    assert result["bars_s"] == [0.5, 2.5, 4.5, 6.5, 8.5, 10.5]
    assert result["structure"]["boundary_times_s"] == [0.0, 6.0, 12.0]
    assert result["analysis_sources"] == {
        "rhythm": {"name": "beat_this", "version": "test"},
        "structure": {"name": "allinone", "version": "test"},
    }
    assert result["energy"]["rms_norm"]
    assert result["energy"]["builds"] is not None
    assert result["tension"]
    assert result["timeline"]
