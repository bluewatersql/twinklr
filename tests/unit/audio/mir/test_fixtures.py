from __future__ import annotations

from pathlib import Path

import numpy as np

from twinklr.core.audio.mir.fixtures import load_fixture_manifest, synthesize_fixture

MANIFEST = Path(__file__).parents[3] / "fixtures" / "mir" / "manifest.json"


def test_fixture_manifest_has_precommitted_diverse_ground_truth() -> None:
    manifest = load_fixture_manifest(MANIFEST)

    assert len(manifest.fixtures) >= 5
    assert {fixture.category for fixture in manifest.fixtures} >= {
        "steady_4_4",
        "non_4_4",
        "tempo_varying",
        "sparse_ambient",
    }
    for fixture in manifest.fixtures:
        assert fixture.beat_times_s
        assert fixture.downbeat_times_s
        assert len(fixture.sections) >= 3
        assert fixture.section_boundaries_s == [section.start_s for section in fixture.sections[1:]]


def test_synthetic_fixture_generation_is_bit_deterministic() -> None:
    fixture = load_fixture_manifest(MANIFEST).fixtures[0]

    first = synthesize_fixture(fixture, sample_rate=22050)
    second = synthesize_fixture(fixture, sample_rate=22050)

    assert first.dtype == np.float32
    assert np.array_equal(first, second)
