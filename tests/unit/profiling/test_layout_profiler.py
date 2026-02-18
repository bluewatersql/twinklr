"""Unit tests for LayoutProfiler."""

from __future__ import annotations

import json
from pathlib import Path

from twinklr.core.profiling.layout.profiler import LayoutProfiler

FIXTURE_XML = Path("data/test/example2/extracted/xlights_rgbeffects.xml")
BASELINE_JSON = Path("data/test/example2/rgbeffects_profile.json")


def test_layout_profiler_profiles_real_fixture() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    assert profile.metadata.source_file == "xlights_rgbeffects.xml"
    assert len(profile.models) > 0


def test_layout_profiler_model_count_matches_baseline() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    expected = len(baseline.get("models", []))
    assert len(profile.models) == expected


def test_layout_profiler_has_dmx_fixture() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    assert any(model.dmx_profile is not None for model in profile.models)


def test_layout_profiler_has_spatial_stats() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    assert profile.spatial is not None


def test_layout_profiler_chain_sequences_type() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    assert isinstance(profile.statistics.chain_sequences, tuple)
