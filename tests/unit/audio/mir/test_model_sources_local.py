from __future__ import annotations

from pathlib import Path

import pytest

from twinklr.core.audio.mir.benchmark import _prepare_input
from twinklr.core.audio.mir.fixtures import load_fixture_manifest
from twinklr.core.audio.mir.sources import (
    AllInOneSource,
    BeatThisSource,
    DSPSource,
    MissingMIRDependencyError,
)

MANIFEST = Path(__file__).parents[3] / "fixtures" / "mir" / "manifest.json"


@pytest.mark.local_only
def test_model_sources_run(tmp_path: Path) -> None:
    """Operator-controlled smoke for local weights; never downloads them itself."""
    manifest = load_fixture_manifest(MANIFEST)
    fixture = manifest.fixtures[0]
    inputs = _prepare_input(
        fixture,
        sample_rate=manifest.sample_rate,
        audio_path=tmp_path / "fixture.wav",
        hop_length=512,
    )
    dsp_rhythm = DSPSource().analyze_rhythm(inputs)

    try:
        beat_this = BeatThisSource().analyze_rhythm(inputs)
        allinone = AllInOneSource().analyze_structure(inputs, dsp_rhythm)
    except MissingMIRDependencyError as error:
        pytest.skip(str(error))

    assert beat_this.beats_s
    assert beat_this.downbeats_s
    assert allinone.boundary_times_s
