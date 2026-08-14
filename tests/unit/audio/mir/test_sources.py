from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from twinklr.core.audio.mir.sources import (
    AllInOneSource,
    BeatThisSource,
    MIRInput,
    MissingMIRDependencyError,
    create_rhythm_source,
    create_structure_source,
)
from twinklr.core.config.models import AudioProcessingConfig, RhythmSourceName, StructureSourceName
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _mir_input() -> MIRInput:
    return MIRInput(
        audio_path=Path("fixture.wav"),
        audio=np.zeros(22050, dtype=np.float32),
        sample_rate=22050,
        hop_length=512,
        onset_envelope=np.zeros(44, dtype=np.float32),
        chroma=np.zeros((12, 44), dtype=np.float32),
    )


def test_source_selection_from_config() -> None:
    default = AudioProcessingConfig()
    configured = AudioProcessingConfig(
        rhythm_source=RhythmSourceName.BEAT_THIS,
        structure_source=StructureSourceName.ALLINONE,
    )

    assert default.rhythm_source is RhythmSourceName.DSP
    assert default.structure_source is StructureSourceName.DSP
    assert create_rhythm_source(configured.rhythm_source).name == "beat_this"
    assert create_structure_source(configured.structure_source).name == "allinone"


class _OfficialAudio2BeatsShape:
    """Fake the upstream ``Audio2Beats`` callable's public return contract."""

    def __call__(self, signal: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
        del signal, sr
        beats = np.asarray([0.5, 1.0, 1.5, 2.0, 2.5])
        downbeats = np.asarray([0.5, 2.5])
        return beats, downbeats


def test_beat_this_adapter_decodes_official_beats_downbeats_order() -> None:
    source = BeatThisSource(predictor=_OfficialAudio2BeatsShape())

    result = source.analyze_rhythm(_mir_input())

    assert result.beats_s == [0.5, 1.0, 1.5, 2.0, 2.5]
    assert result.downbeats_s == [0.5, 2.5]
    assert result.beats_per_bar == 4
    assert result.source == "beat_this"


@dataclass
class _Segment:
    start: float
    end: float
    label: str


@dataclass
class _AllInOneResult:
    segments: list[_Segment]


def test_allinone_adapter_maps_labeled_segments() -> None:
    source = AllInOneSource(
        analyzer=lambda path: _AllInOneResult(
            segments=[_Segment(0.0, 4.0, "intro"), _Segment(4.0, 8.0, "verse")]
        )
    )

    result = source.analyze_structure(_mir_input())

    assert result.boundary_times_s == [0.0, 4.0, 8.0]
    assert result.sections[1]["label"] == "verse"
    assert result.source == "allinone"


def test_missing_model_dependency_has_actionable_extra_name() -> None:
    source = BeatThisSource(importer=lambda name: (_ for _ in ()).throw(ImportError(name)))

    with pytest.raises(MissingMIRDependencyError, match=r"uv sync --extra mir-beats"):
        source.analyze_rhythm(_mir_input())


def test_beat_grid_public_shape_is_unchanged() -> None:
    assert set(BeatGrid.model_fields) == {
        "bar_boundaries",
        "beat_boundaries",
        "eighth_boundaries",
        "sixteenth_boundaries",
        "tempo_bpm",
        "beats_per_bar",
        "duration_ms",
    }
