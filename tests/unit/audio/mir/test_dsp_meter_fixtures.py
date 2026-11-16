"""DSP meter and tempo on the committed MIR fixtures (synthesized from annotations)."""

from __future__ import annotations

from pathlib import Path

import pytest

from twinklr.core.audio.mir.benchmark import _prepare_input as prepare_input
from twinklr.core.audio.mir.fixtures import MIRFixture, load_fixture_manifest
from twinklr.core.audio.mir.metrics import event_f1
from twinklr.core.audio.mir.sources import DSPSource

MANIFEST = Path(__file__).parents[3] / "fixtures" / "mir" / "manifest.json"

# Tracker tempo on each fixture before the meter/octave change (2026-11-16). The
# tempo-change fixture runs 100 -> 140 BPM; the tracker reports its first section.
PINNED_TEMPO_BPM = {
    "steady_4_4_pop": 117.5,
    "waltz_3_4": 99.4,
    "tempo_change_4_4": 99.4,
    "sparse_ambient": 60.1,
    "syncopated_4_4": 129.2,
}

# Downbeat F1 (+/-70 ms) after the meter/octave change; the downbeat rule must not lower it.
MIN_DOWNBEAT_F1 = {
    "steady_4_4_pop": 1.0,
    "waltz_3_4": 1.0,
    "tempo_change_4_4": 0.666,
    "sparse_ambient": 1.0,
    "syncopated_4_4": 1.0,
}

_MANIFEST = load_fixture_manifest(MANIFEST)


@pytest.mark.parametrize("fixture", _MANIFEST.fixtures, ids=lambda fixture: fixture.id)
def test_dsp_meter_matches_annotation_and_tempo_is_unchanged(
    fixture: MIRFixture, tmp_path: Path
) -> None:
    inputs = prepare_input(
        fixture,
        sample_rate=_MANIFEST.sample_rate,
        audio_path=tmp_path / "fixture.wav",
        hop_length=512,
    )

    rhythm = DSPSource().analyze_rhythm(inputs)

    assert rhythm.beats_per_bar == fixture.beats_per_bar
    assert rhythm.tempo_bpm == pytest.approx(PINNED_TEMPO_BPM[fixture.id], rel=0.02)
    octave = rhythm.metadata["time_signature"]["tempo_octave"]
    assert octave["chosen_bpm"] == pytest.approx(rhythm.tempo_bpm)
    downbeat_f1 = event_f1(fixture.downbeat_times_s, rhythm.downbeats_s, tolerance_s=0.070).f1
    assert downbeat_f1 >= MIN_DOWNBEAT_F1[fixture.id]
