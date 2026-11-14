"""Unit tests for LayoutProfiler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.profiling.layout.profiler import LayoutProfiler

FIXTURE_XML = Path("data/test/example2/extracted/xlights_rgbeffects.xml")
BASELINE_JSON = Path("data/test/example2/rgbeffects_profile.json")
requires_fixture = pytest.mark.skipif(
    not FIXTURE_XML.exists() or not BASELINE_JSON.exists(),
    reason="layout fixture files are not present in this environment",
)


@requires_fixture
def test_layout_profiler_profiles_real_fixture() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    assert profile.metadata.source_file == "xlights_rgbeffects.xml"
    assert len(profile.models) > 0


@requires_fixture
def test_layout_profiler_model_count_matches_baseline() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    expected = len(baseline.get("models", []))
    assert len(profile.models) == expected


@requires_fixture
def test_layout_profiler_has_dmx_fixture() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    assert any(model.dmx_profile is not None for model in profile.models)


@requires_fixture
def test_layout_profiler_has_spatial_stats() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    assert profile.spatial is not None


@requires_fixture
def test_layout_profiler_chain_sequences_type() -> None:
    profile = LayoutProfiler().profile(FIXTURE_XML)
    assert isinstance(profile.statistics.chain_sequences, tuple)


def _dmx_layout(tmp_path: Path, **attributes: str) -> Path:
    """A synthetic layout with one DMX moving head carrying `attributes`."""
    rendered = " ".join(f'{key}="{value}"' for key, value in attributes.items())
    path = tmp_path / "xlights_rgbeffects.xml"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<xrgb>\n  <models>\n'
        f'    <model name="Dmx MH1" DisplayAs="DmxMovingHeadAdv" '
        f'StringType="Single Color White" {rendered} />\n'
        "  </models>\n</xrgb>\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        pytest.param(
            {"DmxChannelCount": "16", "versionNumber": "8", "SourceVersion": "2026.19"},
            16,
            id="as-xlights-2026-19-writes-it",
        ),
        pytest.param({"parm1": "12"}, 12, id="parm1-fallback"),
        pytest.param({"DmxChannelCount": "16", "parm1": "4"}, 16, id="dmx-channel-count-wins"),
        pytest.param({}, 0, id="neither"),
    ],
)
def test_dmx_profile_reads_the_channel_count_xlights_writes(
    tmp_path: Path, attributes: dict[str, str], expected: int
) -> None:
    (model,) = LayoutProfiler().profile(_dmx_layout(tmp_path, **attributes)).models
    assert model.dmx_profile is not None
    assert model.dmx_profile.channel_count == expected
